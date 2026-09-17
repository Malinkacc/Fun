# Sprint 7 — non-Luraph obfuscator families (MoonSec V3 / MoonVeil 2.x / WeAreDevs v1)

Status: decoder/tracer pipeline + synthetic emitters + round-trip tests are in
place for all three families; real-sample bootstrap layers are decoded
agent-side.  Full plaintext extraction of the embedded programs (per-family
cipher mirrors) remains as tracked follow-up depth work.

Samples (user-provided, commit 0d4ecd6):
`obfuscator/deobfuscator/samples/other/{moonsec_v3,moonveil_2_0_24,wearedevs}.lua`

## Architecture

Front end: `dynamic_decrypt.py` — sandbox run with AutoMock Roblox env and
identity-wrapped loadstring/load capture (depth-recursive).  All three
families turned out to be SELF-INTERPRETING (no loadstring layer within
500M steps for MoonSec), so per-family observation hooks were built:

| Family   | Modules (package)                          | What they give on real samples |
|----------|--------------------------------------------|--------------------------------|
| MoonSec  | moonsec/string_harvest.py                  | string-table harvest (none: strings stay in locals) |
|          | moonsec/ref_bootstrap_dump.lua             | unparsed bootstrap bodies (env maze, PRNG constants, stream markers) for the Python mirror |
| MoonVeil | moonveil/vm_trace.py                       | opcode-closure catalogue + bootstrap decode pairs [enc,dec] |
|          | moonveil/vm_state.py                       | state-machine call log with in-window table writes |
|          | moonveil/stream_assemble.py                | ordered decoded unit stream (raw chunks + plaintext xforms: env names) |
|          | moonveil/vm_phase.py                       | VM-phase helper call rhythm |
|          | moonveil/vm_tables.py                      | VM-phase table I/O (bytecode array / register file exposed) |
|          | moonveil/vm_lift.py                        | instruction-level lift: word + decoded operands + register effects |
| WeAreDevs| wearedevs/array_trace.py                   | cipher array (8233 entries), rotation progress, plaintext-write detector |

Round trip: `sprint7_emitters.py` + `sprint7_roundtrip.py` (5/5).

## Key findings (real samples, agent-side runs)

* MoonSec V3: bootstrap = 422-iteration PRNG maze building env `h` from a
  marker stream (`\005`/`\006`), `d = getfenv()`; strings decrypted on demand
  by PRNG rejection loops (~8 steps/char); no loadstring up to 500M steps.
* MoonVeil 2.0.24: bootstrap ends ~450k steps; env decoded live
  (`vs, __mode, unpack, byte, char, gmatch, move, pack, create, insert, bor,
  bxor, band, btest, lshift, ...`); VM phase = inline loop over tables:
  bytecode words read from `H[neg_hash]` (floats), operands from a 3-slot
  keystream table, effects as register writes (~95k instrs per 4M steps).
* WeAreDevs v1.0.0: 8233-entry 'M'-prefixed cipher array with head/tail
  rotation (~4M steps per pass in the sandbox); VM resolves strings per use
  via concatenation (no table writes), so plaintext capture needs the
  per-entry cipher mirror.

## Sandbox correctness fix (this sprint)

Closures previously captured `dict(env)` copies: upvalue writes from inner
functions were silently lost.  Now `LuaFunction.closure` holds the live
enclosing env and `_FuncEnv` implements parent-chain reads + write-through
assignments (real Lua upvalue semantics).  Regression: all Luraph and Sprint 7
self-tests green.

## Runner

`opmap.ps1` steps 1-14 (seconds each on user machine): Luraph pipeline (1-4),
dynamic_decrypt (5), moonsec string_harvest (6), moonveil vm_trace/vm_state/
stream_assemble/vm_phase/vm_tables/vm_lift (7-12), wearedevs array_trace (13),
sprint7 round-trip (14).
