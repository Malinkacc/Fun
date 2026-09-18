#!/usr/bin/env node
/**
 * extract.mjs — statically extract + decrypt + parse the bytecode blob embedded
 * in nzl2_vm.lua (custom Luau-style VM, "W4" format).
 *
 * Pipeline:
 *   1. Locate `r1(<blob>, H4({...}))` call near EOF. The obfuscator corrupted the
 *      tail: the `",` separator between the blob literal and the H4({...}) key
 *      call was lost, so the blob string swallowed " H4({" and closed on the
 *      first key fragment's opening quote. We reconstruct all pieces.
 *   2. Decode Lua string escapes (greedy \ddd max 3 decimal digits, \\, \", \n, ...).
 *   3. Layer 1: block permutation (Lua-exact index translation, see decryptLayer1).
 *      Layer 2: position XOR with (i-1+225)%256.
 *   4. t1(y, key) is UNDEFINED in the file (obfuscator bug). Try candidates:
 *      identity / repeating-key XOR / RC4 / keyed-position XOR.
 *   5. Parse the W4 proto tree (little-endian) and dump bytecode.json.
 *
 * Run: node extract.mjs
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SRC = path.join(__dirname, 'nzl2_vm.lua');
const OUT = path.join(__dirname, 'bytecode.json');

const Q = String.fromCharCode(34); // "
const err = (m) => console.error(m);

/* ------------------------------------------------------------------ */
/* Lua string literal decoding                                         */
/* ------------------------------------------------------------------ */
const SINGLE = { '\\': 92, '"': 34, "'": 39, n: 10, t: 9, r: 13, a: 7, b: 8, f: 12, v: 11 };

function decodeLuaString(body) {
  const out = [];
  let i = 0;
  while (i < body.length) {
    const ch = body[i];
    if (ch === '\\') {
      const nx = body[i + 1];
      if (nx === undefined) throw new Error('trailing backslash in literal');
      if (nx >= '0' && nx <= '9') {
        // \ddd — greedy, max 3 decimal digits (e.g. \019\025b -> 19,25,'b')
        let d = '', k = i + 1;
        while (k < body.length && d.length < 3 && body[k] >= '0' && body[k] <= '9') { d += body[k]; k++; }
        out.push(parseInt(d, 10) & 0xff);
        i = k;
      } else if (nx in SINGLE) {
        out.push(SINGLE[nx]); i += 2;
      } else {
        out.push(nx.charCodeAt(0) & 0xff); i += 2;
      }
    } else {
      out.push(ch.charCodeAt(0) & 0xff); i++;
    }
  }
  return Buffer.from(out);
}

/* ------------------------------------------------------------------ */
/* Step 1: locate the r1(...) call and reconstruct blob + key          */
/* ------------------------------------------------------------------ */
const src = fs.readFileSync(SRC, 'latin1');

const callAnchor = src.indexOf('protectedFn=r1(');
if (callAnchor < 0) throw new Error('call site protectedFn=r1( not found');
const openQuote = callAnchor + 'protectedFn=r1('.length; // index of the opening "
if (src[openQuote] !== Q) throw new Error('unexpected char after r1( : ' + JSON.stringify(src[openQuote]));

// Lex the first (blob) string literal: body runs until a quote not preceded by
// an escaping backslash. Escape-aware scan: a backslash always escapes the
// next char (handles \" and \\ correctly: after \\ the quote is a real closer).
let j = openQuote + 1;
while (j < src.length) {
  if (src[j] === '\\') { j += 2; continue; }
  if (src[j] === Q) break;
  j++;
}
const blobClose = j;                       // premature closing quote (corruption artifact)
const blobBodyAsWritten = src.slice(openQuote + 1, blobClose);

// The tail after the premature close, up to the final '})' + ')protectedFn()'.
const endAnchor = src.lastIndexOf('))protectedFn()');
if (endAnchor < 0) throw new Error('tail anchor ))protectedFn() not found');
// text present: f1","f2","f3","f4"}   (the '}' closes the lost H4({ table;
// the final '"' closes fragment 4 — the blob swallowed fragment 1's opener)
const tailText = src.slice(blobClose + 1, endAnchor);
const tailInner = tailText.replace(/"\}\s*$/, '').replace(/\}\s*$/, '');
const fragBodies = tailInner.split('","');
if (fragBodies.length < 2) throw new Error('key fragments not found in tail');
const key = Buffer.concat(fragBodies.map(decodeLuaString));

// Blob variants:
//  A      as-written literal body (its last 5 chars are the swallowed " H4({" source code)
//  A-trim as-written minus the swallowed " H4({"  == the intended blob (preferred)
//  B      full span to the last quote in the file, unescaped quotes stripped
const SWALLOWED = ' H4({';
let variantA = decodeLuaString(blobBodyAsWritten);
let variantATrim;
if (blobBodyAsWritten.endsWith(SWALLOWED)) {
  variantATrim = decodeLuaString(blobBodyAsWritten.slice(0, blobBodyAsWritten.length - SWALLOWED.length));
} else {
  variantATrim = variantA; // swallow marker not found; trim nothing
}
// Variant B: from content start to the last quote in the file, strip unescaped quotes.
const lastQuote = src.lastIndexOf(Q);
function stripUnescapedQuotes(span) {
  let out = '';
  for (let i = 0; i < span.length; i++) {
    if (span[i] === Q && (i === 0 || span[i - 1] !== '\\')) continue;
    out += span[i];
  }
  return out;
}
const variantB = decodeLuaString(stripUnescapedQuotes(src.slice(openQuote + 1, lastQuote)));

/* ------------------------------------------------------------------ */
/* Permutation table (extracted from q1's Lua array literal)           */
/* ------------------------------------------------------------------ */
const permMatch = src.match(/\{17,73,104,209,(?:\d+,)*\d+\}/);
if (!permMatch) throw new Error('permutation table literal not found');
const PERM = permMatch[0].slice(1, -1).split(',').map(Number); // 0-based JS; Lua I4[V4+1] == PERM[V4]
if (PERM.length !== 256 || new Set(PERM).size !== 256) throw new Error('bad permutation table');

/* ------------------------------------------------------------------ */
/* Step 2: decrypt                                                     */
/* ------------------------------------------------------------------ */
// Lua-exact translation of q1:
//   n4 = BE32(A4[1..4]); r4 = A4:sub(5)
//   for i1=1..n4: z=floor((i1-1)/256); V=(i1-1)%256; j1=z*256+I4[V+1]+1 (1-based into r4)
//     C1[i1] = r4:byte(j1)
// 0-based JS: C[i0] = buf[4 + (i0/256|0)*256 + PERM[i0%256]]
// 'task' = the alternative formula given in the task text (C[i]=blob[j+4], off by one
//          vs the Lua source — tested to rule out a transcription ambiguity).
// 'inv'  = inverse direction (out[z*256+PERM[V]] = in[z*256+V]) in case q1's loop
//          direction was mangled by the obfuscator.
function decryptLayer1(buf, n4, mode = 'lua') {
  const N = Math.min(n4, buf.length - 4);
  const C = Buffer.alloc(N);
  let oob = 0;
  if (mode === 'inv') {
    for (let V = 0; V < N; V++) {
      const z = Math.floor(V / 256), v = V % 256;
      const outIdx = z * 256 + PERM[v];
      const inIdx = 4 + V;
      if (outIdx < N && inIdx < buf.length) C[outIdx] = buf[inIdx];
      else oob++;
    }
    return { C, oob };
  }
  const shift = mode === 'task' ? 5 : 4;
  for (let i0 = 0; i0 < N; i0++) {
    const z = Math.floor(i0 / 256), V = i0 % 256;
    const idx = shift + z * 256 + PERM[V];
    if (idx < buf.length) C[i0] = buf[idx];
    else oob++; // source byte was truncated away; stays 0
  }
  return { C, oob };
}
function decryptLayer2(C) {
  const y = Buffer.alloc(C.length);
  for (let i = 0; i < C.length; i++) y[i] = C[i] ^ ((i + 225) & 0xff);
  return y;
}

// t1 candidates for the undefined t1(y1, q4):
function rc4(key, data) {
  const S = Array.from({ length: 256 }, (_, i) => i);
  let jx = 0;
  for (let i = 0; i < 256; i++) { jx = (jx + S[i] + key[i % key.length]) & 0xff; [S[i], S[jx]] = [S[jx], S[i]]; }
  const out = Buffer.alloc(data.length);
  let i = 0; jx = 0;
  for (let n = 0; n < data.length; n++) {
    i = (i + 1) & 0xff; jx = (jx + S[i]) & 0xff;
    [S[i], S[jx]] = [S[jx], S[i]];
    out[n] = data[n] ^ S[(S[i] + S[jx]) & 0xff];
  }
  return out;
}
const T1_CANDIDATES = [
  { name: 'identity', fn: (y) => y },
  { name: 'repeating-key-xor', fn: (y) => Buffer.from(y).map((b, i) => b ^ key[i % key.length]) },
  { name: 'repeating-key-add', fn: (y) => Buffer.from(y).map((b, i) => (b + key[i % key.length]) & 0xff) },
  { name: 'repeating-key-sub', fn: (y) => Buffer.from(y).map((b, i) => (b - key[i % key.length]) & 0xff) },
  { name: 'rc4', fn: (y) => rc4(key, y) },
  { name: 'keyed-position-xor', fn: (y) => Buffer.from(y).map((b, i) => b ^ ((key[i % key.length] + i) & 0xff)) },
];

/* ------------------------------------------------------------------ */
/* Step 3: W4 bytecode parser (little-endian)                          */
/* ------------------------------------------------------------------ */
class ParseError extends Error {}

class Reader {
  constructor(buf) { this.buf = buf; this.pos = 0; }
  get remaining() { return this.buf.length - this.pos; }
  need(n, what) { if (this.pos + n > this.buf.length) throw new ParseError(`overrun reading ${what} at offset ${this.pos} (need ${n}, have ${this.remaining})`); }
  u8(what) { this.need(1, what); return this.buf[this.pos++]; }
  u32(what) { this.need(4, what); const b = this.buf; const p = this.pos; this.pos += 4; return b[p] + b[p + 1] * 256 + b[p + 2] * 65536 + b[p + 3] * 16777216; }
  i32(what) { let v = this.u32(what); if (v >= 2147483648) v -= 4294967296; return v; }
  raw(n, what) { this.need(n, what); const s = this.buf.subarray(this.pos, this.pos + n); this.pos += n; return s; }
  // C4 custom double decoder (== little-endian IEEE754, implemented per spec)
  dbl() {
    this.need(8, 'double');
    const b = this.buf, p = this.pos; this.pos += 8;
    const b0 = b[p], b1 = b[p + 1], b2 = b[p + 2], b3 = b[p + 3], b4 = b[p + 4], b5 = b[p + 5], b6 = b[p + 6];
    let b7 = b[p + 7];
    const sign = b7 >= 128 ? -1 : 1;
    if (b7 >= 128) b7 -= 128;
    const x2 = b7 * 16 + Math.floor(b6 / 16);
    const u2 = (b6 % 16) * 281474976710656 + b5 * 1099511627776 + b4 * 4294967296 + b3 * 16777216 + b2 * 65536 + b1 * 256 + b0;
    if (x2 === 0) return u2 === 0 ? 0 : sign * u2 * Math.pow(2, -1074);
    if (x2 === 2047) return u2 === 0 ? sign * Infinity : NaN;
    return sign * (1 + u2 / 4503599627370496) * Math.pow(2, x2 - 1023);
  }
}

function parseProto(r, path) {
  const instrCount = r.u32('instrCount');       // n1.G1 (first u32; used as param count by the VM's vararg logic)
  const flagByte = r.u8('flag');
  if (flagByte > 1) throw new ParseError(`bad vararg flag ${flagByte} at ${r.pos - 1} (proto ${path})`);
  const numParams = r.u32('numParams');
  const upvalCount = r.u32('upvalCount');
  if (upvalCount > 200) throw new ParseError(`absurd upvalCount ${upvalCount} (proto ${path})`);
  const upvalues = [];
  for (let i = 0; i < upvalCount; i++) {
    const f = r.u8('upval flag');
    upvalues.push({ inStack: f !== 0, idx: r.u32('upval idx') });
  }
  const constCount = r.u32('constCount');
  if (constCount > 100000) throw new ParseError(`absurd constCount ${constCount} (proto ${path})`);
  const constants = [];
  for (let i = 0; i < constCount; i++) {
    const t = r.u8('const type');
    if (t === 0) constants.push({ type: 'nil', value: null });
    else if (t === 1) constants.push({ type: 'bool', value: r.u8('bool') !== 0 });
    else if (t === 2) constants.push({ type: 'double', value: r.dbl() });
    else if (t === 3) { const len = r.u32('str len'); if (len > r.remaining) throw new ParseError(`string const len ${len} exceeds remaining at ${r.pos} (proto ${path})`); constants.push({ type: 'string', value: r.raw(len, 'str bytes') }); }
    else if (t === 4) constants.push({ type: 'protoRef', value: r.u32('protoRef') });
    else throw new ParseError(`unknown const type ${t} at ${r.pos - 1} (proto ${path})`);
  }
  const instrCount2 = r.u32('instrCount2');
  if (instrCount2 > 200000) throw new ParseError(`absurd instrCount2 ${instrCount2} (proto ${path})`);
  const instructions = [];
  for (let i = 0; i < instrCount2; i++) {
    r.need(8, 'instruction');
    const P2 = r.buf[r.pos], J4 = r.buf[r.pos + 1], T4 = r.buf[r.pos + 2], l4 = r.buf[r.pos + 3];
    r.pos += 4;
    const operand = r.i32('operand');
    instructions.push({ op: P2, A: J4, B: T4, C: l4, operand });
  }
  const childCount = r.u32('childCount');
  if (childCount > 10000) throw new ParseError(`absurd childCount ${childCount} (proto ${path})`);
  const children = [];
  for (let i = 0; i < childCount; i++) children.push(parseProto(r, `${path}.${i}`));
  return { path, instrCount, flag: flagByte !== 0, numParams, upvalues, constCount, constants, instrCount2, instructions, childCount, children };
}

/* ------------------------------------------------------------------ */
/* JSON serialization helpers                                          */
/* ------------------------------------------------------------------ */
function stringToJSON(b) {
  try {
    const t = new TextDecoder('utf-8', { fatal: true }).decode(b);
    return t;
  } catch {
    return b.toString('latin1').replace(/[^\x20-\x7e]/g, (c) => '\\x' + c.charCodeAt(0).toString(16).padStart(2, '0'));
  }
}
function constToJSON(c) {
  if (c.type === 'string') return { type: 'string', value: stringToJSON(c.value) };
  return c;
}
function protoToJSON(p) {
  return {
    path: p.path,
    stats: {
      instructionCount: p.instructions.length,
      constantCount: p.constants.length,
      childrenCount: p.children.length,
      numParams: p.numParams,
      vararg: p.flag,
      headerInstrCount: p.instrCount,
    },
    upvalues: p.upvalues,
    first10Constants: p.constants.slice(0, 10).map(constToJSON),
    instructions: p.instructions,
    children: p.children.map(protoToJSON),
  };
}

/* ------------------------------------------------------------------ */
/* Parser self-test: serialize a synthetic proto in W4 format and      */
/* round-trip it, to prove the parser matches the spec.                */
/* ------------------------------------------------------------------ */
function u32le(v) { const b = Buffer.alloc(4); b.writeUInt32LE(v >>> 0, 0); return b; }
function i32le(v) { const b = Buffer.alloc(4); b.writeInt32LE(v | 0, 0); return b; }
function serializeProto(p) {
  const parts = [];
  parts.push(u32le(p.instrCount), Buffer.from([p.flag ? 1 : 0]), u32le(p.numParams), u32le(p.upvalues.length));
  for (const u of p.upvalues) parts.push(Buffer.from([u.inStack ? 1 : 0]), u32le(u.idx));
  parts.push(u32le(p.constants.length));
  for (const c of p.constants) {
    if (c.type === 'nil') parts.push(Buffer.from([0]));
    else if (c.type === 'bool') parts.push(Buffer.from([1, c.value ? 1 : 0]));
    else if (c.type === 'double') { const b = Buffer.alloc(9); b[0] = 2; b.writeDoubleLE(c.value, 1); parts.push(b); }
    else if (c.type === 'string') { parts.push(Buffer.from([3]), u32le(c.value.length), Buffer.from(c.value, 'latin1')); }
    else if (c.type === 'protoRef') parts.push(Buffer.from([4]), u32le(c.value));
  }
  parts.push(u32le(p.instructions.length));
  for (const i of p.instructions) parts.push(Buffer.from([i.op, i.A, i.B, i.C]), i32le(i.operand));
  parts.push(u32le(p.children.length));
  for (const ch of p.children) parts.push(serializeProto(ch));
  return Buffer.concat(parts);
}
function selfTest() {
  const synth = {
    instrCount: 7, flag: true, numParams: 3,
    upvalues: [{ inStack: true, idx: 0 }, { inStack: false, idx: 2 }],
    constants: [
      { type: 'nil', value: null },
      { type: 'bool', value: true },
      { type: 'double', value: -1234.5 },
      { type: 'string', value: 'helloWORLD' },
      { type: 'protoRef', value: 4 },
    ],
    instructions: [{ op: 31, A: 1, B: 0, C: 0, operand: -3 }, { op: 216, A: 0, B: 0, C: 0, operand: 77 }],
    children: [{ instrCount: 1, flag: false, numParams: 0, upvalues: [], constants: [{ type: 'double', value: 0.125 }], instructions: [{ op: 245, A: 2, B: 0, C: 0, operand: 0 }], children: [] }],
  };
  const bin = serializeProto(synth);
  const r = new Reader(bin);
  const back = parseProto(r, 'T');
  const ok = r.pos === bin.length
    && back.instrCount === 7 && back.flag === true && back.numParams === 3
    && back.upvalues.length === 2 && back.upvalues[1].idx === 2
    && back.constants[2].value === -1234.5 && back.constants[3].value.toString() === 'helloWORLD'
    && back.constants[4].value === 4
    && back.instructions[0].operand === -3
    && back.children.length === 1 && back.children[0].constants[0].value === 0.125;
  console.log(`parser self-test: ${ok ? 'PASS (round-trip exact, consumed ' + r.pos + '/' + bin.length + ' bytes)' : 'FAIL'}`);
  if (!ok) process.exit(1);
}
if (process.argv.includes('--selftest')) { selfTest(); process.exit(0); }

/* ------------------------------------------------------------------ */
/* Stats + notable strings                                             */
/* ------------------------------------------------------------------ */
function walkStats(p, acc) {
  acc.protos++; acc.instructions += p.instructions.length; acc.constants += p.constants.length;
  acc.upvalues += p.upvalues.length;
  p.constants.forEach((c, i) => { if (c.type === 'string') acc.stringList.push({ proto: p.path, constIdx: i, value: c.value }); });
  p.children.forEach((c) => walkStats(c, acc));
}
function printable(b) {
  const t = b.toString('latin1');
  return t.length >= 3 && [...t].every((ch) => ch >= ' ' && ch <= '~');
}

/* ------------------------------------------------------------------ */
/* Main                                                                */
/* ------------------------------------------------------------------ */
function hex(b, n) { return b.subarray(0, n).toString('hex').match(/../g).join(' '); }

// entropy / structure analysis for documentation
function analyze(t) {
  const freq = new Array(256).fill(0);
  for (const b of t) freq[b]++;
  let H = 0;
  for (const f of freq) if (f) { const p = f / t.length; H -= p * Math.log2(p); }
  const ascii = [...t].filter((b) => b >= 0x20 && b <= 0x7e).length / t.length;
  let run = 0, best = 0, bestAt = 0;
  for (let i = 0; i < t.length; i++) {
    const ok = t[i] >= 0x20 && t[i] <= 0x7e;
    if (ok) { run++; if (run > best) { best = run; bestAt = i - run + 1; } } else run = 0;
  }
  const zeros = freq[0];
  return {
    entropyBitsPerByte: +H.toFixed(3),
    asciiFraction: +ascii.toFixed(4),
    longestAsciiRun: best,
    longestAsciiRunAt: bestAt,
    zeroBytes: zeros,
    sample: t.subarray(bestAt, Math.min(bestAt + best, bestAt + 60)).toString('latin1'),
  };
}

function tryVariant(name, buf) {
  const n4 = buf[0] * 16777216 + buf[1] * 65536 + buf[2] * 256 + buf[3];
  err(`\n=== variant ${name}: ${buf.length} bytes, declared n4=${n4}, payload=${buf.length - 4}, fits=${n4 <= buf.length - 4} ===`);
  const results = [];
  for (const mode of ['lua', 'task', 'inv']) {
    const { C, oob } = decryptLayer1(buf, n4, mode);
    const y = decryptLayer2(C);
    if (mode === 'lua') {
      if (oob) err(`  layer1(${mode}): ${oob} output bytes had no source (truncated blob), filled 0`);
      err(`  after layer1 : ${hex(C, 64)}`);
      err(`  after layer2 : ${hex(y, 64)}`);
    } else {
      err(`  layer1(${mode}): oob=${oob}, after layer2: ${hex(y, 16)}`);
    }
    for (const cand of T1_CANDIDATES) {
      if (mode !== 'lua' && cand.name !== 'identity') continue; // ambiguity check only
      const t = cand.fn(y);
      if (mode === 'lua') err(`  t1=${cand.name}: ${hex(t, 96)}`);
      // Run the FULL parser regardless of header plausibility (the pre-filter is only
      // advisory); bound checks inside reject garbage quickly.
      const first = t[0] + t[1] * 256 + t[2] * 65536 + t[3] * 16777216;
      try {
        const r = new Reader(t);
        const parse = parseProto(r, '0');
        results.push({ mode, cand, parse, consumed: r.pos, avail: t.length });
        err(`  [${mode}/${cand.name}] PARSED full tree ${r.pos}/${t.length} bytes (first u32 = ${first})`);
      } catch (e) {
        err(`  [${mode}/${cand.name}] parse failed (first u32 = ${first}, flag = ${t[4]}): ${e.message}`);
      }
    }
  }
  return { n4, results };
}

const variantRuns = [
  ['A-trim (intended blob)', variantATrim],
  ['B (span-to-last-quote)', variantB],
  ['A (as-written)', variantA],
];

selfTest(); // validate the W4 parser against a synthetic round-trip before trusting it

let winner = null;
for (const [name, buf] of variantRuns) {
  const run = tryVariant(name, buf);
  // a winner parses the full tree and consumes (nearly) all available bytes
  const ok = run.results.find((rr) => rr.consumed <= rr.avail && rr.consumed >= rr.avail - 8);
  if (ok) { winner = { name, buf, run, ok }; break; }
  const anyParse = run.results.find((rr) => rr.parse);
  if (anyParse && !winner) winner = { name, buf, run, ok: anyParse, partial: true };
}

console.log('================ REPORT ================');
console.log(`source literal: body ${blobBodyAsWritten.length} chars @${openQuote + 1}..${blobClose - 1}`);
console.log(`key fragments (${fragBodies.length}): ${fragBodies.map((f) => JSON.stringify(f)).join(', ')}`);
console.log(`key (${key.length} bytes): ${key.toString('hex').match(/../g).join(' ')}`);

if (!winner || !winner.ok) {
  // Documented failure: dump analysis of the best-decrypted prefix we can produce
  // (layer1+layer2, identity t1) and write an evidence JSON instead of a proto tree.
  const n4 = variantATrim[0] * 16777216 + variantATrim[1] * 65536 + variantATrim[2] * 256 + variantATrim[3];
  const { C, oob } = decryptLayer1(variantATrim, n4, 'lua');
  const y = decryptLayer2(C);
  const stats = analyze(y);
  console.log('\n--- failure documentation (variant A-trim, identity t1) ---');
  console.log(`declared n4 = ${n4}, available payload = ${variantATrim.length - 4} bytes (${((variantATrim.length - 4) / n4 * 100).toFixed(1)}% of declared)`);
  console.log(`layer1 OOB reads (truncated source): ${oob}`);
  console.log(`decrypted-prefix analysis: ${JSON.stringify(stats)}`);
  const doc = {
    status: 'parse_failed',
    reason: 'no t1 candidate (identity / repeating-key xor/add/sub / RC4 / keyed-position-xor) yields a parseable W4 proto tree; blob is a truncated prefix of its declared length',
    source: 'nzl2_vm.lua',
    blobLiteral: { openQuote, blobClose, bodyChars: blobBodyAsWritten.length },
    declaredPayloadLength: n4,
    variants: {
      'A-trim (intended blob, tail " H4({" swallowed)': variantATrim.length,
      'A (as-written)': variantA.length,
      'B (span to last quote, unescaped quotes stripped)': variantB.length,
    },
    keyHex: key.toString('hex'),
    keyFragmentsLua: fragBodies,
    permutationTable: PERM,
    layer1AfterHex64: C.subarray(0, 64).toString('hex'),
    layer2AfterHex64: y.subarray(0, 64).toString('hex'),
    layer2Analysis: stats,
    t1CandidatesTried: T1_CANDIDATES.map((c) => c.name),
    w4Format: {
      proto: 'u32 instrCount, u8 flag, u32 numParams, u32 upvalCount, upvals{u8 flag,u32 idx}, u32 constCount, consts{type u8: 0 nil/1 bool/2 double(C4)/3 string(u32 len+bytes)/4 protoRef(u32)}, u32 instrCount2, instrs{op,A,B,C u8 + s32 LE operand}, u32 childCount, children[]',
    },
  };
  fs.writeFileSync(OUT, JSON.stringify(doc, null, 1));
  console.log(`wrote evidence JSON to ${OUT}`);
  console.log('identity-t1 worked: NO (no candidate did)');
  process.exit(2);
}

const { name, run, ok } = winner;
console.log(`winning variant: ${name}`);
console.log(`t1 variant: ${ok.cand.name}${winner.partial ? ' (partial consumption — see anomalies)' : ''}`);
console.log(`declared n4: ${run.n4} | blob bytes: ${winner.buf.length} | payload: ${winner.buf.length - 4}`);
console.log(`parse: SUCCESS — consumed ${ok.consumed} of ${ok.avail} decrypted bytes (${ok.avail - ok.consumed} left)`);

const acc = { protos: 0, instructions: 0, constants: 0, upvalues: 0, stringList: [] };
walkStats(ok.parse, acc);
console.log(`total protos: ${acc.protos} | instructions: ${acc.instructions} | constants: ${acc.constants} | upvalues: ${acc.upvalues} | string constants: ${acc.stringList.length}`);

// notable strings: printable, len>=4, deduped
const seen = new Set();
const notable = [];
for (const s of acc.stringList) {
  if (!printable(s.value) || s.value.length < 3) continue;
  const t = s.value.toString('latin1');
  if (seen.has(t)) continue;
  seen.add(t);
  notable.push({ proto: s.proto, constIdx: s.constIdx, value: t });
}
console.log(`\nnotable (printable, deduped) string constants: ${notable.length}`);
for (const n of notable.slice(0, 120)) console.log(`  [${n.proto} k${n.constIdx}] ${JSON.stringify(n.value)}`);
if (notable.length > 120) console.log(`  ... and ${notable.length - 120} more`);

fs.writeFileSync(OUT, JSON.stringify(protoToJSON(ok.parse), null, 1));
console.log(`\nwrote ${OUT} (${fs.statSync(OUT).size} bytes)`);
console.log('identity-t1 worked: ' + (ok.cand.name === 'identity' ? 'YES' : 'NO — used ' + ok.cand.name));
