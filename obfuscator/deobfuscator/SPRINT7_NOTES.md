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
  PROOF (this sprint): the payload stage dispatches by self-invocation
  `f(8, nil, f, e, n)` -- tail recursion per element, depth = element count
  (tens of thousands).  Interpreting that in CPython is infeasible by
  construction (MAX_DEPTH 20000 + 256 MB-stack thread still die), so the
  Python mirror (iterative re-implementation of the modes) is the ONLY
  route; ref_bootstrap_dump.lua carries the exact constants for it.
* MoonVeil 2.0.24: bootstrap ends ~450k steps; env decoded live
  (`vs, __mode, unpack, byte, char, gmatch, move, pack, create, insert, bor,
  bxor, band, btest, lshift, ...`); VM phase = inline loop over tables:
  bytecode words read from `H[neg_hash]` (floats), operands from a 3-slot
  keystream table, effects as register writes (~95k instrs per 4M steps).
* WeAreDevs v1.0.0: 8233-entry 'M'-prefixed cipher array with head/tail
  rotation (~4M steps per pass in the sandbox).  RESOLVED by
  `wearedevs/array_mirror.py` (slice 4b): the bootstrap `do` block decrypts
  the array in place with two codecs -- '(' entries = base64 with custom
  64-char alphabet table `S`, 'M' entries = ascii85-like with custom 85-value
  map `l` (groups of <=5 chars forward, Y=Y*85+m, missing tail positions use
  pad value 84 = `480327835%11715311`, n chars emit n-1 bytes big-endian).
  Both alphabets parse as exact bijections (0..63 / 0..84).  Decoded: 951
  printable strings (Roblox GUI-lib API: InvokeServer, WaitForChild,
  BuildConfigSection, Colorpicker, Dropdown, cloneref, ... plus ~250 random
  12-char renamed identifiers) and ~7280 short binary blobs (bytes 0x00-0x03
  dominate = VM data).  Verification: re-encoding decoded bytes reproduces
  2553/8233 cipher entries byte-exactly; the rest differ only in the final
  partial group (ascii85 tail encoding is non-injective; decoded bytes are
  identical).  The earlier sandbox plain=0 observation is explained: the
  decrypt block runs after the rotation phase, beyond the traced window.

## MoonSec V3 VM architecture (slice 2b-4, `moonsec/vm_model.py`)

Static model of what the stage2/stage3 constants parameterise (all anchors
verbatim in the sample):

* Proto-stream decoder: `local function de(u,...) local a=t(e,">4^K...")` --
  a 13702-char blob over an 85-char printable alphabet, decoded by the same
  payload decoder `t` mirrored in mirror.py.
* Proto assembler `ee()` builds one function proto as
  `{instructions, nested_protos, nparams, {const_pool}}`: typed constant
  pool (tag 2 = boolean via `o()~=#{}`, tag 1 = string via `_()` with
  trailing-zero strip, tag 0 = number via `p()`); instruction loop reads a
  packed byte, `bit(e,1)==0` selects instructions, `f=bits(e,2,3)` picks
  operand-B kind (0 -> two extra words, 1 -> one, u[2]/u[3] -> minus 2^16
  offsets), `o=bits(e,4,6)` selects constant-pool substitution for fields
  1/3/4; nested protos recurse via `ee()`.
* VM closure `_(z,o,m)`: preamble resolves `l=f(7)` (env proxy),
  `t=f(6,49,1,79,z)=z[49]` (instruction array), `k=f(6,63,2,43,z)=z[63]`
  (constant array), `j=f(6,98,3,28,z)=z[98]` (varargs boundary) -- keys are
  exactly the stage2 constants XiHzKHKe=49, grtQZmMW=63, dbYQXyMl=98.
* Closure wiring: stream marker \006 installs
  `d[name]=function(n,e) return f(8,nil,f,e,n) end`; factory mode 8 =
  `do return n(l,nil,n) end` -- the proto hand-off channel.  Factory mode
  table (verbatim): 1 = bit-range extractor, 2 = bases (16777216,65536,256),
  4/5 = byte-reader closures, 6 = `d[n]` index, 7 = metatable proxy,
  8 = closure creation.
* VM dispatch: `f=e[g]` (g=1) with numeric guards; opcode domain ~[77..114]
  (bounds 76/96/99/101/104/114 from stage2, literal leaves 98..104), leaves
  are unrolled Lua 5.1 opcode groups.  VM body = 53652 chars.
* Next (2b-5): mirror the de-blob decode + ee framing in Python to recover
  the literal instruction array, then map opcode leaves to Lua 5.1 semantics.

## Sandbox correctness fix (this sprint)

Closures previously captured `dict(env)` copies: upvalue writes from inner
functions were silently lost.  Now `LuaFunction.closure` holds the live
enclosing env and `_FuncEnv` implements parent-chain reads + write-through
assignments (real Lua upvalue semantics).  Regression: all Luraph and Sprint 7
self-tests green.

## Runner

`opmap.ps1` steps 1-18 (seconds each on user machine): Luraph pipeline (1-4),
dynamic_decrypt (5), moonsec string_harvest (6), moonveil vm_trace/vm_state/
stream_assemble/vm_phase/vm_tables/vm_lift (7-12), wearedevs array_trace (13),
sprint7 round-trip (14), moonsec mirror (15), wearedevs array_mirror (16),
moonveil opcode_semantics (17), moonsec vm_model (18).
