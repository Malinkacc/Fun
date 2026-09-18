// Synthetic round-trip self-test for disasm.mjs: build a small proto tree,
// write it as bytecode.json format, run the disassembler on it.
import fs from 'fs';
import { execSync } from 'child_process';

const synth = {
  instructions: [
    { op: 31, a: 0, b: 0, c: 0, sbx: 0 },   // LOADK
    { op: 100, a: 1, b: 0, c: 2, sbx: 0 },  // ADD
    { op: 216, a: 0, b: 0, c: 0, sbx: 5 },  // JMP fwd
    { op: 61, a: 3, b: 0, c: 0, sbx: 2 },   // TESTT
    { op: 138, a: 0, b: 2, c: 0, sbx: 0 },  // RETURN
  ],
  numParams: 2,
  vararg: false,
  upvalues: [{ fromStack: true, index: 0 }],
  constants: [{ str: 'game:GetService("Players")' }, { num: 3.14 }, { bool: true }, null, { protoIdx: 0 }],
  children: [{
    instructions: [{ op: 188, a: 0, b: 2, c: 0, sbx: 0 }],
    numParams: 1, vararg: true, upvalues: [{ fromStack: false, index: 1 }],
    constants: [{ str: 'child proto const' }], children: [],
  }],
};
fs.writeFileSync('_synth_bytecode.json', JSON.stringify(synth));
execSync('node disasm.mjs _synth_bytecode.json _synth_disasm.txt');
const txt = fs.readFileSync('_synth_disasm.txt', 'utf8');
console.log(txt.split('\n').slice(0, 22).join('\n'));
const need = ['LOADK', 'ADD', 'JMP', 'TESTT', 'RETURN', 'CALL', 'PROTO main.0', 'const[0]'];
const missing = need.filter(n => !txt.includes(n));
console.log(missing.length ? 'MISSING: ' + missing.join(',') : 'SELF-TEST OK: all expected mnemonics present');
