"""MoonVeil 2.x VM lifter from table-I/O traces (Sprint 7, slice 3f).

Consumes the op log of vm_tables.py (slice 3e) and cuts it into VM
instructions.  The real-sample trace shows a stable per-instruction rhythm:

    g  key=['s','H']          <- instruction boundary (state/env fetch)
    g  key=<int>  val=<word>  <- bytecode word (float) from the H array
    g  k / g 2 / g k / g 3 / g 1 ...  <- keystream operand decode cycles
    s  ...                    <- register/pc writes (instruction effect)

lift_from_ops() groups at every string-key 'H' read, takes the first numeric
read as the instruction word, collects the index-1 keystream reads as decoded
operands and all writes as the instruction effect, then renders a lifted
pseudo-code listing (word + operands + writes), the same shape the Luraph
lifter produces before opcode semantics are applied.

Usage:
    py -m obfuscator.deobfuscator.moonveil.vm_lift --test
    py -m obfuscator.deobfuscator.moonveil.vm_lift --trace out\\tables.json --outdir out
    py -m obfuscator.deobfuscator.moonveil.vm_lift path\\sample.lua --max-steps 4000000 --start-step 450000 --outdir out
"""

import os
import sys
import json
import argparse

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)


def lift_from_ops(ops):
    """Cut a vm_tables op log into instruction records."""
    instrs = []
    cur = None
    for op in ops:
        step, kind, tid, key, val = op
        if kind == 'g' and key[:1] == ['s'] and key[1] == 'H':
            cur = {'step': step, 'word': None, 'operands': [], 'writes': [], 'tid': tid}
            instrs.append(cur)
            continue
        if cur is None:
            continue
        if kind == 'g':
            if cur['word'] is None and key[:1] == ['n'] and val[:1] == ['n']:
                cur['word'] = val[1]
            elif key[:1] == ['n'] and key[1] == 1:
                cur['operands'].append(val)
        else:
            cur['writes'].append([tid, key, val])
    return instrs


def render(instrs, limit=None):
    lines = []
    for i, ins in enumerate(instrs[:limit] if limit else instrs):
        ops = ', '.join('%s:%s' % (o[0], json.dumps(o[1], ensure_ascii=False)[:26])
                        for o in ins['operands'])
        wr = '; '.join('t%x[%s]=%s' % (w[0] % 0xffff, json.dumps(w[1], ensure_ascii=False)[:16],
                                       json.dumps(w[2], ensure_ascii=False)[:16])
                       for w in ins['writes'])
        lines.append('#%-5d step=%-9d word=%-10s ops=[%s] %s' %
                     (i + 1, ins['step'], ins['word'], ops, ('writes: ' + wr) if wr else ''))
    return lines


# --------------------------------------------------------------------------- #
# self-test
# --------------------------------------------------------------------------- #

def _synth_ops():
    ops = []
    st = 100
    for i, w in ((1, 11.0), (2, 22.0)):
        ops.append([st, 'g', 0xA0, ['s', 'H'], ['T', 0]]); st += 1
        ops.append([st, 'g', 0xA0, ['n', i], ['n', w]]); st += 1
        ops.append([st, 'g', 0xB0, ['n', 3], ['n', 9]]); st += 1
        ops.append([st, 'g', 0xB0, ['n', 1], ['n', 7]]); st += 1
        ops.append([st, 's', 0xC0, ['n', i], ['n', w + 7]]); st += 1
        ops.append([st, 's', 0xD0, ['n', 1], ['n', i + 1]]); st += 1
    return ops


def _selftest():
    fails = []

    def chk(tag, cond, extra=''):
        print(('[OK] ' if cond else '[XX] ') + tag + (' ' + extra if extra else ''))
        if not cond:
            fails.append(tag)

    ins = lift_from_ops(_synth_ops())
    chk('T1 two instructions cut at H reads', len(ins) == 2, 'n=%d' % len(ins))
    chk('T2 words 11.0/22.0', [i['word'] for i in ins] == [11.0, 22.0],
        str([i['word'] for i in ins]))
    chk('T3 operand decode captured (7)', len(ins) == 2 and ins[0]['operands'] == [['n', 7]],
        str(ins[0]['operands'] if ins else None))
    ok4 = len(ins) == 2 and any(w[2] == ['n', 18.0] for w in ins[0]['writes'])
    chk('T4 register write 11+7=18 captured', ok4,
        str(ins[0]['writes'] if ins else None))
    chk('T5 empty log lifts to nothing', lift_from_ops([]) == [])
    lines = render(ins)
    chk('T6 render produces 2 lines with word', len(lines) == 2 and 'word=11.0' in lines[0],
        lines[0][:60] if lines else '')

    print('')
    print('Result: %d/6' % (6 - len(fails)))
    if fails:
        print('[XX] FAILURES: %d' % len(fails))
        return 1
    print('[OK] ALL PASSED')
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description='MoonVeil VM lifter (table-I/O trace -> instrs)')
    ap.add_argument('sample', nargs='?')
    ap.add_argument('--test', action='store_true')
    ap.add_argument('--trace', default=None)
    ap.add_argument('--max-steps', type=int, default=4000000)
    ap.add_argument('--start-step', type=int, default=450000)
    ap.add_argument('--show', type=int, default=12)
    ap.add_argument('--outdir', default=None)
    a = ap.parse_args(argv)
    if a.test:
        return _selftest()
    if a.trace:
        with open(a.trace, encoding='utf-8') as fh:
            ops = json.load(fh)['ops']
    elif a.sample:
        from obfuscator.deobfuscator.moonveil.vm_tables import trace_tables
        src = open(a.sample, encoding='utf-8', errors='replace').read()
        print('tracing: %s (max_steps=%d start_step=%d)' % (a.sample, a.max_steps, a.start_step))
        res = trace_tables(src, max_steps=a.max_steps, start_step=a.start_step)
        ops = res.ops
        print('ops=%d error=%s' % (len(ops), res.error))
    else:
        ap.error('sample path or --trace required (or --test)')
    ins = lift_from_ops(ops)
    print('instructions=%d' % len(ins))
    for ln in render(ins, a.show):
        print('  ' + ln)
    if a.outdir:
        if not os.path.isdir(a.outdir):
            os.makedirs(a.outdir)
        with open(os.path.join(a.outdir, 'lifted_mv.txt'), 'w', encoding='utf-8') as fh:
            fh.write('\n'.join(render(ins)) + '\n')
        with open(os.path.join(a.outdir, 'lifted_mv.json'), 'w', encoding='utf-8') as fh:
            json.dump(ins, fh, ensure_ascii=False)
        print('saved -> %s' % a.outdir)
    return 0


if __name__ == '__main__':
    sys.exit(main())
