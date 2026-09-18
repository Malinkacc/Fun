const fs=require("fs");const F=require("fengari");
const {lua,lauxlib,lualib,to_luastring}=F;
const L=lauxlib.luaL_newstate();
lualib.luaL_openlibs(L);
// подключаем bit32 (в Lua 5.3 есть; fengari требует явной регистрации)
lauxlib.luaL_requiref(L, to_luastring("bit32"), lualib.luaopen_bit32, 1);
lua.lua_pop(L,1);
const st=lauxlib.luaL_dostring(L,to_luastring(fs.readFileSync("/home/user/work/diff_test.lua","utf8")));
if(st!==lua.LUA_OK){console.error("LUA ERROR:",lua.lua_tojsstring(L,-1));process.exit(1);}
