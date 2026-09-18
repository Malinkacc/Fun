# -*- coding: utf-8 -*-
vm = open('/home/user/deobfuscated/vm.lua', encoding='utf-8').read()
b32 = open('bit32_pure.lua', encoding='utf-8').read()
deserializer = vm[vm.index('local function readU32'):vm.index('local function runProto')]
names_block  = vm[vm.index('OPNAMES = OPNAMES or {'):vm.index('return {\n  decryptBlob')].rstrip() + "\n"
bit32block = ("local bit32 = (function()\n" + b32.rstrip().rsplit("return bit32", 1)[0] + "  return bit32\nend)()\n")

head = '''--=============================================================================
--  unpack_stage2.lua - вскрытие "второго слоя" защищённого скрипта
--=============================================================================
--  1) читает исходный обфусцированный .lua (тот, где `local protectedFn=r1("...")`);
--  2) аккуратно извлекает строковый литерал с зашифрованным блоком (учитывает эскейпы
--     \\ddd, \\xNN, \\n и длинные строки [[...]] / [==[...]==]);
--  3) снимает "шифр": перестановка внутри каждых 256 байт по таблице SHUFFLE
--     + XOR с байтом (i-1+225) %% 256 ->  получаются байты байткода;
--  4) разбирает контейнер (deserialize) и сохраняет:
--        stage2.bin - сырой байткод,
--        stage2.dis - читаемый листинг (дизассемблер),
--     а на экран печатает все строковые константы (URL, имена, ключи) и сводку.
--
--  Запуск:  lua unpack_stage2.lua protected.lua [папка_вывода]
--
--  Инструмент НЕ исполняет байткод - только разбирает его.
--=============================================================================

__BIT32__

-- Таблица перестановки, "зашитая" в оригинале (256 значений, это полная перестановка 0..255).
local SHUFFLE = {17,73,104,209,217,201,28,157,223,232,48,123,187,163,240,179,200,126,172,31,9,33,100,7,93,159,122,203,205,183,43,145,202,254,13,152,142,210,1,156,244,255,139,204,119,136,26,39,51,218,91,14,161,32,135,249,70,146,81,94,12,10,228,224,22,192,97,185,147,227,238,162,246,176,199,212,115,68,241,186,129,178,116,34,216,114,69,242,41,130,155,54,2,61,35,27,11,40,64,113,141,117,15,167,220,252,0,177,236,208,182,30,56,132,131,37,127,243,88,111,5,50,49,150,85,16,174,245,112,62,52,124,38,175,247,197,44,190,171,20,57,118,121,184,230,109,65,58,108,180,134,76,125,225,137,24,80,98,8,53,83,74,19,95,193,89,149,165,110,251,6,102,84,4,169,18,158,103,23,107,79,173,143,222,140,151,101,120,47,25,215,250,234,170,154,42,168,166,77,96,90,78,67,55,226,195,231,133,221,211,181,237,59,63,191,66,233,46,138,29,214,45,235,160,71,60,21,86,253,3,213,207,36,239,106,128,99,198,194,75,87,153,229,219,206,144,72,82,248,105,196,189,188,164,148,92}

------------------------------------------------------------------ 1. Извлечение литерала
local function findBlobLiteral(src)
  local s = src:find("r1%s*%(")
  if not s then return nil, "не найдена конструкция r1(...) с зашифрованным блоком" end
  local i = src:find("(", s, true) + 1
  while src:sub(i, i):match("%s") do i = i + 1 end
  local c = src:sub(i, i)
  if c == '"' or c == "'" then
    local out, j = {}, i + 1
    while j <= #src do
      local ch = src:sub(j, j)
      if ch == "\\\\" then
        local nxt = src:sub(j + 1, j + 1)
        if nxt:match("%d") then
          local digits = src:match("^\\\\(%d%d?%d?)", j)
          local num = tonumber(digits)
          if num and num <= 255 then
            out[#out + 1] = string.char(num)
            j = j + 1 + #digits
          else
            out[#out + 1] = nxt; j = j + 2
          end
        elseif nxt == "n" then out[#out + 1] = "\\n"; j = j + 2
        elseif nxt == "t" then out[#out + 1] = "\\t"; j = j + 2
        elseif nxt == "r" then out[#out + 1] = "\\r"; j = j + 2
        elseif nxt == "a" then out[#out + 1] = "\\a"; j = j + 2
        elseif nxt == "x" then
          local hex = src:match("^\\\\x(%x%x?)", j)
          out[#out + 1] = string.char(tonumber(hex, 16) or 0); j = j + 2 + #hex
        else
          out[#out + 1] = nxt; j = j + 2
        end
      elseif ch == c then
        return table.concat(out)
      else
        out[#out + 1] = ch; j = j + 1
      end
    end
    return nil, "незакрытый строковый литерал"
  elseif c == "[" then
    local eq = src:match("^%[(=*)%[", i)
    if eq then
      local e = src:find("]" .. eq .. "]", i + #eq + 2, true)
      if not e then return nil, "незакрытая длинная строка" end
      return src:sub(i + #eq + 2, e - 1)
    end
  end
  return nil, "неизвестный тип литерала: " .. tostring(c)
end

------------------------------------------------------------------ 2. Снятие "шифра"
local function decodeBlob(blob)
  local n    = blob:byte(1) * 16777216 + blob:byte(2) * 65536 + blob:byte(3) * 256 + blob:byte(4)
  local body = blob:sub(5)
  if not (n > 0) then return nil, "пустой блок" end
  local need = math.ceil(n / 256) * 256
  if #body < need then
    return nil, string.format("блок обрезан: заявлено %d байт (с выравниванием нужно %d), есть %d",
                              n, need, #body)
  end
  local shuffled, plain = {}, {}
  for i = 1, n do
    local block = math.floor((i - 1) / 256)
    local slot  = (i - 1) % 256
    shuffled[i] = body:byte(block * 256 + SHUFFLE[slot + 1] + 1)
  end
  for i = 1, n do
    plain[i] = string.char(bit32.bxor(shuffled[i], (i - 1 + 225) % 256))
  end
  return table.concat(plain)
end

------------------------------------------------------------------ 3. Контейнер байткода
local strByte = string.byte
local strSub  = string.sub
local unpack  = table.unpack or unpack

__DESERIALIZER__
------------------------------------------------------------------ 4. Таблица опкодов и дизассемблер
__NAMES__
local function collectStrings(p, acc, path)
  acc  = acc or {}
  path = path or "proto#1"
  for i = 1, #p.consts_ do
    local c = p.consts_[i]
    if type(c) == "string" then acc[#acc + 1] = { path .. ".K" .. i, c } end
  end
  for i = 1, #p.protos do collectStrings(p.protos[i], acc, path .. "/sub" .. i) end
  return acc
end

local M = { extract = findBlobLiteral, decode = decodeBlob, deserialize = deserialize,
            disassemble = disassemble, collectStrings = collectStrings, SHUFFLE = SHUFFLE }

--===== CLI ====================================================================
if type(io) == "table" and io.open and arg and arg[1] then
  local srcPath, outDir = arg[1], arg[2] or "."
  local fh = assert(io.open(srcPath, "rb"), "не открыть " .. srcPath)
  local src = fh:read("*a"); fh:close()

  local blob, err = findBlobLiteral(src)
  if not blob then print("ОШИБКА: " .. tostring(err)); os.exit(1) end
  print(string.format("[1/4] литерал извлечён: %d байт (заявленная длина блока: %d)",
        #blob, blob:byte(1) * 16777216 + blob:byte(2) * 65536 + blob:byte(3) * 256 + blob:byte(4)))

  local chunk, derr = decodeBlob(blob)
  if not chunk then print("ОШИБКА: " .. tostring(derr)); os.exit(1) end
  print(string.format("[2/4] блок расшифрован: %d байт байткода", #chunk))

  local fo = assert(io.open(outDir .. "/stage2.bin", "wb")); fo:write(chunk); fo:close()
  print("[3/4] записан " .. outDir .. "/stage2.bin")

  local p = deserialize(chunk)
  local fl = assert(io.open(outDir .. "/stage2.dis", "w"))
  fl:write(table.concat(disassemble(p), "\\n") .. "\\n"); fl:close()
  print(string.format("[4/4] записан %s/stage2.dis (%d инструкций в главном прототипе, вложенных прототипов: %d)",
        outDir, #p.instrs, #p.protos))

  print("\\n--- Строковые константы (самое интересное: URL, имена, ключи) ---")
  for _, s in ipairs(collectStrings(p)) do
    print(string.format("  %-16s %q", s[1], s[2]))
  end
end

return M
'''
out = (head.replace('__BIT32__', bit32block)
           .replace('__DESERIALIZER__', deserializer)
           .replace('__NAMES__', names_block))
open('/home/user/deobfuscated/unpack_stage2.lua','w',encoding='utf-8').write(out)
print("unpack_stage2.lua:", len(out), "байт")
