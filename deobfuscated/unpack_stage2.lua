--=============================================================================
--  unpack_stage2.lua - вскрытие "второго слоя" защищённого скрипта
--=============================================================================
--  1) читает исходный обфусцированный .lua (тот, где `local protectedFn=r1("...")`);
--  2) аккуратно извлекает строковый литерал с зашифрованным блоком (учитывает эскейпы
--     \ddd, \xNN, \n и длинные строки [[...]] / [==[...]==]);
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

local bit32 = (function()
-- Чистая реализация используемых функций bit32 (для сред, где нет bit32: Lua 5.1, Lua 5.4, LuaJIT).
-- Все константные маски записаны как вещественные числа (x.0), чтобы избежать проблем
-- с 32-битной целочисленной арифметикой в некоторых сборках Lua.
local bit32 = _G.bit32   -- если библиотека уже есть (Luau/Lua 5.2-5.3) - используем её
if not bit32 then
  local TWO32 = 4294967296.0
  local MASK16 = 65536.0
  local NIB = {}
  for i = 0, 15 do
    NIB[i] = {}
    for j = 0, 15 do
      local a, b, rA, rO, rX, bit = i + 0.0, j + 0.0, 0.0, 0.0, 0.0, 1.0
      for _ = 1, 4 do
        local x, y = a % 2, b % 2
        if x == 1 and y == 1 then rA = rA + bit end
        if x == 1 or  y == 1 then rO = rO + bit end
        if x ~= y             then rX = rX + bit end
        a, b, bit = (a - x) / 2, (b - y) / 2, bit * 2
      end
      NIB[i][j] = {rA, rO, rX}
    end
  end
  local function bin(a, b, which)
    a, b = a % TWO32, b % TWO32
    local r, mul = 0.0, 1.0
    for _ = 1, 8 do
      local an, bn = a % 16, b % 16
      r = r + NIB[an][bn][which] * mul
      a, b, mul = (a - an) / 16, (b - bn) / 16, mul * 16
    end
    return r
  end
  local function fold(f, a, ...)
    for i = 1, select("#", ...) do a = f(a, select(i, ...)) end
    return a
  end
  local function lshift(a, n)
    if n < 0 or n >= 32 then return 0.0 end
    a = a % TWO32
    local hi, lo = math.floor(a / MASK16), a % MASK16
    return (((hi * 2 ^ n) % MASK16) * MASK16 + lo * 2 ^ n) % TWO32
  end
  local function rshift(a, n)
    if n < 0 or n >= 32 then return 0.0 end
    return math.floor((a % TWO32) / 2 ^ n)
  end
  local function lrotate(a, n)
    n = n % 32
    if n == 0 then return a % TWO32 end
    return (lshift(a, n) + rshift(a, 32 - n)) % TWO32
  end
  bit32 = {
    band = function(a, ...) return fold(function(x, y) return bin(x, y, 1) end, a, ...) end,
    bor  = function(a, ...) return fold(function(x, y) return bin(x, y, 2) end, a, ...) end,
    bxor = function(a, ...) return fold(function(x, y) return bin(x, y, 3) end, a, ...) end,
    bnot = function(a) return 4294967295.0 - (a % TWO32) end,
    lshift = lshift,
    rshift = rshift,
    lrotate = lrotate,
    rrotate = function(a, n) return lrotate(a, (32 - (n % 32)) % 32) end,
  }
end
  return bit32
end)()


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
      if ch == "\\" then
        local nxt = src:sub(j + 1, j + 1)
        if nxt:match("%d") then
          local digits = src:match("^\\(%d%d?%d?)", j)
          local num = tonumber(digits)
          if num and num <= 255 then
            out[#out + 1] = string.char(num)
            j = j + 1 + #digits
          else
            out[#out + 1] = nxt; j = j + 2
          end
        elseif nxt == "n" then out[#out + 1] = "\n"; j = j + 2
        elseif nxt == "t" then out[#out + 1] = "\t"; j = j + 2
        elseif nxt == "r" then out[#out + 1] = "\r"; j = j + 2
        elseif nxt == "a" then out[#out + 1] = "\a"; j = j + 2
        elseif nxt == "x" then
          local hex = src:match("^\\x(%x%x?)", j)
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

local function readU32(data,pos) local b1=strByte(data,pos) local b2=strByte(data,pos+1) local b3=strByte(data,pos+2) local b4=strByte(data,pos+3) return b1+b2*256+b3*65536+b4*16777216,pos+4 end
local function readI32(data,pos) local raw,pos=readU32(data,pos) if raw>=2147483648 then raw=raw-4294967296 end return raw,pos end
local function readF64(data,pos) local b1=strByte(data,pos) local b2=strByte(data,pos+1) local b3=strByte(data,pos+2) local b4=strByte(data,pos+3) local b5=strByte(data,pos+4) local b6=strByte(data,pos+5) local b7=strByte(data,pos+6) local b8=strByte(data,pos+7) local sign=1 if b8>=128 then sign=-1;b8=b8-128 end local expBits=b8*16+math.floor(b7/16) local mant=(b7 % 16)*281474976710656+b6*1099511627776+b5*4294967296+b4*16777216+b3*65536+b2*256+b1 local val if expBits==0 then if mant==0 then val=0 else val=sign*mant*2^(-1074) end elseif expBits==2047 then if mant==0 then val=sign*math.huge else val=0/0 end else val=sign*(1+mant/4503599627370496)*2^(expBits-1023) end return val,pos+8 end
local function deserialize(data,pos)pos=pos or 1 local p={}p.numParams,pos=readU32(data,pos)p.isVararg=strByte(data,pos)~=0 pos=pos+1 p.maxStack,pos=readU32(data,pos)b1,pos=readU32(data,pos)p.upvalDescs={}for idx=1,b1 do local flag=strByte(data,pos)~=0 pos=pos+1 local val_ val_,pos=readU32(data,pos)p.upvalDescs[idx]={fromReg=flag,index=val_}end F4,pos=readU32(data,pos)p.consts_={}for idx=1,F4 do local tag=strByte(data,pos)pos=pos+1 if tag==0 then p.consts_[idx]=nil elseif tag==1 then p.consts_[idx]=(strByte(data,pos)~=0)pos=pos+1 elseif tag==2 then local num num,pos=readF64(data,pos)p.consts_[idx]=num elseif tag==3 then local len_ len_,pos=readU32(data,pos)p.consts_[idx]=strSub(data,pos,pos+len_-1)pos=pos+len_ elseif tag==4 then local num num,pos=readU32(data,pos)p.consts_[idx]={z1=num}end end nInstr,pos=readU32(data,pos)p.instrs={}for idx=1,nInstr do local instr={}instr.op_=strByte(data,pos)instr.A_=strByte(data,pos+1)instr.B_=strByte(data,pos+2)instr.C_=strByte(data,pos+3)instr.D_=readI32(data,pos+4)p.instrs[idx]=instr pos=pos+8 end nProtos,pos=readU32(data,pos)p.protos={}for idx=1,nProtos do p.protos[idx],pos=deserialize(data,pos) end return p,pos end

------------------------------------------------------------------ 4. Таблица опкодов и дизассемблер
OPNAMES = OPNAMES or {
  [4] = "SETTABLE",
  [8] = "MULK",
  [9] = "DEADLOCK",
  [10] = "LSHIFT",
  [14] = "GETUPVAL",
  [15] = "APPEND",
  [16] = "LOADNIL",
  [17] = "BOR",
  [24] = "CONCAT_TABLE",
  [26] = "SETTABLEKS",
  [27] = "JUMPIFEQK",
  [29] = "GETTABLE",
  [31] = "LOADK",
  [33] = "MUL",
  [39] = "CONCAT_STR",
  [41] = "JUMPBACK",
  [43] = "NOOP_FALSE",
  [44] = "NOOP",
  [45] = "ERROR",
  [46] = "MATH_M2",
  [48] = "FLOOR",
  [49] = "PACK_REGS",
  [50] = "CALL2",
  [51] = "UNM",
  [52] = "MATH_H2",
  [59] = "DIVK",
  [60] = "JUMPIFNOT",
  [61] = "JUMPIF",
  [66] = "GE",
  [68] = "SPLIT",
  [72] = "INDEX_OF",
  [73] = "LROTATE",
  [80] = "GETMETATABLE",
  [81] = "NOOP",
  [83] = "EQ",
  [84] = "RROTATE",
  [85] = "STR_C2",
  [86] = "NOOP",
  [87] = "SUB_AND_JUMP",
  [88] = "PACK_INTO",
  [91] = "MOVE",
  [93] = "JUMPNIL_SKIP",
  [96] = "NOOP",
  [99] = "LT",
  [100] = "ADD",
  [104] = "SUBK",
  [106] = "LTK",
  [107] = "POW",
  [109] = "TONUMBER",
  [112] = "MATH_Y2",
  [113] = "MOD",
  [116] = "NOT",
  [117] = "SIGN",
  [119] = "STR_BYTE",
  [121] = "LOADNIL",
  [125] = "IDIV",
  [128] = "NE",
  [132] = "APPEND_TO",
  [133] = "GETGLOBAL",
  [134] = "TOSTRING",
  [136] = "MOVE",
  [138] = "RETURN",
  [141] = "SETTABLE",
  [144] = "LEN",
  [145] = "BAND",
  [146] = "NOOP",
  [148] = "GETTABLE",
  [150] = "SUB_STRING",
  [151] = "LEK",
  [153] = "LOADBOOL_B",
  [155] = "DIV",
  [156] = "SWAP",
  [157] = "SETGLOBAL",
  [160] = "MODK",
  [161] = "SETUPVAL",
  [162] = "BXOR",
  [163] = "STR_W1",
  [164] = "NOOP",
  [165] = "SETTABLEKS",
  [166] = "RSHIFT",
  [170] = "NOOP",
  [172] = "ASSERT",
  [174] = "TAILCALL",
  [176] = "STR_S1",
  [178] = "NOOP",
  [179] = "EQK",
  [182] = "NOOP_TRUE",
  [183] = "GETTABLEKS",
  [185] = "SUB",
  [188] = "CALL",
  [189] = "STR_V1",
  [191] = "GT",
  [194] = "GETTABLE_N",
  [196] = "LEN",
  [200] = "UNPACK_REGS",
  [203] = "CLEAR_REGS",
  [205] = "NOOP",
  [207] = "FORLOOP",
  [208] = "ADDK",
  [209] = "GETTABLEKS",
  [213] = "NOTNOT",
  [214] = "CLOSURE",
  [216] = "JUMP",
  [219] = "AND",
  [225] = "TYPE",
  [231] = "REMOVE",
  [234] = "LOADINT_B",
  [237] = "VARARG",
  [242] = "BNOT",
  [243] = "MATH_Z2",
  [244] = "MATH_K2",
  [245] = "NEWTABLE",
  [248] = "OR",
  [252] = "SETMETATABLE",
  [253] = "CHAR",
  [255] = "LE"
}

-- Опкоды, у которых операнд D - индекс константы (для дизассемблера).
local CONST_OPS = {[8]=1,[26]=1,[27]=1,[31]=1,[59]=1,[104]=1,[106]=1,[133]=1,[151]=1,
                   [157]=1,[160]=1,[165]=1,[179]=1,[183]=1,[208]=1,[209]=1}

--- Читаемый листинг прототипа (и всех вложенных).
function disassemble(p, out, depth, id)
  out   = out or {}
  depth = depth or 0
  id    = id or 1
  local pad = string.rep("  ", depth)
  local function fmt(v) return type(v) == "string" and ("\"" .. v .. "\"") or tostring(v) end
  table.insert(out, string.format("%s-- proto #%d: params=%d vararg=%s maxstack=%d upvalues=%d",
      pad, id, p.numParams, tostring(p.isVararg), p.maxStack, #p.upvalDescs))
  for i = 1, #p.upvalDescs do
    local u = p.upvalDescs[i]
    table.insert(out, string.format("%s--   upvalue %d: %s", pad, i - 1,
        u.fromReg and ("регистр #" .. u.index .. " внешней функции")
                  or ("upvalue #" .. u.index .. " внешней функции")))
  end
  for i = 1, #p.consts_ do
    local c = p.consts_[i]
    if type(c) == "table" then
      table.insert(out, string.format("%s--   K%d = <прототип #%d>", pad, i, c.z1 + 1))
    else
      table.insert(out, string.format("%s--   K%d = %s", pad, i, fmt(c)))
    end
  end
  for i = 1, #p.instrs do
    local ins  = p.instrs[i]
    local name = OPNAMES[ins.op_] or ("UNKNOWN_" .. ins.op_)
    local extra = ""
    if CONST_OPS[ins.op_] then
      extra = "   -- K" .. (ins.D_ + 1) .. " = " .. fmt(p.consts_[ins.D_ + 1])
    end
    table.insert(out, string.format("%s[%4d] %-14s A=%d B=%d C=%d D=%d%s",
        pad, i, name, ins.A_, ins.B_, ins.C_, ins.D_, extra))
  end
  for i = 1, #p.protos do
    disassemble(p.protos[i], out, depth + 1, i)
  end
  return out
end

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
  fl:write(table.concat(disassemble(p), "\n") .. "\n"); fl:close()
  print(string.format("[4/4] записан %s/stage2.dis (%d инструкций в главном прототипе, вложенных прототипов: %d)",
        outDir, #p.instrs, #p.protos))

  print("\n--- Строковые константы (самое интересное: URL, имена, ключи) ---")
  for _, s in ipairs(collectStrings(p)) do
    print(string.format("  %-16s %q", s[1], s[2]))
  end
end

return M
