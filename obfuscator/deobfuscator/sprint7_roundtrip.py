"""Sprint 7 round-trip tests (slice 5, part 2).

Emits synthetic samples of the three Sprint-7 families and checks that the
corresponding decoder pipeline recovers the ground truth:

  T1 MoonSec shape   -> dynamic_decrypt captures the inner source by identity
  T2 MoonVeil shape  -> vm_trace recovers opcode shapes in program order
  T3 WeAreDevs shape -> array_trace captures every plaintext string
  T4 emitters deterministic
  T5 baseline engine digests all three emitted sources

Usage:
    py -m obfuscator.deobfuscator.sprint7_roundtrip --test
"""

import os
import sys

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from obfuscator.deobfuscator.sprint7_emitters import (emit_moonsec, emit_moonveil,
                                                        emit_wearedevs)

_PROG = [(1, 105, 55, 1), (2, 170, 40, 2), (3, 13, 9, 3)]
_STRS = ['alpha', 'beta', 'gamma', 'delta']


def _selftest():
    fails = []

    def chk(tag, cond, extra=''):
        print(('[OK] ' if cond else '[XX] ') + tag + (' ' + extra if extra else ''))
        if not cond:
            fails.append(tag)

    inner = 'return 41 + 1'
    src1 = emit_moonsec(inner)
    from obfuscator.deobfuscator.dynamic_decrypt import capture_layers
    r1 = capture_layers(src1, max_steps=500000, max_depth=2)
    got1 = [l['text'] for l in r1.layers]
    chk('T1 moonsec-shape: loadstring layer captured by identity',
        got1 == [inner], 'got=%s err=%s' % (got1, r1.error))

    src2 = emit_moonveil(_PROG)
    from obfuscator.deobfuscator.moonveil.vm_trace import trace_vm
    r2 = trace_vm(src2, max_steps=500000)
    kinds = []
    for sig, nums, st, decs, post in r2.seq:
        if '/' in sig:
            kinds.append('DIV')
        elif 'a.g(' in sig:
            kinds.append('MUL')
        else:
            kinds.append('SUB')
    chk('T2 moonveil-shape: opcode shapes SUB/DIV/MUL in order',
        kinds == ['SUB', 'DIV', 'MUL'], 'kinds=%s err=%s' % (kinds, r2.error))

    src3 = emit_wearedevs(_STRS, 3)
    from obfuscator.deobfuscator.wearedevs.array_trace import trace_array
    r3 = trace_array(src3, max_steps=500000)
    pv = sorted(p[1] for p in r3.plain)
    chk('T3 wearedevs-shape: plaintext strings recovered', pv == sorted(_STRS),
        'got=%s err=%s' % (pv, r3.error))

    chk('T4 emitters deterministic', emit_moonveil(_PROG) == src2
        and emit_wearedevs(_STRS, 3) == src3 and emit_moonsec(inner) == src1)

    from obfuscator.deobfuscator.engine import DeobfuscatorEngine
    eng = DeobfuscatorEngine()
    ok5 = True
    for s in (src1, src2, src3):
        try:
            pr = eng.deobfuscate_ex(s)
            _ = pr.cleaned_source
        except Exception as e:
            ok5 = False
            print('    engine error: %s' % str(e)[:80])
    chk('T5 baseline engine digests emitted sources', ok5)

    print('')
    print('Result: %d/5' % (5 - len(fails)))
    if fails:
        print('[XX] FAILURES: %d' % len(fails))
        return 1
    print('[OK] ALL PASSED')
    return 0


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description='Sprint 7 round-trip tests')
    ap.add_argument('--test', action='store_true')
    a = ap.parse_args(argv)
    if a.test:
        return _selftest()
    ap.error('use --test')


if __name__ == '__main__':
    sys.exit(main())
