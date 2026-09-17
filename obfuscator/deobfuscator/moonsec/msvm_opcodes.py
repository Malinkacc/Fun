"""MoonSec V3 proto-opcode profiler (Sprint 7, slice 2b-7).

Slice 2b-6 lifted the whole VM proto tree (consts + instructions + nested
protos) from the shipped blob.  This module turns that instruction array into
an EMPIRICAL operand-shape profile per opcode -- the evidence base for mapping
proto opcodes (range 1..153) to Lua 5.1 semantics in later slices.

Why empirical first: the VM interpreter `_(z,o,m)` -> `ne(...)` is a ~53 KB
obfuscated dispatch state machine, so reading 90 mnemonics off it statically is
unreliable, and dynamic tracing of the full sample is blocked by sandbox
recursion limits.  Operand shapes (how many operands an opcode carries, whether
an operand slot is filled by a constant-pool substitution, and the A-field
range) are, however, directly observable in the lifted proto and strongly
constrain each opcode's Lua 5.1 effect class.

Per-opcode profile fields:

    count   number of instructions with this opcode (whole tree)
    withB   instructions whose B slot is present (fk kind supplies B)
    withC   instructions whose C slot is present
    Bconst  B slot filled by a NON-numeric constant-pool value (str/bool/float)
    Cconst  same for C
    Amin/Amax  observed range of the A field (destination register / arg count)

Note: a substituted NUMERIC constant is an int after int_fix, so it is
indistinguishable from a raw integer operand in the lifted tree; Bconst/Cconst
therefore count only non-numeric substitutions.  withB/withC and the A range are
exact.

Usage:
    py -m obfuscator.deobfuscator.moonsec.msvm_opcodes --test
    py -m obfuscator.deobfuscator.moonsec.msvm_opcodes --protos out\\protos.json --outdir out
"""

import os
import sys
import json
import argparse
from collections import defaultdict

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)


def opcode_profile(protos):
    """Aggregate operand-shape statistics per opcode over a proto tree.

    `protos` is the list returned by proto_decode.decode_all / loaded from
    protos.json: each proto is {'instrs': [[op,A,B,C],...], 'consts': [...],
    'nested': [...], 'nparams': int}."""
    prof = defaultdict(lambda: {
        'count': 0, 'withB': 0, 'withC': 0,
        'Bconst': 0, 'Cconst': 0, 'Amin': None, 'Amax': None,
    })

    def is_const(v):
        return v is not None and not isinstance(v, int) and not isinstance(v, bool)

    def walk(p):
        for ins in p['instrs']:
            op = ins[0]
            if not isinstance(op, int):
                continue  # opcode itself was const-substituted; skip for profiling
            A, B, C = ins[1], ins[2], ins[3]
            d = prof[op]
            d['count'] += 1
            if isinstance(A, int):
                d['Amin'] = A if d['Amin'] is None else min(d['Amin'], A)
                d['Amax'] = A if d['Amax'] is None else max(d['Amax'], A)
            if B is not None:
                d['withB'] += 1
                if is_const(B):
                    d['Bconst'] += 1
            if C is not None:
                d['withC'] += 1
                if is_const(C):
                    d['Cconst'] += 1
        for q in p['nested']:
            walk(q)

    for p in protos:
        walk(p)
    return dict(prof)


def render_profile(prof, limit=25):
    """Human-readable top-N opcodes by frequency with their operand shapes."""
    lines = []
    ordered = sorted(prof.items(), key=lambda kv: (-kv[1]['count'], kv[0]))
    for op, d in ordered[:limit]:
        lines.append(
            'op %3d  x%-4d  B:%d/%d C:%d/%d  A:[%s..%s]' % (
                op, d['count'], d['Bconst'], d['withB'], d['Cconst'], d['withC'],
                d['Amin'], d['Amax']))
    return lines


def _synth_protos():
    """Tiny proto tree with known operand shapes for the self-test."""
    return [{
        'nparams': 0,
        'consts': ['s0', 5],
        'instrs': [
            [1, 0, 2, None],        # op1: raw int B
            [1, 1, 's0', None],     # op1: const-str B
            [2, 3, None, 4],        # op2: C only
            [3, 0, None, None],     # op3: no operands
        ],
        'nested': [{
            'nparams': 0, 'consts': [], 'nested': [],
            'instrs': [[1, 2, 7, None]],   # op1 in nested proto
        }],
    }]


def _selftest():
    fails = []

    def chk(tag, cond, extra=''):
        print(('[OK] ' if cond else '[XX] ') + tag + (' ' + extra if extra else ''))
        if not cond:
            fails.append(tag)

    prof = opcode_profile(_synth_protos())
    chk('T1 per-opcode counts incl. nested walk',
        prof[1]['count'] == 3 and prof[2]['count'] == 1 and prof[3]['count'] == 1,
        'op1=%d op2=%d op3=%d' % (prof[1]['count'], prof[2]['count'], prof[3]['count']))
    chk('T2 operand presence + const-substitution detection',
        prof[1]['withB'] == 3 and prof[1]['Bconst'] == 1 and prof[1]['withC'] == 0
        and prof[2]['withC'] == 1 and prof[2]['Cconst'] == 0
        and prof[3]['withB'] == 0 and prof[3]['withC'] == 0,
        'op1 B%d/Bc%d  op2 C%d  op3 B%d' % (
            prof[1]['withB'], prof[1]['Bconst'], prof[2]['withC'], prof[3]['withB']))
    chk('T3 A-field range tracking',
        prof[1]['Amin'] == 0 and prof[1]['Amax'] == 2 and prof[2]['Amin'] == 3,
        'op1 A[%s..%s] op2 A[%s..%s]' % (
            prof[1]['Amin'], prof[1]['Amax'], prof[2]['Amin'], prof[2]['Amax']))
    lines = render_profile(prof, limit=3)
    chk('T4 render_profile emits one line per opcode',
        len(lines) == 3 and lines[0].startswith('op   1'),
        'first=%r' % lines[0])

    print('')
    print('Result: %d/4' % (4 - len(fails)))
    if fails:
        print('[XX] FAILURES: %d' % len(fails))
        return 1
    print('[OK] ALL PASSED')
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description='MoonSec proto-opcode profiler')
    ap.add_argument('--test', action='store_true')
    ap.add_argument('--protos', default=None, help='protos.json from proto_decode --sample')
    ap.add_argument('--outdir', default='out')
    ap.add_argument('--show', type=int, default=25)
    a = ap.parse_args(argv)
    if a.test:
        return _selftest()
    if not a.protos:
        print('need --protos path (or --test)')
        return 2
    protos = json.load(open(a.protos, encoding='utf-8'))
    prof = opcode_profile(protos)
    print('distinct opcodes=%d total instrs=%d' % (
        len(prof), sum(d['count'] for d in prof.values())))
    print('top %d by frequency:' % a.show)
    for line in render_profile(prof, a.show):
        print('  ' + line)
    os.makedirs(a.outdir, exist_ok=True)
    p = os.path.join(a.outdir, 'opcode_profile.json')
    json.dump({str(k): v for k, v in sorted(prof.items())},
              open(p, 'w', encoding='utf-8'), indent=1)
    print('saved ->', p)
    return 0


if __name__ == '__main__':
    sys.exit(main())
