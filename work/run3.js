const fs=require("fs");const F=require("fengari");
const {lua,lauxlib,lualib,to_luastring}=F;
const L=lauxlib.luaL_newstate();lualib.luaL_openlibs(L);
// эмулируем loadfile/dofile чтением файла на стороне JS
lauxlib.luaL_dostring(L, to_luastring(`
function loadfile(p) local f=io.open and io.open(p,"r") end  -- в fengari io нет; подменим ниже
`));
const src = fs.readFileSync("/home/user/work/bit32_test.lua","utf8")
  .replace("local f=loadfile('bit32_pure.lua') return f() end", "local f=function() return (function() " + fs.readFileSync("/home/user/work/bit32_pure.lua","utf8") + " end)() end return f() end");
// проще: подставим содержимое модуля напрямую
const test = fs.readFileSync("/home/user/work/bit32_test.lua","utf8");
const mod  = fs.readFileSync("/home/user/work/bit32_pure.lua","utf8");
const combined = "local _mod = function() " + mod + " end\n" + test.replace("local bit32 = (function() local f=loadfile('bit32_pure.lua') return f() end)()", "local bit32 = _mod()");
const st=lauxlib.luaL_dostring(L,to_luastring(combined));
if(st!==lua.LUA_OK){console.error("LUA ERROR:",lua.lua_tojsstring(L,-1));process.exit(1);}
