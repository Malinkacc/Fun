"""MoonSec V3 proto-tree lifter (Sprint 7, slice 2b-8).

Renders the 2b-6 lifted proto tree (protos.json) as readable pseudo-Lua:
one labelled block per function proto, its constant pool resolved to literals,
its instructions listed with resolved operands, and nested protos indented as
inner blocks.  This is the readability layer that the opcode-mnemonic mapping
(slice 2b-9) will later refine into real Lua 5.1 statements.

Honesty note on operands: after constant-pool substitution an operand is either
a substituted literal (str/bool/float), None (absent), or a raw int.  A raw int
is either a register index or an immediate/RK operand, and those two are NOT
distinguishable from the lifted tree alone (that needs per-opcode semantics).
So this lifter prints raw ints verbatim and only renders non-int operands as
literals; it does NOT guess register-vs-immediate.

Usage:
    py -m obfuscator.deobfuscator.moonsec.msvm_lift --test
    py -m obfuscator.deobfuscator.moonsec.msvm_lift --protos out\\protos.json --outdir out
"""

import os
import sys
import json
import argparse

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)


def _lit(v, maxlen=40):
    """Render a constant/operand value as a literal (or '_' when absent)."""
    if v is None:
        return '_'
    if isinstance(v, bool):
        return 'true' if v else 'false'
    if isinstance(v, bytes):
        try:
            s = v.decode('utf-8')
        except UnicodeDecodeError:
            s = repr(v)
        return _trim(repr(s), maxlen)
    if isinstance(v, dict):
        if '__bytes__' in v:
            return _trim("x'" + str(v['__bytes__']) + "'", maxlen)
        return _trim(repr(v), maxlen)
    if isinstance(v, str):
        return _trim(repr(v), maxlen)
    return str(v)


def _trim(s, maxlen):
    return s if len(s) <= maxlen else s[:maxlen - 3] + '...'


def lift_proto(proto, idx='0', depth=0):
    """Render one proto (and its nested protos) as a list of lines."""
    pad = '  ' * depth
    out = []
    out.append('%s== proto %s (nparams=%s consts=%d instrs=%d nested=%d)' % (
        pad, idx, proto.get('nparams'), len(proto['consts']),
        len(proto['instrs']), len(proto['nested'])))
    for ci, c in enumerate(proto['consts']):
        out.append('%s  const[%d] = %s' % (pad, ci, _lit(c)))
    for ii, ins in enumerate(proto['instrs']):
        op, A, B, C = ins[0], ins[1], ins[2], ins[3]
        out.append('%s  #%-4d op=%-4s A=%-4s B=%-14s C=%s' % (
            pad, ii, _lit(op), _lit(A), _lit(B), _lit(C)))
    for ni, np_ in enumerate(proto['nested']):
        out.extend(lift_proto(np_, '%s.%d' % (idx, ni), depth + 1))
    return out


def lift_all(protos):
    lines = []
    for pi, p in enumerate(protos):
        lines.extend(lift_proto(p, str(pi), 0))
    return '\n'.join(lines)


def _synth_protos():
    return [{
        'nparams': 1,
        'consts': ['hello', 42, True],
        'instrs': [
            [7, 0, 'hello', None],
            [3, 1, 2, 42],
        ],
        'nested': [{
            'nparams': 0, 'consts': [], 'nested': [],
            'instrs': [[9, 0, None, None]],
        }],
    }]


def _selftest():
    fails = []

    def chk(tag, cond, extra=''):
        print(('[OK] ' if cond else '[XX] ') + tag + (' ' + extra if extra else ''))
        if not cond:
            fails.append(tag)

    txt = lift_all(_synth_protos())
    lines = txt.splitlines()
    chk('T1 proto header line with counts',
        lines[0].startswith('== proto 0 (nparams=1 consts=3 instrs=2 nested=1)'),
        lines[0])
    chk('T2 constant pool resolved to literals',
        any("const[0] = 'hello'" in l for l in lines)
        and any('const[1] = 42' in l for l in lines)
        and any('const[2] = true' in l for l in lines),
        '')
    i0 = [l for l in lines if l.strip().startswith('#0') and 'op=7' in l]
    chk('T3 instruction line with const operand literal + absent C',
        len(i0) == 1 and "'hello'" in i0[0] and i0[0].rstrip().endswith('C=_'),
        i0[0] if i0 else 'no #0/op=7 line')
    chk('T4 nested proto indented under parent',
        any(l.startswith('  == proto 0.0') for l in lines)
        and any(l.startswith('    #') and 'op=9' in l for l in lines),
        '')

    print('')
    print('Result: %d/4' % (4 - len(fails)))
    if fails:
        print('[XX] FAILURES: %d' % len(fails))
        return 1
    print('[OK] ALL PASSED')
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description='MoonSec proto-tree lifter')
    ap.add_argument('--test', action='store_true')
    ap.add_argument('--protos', default=None)
    ap.add_argument('--outdir', default='out')
    ap.add_argument('--show', type=int, default=40)
    a = ap.parse_args(argv)
    if a.test:
        return _selftest()
    if not a.protos:
        print('need --protos path (or --test)')
        return 2
    protos = json.load(open(a.protos, encoding='utf-8'))
    txt = lift_all(protos)
    lines = txt.splitlines()
    print('lifted %d protos -> %d lines' % (len(protos), len(lines)))
    for l in lines[:a.show]:
        print(l)
    if len(lines) > a.show:
        print('  ... (%d more lines)' % (len(lines) - a.show))
    os.makedirs(a.outdir, exist_ok=True)
    p = os.path.join(a.outdir, 'lifted_msvm.txt')
    open(p, 'w', encoding='utf-8').write(txt + '\n')
    print('saved ->', p)
    return 0


if __name__ == '__main__':
    sys.exit(main())
