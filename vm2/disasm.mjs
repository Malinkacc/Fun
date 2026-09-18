// Disassembler for the NZL v2 VM bytecode.
// Input: bytecode.json (produced by extract.mjs) + opcodes.mjs (transcribed semantics).
// Output: disasm.txt — full annotated listing of every proto.
import fs from 'fs';
import { OPCODES, DEAD_OPCODES, OP_COUNT } from './opcodes.mjs';

const bc = JSON.parse(fs.readFileSync(process.argv[2] ?? 'bytecode.json', 'utf8'));
const out = [];

function esc(s) {
  return String(s).replace(/\\/g, '\\\\').replace(/"/g, '\\"').replace(/\n/g, '\\n').replace(/\r/g, '\\r').replace(/\t/g, '\\t').replace(/[^\x20-\x7e]/g, c => '\\x' + c.charCodeAt(0).toString(16).padStart(2, '0'));
}
function kstr(k) {
  if (k === null || k === undefined) return 'nil';
  if (typeof k === 'object') {
    if ('str' in k) return '"' + esc(k.str) + '"';
    if ('num' in k) return String(k.num);
    if ('bool' in k) return String(k.bool);
    if ('protoIdx' in k) return `<proto#${k.protoIdx}>`;
    return JSON.stringify(k);
  }
  return String(k);
}

let protoCounter = 0;
function disasmProto(p, depth, path) {
  const id = path;
  const ind = '  '.repeat(depth);
  out.push(`${ind}===== PROTO ${id} =====`);
  out.push(`${ind}  instructions: ${p.instructions.length}, params: ${p.numParams}, vararg: ${p.vararg}, upvalues: ${(p.upvalues ?? []).length}, constants: ${(p.constants ?? []).length}, children: ${(p.children ?? []).length}`);
  (p.upvalues ?? []).forEach((u, i) => out.push(`${ind}  upvalue[${i}]: ${u.fromStack ? 'stack' : 'parent'} #${u.index}`));
  (p.constants ?? []).forEach((k, i) => {
    const v = kstr(k);
    out.push(`${ind}  const[${i}] = ${v.length > 100 ? v.slice(0, 100) + '…(' + v.length + ')' : v}`);
  });
  const instrs = p.instructions ?? [];
  for (let i = 0; i < instrs.length; i++) {
    const ins = instrs[i];
    const op = OPCODES[ins.op];
    const name = op ? op.mnemonic : `UNKNOWN_${ins.op}`;
    const dead = op && op.dead ? '  ; DEAD' : '';
    const note = op && op.note ? '  ; ' + op.note.replace(/\s+/g, ' ').slice(0, 90) : '';
    const raw = `${ins.op},${ins.a},${ins.b},${ins.c},${ins.sbx}`;
    out.push(`${ind}  [${String(i).padStart(4)}] ${name.padEnd(12)} A=${String(ins.a).padStart(3)} B=${String(ins.b).padStart(3)} C=${String(ins.c).padStart(3)} sBx=${String(ins.sbx).padStart(6)}   ; ${op ? op.sem.replace(/\s+/g, ' ').slice(0, 80) : '???'}${dead}${note}`);
  }
  out.push('');
  (p.children ?? []).forEach((c, ci) => disasmProto(c, depth + 1, `${path}.${ci}`));
}

disasmProto(bc, 0, 'main');
const text = out.join('\n');
fs.writeFileSync(process.argv[3] ?? 'disasm.txt', text);
console.log(`disasm: ${text.split('\n').length} lines -> ${process.argv[3] ?? 'disasm.txt'}`);
console.log(`opcodes table: ${OP_COUNT} entries, ${DEAD_OPCODES.length} dead: ${DEAD_OPCODES.join(',')}`);
// quick stats: opcode histogram
const hist = {};
(function walk(p) {
  for (const ins of (p.instructions ?? [])) hist[ins.op] = (hist[ins.op] ?? 0) + 1;
  (p.children ?? []).forEach(walk);
})(bc);
const top = Object.entries(hist).sort((a, b) => b[1] - a[1]).slice(0, 15).map(([op, n]) => `${OPCODES[op]?.mnemonic ?? op}:${n}`);
console.log('opcode histogram top15:', top.join(' '));
const unknown = Object.keys(hist).filter(op => !OPCODES[op]);
if (unknown.length) console.log('UNKNOWN OPCODES IN BYTECODE:', unknown.join(','));
