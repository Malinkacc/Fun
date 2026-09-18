// Execute/compile a Lua file in real Luau (WASM). Usage: node run_luau.mjs file.lua [--exec]
import fs from 'fs';
const { Lua } = await import('@luau-rs/luau');
const lua = await Lua.create();
const src = fs.readFileSync(process.argv[2], 'utf8');
try {
  lua.compile(src);
  console.log('COMPILE: OK');
} catch (e) {
  console.log('COMPILE FAIL:', (e.message ?? String(e)).split('\n').slice(0, 3).join(' | '));
  process.exit(1);
}
if (process.argv.includes('--exec')) {
  try {
    const r = lua.execute(src);
    console.log('EXEC: finished, returned:', JSON.stringify(r).slice(0, 120));
  } catch (e) {
    console.log('EXEC ERROR:', (e.message ?? String(e)).split('\n').slice(0, 4).join(' | '));
  }
}
