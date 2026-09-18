"""WeAreDevs v1 runtime names & slot map (Sprint 7, slice 2c-2).

Static resolution of the runtime vocabulary used by the flattened
dispatch program (slice 2c-1):

* NAME DECODER: ``local function m(m) return V[m + 10322] end`` -- magic
  ints in the program (``m(259459+-266860)``) index the decrypted string
  array V directly (1-based Lua, offset 10322).
* ORDER: V is rotated BEFORE decryption -- three in-place reversals
  ``{1..6233}, {1..209}, {1..8233}`` (step formulas fold to 1/1), then the
  base64/ascii85 decrypt (slice 4b) runs in place.  So the final array is
  decrypt(reverse3(raw)); the 4b mirror decoded reverse3-free order,
  which is why per-entry strings looked right but global order was not
  resolved yet.
* SLOT MAP: the 19-target simultaneous assignment at the top of the VM
  wrapper (parsed structurally by dispatch_map.Parser):

    p  decref(name)            K  0 (id counter base)
    U  closure maker arity 8   y  closure maker arity 1
    c  closure maker arity 6   i  refcount++ + env/proxy wrap
    B  closure maker varargs   h  {} refcount table
    r  closure maker arity 4   T  closure maker arity 10
    W  {} name->value store    n  closure maker arity 3
    I  closure maker arity 5   O  id allocator (K=K+1; h[K]=1; return K)
    v  closure maker arity 2   w  closure maker arity 7
    C  decref-array cleanup    Q  THE DISPATCHER function(Q,q,S,A)

  Wrapper params: S=setmetatable, V=getfenv() (env), A=getmetatable,
  N=select, q=newproxy, l={...} (script args), Y=unpack; entry
  ``B(4635360,{})(Y(l))`` = main closure (varargs maker, state 4635360,
  empty upvalues) applied to unpack(script args).

Usage:
    py -m obfuscator.deobfuscator.wearedevs.rt_names --test
    py -m obfuscator.deobfuscator.wearedevs.rt_names --sample path\\wearedevs.lua --outdir out
"""

import os
import re
import sys
import json
import argparse

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from obfuscator.deobfuscator.wearedevs.dispatch_map import (
    tokenize, fold_constants, analyze_source)

DECODER_OFFSET = 10322          # m(n) = V[n + 10322]  (1-based)
ROT_PASSES = [(1, 8233), (1, 209), (210, 8233)]  # reversals; net = rotate tail-209 to front
M_CALL_RE = re.compile(r'\bm\((-?\d+)\)')

# (slot name, role) -- proven by structural parse + raw reading (see docstring)
SLOT_MAP = [
    ('p', 'decref'), ('K', 'id-counter-base'), ('U', 'closure8'),
    ('y', 'closure1'), ('c', 'closure7'), ('i', 'refcount+env'),
    ('B', 'closure-varargs'), ('h', 'refcounts'), ('r', 'closure4'),
    ('T', 'closure10'), ('W', 'name-store'), ('n', 'closure5'),
    ('I', 'closure2'), ('J', 'closure0'), ('O', 'id-alloc'),
    ('v', 'closure3'), ('w', 'closure6'), ('C', 'decref-array'),
    ('Q', 'dispatcher'),
]


def rotate01(arr, passes=None):
    """Mirror the reversal passes (arr is 0-based)."""
    out = list(arr)
    for a, b in (passes or ROT_PASSES):
        i, j = a - 1, b - 1
        while i < j:
            out[i], out[j] = out[j], out[i]
            i += 1
            j -= 1
    return out


def build_final_array(src):
    """raw -> rotate01 -> decode -> list of str (the array as the VM sees it)."""
    from obfuscator.deobfuscator.wearedevs.array_mirror import (
        extract_arrays, decode_array)
    b64, a85, raw = extract_arrays(src)
    if not raw:
        raise ValueError('string array not found')
    rotated = rotate01(raw)
    return [d.decode('latin1') if isinstance(d, bytes) else d
            for d in decode_array(rotated, b64, a85)]


def name_of(arr, n):
    """m(n): magic int -> string (arr = FINAL decrypted array, 0-based)."""
    idx = n + DECODER_OFFSET - 1
    if 0 <= idx < len(arr):
        return arr[idx]
    return None


def fold_text(src):
    """Token-stream constant folding -> text (for m(<const>) scanning)."""
    toks = tokenize(src)
    toks, _ = fold_constants(toks)
    out = []
    last = 0
    for t in toks:
        out.append(src[last:t[2] - 0 if False else t[2]])
        out.append(str(t[1]) if t[0] == 'num' else src[t[2]:t[3]])
        last = t[3]
    out.append(src[last:])
    return ''.join(out)


def collect_magic_ints(region_text):
    """All m(<int>) constants in a folded region text."""
    return [int(x) for x in M_CALL_RE.findall(region_text)]


def analyze(src):
    """Full static resolution for one sample.  Returns info dict."""
    final = build_final_array(src)

    info = analyze_source(src)
    fpos, tail = info['region']
    region = src[fpos:tail]
    folded = fold_text(region)
    ints = collect_magic_ints(folded)
    table = {}
    miss = 0
    printable = 0
    for n in ints:
        s = name_of(final, n)
        if s is None:
            miss += 1
            continue
        table[str(n)] = s
        if s and all(32 <= ord(c) < 127 for c in s):
            printable += 1
    return {
        'decoder_offset': DECODER_OFFSET,
        'rot_passes': ROT_PASSES,
        'array_len': len(final),
        'slot_map': SLOT_MAP,
        'm_calls': len(ints),
        'm_resolved': len(table),
        'm_miss': miss,
        'm_printable': printable,
        'm_table': table,
        'magic_keys': {str(n): name_of(final, n) for n in (-7317, -8020, -4449)},
        'dispatch': {k: v for k, v in info.items() if k != 'leaves'},
        'n_leaves': len(info['leaves']),
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description='WeAreDevs runtime names / slot map')
    ap.add_argument('--test', action='store_true')
    ap.add_argument('--sample', default=None)
    ap.add_argument('--outdir', default=None)
    ap.add_argument('--show', type=int, default=20)
    a = ap.parse_args(argv)
    if a.test:
        return _selftest()
    if a.sample:
        src = open(a.sample, encoding='utf-8', errors='replace').read()
        info = analyze(src)
        print('array=%d ; rotation passes=%s' % (info['array_len'], info['rot_passes']))
        print('m() calls=%d ; resolved=%d ; miss=%d ; printable=%d' %
              (info['m_calls'], info['m_resolved'], info['m_miss'],
               info['m_printable']))
        print('magic keys: %s' % info['magic_keys'])
        gt = {'-7317': '__index', '-8020': '__gc', '-4449': '__len', '-2896': 'unpack'}
        bad = [k for k, v in gt.items()
               if (info['magic_keys'].get(k) or info['m_table'].get(k)) != v]
        print('ground truth: %s' % ('[OK] all %d match' % len(gt) if not bad
                                    else '[XX] mismatch at %s' % bad))
        items = sorted(info['m_table'].items(), key=lambda kv: int(kv[0]))
        print('resolved names (first %d):' % a.show)
        for k, v in items[:a.show]:
            print('  m(%s) = %r' % (k, v[:60]))
        if a.outdir:
            if not os.path.isdir(a.outdir):
                os.makedirs(a.outdir)
            path = os.path.join(a.outdir, 'wd_names.json')
            with open(path, 'w', encoding='utf-8') as fh:
                json.dump(info, fh, ensure_ascii=False, indent=1)
            print('saved -> %s' % path)
        return 0
    ap.error('use --test or --sample')


# --------------------------------------------------------------------------- #
# self-test
# --------------------------------------------------------------------------- #

def _selftest():
    fails = []

    def chk(tag, cond, extra=''):
        print(('[OK] ' if cond else '[XX] ') + tag + (' ' + extra if extra else ''))
        if not cond:
            fails.append(tag)

    # T1 rotation step constants fold to 1/1
    chk('T1 rotation steps', 255788966 % 1061365 == 1 and 1816298975 % 12189926 == 1,
        '%d/%d' % (255788966 % 1061365, 1816298975 % 12189926))

    # T2 reversal mirror on synthetic data (same passes, hand-computed)
    data = list('abcdef')
    out = rotate01(data, passes=[(1, 4), (1, 2), (1, 6)])
    x = list(data)
    for a, b in [(1, 4), (1, 2), (1, 6)]:
        i, j = a - 1, b - 1
        while i < j:
            x[i], x[j] = x[j], x[i]
            i += 1
            j -= 1
    chk('T2 rotate mirror', out == x, ''.join(out))

    # T3 decoder offset on a synthetic array sized like the real one
    arr = ['x%d' % (i + 1) for i in range(11000)]
    chk('T3 decoder offset', name_of(arr, -73) == 'x10249', str(name_of(arr, -73)))

    # T4 out-of-range magic int -> None (no crash)
    chk('T4 out-of-range safe', name_of(arr, 999999) is None and name_of(arr, -99999) is None)

    # T5 slot map shape
    names = [s for s, _ in SLOT_MAP]
    roles = set(r for _, r in SLOT_MAP)
    chk('T5 slot map shape', len(SLOT_MAP) == 19 and len(names) == len(set(names))
        and len(roles) == len(SLOT_MAP) and SLOT_MAP[-1] == ('Q', 'dispatcher'),
        '%d slots' % len(SLOT_MAP))

    # T6 magic-int extraction from a folded snippet
    ft = fold_text('K2=m(259459+-266860)t,f=m(179626-185170),m(-850931+848203)')
    ints = collect_magic_ints(ft)
    chk('T6 magic-int extraction', ints == [-7401, -5544, -2728], str(ints))

    print('')
    print('Result: %d/6' % (6 - len(fails)))
    if fails:
        print('[XX] FAILURES: %d' % len(fails))
        return 1
    print('[OK] ALL PASSED')
    return 0


if __name__ == '__main__':
    sys.exit(main())
