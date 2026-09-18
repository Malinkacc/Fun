const fs = require("fs");
const { lua, lauxlib, lualib, to_luastring } = require("fengari");
const L = lauxlib.luaL_newstate();
lualib.luaL_openlibs(L);
const code = fs.readFileSync("runner.lua","utf8");
const status = lauxlib.luaL_dostring(L, to_luastring(code));
if (status !== lua.LUA_OK) { console.error("LUA ERROR:", lua.lua_tojsstring(L, -1)); process.exit(1); }
