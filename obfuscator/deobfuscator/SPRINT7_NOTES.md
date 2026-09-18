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

## MoonSec V3 proto blob decoded (slice 2b-5, `moonsec/proto_decode.py`)

The 13702-char proto blob is DECODED.  Two-stage result:

* Payload mirror proven byte-exact.  `mirror.decode_payload(payload1, seed)`
  reproduces the real constants table exactly
  (`\x02\x044083V_TpiQHS\x02\x010hcQSdrdZ...`, 51 records, terminator `\x05`).
  Record format = `\x02` tag, digit-count byte, ASCII digit string, name.
  The decoder's unknown-char -> 0 fallback is NOT an error path: it is a
  deliberate many-to-one encoding (out-of-sbox body characters represent
  nibble 0).  Payload1 body: 66 distinct chars, 15/16 sbox chars present,
  88/1276 out-of-sbox; empirical char->nibble map has zero conflicts.
* Blob seed recovered = 252 (unique).  The shipped blob does NOT use the
  synthetic ee() framing (first dword is little-endian count = 70; const
  records use a tag/length layout that does not round-trip decode_proto), so
  structural validation fails.  Instead the seed is found by scoring every
  candidate decode for real VM API string constants (`find_seed_by_tokens`).
  Seed 252 is the ONLY candidate exposing the stdlib/import names -- it hits
  9/12 API tokens with a 109-char ASCII run; every other seed hits 0.
* String-constant table fully recovered (44 entries) via
  `extract_blob_strings` (printable-ASCII runs): `print`, `string`, `char`,
  `pcall`, `getfenv`, `load`, `loadstring`, `type`, `setmetatable`; MoonSec
  internals `cfex`, `getinternalsyscall`, `isoverwritten`,
  `MoonSec_StringsHiddenAttr`, `wasFederalReallyHereAttribute`; and the
  anti-tamper taunts `Federal was here`, `Hands Up Skid`,
  `A picture taken from your webcam:` + the webcam ASCII art,
  `Your platform is unable to execute this script.`
* `--test` is 7/7 (T7 = synthetic real-blob-path round-trip: encode API names
  at seed 252, recover seed + strings).  `--sample` writes
  `_captures/msvm/blob_strings.json` + `blob_decoded.bin` (6843 bytes).
* Remaining (2b-6): reverse the exact numeric record framing (LE-count header
  + tagged const/instr/nested records) to lift the literal instruction array,
  then map the opcode domain (~77..114) to Lua 5.1 semantics.

## MoonSec V3 proto blob FULLY parsed (slice 2b-6, `moonsec/proto_decode.py`)

The 2b-5 "remaining" item is DONE.  The framing mystery (why the first dword
read as a huge BE count) is resolved: **factory mode 4 `n()` is LITTLE-endian**,
not big-endian.  Mode 4 returns `(h*2^24)+(f*2^16)+(n*256)+e` over
`string.byte(a, pos, pos+3)`; the first byte `e` is the least-significant, so
every dword (counts, string lengths, n-operands) is LE, and `_()` (two `n()`
words, low first) is a standard little-endian IEEE754 double.

With the whole stream reinterpreted as LE, the blob parses as a single nested
proto tree that consumes the decode EXACTLY:

    seed 252 -> 6843 bytes -> consumed 6843/6843 (100.0%)
    root proto: 70 consts (43 strings + 27 numbers), 284 instrs, 7 nested
    whole tree: 14 protos, 516 instrs, 97 consts, 90 distinct opcodes (1..153)
    const numbers: 47, 0, 22, 8, 3, 2, 38, 7, 12, 9, 6, 13, ... (clean)
    top opcodes: 152(x37) 24(x27) 12(x25) 27(x21) 5(x20) 2(x19) 6(x15) ...

Constant substitution is live: e.g. root instr #2 = `[8, 0,
'MoonSec_StringsHiddenAttr', None]` -- ok-bit2 replaced operand B with const[1].

Implementation: `Stream.word4be`->`word4le`, `float64` = `struct '<d'`, string
length LE; `decode_proto` reads all counts/operands LE; `decode_full` returns
(proto, consumed, total) and `find_seed` now scores candidates by consumed
fraction (>=0.9) so the real blob is found structurally (no token fallback
needed).  Synthetic writer switched to LE (`_w4le`, `_w_float`='<d').
`--test` is 8/8 (T8 = real-blob structural discovery + exact-consume).
`--sample` writes `protos.json` (full tree) + `proto_stats.json` +
`blob_decoded.bin`.

* Next (2b-7): map the 90 proto opcodes (range 1..153) to Lua 5.1 semantics by
  correlating the lifted instruction array against the VM interpreter dispatch
  (`function ne(...)` @183337) and the runtime opcode domain (~77..114), then
  lift the proto tree to readable Lua like the Luraph pipeline.

## MoonSec V3 opcode operand-shape profile (slice 2b-7, `moonsec/msvm_opcodes.py`)

First 2b-7 artifact: an EMPIRICAL operand-shape profile of every proto opcode,
computed from the 2b-6 lifted tree (516 instrs, 90 distinct opcodes).  The VM
interpreter dispatch is a ~53 KB obfuscated state machine and full-sample
dynamic tracing is blocked by sandbox recursion limits, so operand shapes are
the reliable evidence base for the mnemonic mapping (next slice).

Per opcode: count, withB/withC (operand slots present), Bconst/Cconst (slot
filled by a non-numeric constant-pool value), Amin/Amax (A-field range).
Representative shapes already discriminate effect classes:

    op 152 x37  B:0/37 C:0/0  A:[0..0]    always-B, never-C, A fixed  -> unary/jump-like
    op  24 x27  B:0/27 C:0/24 A:[0..26]   B+C, wide A                 -> binary (arith/cmp)
    op  12 x25  B:7/25 C:0/5  A:[0..24]   B often const               -> LOADK/const-heavy
    op 143 x12  B:0/12 C:0/12 A:[3..20]   always B+C                  -> binary
    op 148 x12  B:0/12 C:0/12 A:[3..12]   always B+C                  -> binary
    op  65 x10  B:0/10 C:0/10 A:[0..0]    always B+C, A fixed         -> call/settable-like

Caveat: a substituted NUMERIC const is an int after int_fix, so Bconst/Cconst
count only non-numeric substitutions; withB/withC and the A range are exact.

`--test` is 4/4 (synthetic tree with known shapes).  `--protos protos.json`
prints the top-N shapes and writes `opcode_profile.json`.  opmap STEP 20 added.

* Next (2b-8): correlate each opcode's shape against the VM dispatch handler
  bodies to assign Lua 5.1 mnemonics, then emit a lifter (proto tree -> Lua).

## MoonSec V3 proto-tree lifter (slice 2b-8, `moonsec/msvm_lift.py`)

Renders the lifted proto tree as readable pseudo-Lua: one labelled block per
proto (`== proto 0 (nparams=.. consts=.. instrs=.. nested=..)`), the constant
pool resolved to literals (strings quoted, non-utf8 bytes as `x'<hex>'` from the
protos.json `__bytes__` form), instructions as `#i op=.. A=.. B=.. C=..` with
substituted constants shown as literals and absent slots as `_`, nested protos
indented one level per depth.

Honesty: a raw int operand is register-or-immediate and is NOT resolvable from
the lifted tree alone (needs per-opcode semantics), so ints are printed
verbatim; only non-int operands are rendered as literals.  Real sample lifts to
627 lines (`lifted_msvm.txt`), e.g.
`#1 op=8 A=0 B='MoonSec_StringsHiddenAttr' C=_`.

`--test` is 4/4.  `--protos protos.json` writes `lifted_msvm.txt`.  opmap
STEP 21 added.

* Next (2b-9): opcode mnemonic mapping (shapes + VM dispatch handler bodies ->
  Lua 5.1 names), then upgrade the lifter from pseudo-Lua to real statements.

## MoonSec V3 dispatch extractor (slice 2b-9 part 1, `moonsec/msvm_dispatch.py`)

Static extraction of per-opcode HANDLER BODIES from the obfuscated interpreter
(`function ne(...)` @183337, ~53 KB), no sandbox:

* stage2 numeric constants (51) re-decoded from payload1 (seed 107) resolve
  every `h.Name` guard of the dispatch tree.
* Lua tokenizer + block parser build the guard tree of
  `while le do ... e=t[n];f=e[g]; if ... end ... n=1+n end`; a sequential
  walker threads the candidate opcode set through the guards, so
  `repeat if f~=K then BODY;break;end FALL until true` wrappers put BODY on
  S\{K} and FALL on {K}; raw statements become (opset, span) segments.
* DOMAIN PROOF: the tree covers opcodes 1..160 with EMPTY residual, and all
  90 proto opcodes (1..153) are covered -- there is NO opcode remap between
  fetch and dispatch.  vm_model.py's "~77..114" was an artifact of scanning
  only the upper half of the tree (bounds 76/96/99/101/104/114 are real
  guards, but of the f>76 subtree only).
* Driver loop: handlers advance pc inline between fused sub-ops
  (`n=n+1;e=t[n];`), shared tail `n=1+n` completes the last step; `if n<-40
  then n=n+42 end` is the pc-wrap guard (gtWTPyqI=40, ROzjrxmk=42).
* Register file `l` = factory mode 7 proxy:
  `setmetatable({},{__call=function(e,c,d,l,n) if n then return e[n] elseif
  l then return e else e[c]=d end end})` => `l(a,b)` is LOADIMM R[a]:=b;
  `o`=globals, `m`=upvalues, `k`=constant array (op 8 = CLOSURE:
  `l[e[d]]=_(k[e[c]],nil,m)`).
* Op 24 = CLOSURE upvalue-descriptor pseudo-instruction: the CLOSURE handler
  consumes `e[r]` following instructions (`if e[g]==24 then f[d-1]={l,e[c]}`
  = stack upvalue), matching Lua 5.1 CLOSURE semantics; proto records with
  opcode 24 are descriptors, not dispatchable ops.
* 17 byte-identical duplicate-body groups ([8,111] CLOSURE, [44,47,60],
  [101,128], [64,151], [105,145], [152,154..160] phantom-tail, ...).
* Catalog: 191 segments; 76/160 ops (50/90 proto ops) already reduce to
  canonical primitives (MOVE/LOADIMM/ADD../GET../SET../GET/SETGLOBAL/
  GET/SETUPVAL/NEWTABLE/LOADBOOL/LOADNIL/LEN/TEST/EQ/JMP/CALL/RET/...).
  The rest are state-machine-unrolled composites (e.g. op 5 = MOVE via a
  7-state alias unroller; op 100 = CONCAT A B C; op 152 top-count) -- alias
  executor next (2b-9 part 2), then the lifter upgrade (2b-10).

`--test` is 6/6 (tokenizer, guard reduction incl. flips, tree walk pinning on
a synthetic dispatcher, repeat-wrapper pair splitting, non-overlapping
primitive matching, composite-isolation).  `--sample` writes
`msvm_dispatch.json` (per-op segments/prims/unmatched + duplicates + coverage).

* Next (2b-9 part 2): symbolic alias-unroller executor for the composite
  handlers -> full per-op mnemonic table; then 2b-10 upgrades msvm_lift from
  pseudo-Lua to real statements (register-vs-immediate resolved per-op).

## MoonSec V3 opcode semantics (slice 2b-9 part 2, `moonsec/msvm_semantics.py`)

The alias-executor half of 2b-9: per-opcode handler streams become canonical
register-transfer effects and Lua 5.1 style mnemonics.  RESULT: **all 160
dispatch opcodes resolve with zero unresolved markers**; the 90 opcodes used
by the embedded program (516 instrs) map to:

    JMP(x37) MOVE LOADK SETGLOBAL GETUPVAL FORLOOP FORPREP CLOSE_UV
    RETURN_1/_m/_0 GETGLOBAL GETTABLE SETTABLE NEWTABLE LOADBOOL LOADNIL
    TEST TESTN TESTSET EQ_C/EQ_K NE_C/NE_R CALL_0 CALLC VARARG SELF CONCAT
    CLOSURE ADD/SUB/MUL/MOD/POW LEN NOP + SUPERINSTRUCTIONS (fused chains)

Superinstruction examples: op 122 = LOADK x5 + GETTABLE; op 9 = 5x LOADIMM +
CALL; op 18 = LOADBOOL+SETUPVAL+GETUPVAL+NEWTABLE x3; op 88/144 =
MOVE+GETUPVAL+CALL(+SELF); op 119 = TAILCALL+RETURN_m+RETURN_0.  Top-count
op 152 = JMP (x37) -- exactly what the 2b-7 operand profile predicted
("A fixed, B/C absent -> jump-like").  Opcode 24 records are ALL CLOSURE
upvalue descriptors (positional: `for d=1,e[r] do ... if e[g]==24 then
f[d-1]={l,e[c]} else f[d-1]={o,e[c]} end` = stack vs env-bound upvalue);
its dispatch body is MOVE-shaped but unused.

Pipeline (all static): (1) context-aware op-walk over the guard tree --
negative-constant guards (`if-4~=f`) and `h.NAME` guards parse as opcode
splits; state-machine headers (`VAR=0; while VAR>-1 do`) become SM markers;
(2) per-op SM expansion: conditions on the state var split the STATE set
(states 0,1,2,... in order, `VAR=-2` terminates), other conditions are
runtime choices and BOTH branches are kept (ALT); dummy for-selectors and
`repeat if c then A break;end B` wrappers execute exactly one branch via the
sequential walk; (3) symbolic alias executor resolves obfuscated temporaries
(`f=e;r=d;o=c;s=l;h=s[f[o]];t=f[r];l[t]=h` -> R[A]:=R[B]) through a small
expression parser into canonical operands (A/B/C fields, R[x], K[x], G[x],
U[x], INSTR, pc); (4) effect classifier assigns mnemonics; `local n/e`
declarations shadow pc/INSTR; step pairs (`n=n+1`,`e=t[n]`) are folded.

Also refined `msvm_dispatch.parse_cond` with the same robust condition
parser (unary-minus + h.NAME consts, 3..4 token forms): its real-sample
catalog improved to 19 duplicate-body groups ([8,111] CLOSURE, [44,47,60],
[20,97,99], [75,133], [101,128], [105,145], [152,154..160] phantom-tail,
...); coverage proof unchanged (1..160, empty residual).

`--test` is 6/6 (depth-aware statement split; synthetic 3-op dispatcher with
plain/proxy/unrolled-MOVE handlers; alias resolution).  `--sample` writes
`msvm_semantics.json` (per-op names/details/unresolved/alts).  opmap STEP 23
added.

* Next (2b-10): upgrade `msvm_lift` from pseudo-Lua to real statements using
  this mnemonic table (skip CLOSURE descriptors positionally; decode
  jumps/branches to labels; register-vs-immediate per mnemonic).

## MoonSec V3 decompiler (slice 2b-10, `moonsec/msvm_decomp.py`)

The chain-2b finale: the decoded proto tree lifts to READABLE LUA with real
statements (the 2b-8 pseudo listing stays for raw reference).  Execution
model proven on the real sample while building this:

* Field map: instruction = [op, A, B, C]; VM fields e[g]/e[d]/e[c]/e[r] =
  op/A/B/C.  EVERY control transfer uses **B** (`n=e[c]` + loop tail +1 ->
  target slot B+1): JMP (152/28), TEST/TESTN/TESTSET, EQ/NE (C is the
  compare operand, R or immediate), FORLOOP/FORPREP, EQ_K (59/96).
  A TEST-like TRUE branch SKIPS the next slot -> the slot after a
  conditional is dead padding (rendered as a comment).
* EQ/NE direction: handlers are `if (A==C) then skip else goto` (and ~=
  mirror), so the decompiler emits the goto under the NEGATED condition --
  verified against the taunt leaf: `if r0 == "" then return
  U["vzqmDbuPGFdLEJP"] end; return "Federal was here"`.
* Superinstructions consume `1 + #refetch-pairs` slots (msvm_semantics
  `consumed`); each chain element renders from its OWN slot's A/B/C
  (e.g. op 25 = 3x GETGLOBAL + GETTABLE + tailcall/return chain over 7
  slots).  CLOSURE-with-descriptors (112/123, handler
  `for d=1,e[r] do n=n+1; local e=t[n]; if e[g]==24 ...`) consumes 1+C
  slots; op 8/111 consume 1 (proto from constants).
* Opcode 24 never dispatches (slot body `n=-2`); op-24 slots are
  descriptors/fillers.  Anti-tamper regions contain intentionally DEAD
  slots (TEST/JMP with non-integer targets, orphan op-24); all of them
  are rendered as explicit `--[[dead ...]]` comments, nothing dropped.
* Real sample: 516 slots -> 368 macros, 12 dead/unresolved (2.3%,
  almost all in the root's anti-tamper block), output
  `msvm_decompiled.lua` with labels/gotos, resolved constants, upvalue
  NAMES (`r6 = U["getfenv"]`) and per-slot provenance comments.

`--test` is 6/6 (statements with reg/literal operands; JMP/label/TEST-skip;
table ops; descriptor consumption; superinstr per-slot rendering; dead-slot
marking).  opmap STEP 24 added.  `msvm_semantics` now also emits per-slot
`chain` entries as [name, detail] pairs plus `consumed`.

## Chain 2b status (MoonSec V3 -> plaintext)

COMPLETE end-to-end: payload mirror (2b-1..3) -> proto tree at seed 252
(2b-5/2b-6, 100.0% consume) -> operand profiles (2b-7) -> pseudo listing
(2b-8) -> dispatch extraction (2b-9p1) -> mnemonic table (2b-9p2) ->
readable Lua decompiler (2b-10).  Remaining known limits: dead-slot regions
are marked not interpreted; a few superinstr chain entries keep candidate
ambiguity (rendered from the most-resolved variant); vararg-boundary forms
(`RETURN_m`, multres calls) render with `...` markers.

## MoonSec V3 one-command decompiler (slice 2b-11, `moonsec/decompile.py`)

Single entry wiring the whole verified chain with no new RE logic:

    py -m obfuscator.deobfuscator.moonsec.decompile --in obfuscated.lua --out deobf.lua --clean

extract_blob -> find_seed -> decode_payload -> decode_full (>=90% consume
guard) -> msvm_semantics (dispatch + alias executor) -> msvm_decomp
(readable Lua) -> clean_lua (provenance comments stripped, code+labels
kept).  The report line prints blob size, recovered seed, consume ratio,
slot/macro/dead counts.  On the real sample: blob=13702, seed=252,
6843/6843 (100.0%), 14 protos, 516 slots, 368 macros, 12 dead (2.3%).
`msvm_decomp` gained `--clean` and `clean_lua`; `lua_lit` now renders
live-path bytes constants as proper Lua strings / x'<hex>'.

`--test` is 6/6 (clean_lua code/comment split; full chain on the in-repo
real sample with honest skip if absent).  opmap STEP 25 added.

## MoonSec V3 structured control flow (slice 2b-12, `moonsec/msvm_struct.py`)

The goto-form Lua (2b-10) upgrades to STRUCTURED control flow where the CFG
proves it; every unmatched site falls back to the goto form, so structure
never costs correctness:

* repeat-until: TEST-family latch with BACKWARD target T (handler TRUE
  exits, FALSE repeats) -> `repeat <body T..S> until <cond>`.  Arbitrary
  gotos INSIDE the body are legal (they stay in the loop), so no interior
  check for loops; anti-tamper back-edges that target mid-superinstr
  slots (not macro starts) simply never qualify.  On the sample this
  recovered the embedded program's own dispatch loop (proto 0.1).
* if-then / if-else / if-return: TEST-family with FORWARD target T.
  TRUE branch skips one PADDING slot (S+1) — the padding slot is still
  rendered after the construct (it can be a jump target from elsewhere);
  then-region = S+2..join.  Else-terminator = `goto J>T` inside T..;
  then-terminator = RETURN; otherwise join at T.  Safety: no jump target
  may land strictly inside a then/else region (checked against the
  proto's full target set) -> fallback.
* Deliberately kept in goto/marker form: EQ_K + TESTSET (inverted/derived
  polarity), numeric FORLOOP/FORPREP (control-var register writes live in
  the alias-unrolled handlers — documented gap), unconditional JMPs.
* Labels are emitted only for targets still referenced by a remaining
  goto.  Real sample: 14 protos -> if=8 ifelse=4 ifret=2 repeat=2
  structured, fallback gotos=53, dead=3; `decompile --struct --clean`
  gives the one-command structured output.

`--test` is 6/6 (repeat; if-then incl. pad retention; if-else order;
if-return; if nested in repeat; interior-jump fallback with labels).
opmap STEP 26 added.  `decompile.py` gained `--struct`.

## WeAreDevs v1 flattened dispatch tree (slice 2c-1, `wearedevs/dispatch_map.py`)

The sample is NOT a bytecode VM.  After the string-array decrypt (slice 4b)
the program runs as a Prometheus-style flattened state machine, all inside
one dispatcher `function(Q,q,S,A)` (slot Q of the big simultaneous
assignment at ~offset 130.5k):

* `while Q do <if-tree> end` -- a nested binary search over the numeric
  state variable Q with folded-constant predicates (`Q>699130+7433818`,
  `2804890624%12750735>Q`, all three spellings equivalent after folding);
* leaves = linear basic blocks of the original program; Q is ALSO used as
  a temporary inside blocks, so a leaf's transition is its LAST assignment
  to plain `Q`, not its last statement;
* transitions: `Q=<const>` straight, `Q=x and A or B` conditional branch,
  `Q=nil` halt, `Q=<table lookup>` indirect (665 -- data-dependent);
* entry = `return(B(4635360,{}))(Y(l))` -> state 4635360 (B builds the
  entry closure; Y(l) = unpack(varargs) = the original script arguments).

`dispatch_map.py` folds constants on the TOKEN stream (runs of
num/+-/%()/ tokens, prefix-position rule so call parens survive: `m(a-b)`
stays a call; balanced-prefix cut; floats like `482112+-482111.5` = 0.5
supported), parses the tree structurally (expr parser handles and/or/not
KEYWORDS, multi-assign with expanding call `C,x=K(i,C)`, index/table
lvalues), derives each leaf's [lo,hi] range from its comparison path and
VALIDATES that every transition target lands in exactly one leaf range.

Real sample (1.58 MB region): 59505 folded consts, 3361 if-nodes ->
3362 leaves (nodes+1 = perfect binary structure), 4020 transitions
ALL resolved in-range (100.0%), distinct states 2849; kinds:
straight=1374, cond=1323, indirect=665.  Entry leaf 2829 straight ->
13048532.  Output: `wd_dispatch.json` (leaf spans, pred paths, ranges,
transitions) -- the base graph for lifting slices (2c-2+: handler
semantics via the S/m/W tables, then block-level decompiler).

`--test` is 6/6 (folding; leaf ranges; transition kinds; range resolution
incl. bounded miss; entry extraction; mini tree with multi-assign tail +
indirect lookup).  opmap STEP 27 added.

## WeAreDevs runtime names & slot map (slice 2c-2, `wearedevs/rt_names.py`)

Static resolution of the flattened program's vocabulary:

* NAME DECODER (verbatim anchor): `local function m(m) return V[m+10322] end`
  -- magic ints ARE array indices (1-based Lua, offset 10322).
* ORDER: V is rotated BEFORE decryption -- three in-place reversal passes
  `{1..8233}, {1..209}, {210..8233}` (step formulas fold to 1/1); the net
  permutation = rotate the tail-209 block to the front.  The slice-4b
  mirror decoded the unrotated order (per-entry codecs were right, global
  order was not) -- `rt_names` composes rotate01(raw) then the 4b codecs.
* SLOT MAP (19 targets = 19 values, parsed structurally with the 2c-1
  Parser): p decref; K 0; U/y/c/B/r/T/n/I/J/v/w closure makers with inner
  arities 8/1/7/varargs/4/10/5/2/0/3/6; i refcount++ + env-proxy
  (metamethod keys DECODED: `__index`, `__gc`, `__len`); h {} refcounts;
  W {} name->value store; O id-allocator (K=K+1; h[K]=1); C decref-array;
  Q THE DISPATCHER function(Q,q,S,A).  Wrapper params: S=setmetatable,
  V=getfenv() (env), A=getmetatable, N=select, q=newproxy, l={...},
  Y=unpack; entry = `B(4635360,{})(Y(l))` = main varargs closure applied
  to unpack(script args).
* GROUND TRUTHS (all [OK] on the real sample): m(-2896)='unpack' (the
  `unpack or table[m(...)]` fallback idiom), magic keys __index/__gc/
  __len; 10391 m() call sites resolved 8231 distinct ints, 0 misses;
  identifiers include game/string/table/math/concat/cloneref/
  WaitForChild/InvokeServer/FindFirstChild/fireclickdetector/listfiles/
  gmatch/UDim/BuildConfigSection + the renamed 12-char identifiers.

Parser upgrades shipped in `dispatch_map.py` (needed for the slot map):
`function` expressions (params incl. `...`), `while/repeat/for/do/if`
statements, `local function`, `...` token (lexer len-op fix).  The
2c-1 tree results are unchanged (6/6 still green).

`rt_names --test` is 6/6 (rotation steps; reversal mirror; decoder
offset; out-of-range safety; slot-map shape; magic-int extraction).
opmap STEP 28 added.  Output: `wd_names.json` (m_table, slot map, magic
keys, stats) -- together with `wd_dispatch.json` the base for the
block-level decompiler (2c-3).

## WeAreDevs block-level lift (slice 2c-3, `wearedevs/block_lift.py`)

Renders every dispatch-tree leaf as readable pseudo-Lua -- a BLOCK-LEVEL
DECOMPILATION of the whole flattened program:

* every `m(<magic int>)` call site becomes the decoded name literal
  (8231 names from slice 2c-2); constant arithmetic is folded; assignments,
  multi-assigns, calls, index chains, table constructors render
  structurally; unresolved m() stays verbatim (no guessing);
* each block header: leaf id, state range, kind, state target(s), the
  resolved successor leaf(s) and the full predicate path from the tree
  root (e.g. `--[L2829 | states 4633616..4637399 | straight ->
  13048532 (L1601)]` + `-- path: (Q>8132948)N ... (Q<4637400)Y`);
* `wd_blocks.lua` (all 3362 blocks) + `wd_cfg.json` (leaf -> state
  targets -> successor leaves = the program CFG); `--leaf N` prints one
  block; `rt_names.build_final_array` factored out and reused.

Real sample: leaves=3362 ; rendered=3362 (100%) ; m-subs=10391 ;
names=8231.  The program READS: entry block creates a closure named
"hYw2ScQoIE2gA" (`W[K] = Q` name-store init), blocks load API names into
`W[S[k]]` (e.g. `Q, l = h, "WaitForChild"` -> `W[S[1]] = Q`),
`InvokeServer`/`Colorpicker`/`BuildConfigSection` appear as literals at
their call sites.

Cosmetic fix shipped: dispatch_map leaf `rhs`/pred `path` texts were cut
from folded text with absolute offsets (mixed coordinate systems) -- now
sliced from the raw source and re-folded (`fold_render`), so
`wd_dispatch.json` texts are honest (tree numbers unchanged).

`block_lift --test` is 6/6 (fold_render; m() substitution; index/call
chain; multi-assign; table constructor; m() miss kept verbatim).
opmap STEP 29 added.

## Coverage panel (slice 2d-1, `deobfuscator/coverage_panel.py`)

One command, LIVE instant metrics only (no sandbox tracing; formulas
printed next to every value):

* Luraph v14.6 -- 97.4%: dispatch interval union 157 leaves over
  [0..2^30] = 100%; known-opcode lift 2925 instrs with 151 honest
  fallbacks = 94.8% (built-in frames dump).
* MoonSec v3 -- 80.2%: stream 6843/6843 = 100%; protos 14/14 = 100%;
  non-dead 516 slots (12 dead) = 97.7%; branch sites structured
  16/69 = 23.2% (the honest goto-fallback share from 2b-12).
* WeAreDevs v1.0.0 -- 100.0%: array 8233/8233; m() sites 10391/10391;
  blocks 3362/3362; transitions 4020/4020 in-range.
* MoonVeil 2.0.24 -- n/a (trace-based, sandbox-minutes; static anchors
  listed: bootstrap decoder, 132 opcode words, rhythm cut).

Overall (three families with live metrics): **92.5%** vs recorded
baseline ~15% (Sprint 6 audit in the backlog).  Output: `coverage.md`
markdown panel + `coverage.json`.  Family coverage = mean of its pct
metrics; overall = mean over families with live data.  `--test` is 6/6
(aggregation over pct-only; all-info family -> None; md rows + n/a;
overall math; providers present; MoonVeil honest n/a).  opmap STEP 30.

## WeAreDevs CFG lift (slice 2c-4, `wearedevs/cfg_lift.py`)

Joins blocks through the control-flow graph: the transition assignment
(last plain-Q) becomes CONTROL, the rest stays as body.  The obfuscator
builds conditions THROUGH TEMPS (`L=6798405 l=1048603 Q=l and L; Q=Q or l`),
so transition extraction runs a version-correct sequential dataflow
substitution (env per statement; reads capture values at read time;
budget-capped) and unwraps `cond and TRUE or FALSE` from the substituted
value.  Emitter: straight runs collapse into regions; cond renders
`if <cond> then <true chain> else <false chain> end` (depth-limited);
multi-pred blocks get labels; cycles = back-gotos; equal cond targets
degenerate to straight.

Real-sample findings:

* entry closure flow: 3362 blocks -> 75 regions, 33 ifs, 32 labels,
  32 gotos (vs 4020 raw transitions); conditions read like program logic
  (`if W[K] ~= "hYw2ScQoIE2gA" then` -- the closure-registration check).
* the 656 "indirect" leaves are DECOY TRAPS: `Q = V[m(...)]` reads a
  GLOBAL (wrapper V = getfenv()) into the state var -- a table state
  would crash the number-comparison tree on entry; only 2 are reachable.
* ~513 leaves have zero predecessors (more decoys); the tree is SHARED
  by all closures -- every closure enters the dispatcher at its own
  state (maker call `C(x, L)`), so the other islands are other closures
  -> mapping closure entry states is the 2c-5 slice.

Output: `wd_flow.lua` (joined control flow) + `wd_flow.json` (stats).
`--test` is 8/8 (chain join; if/else; join labels; indirect marker;
cycle back-goto; equal targets; temp bool-build; version-correct
dataflow).  opmap STEP 31.  Also fixed: `not` rendering lost its operand
(ternary precedence) in block_lift.render_expr.

## WeAreDevs closure map (slice 2c-5, `wearedevs/closures.py`)

The dispatch tree is SHARED by all closures; creations are direct maker
calls `maker(STATE, {upvalues})` inside leaf bodies (494 in-tree) plus
the tail main `B(4635360,{})`:

* collected: **494 creations -> 495 closures (incl. main)**; per-closure
  BFS (fresh visited per root) PARTITIONS the tree: total regions
  3355 / 3362 leaves (99.8%; the 7 left = decoy islands);
* inventory: main=75 regions; the biggest closure is 99 regions (state
  4121693 -- larger than main), then 73/47/45/42/40/38/38/36...;
  395 closures are tiny (<10 regions -- getters/setters/wrappers);
  size histogram: <10:395, 10-19:55, 20-29:25, 30-39:13, 40-49:4,
  70-79:2, 90-99:1;
* this is the FUNCTION INVENTORY of the original (Roblox GUI-lib)
  program recovered purely statically -- call-graph skeleton complete
  (names of closures = future slice: registration writes W[id]=name).

Output: `wd_closures.json` (state -> maker/def_leaf/entry_leaf/regions/
bodies/ifs/gotos).  `--test` is 6/6 (creation collection; non-maker
ignored; non-const state ignored; varargs B; island BFS sizes; re-run
stability).  opmap STEP 32.

## Bot integration (slice 2e-1, `bot/sprint7.py`)

The three sprint-7 tools are now Discord slash commands.  Zero touch on
the existing 7 bot commands: a NEW module `bot/sprint7.py` registers
them; `bot/bot.py` gets exactly two lines appended at the end
(`from bot.sprint7 import register_sprint7` + call with `globals()`) so
the new commands reuse the bot's own access control, embed helpers,
colors and file-size limits.

* `/moonsec file [struct]` -- MoonSec V3 -> readable `.lua` back in the
  channel (stats embed: blob/seed/consume, protos/slots/macros/dead,
  structured counts); falls back to an honest error embed if the file is
  not MoonSec V3 (the chain refuses, nothing guessed);
* `/wdmap file` -- WeAreDevs closure map (creations/closures, tree
  partition %, top-8 sizes) + `wd_closures.json` attachment;
* `/coverage` -- the live coverage panel: overall embed (92.5% vs
  baseline 15%) + `coverage.md` attachment.

Heavy work runs in the executor (timeouts 120-300 s; real samples need
0.1 s / 10 s / 18 s).  Head-less core is discord-free and self-tested:
`py -m bot.sprint7 --test` = 3/3 (moonsec core on the real sample;
coverage overall 92.5%; wdmap 495 closures / 99.8% partition).
opmap STEP 33.

## Sandbox correctness fix (this sprint)

Closures previously captured `dict(env)` copies: upvalue writes from inner
functions were silently lost.  Now `LuaFunction.closure` holds the live
enclosing env and `_FuncEnv` implements parent-chain reads + write-through
assignments (real Lua upvalue semantics).  Regression: all Luraph and Sprint 7
self-tests green.

## Runner

`opmap.ps1` steps 1-33 (seconds each on user machine): Luraph pipeline (1-4),
dynamic_decrypt (5), moonsec string_harvest (6), moonveil vm_trace/vm_state/
stream_assemble/vm_phase/vm_tables/vm_lift (7-12), wearedevs array_trace (13),
sprint7 round-trip (14), moonsec mirror (15), wearedevs array_mirror (16),
moonveil opcode_semantics (17), moonsec vm_model (18), moonsec proto_decode
(19), moonsec msvm_opcodes (20), moonsec msvm_lift (21), moonsec
msvm_dispatch (22), moonsec msvm_semantics (23), moonsec msvm_decomp (24),
moonsec decompile (25), moonsec msvm_struct (26), wearedevs dispatch_map
(27), wearedevs rt_names (28), wearedevs block_lift (29), coverage panel
(30), wearedevs cfg_lift (31), wearedevs closures (32), bot sprint7 core
(33).
