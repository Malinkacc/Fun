"""WeAreDevs v1 closure map (Sprint 7, slice 2c-5).

The dispatch tree is SHARED by all closures of the program: every closure
enters the dispatcher at its own state.  Closure creations are direct
calls of the maker slots (slice 2c-2 map: U=8, y=1, c=7, B=varargs,
r=4, T=10, n=5, I=2, J=0, v=3, w=6) of the shape

    maker(STATE, {upvalues})

inside leaf bodies (494 in-tree) plus the main entry from the tail
``B(4635360,{})``.  This module collects the creations, resolves every
state to its entry leaf and BFS-lifts each closure separately (fresh
visited set per closure -- emit_flow already does that), producing a
per-closure size map that partitions the 3362 leaves into the program's
actual functions.

Usage:
    py -m obfuscator.deobfuscator.wearedevs.closures --test
    py -m obfuscator.deobfuscator.wearedevs.closures --sample path\\wearedevs.lua --outdir out
"""

import os
import sys
import json
import argparse

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from obfuscator.deobfuscator.wearedevs.dispatch_map import (
    tokenize, fold_constants, Parser, analyze_source, resolve_target)
from obfuscator.deobfuscator.wearedevs.cfg_lift import build_names, parse_leaves, emit_flow

MAKERS = ('U', 'y', 'c', 'B', 'r', 'T', 'n', 'I', 'J', 'v', 'w')


# --------------------------------------------------------------------------- #
# creation collector (pure over parsed statements -- unit-tested)
# --------------------------------------------------------------------------- #

def _walk_calls(a, out):
    if not isinstance(a, tuple):
        return
    if a[0] == 'call':
        out.append(a)
        for x in a[2]:
            _walk_calls(x, out)
        return
    for x in a:
        if isinstance(x, tuple):
            _walk_calls(x, out)
        elif isinstance(x, list):
            for y in x:
                _walk_calls(y, out)


def creations_in_body(body):
    """Maker creations in parsed statements -> [(maker, state)]."""
    out = []
    calls = []
    for st in body:
        for x in st:
            if isinstance(x, tuple):
                _walk_calls(x, calls)
            elif isinstance(x, list):
                for y in x:
                    _walk_calls(y, out and out or calls) if False else \
                        _walk_calls(y, calls)
    for c in calls:
        callee = c[1]
        if callee[0] == 'name' and callee[1] in MAKERS and len(c[2]) == 2 \
                and c[2][0][0] == 'num':
            out.append((callee[1], int(c[2][0][1])))
    return out


def collect_creations(src, info):
    """All in-tree creations -> list of {leaf, maker, state}."""
    res = []
    for lf in info['leaves']:
        s, e = lf['span']
        if s < 0 or e is None or e <= s:
            continue
        toks = tokenize(src[s:e], base=s)
        toks, _ = fold_constants(toks)
        p = Parser(toks, 0)
        body = p.parse_block(set())
        for maker, state in creations_in_body(body):
            res.append({'leaf': lf['id'], 'maker': maker, 'state': state})
    return res


# --------------------------------------------------------------------------- #
# closure map
# --------------------------------------------------------------------------- #

def _bounds(info):
    leaves = info['leaves']
    bounded = sorted(leaves,
                     key=lambda lf: lf['lo'] if lf['lo'] is not None else -(1 << 62))
    los = [lf['lo'] if lf['lo'] is not None else -(1 << 62) for lf in bounded]
    return bounded, los


def build_closure_map(src, main_state=None):
    """{state: {maker, def_leaf, entry_leaf, regions, bodies, ifs, gotos}}.

    main_state: the tail entry (excluded from islands, reported as main)."""
    mtab, info = build_names(src)
    nodes = parse_leaves(src, mtab, info)
    bounded, los = _bounds(info)
    creations = collect_creations(src, info)
    by_state = {}
    for c in creations:
        e = by_state.get(c['state'])
        if e is None or c['maker'] == 'B':  # varargs maker wins (entry-style)
            by_state[c['state']] = {'maker': c['maker'], 'def_leaf': c['leaf']}
    for st, e in by_state.items():
        e['entry_leaf'] = resolve_target(bounded, los, st)
    if main_state is not None and main_state not in by_state:
        by_state[main_state] = {'maker': 'B', 'def_leaf': None,
                                'entry_leaf': resolve_target(bounded, los,
                                                             main_state)}
    sizes = []
    for st, e in by_state.items():
        rl = e.get('entry_leaf')
        if rl is None or rl not in nodes:
            e['regions'] = e['bodies'] = e['ifs'] = e['gotos'] = 0
            continue
        lines, stats = emit_flow(nodes, rl)
        e['regions'] = stats['regions']
        e['bodies'] = stats['bodies']
        e['ifs'] = stats['ifs']
        e['gotos'] = stats['gotos']
        sizes.append(st)
    covered = set()
    for st, e in by_state.items():
        covered.add(e.get('entry_leaf'))
    covered.discard(None)
    return {
        'nodes': nodes,
        'closures': by_state,
        'creations': len(creations),
        'mtab': mtab,
        'covered_leaves': len(covered),
        'n_leaves': len(nodes),
    }


# --------------------------------------------------------------------------- #
# driver
# --------------------------------------------------------------------------- #

def main(argv=None):
    ap = argparse.ArgumentParser(description='WeAreDevs closure map (2c-5)')
    ap.add_argument('--test', action='store_true')
    ap.add_argument('--sample', default=None)
    ap.add_argument('--outdir', default=None)
    ap.add_argument('--top', type=int, default=10)
    a = ap.parse_args(argv)
    if a.test:
        return _selftest()
    if a.sample:
        src = open(a.sample, encoding='utf-8', errors='replace').read()
        from obfuscator.deobfuscator.wearedevs.dispatch_map import extract_entry
        _fn, main_state = extract_entry(src)
        res = build_closure_map(src, main_state=main_state)
        cls = res['closures']
        reg = sorted(((st, e['regions']) for st, e in cls.items()),
                     key=lambda kv: -kv[1])
        total_regions = sum(e['regions'] for e in cls.values())
        print('creations=%d ; closures=%d ; main=%s ; covered leaves=%d/%d'
              % (res['creations'], len(cls), main_state,
                 res['covered_leaves'], res['n_leaves']))
        print('regions: total=%d ; main=%d ; biggest others: %s'
              % (total_regions, cls.get(main_state, {}).get('regions', 0),
                 ', '.join('%d@%d' % (r, st) for st, r in reg[1:a.top + 1])))
        hist = {}
        for st, e in cls.items():
            b = e['regions'] // 10 * 10
            hist[b] = hist.get(b, 0) + 1
        print('size histogram (regions bucket of 10): %s'
              % ', '.join('%d-%d:%d' % (k, k + 9, v)
                          for k, v in sorted(hist.items())))
        if a.outdir:
            if not os.path.isdir(a.outdir):
                os.makedirs(a.outdir)
            out = {'creations': res['creations'], 'main': main_state,
                   'closures': {str(st): e for st, e in cls.items()}}
            p1 = os.path.join(a.outdir, 'wd_closures.json')
            with open(p1, 'w', encoding='utf-8') as fh:
                json.dump(out, fh, ensure_ascii=False, indent=1)
            print('saved -> %s' % p1)
        return 0
    ap.error('use --test or --sample')


# --------------------------------------------------------------------------- #
# self-test
# --------------------------------------------------------------------------- #

def _parse(code):
    toks = tokenize(code)
    toks, _ = fold_constants(toks)
    p = Parser(toks, 0)
    return p.parse_block(set())


def _selftest():
    fails = []

    def chk(tag, cond, extra=''):
        print(('[OK] ' if cond else '[XX] ') + tag + (' ' + extra if extra else ''))
        if not cond:
            fails.append(tag)

    body = _parse('r(12114183,{})y(109867,{})')
    cr = creations_in_body(body)
    chk('T1 creations collected', sorted(cr) == [('r', 12114183), ('y', 109867)],
        str(cr))

    body = _parse('f(123,{}) g(5) x=9')
    chk('T2 non-maker ignored', creations_in_body(body) == [])

    body = _parse('r(x,{}) r("s",{})')
    chk('T3 non-const state ignored', creations_in_body(body) == [])

    body = _parse('B(4635360,{})')
    cr = creations_in_body(body)
    chk('T4 varargs maker B', cr == [('B', 4635360)], str(cr))

    # T5: per-closure BFS isolates islands (fresh visited per root)
    from obfuscator.deobfuscator.wearedevs.cfg_lift import _n, emit_flow
    nodes = {0: _n('straight', [1], body=['a = 1']),
             1: _n('halt', body=['b = 2']),
             2: _n('straight', [3], body=['c = 3']),
             3: _n('straight', [4], body=['d = 4']),
             4: _n('halt', body=['e = 5'])}
    l1, s1 = emit_flow(nodes, 0)
    l2, s2 = emit_flow(nodes, 2)
    chk('T5 island BFS sizes', s1['regions'] == 2 and s2['regions'] == 3,
        '%d/%d' % (s1['regions'], s2['regions']))

    # T6: multi-root coverage recomputes per root (no cross-talk)
    l3, s3 = emit_flow(nodes, 2)
    chk('T6 re-run stable', s3['regions'] == s2['regions']
        and len(l3) == len(l2), '')

    print('')
    print('Result: %d/6' % (6 - len(fails)))
    if fails:
        print('[XX] FAILURES: %d' % len(fails))
        return 1
    print('[OK] ALL PASSED')
    return 0


if __name__ == '__main__':
    sys.exit(main())
