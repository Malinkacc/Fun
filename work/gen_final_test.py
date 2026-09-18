vm = open('/home/user/deobfuscated/vm.lua', encoding='utf-8').read()
blobs = open('/home/user/work/blob_test.lua', encoding='utf-8').read()
test = '''
local vm = (function()
__VM__
end)()
t1 = function(s, key) return s end   -- «внешний» загрузчик (в оригинале его НЕТ)
print("=== A. Сквозной путь: decryptBlob -> deserialize -> runProto ===")
for i = 1, #BLOBS do
  local ok, err = pcall(function()
    local chunk = vm.decryptBlob(BLOBS[i], "key-which-is-ignored")
    assert(chunk == EXPECT[i], "расшифровка не совпала (чанк "..i..")")
    vm.runProto(vm.deserialize(chunk), {})
  end)
  print(string.format("   chunk%d -> %s", i, tostring(err or "OK (расшифровано и исполнено)")))
end
print("")
print("=== B. Модуль возвращает: ===")
local t = {}
for k in pairs(vm) do t[#t+1] = k end
table.sort(t)
print("   " .. table.concat(t, ", "))
'''.replace('__VM__', vm)
open('/home/user/work/final_test2.lua','w').write(blobs + test)
print("final_test2.lua пересобран под текущий vm.lua")
