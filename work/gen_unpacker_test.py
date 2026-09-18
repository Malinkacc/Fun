up   = open('/home/user/deobfuscated/unpack_stage2.lua', encoding='utf-8').read()
up   = up.replace('if type(io) == "table" and io.open and arg and arg[1] then', 'if false then')
text = open('fake_original.lua', encoding='utf-8').read()
assert ']]' not in text
tail = '''
local up = (function()
__UP__
end)()

local blob, err = up.extract(SRC)
assert(blob, "не извлеклось: " .. tostring(err))
print(string.format("1) литерал извлечён: %d байт (заголовок длины: %d)", #blob,
      blob:byte(1)*16777216 + blob:byte(2)*65536 + blob:byte(3)*256 + blob:byte(4)))

local chunk, derr = up.decode(blob)
assert(chunk, "не расшифровалось: " .. tostring(derr))
print(string.format("2) блок расшифрован: %d байт байткода", #chunk))

local p = up.deserialize(chunk)
print(string.format("3) контейнер разобран: инструкций=%d, вложенных прототипов=%d, констант=%d",
      #p.instrs, #p.protos, #p.consts_))

print("--- строковые константы (то, что ищет аудитор) ---")
for _, s in ipairs(up.collectStrings(p)) do
  print("   " .. s[1] .. " = " .. ("%q"):format(s[2]))
end

print("--- первые 10 строк листинга stage2.dis ---")
local ls = up.disassemble(p)
for i = 1, math.min(10, #ls) do print(ls[i]) end
'''.replace('__UP__', up)
open('test_unpacker.lua', 'w').write("local SRC = [[" + text + "]]\n" + tail)
print("test_unpacker.lua пересобран")
