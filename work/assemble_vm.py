# -*- coding: utf-8 -*-
engine = open('dispatcher_clean.lua', encoding='utf-8').read()
b32    = open('bit32_pure.lua', encoding='utf-8').read()
names  = open('names_lua.txt', encoding='utf-8').read()

bit32wrapped = ("local bit32 = (function()\n" + b32.rstrip().rsplit("return bit32", 1)[0] + "  return bit32\nend)()\n")

header = '''--=============================================================================
--  ДЕОБФУСЦИРОВАННАЯ ВЕРСИЯ "ЗАЩИЩЁННОГО" СКРИПТА  (4 строки -> читаемая VM)
--=============================================================================
--  Схема оригинала:
--    1) в тексте лежит гигантский строковый литерал (blob, ~80 КБ, с префиксом длины);
--    2) decryptBlob(): внутри каждых 256 байт переставляет байты по таблице SHUFFLE,
--       затем XOR-ит всё с байтом (i-1+225)%256, т.е. с константой 0xE1 (225);
--    3) t1(plain, key) - вызов ВНЕШНЕЙ глобальной функции, которой в присланном коде НЕТ;
--       предполагается, что она возвращает байткод (loadstring/декодер);
--    4) deserialize(): разбирает Luau-подобный контейнер: u32 numParams, u8 isVararg,
--       u32 maxStack, список upvalue-описателей, пул констант (nil/bool/float64/string/proto),
--       инструкции по 8 байт (op,A,B,C + знаковый i32 D), вложенные прототипы;
--    5) runProto(): интерпретатор. Регистры - обычная таблица Lua; для каждого из
--       116 реализованных опкодов свой обработчик в цепочке if/elseif.
--
--  Изменения относительно оригинала (логика интерпретатора НЕ менялась -
--  проверено дифференциальным тестом на 4 синтетических чанках):
--    * вырезаны 9 обработчиков-заглушек, которые ничего не делали (NOOP);
--    * к каждому опкоду добавлено имя и описание + таблица OPNAMES;
--    * добавлен чистый Lua-fallback для bit32 (оригинал падает без bit32: Lua 5.1/5.4);
--    * добавлен disassemble() - читаемый листинг байткода;
--    * исправлено обращение к полю D инструкции (артефакт переименования).
--=============================================================================

'''

tail = '''
--===== 2. ТАБЛИЦА ОПКОДОВ =====================================================

OPNAMES = OPNAMES or {
''' + names + '''
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
  local function fmt(v) return type(v) == "string" and ("\\"" .. v .. "\\"") or tostring(v) end
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

return {
  decryptBlob = decryptBlob,
  deserialize = deserialize,
  runProto    = runProto,
  disassemble = disassemble,
  OPNAMES     = OPNAMES,
}
'''

open('/home/user/deobfuscated/vm.lua','w',encoding='utf-8').write(header + bit32wrapped + '\nlocal strByte = string.byte\nlocal strSub  = string.sub\nlocal unpack  = table.unpack or unpack\n\n' + engine + '\n' + tail)
print("vm.lua собран:", len(header+bit32wrapped+engine+tail), "байт")
