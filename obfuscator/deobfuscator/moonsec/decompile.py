"""MoonSec V3 one-command decompiler (slice 2b-11).

End-to-end entry for the chain-2b pipeline: takes an obfuscated Lua file
and emits readable Lua.  Wires together the verified slices with NO new
reverse-engineering logic:

    extract_blob -> find_seed -> decode_payload -> decode_full
        -> msvm_semantics.extract (dispatch extraction + alias executor)
        -> msvm_decomp.lift_tree (readable Lua)
        -> optional clean_lua (strip provenance comments)

Everything produced is annotated in the report: blob size, recovered
seed, proto-tree consume ratio (100.0% expected on genuine MoonSec V3
samples), slot/macro/dead counts.

Usage:
    py -m obfuscator.deobfuscator.moonsec.decompile --test
    py -m obfuscator.deobfuscator.moonsec.decompile --in path\\obfuscated.lua --out out\\deobf.lua --clean --show 40
"""

import os
import re
import sys
import json
import argparse

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from obfuscator.deobfuscator.moonsec.msvm_decomp import (
    lift_tree, clean_lua,
)


def decompile_source(src, structured=False):
    """Full chain on obfuscated source text.
    Returns (lua_text, stats, info) or raises ValueError with a reason."""
    from obfuscator.deobfuscator.moonsec.proto_decode import (
        extract_blob, find_seed, decode_full,
    )
    from obfuscator.deobfuscator.moonsec.mirror import decode_payload
    from obfuscator.deobfuscator.moonsec.msvm_semantics import extract as extract_sem

    blob = extract_blob(src)
    if not blob:
        raise ValueError('MoonSec proto blob not found in source')
    f, _protos_hint = find_seed(blob)
    if f is None:
        raise ValueError('proto seed not discovered (not MoonSec V3?)')
    data = decode_payload(blob, f)
    proto, consumed, total = decode_full(data)
    frac = 100.0 * consumed / max(1, total)
    if frac < 90.0:
        raise ValueError('proto tree consumes only %.1f%% of the blob' % frac)
    sem = extract_sem(src)
    opinfo = {str(k): v for k, v in sem['ops'].items()}
    if structured:
        from obfuscator.deobfuscator.moonsec.msvm_struct import lift_tree_struct
        text, stats = lift_tree_struct(proto, opinfo)
    else:
        text, stats = lift_tree(proto, opinfo)
    if structured:
        tot = {}
        for s in stats:
            for k, v in s.items():
                if isinstance(v, int):
                    tot[k] = tot.get(k, 0) + v
        info = {
            'blob_chars': len(blob), 'seed': f, 'consumed': consumed,
            'total': total, 'consume_pct': frac, 'protos': len(stats),
            'slots': tot.get('linear', 0) + tot.get('goto', 0)
                     + tot.get('for', 0) + tot.get('dead', 0)
                     + tot.get('filler', 0) + tot.get('ret', 0)
                     + tot.get('if', 0) + tot.get('ifelse', 0)
                     + tot.get('ifret', 0) + tot.get('repeat', 0),
            'macros': tot.get('linear', 0) + tot.get('goto', 0)
                      + tot.get('for', 0) + tot.get('if', 0)
                      + tot.get('ifelse', 0) + tot.get('ifret', 0)
                      + tot.get('repeat', 0) + tot.get('ret', 0),
            'dead': tot.get('dead', 0),
            'filler': tot.get('filler', 0),
            'struct': tot,
        }
    else:
        info = {
            'blob_chars': len(blob),
            'seed': f,
            'consumed': consumed,
            'total': total,
            'consume_pct': frac,
            'protos': len(stats),
            'slots': sum(s['slots'] for s in stats),
            'macros': sum(s['macros'] for s in stats),
            'dead': sum(s['junk'] for s in stats),
            'filler': sum(s['filler'] for s in stats),
        }
    return text, stats, info


# --------------------------------------------------------------------------- #
# self-test
# --------------------------------------------------------------------------- #

_REAL = os.path.join(_REPO_ROOT, 'obfuscator', 'deobfuscator', 'samples',
                     'other', 'moonsec_v3.lua')


def _selftest():
    fails = []

    def chk(tag, cond, extra=''):
        print('[%s] %s%s' % ('OK' if cond else 'XX', tag,
                             (' -- ' + str(extra)) if extra and not cond else ''))
        if not cond:
            fails.append(tag)

    # T1: clean_lua is exported and strips provenance but keeps code
    txt = 'function f()\n  r1 = "x"  --[[#2.1 op=12]]\nL3:\n  return r1  --[[#4.1 op=4]]\nend'
    c = clean_lua(txt)
    chk('T1 clean keeps code', 'r1 = "x"' in c and 'L3:' in c and 'return r1' in c, c)
    chk('T2 clean strips comments', '--[[' not in c, c)

    # T3..T6: full chain on the real in-repo sample (skipped honestly if absent)
    if not os.path.exists(_REAL):
        print('[!!] real sample not present -- chain tests skipped (not a failure of logic)')
        print('')
        print('Result: %d/6' % (6 - len(fails) - 4))
        if fails:
            print('[XX] FAILURES: %d' % len(fails))
            return 1
        print('[OK] PASSED (2/6 run)')
        return 0

    src = open(_REAL, encoding='utf-8', errors='replace').read()
    text, stats, info = decompile_source(src)
    chk('T3 chain consume 100%', abs(info['consume_pct'] - 100.0) < 0.01, info)
    chk('T4 chain 14 protos / 516 slots',
        info['protos'] == 14 and info['slots'] == 516, info)
    chk('T5 readable output',
        'function proto_0(' in text and 'return' in text and 'goto L' in text,
        text[:120])
    cl = clean_lua(text)
    chk('T6 clean output has no provenance', '--[[' not in cl, cl[:120])

    print('')
    print('Result: %d/6' % (6 - len(fails)))
    if fails:
        print('[XX] FAILURES: %d' % len(fails))
        return 1
    print('[OK] ALL PASSED')
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description='MoonSec V3 one-command decompiler')
    ap.add_argument('--test', action='store_true')
    ap.add_argument('--in', dest='inp', default=None)
    ap.add_argument('--out', dest='out', default=None)
    ap.add_argument('--outdir', default='out')
    ap.add_argument('--clean', action='store_true')
    ap.add_argument('--struct', action='store_true',
                    help='structured control flow (if/else/repeat) output')
    ap.add_argument('--show', type=int, default=40)
    a = ap.parse_args(argv)
    if a.test:
        return _selftest()
    if not a.inp:
        print('need --in path (or --test)')
        return 2
    src = open(a.inp, encoding='utf-8', errors='replace').read()
    try:
        text, stats, info = decompile_source(src, structured=a.struct)
    except ValueError as e:
        print('[XX] %s' % e)
        return 1
    if a.clean:
        text = clean_lua(text)
    outp = a.out or os.path.join(a.outdir, 'decompiled.lua')
    d = os.path.dirname(outp)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(outp, 'w', encoding='utf-8') as fh:
        fh.write(text + '\n')
    print('blob=%d chars ; seed=%d ; consumed %d/%d (%.1f%%)'
          % (info['blob_chars'], info['seed'], info['consumed'],
             info['total'], info['consume_pct']))
    print('protos=%d ; slots=%d ; macros=%d ; dead=%d (%.1f%%) ; filler(op24)=%d'
          % (info['protos'], info['slots'], info['macros'], info['dead'],
             100.0 * info['dead'] / max(1, info['slots']), info['filler']))
    if a.struct and stats and 'if' in stats[0]:
        tot = {}
        for s in stats:
            for k, v in s.items():
                if isinstance(v, int):
                    tot[k] = tot.get(k, 0) + v
        print('structured: if=%d ifelse=%d ifret=%d repeat=%d ; fallback gotos=%d'
              % (tot.get('if', 0), tot.get('ifelse', 0), tot.get('ifret', 0),
                 tot.get('repeat', 0), tot.get('goto', 0)))
    lines = text.split('\n')
    for ln in lines[:a.show]:
        print(ln)
    if len(lines) > a.show:
        print('... (%d more lines)' % (len(lines) - a.show))
    print('saved ->', outp)
    return 0


if __name__ == '__main__':
    sys.exit(main())
