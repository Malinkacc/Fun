"""WeAreDevs v1 CFG lift (Sprint 7, slice 2c-4).

Joins the block-level lift (slice 2c-3) through the control-flow graph:
the transition assignment of every leaf (slice 2c-1: LAST plain-Q
assignment) becomes CONTROL FLOW, the remaining statements stay as the
block body.  Straight runs of blocks collapse into one region; conditional
transitions (``Q = x and A or B``) render as ``if x then ... else ... end``
with the two successor chains inside; multi-predecessor blocks get labels;
cycles resolve as back-gotos (structured loops are a documented 2c-5 gap).
Indirect transitions (665 data-dependent ``Q = <lookup>``) stay honest
markers.  Nothing is guessed: every emitted edge maps to a resolved
leaf-level transition.

Usage:
    py -m obfuscator.deobfuscator.wearedevs.cfg_lift --test
    py -m obfuscator.deobfuscator.wearedevs.cfg_lift --sample path\\wearedevs.lua --outdir out [--leaf 2829]
"""

import os
import sys
import json
import argparse

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from obfuscator.deobfuscator.wearedevs.dispatch_map import (
    tokenize, fold_constants, Parser, analyze_source, resolve_target,
    fold_render)
from obfuscator.deobfuscator.wearedevs.rt_names import build_final_array
from obfuscator.deobfuscator.wearedevs.rt_names import name_of, collect_magic_ints
from obfuscator.deobfuscator.wearedevs.block_lift import render_expr

_MAX_DEPTH = 24


# --------------------------------------------------------------------------- #
# leaf parsing -> graph nodes
# --------------------------------------------------------------------------- #

def _last_q_stmt(body):
    for st in reversed(body):
        if st[0] == 'assign':
            for k, tg in enumerate(st[1]):
                if tg[0] == 'name' and tg[1] == 'Q':
                    return st, k
    return None, -1


class _Budget(Exception):
    pass


def _subst(ast, env, budget):
    """Deeply substitute name -> value AST per the sequential env."""
    if budget[0] <= 0:
        raise _Budget()
    k = ast[0]
    if k == 'name':
        v = env.get(ast[1])
        if v is None:
            return ast
        budget[0] -= 1
        return v
    if k in ('num', 'str', 'kw', 'vararg'):
        return ast
    if k == 'un':
        return ('un', ast[1], _subst(ast[2], env, budget), ast[3], ast[4])
    if k == 'bin':
        return ('bin', ast[1], _subst(ast[2], env, budget),
                _subst(ast[3], env, budget), ast[4], ast[5])
    if k == 'paren':
        return ('paren', _subst(ast[1], env, budget), ast[2], ast[3])
    if k == 'call':
        return ('call', _subst(ast[1], env, budget),
                [_subst(a, env, budget) for a in ast[2]], ast[3], ast[4])
    if k == 'index':
        return ('index', _subst(ast[1], env, budget),
                _subst(ast[2], env, budget), ast[3], ast[4])
    if k == 'table':
        return ('table', [(None if f[0] is None else _subst(f[0], env, budget),
                           _subst(f[1], env, budget)) for f in ast[1]],
                ast[2], ast[3])
    return ast


def _env_of(body, skip):
    """Sequential env: last assigned value per plain-name target.
    Substitution happens statement by statement (version-correct reads)."""
    env = {}
    budget = [20000]
    for st in body:
        if st is skip or st[0] != 'assign':
            continue
        tgts, vals = st[1], st[2]
        if any(t[0] != 'name' for t in tgts):
            continue
        if len(vals) != len(tgts):
            continue  # expanding call: skip (returns unknown)
        try:
            newvals = [_subst(v, env, budget) for v in vals]
        except _Budget:
            continue
        for t, v in zip(tgts, newvals):
            env[t[1]] = v
    return env


def _unwrap_cond(val):
    """``cond and TRUE or FALSE`` (possibly built through temps) ->
    (cond_ast, true_num|None, false_num|None)."""
    if val[0] == 'bin' and val[1] == 'or':
        a, b = val[2], val[3]
        false_v = b[1] if b[0] == 'num' else None
        if a[0] == 'bin' and a[1] == 'and':
            cond, true_v = a[2], a[3]
        else:
            cond, true_v = a, None
        true_n = true_v[1] if true_v is not None and true_v[0] == 'num' else None
        return cond, true_n, false_v
    return None, None, None


def _transition_of(body, mtab):
    """Extract (kind, cond_text, true_state, false_state, indirect_text)
    from a parsed leaf body using last-Q + sequential substitution."""
    qst, qi = _last_q_stmt(body)
    if qst is None:
        return ('stop', '', None, None, '')
    vals = qst[2]
    if qi < len(vals):
        raw = vals[qi]
    elif vals and vals[-1][0] == 'call':
        return ('indirect', '', None, None,
                render_expr(vals[-1], mtab))
    else:
        return ('halt', '', None, None, '')
    if raw[0] == 'num':
        return ('straight', '', raw[1], None, '')
    if raw[0] == 'kw' and raw[1] == 'nil':
        return ('halt', '', None, None, '')
    try:
        env = _env_of(body, qst)
        sub = _subst(raw, env, [20000])
    except _Budget:
        sub = raw
    if sub[0] == 'num':
        return ('straight', '', sub[1], None, '')
    if sub[0] == 'kw' and sub[1] == 'nil':
        return ('halt', '', None, None, '')
    if sub[0] == 'bin' and sub[1] == 'or':
        cond, tn, fn = _unwrap_cond(sub)
        if cond is not None:
            return ('cond', render_expr(cond, mtab), tn, fn, '')
        return ('indirect', '', None, None, render_expr(sub, mtab))
    return ('indirect', '', None, None, render_expr(sub, mtab))


def parse_leaves(src, mtab, info):
    """Parse every leaf; returns {leaf_id: node} where node =
    {kind, cond, succ, indirect, body: [rendered lines]}.
    kind: straight | cond | halt | indirect | stop(no/odd transition)."""
    from obfuscator.deobfuscator.wearedevs.rt_names import name_of
    leaves = info['leaves']
    bounded = sorted(leaves,
                     key=lambda lf: lf['lo'] if lf['lo'] is not None else -(1 << 62))
    los = [lf['lo'] if lf['lo'] is not None else -(1 << 62) for lf in bounded]
    nodes = {}
    for lf in leaves:
        s, e = lf['span']
        node = {'kind': 'stop', 'cond': '', 'succ': [], 'indirect': '',
                'body': [], 'states': lf['targets'], 'lo': lf['lo'], 'hi': lf['hi']}
        if s >= 0 and e is not None and e > s:
            toks = tokenize(src[s:e], base=s)
            toks, _ = fold_constants(toks)
            p = Parser(toks, 0)
            body = p.parse_block(set())
            qst, qi = _last_q_stmt(body)
            out_lines = []
            for st in body:
                if st is qst:
                    # transition statement: render the non-Q part only
                    tgs = [t for j, t in enumerate(st[1]) if j != qi]
                    vals = [v for j, v in enumerate(st[2]) if j != qi]
                    if tgs:
                        # expanding call fed the extra target: keep all vals
                        if len(vals) != len(tgs) and st[2] and st[2][-1][0] == 'call':
                            vals = st[2]
                        out_lines.append('%s = %s' % (
                            ', '.join(render_expr(t, mtab) for t in tgs),
                            ', '.join(render_expr(v, mtab) for v in vals)))
                    continue
                out_lines.append(_render_stmt_flat(st, mtab))
            node['body'] = out_lines
            kind, cond, tn, fn, ind = _transition_of(body, mtab)
            node['kind'] = kind
            node['cond'] = cond
            node['indirect'] = ind
            if kind == 'straight':
                node['succ'] = [tn]
            elif kind == 'cond':
                node['succ'] = [tn, fn]
        rid = []
        for tg in lf['targets']:
            r = resolve_target(bounded, los, tg)
            if r is not None:
                rid.append(r)
        node['resolved_states'] = rid
        nodes[lf['id']] = node
    # map state targets -> successor leaf ids
    for nid, node in nodes.items():
        if node['kind'] == 'straight':
            node['succ_leaf'] = _to_leaf(bounded, los, node['succ'][0]) \
                if node['succ'] else None
        elif node['kind'] == 'cond':
            node['succ_leaf'] = [_to_leaf(bounded, los, node['succ'][0]),
                                 _to_leaf(bounded, los, node['succ'][1])]
        else:
            node['succ_leaf'] = None
    return nodes


def _to_leaf(bounded, los, state):
    if state is None:
        return None
    return resolve_target(bounded, los, state)


def _val_kind(val):
    if val[0] == 'num':
        return 'straight'
    if val[0] == 'kw' and val[1] == 'nil':
        return 'halt'
    if val[0] == 'bin' and val[1] == 'or':
        return 'cond'
    return 'indirect'


def _render_stmt_flat(st, mtab):
    from obfuscator.deobfuscator.wearedevs.block_lift import render_stmt
    return render_stmt(st, mtab)


# --------------------------------------------------------------------------- #
# emitter (pure -- unit-tested on hand-built nodes)
# --------------------------------------------------------------------------- #

def emit_flow(nodes, entry, max_depth=_MAX_DEPTH):
    """Emit the joined control flow.  Returns (lines, stats)."""
    preds = {}
    for nid, n in nodes.items():
        succs = []
        if n['kind'] == 'straight':
            succs = [n['succ_leaf']]
        elif n['kind'] == 'cond':
            succs = list(n['succ_leaf'])
        for s in succs:
            if s is not None:
                preds[s] = preds.get(s, 0) + 1
    needs_label = {nid for nid, c in preds.items() if c >= 2}
    needs_label.add(entry)

    lines = []
    stats = {'regions': 0, 'labels': 0, 'ifs': 0, 'gotos': 0,
             'halts': 0, 'indirects': 0, 'bodies': 0}
    visited = set()

    def out(indent, txt):
        lines.append('  ' * indent + txt)

    def emit_node(nid, indent, depth):
        while True:
            if nid is None:
                out(indent, 'goto --[[indirect]]')
                stats['indirects'] += 1
                stats['gotos'] += 1
                return
            if nid in visited:
                out(indent, 'goto L%d' % nid)
                stats['gotos'] += 1
                return
            visited.add(nid)
            stats['regions'] += 1
            n = nodes[nid]
            if nid in needs_label or stats['regions'] == 1:
                out(indent, 'L%d:' % nid)
                stats['labels'] += 1
            for b in n['body']:
                out(indent, b)
                stats['bodies'] += 1
            if n['kind'] == 'halt':
                out(indent, '-- halt (Q = nil)')
                stats['halts'] += 1
                return
            if n['kind'] == 'indirect':
                out(indent, '-- indirect: Q = %s' % n['indirect'])
                stats['indirects'] += 1
                return
            if n['kind'] == 'stop':
                out(indent, '-- stop (no resolved transition)')
                return
            if n['kind'] == 'straight':
                nxt = n['succ_leaf']
                if nxt is None:
                    out(indent, 'goto --[[indirect]]')
                    stats['indirects'] += 1
                    return
                nid = nxt
                continue
            if n['kind'] == 'cond':
                t, f = n['succ_leaf']
                if t is not None and t == f:
                    nid = t
                    continue
                stats['ifs'] += 1
                out(indent, 'if %s then' % n['cond'])
                if depth <= 0:
                    out(indent + 1, 'goto %s' % ('L%d' % t if t is not None
                                                 else '--[[indirect]]'))
                    stats['gotos'] += 1
                    out(indent, 'else')
                    if f is None:
                        out(indent + 1, 'goto --[[indirect]]')
                        stats['indirects'] += 1
                    else:
                        out(indent + 1, 'goto L%d' % f)
                        stats['gotos'] += 1
                    out(indent, 'end')
                    return
                out(indent + 1, '-- true branch')
                if t is None:
                    out(indent + 1, 'goto --[[indirect]]')
                    stats['indirects'] += 1
                else:
                    emit_node(t, indent + 1, depth - 1)
                out(indent, 'else')
                out(indent + 1, '-- false branch')
                if f is None:
                    out(indent + 1, 'goto --[[indirect]]')
                    stats['indirects'] += 1
                else:
                    emit_node(f, indent + 1, depth - 1)
                out(indent, 'end')
                return
            return

    emit_node(entry, 0, max_depth)
    return lines, stats


# --------------------------------------------------------------------------- #
# sample driver
# --------------------------------------------------------------------------- #

def build_names(src):
    final = build_final_array(src)
    info = analyze_source(src)
    fpos, tail = info['region']
    folded = fold_render(src[fpos:tail])
    mtab = {}
    for n in collect_magic_ints(folded):
        s = name_of(final, n)
        if s is not None:
            mtab[n] = s
    return mtab, info


def lift(src):
    mtab, info = build_names(src)
    nodes = parse_leaves(src, mtab, info)
    entry_leaf = info['entry_leaf']
    lines, stats = emit_flow(nodes, entry_leaf)
    kinds = {}
    for n in nodes.values():
        kinds[n['kind']] = kinds.get(n['kind'], 0) + 1
    return {'lines': lines, 'stats': stats, 'kinds': kinds,
            'leaves': len(nodes), 'entry_leaf': entry_leaf,
            'entry': info['entry'], 'names': len(mtab)}


def main(argv=None):
    ap = argparse.ArgumentParser(description='WeAreDevs CFG lift (2c-4)')
    ap.add_argument('--test', action='store_true')
    ap.add_argument('--sample', default=None)
    ap.add_argument('--outdir', default=None)
    ap.add_argument('--show', type=int, default=40)
    a = ap.parse_args(argv)
    if a.test:
        return _selftest()
    if a.sample:
        src = open(a.sample, encoding='utf-8', errors='replace').read()
        res = lift(src)
        print('leaves=%d ; kinds: %s' % (res['leaves'], res['kinds']))
        print('entry=%s -> L%s' % (res['entry'], res['entry_leaf']))
        print('flow: %s' % ', '.join('%s=%d' % kv
                                     for kv in sorted(res['stats'].items())))
        for l in res['lines'][:a.show]:
            print(l)
        if a.outdir:
            if not os.path.isdir(a.outdir):
                os.makedirs(a.outdir)
            p1 = os.path.join(a.outdir, 'wd_flow.lua')
            with open(p1, 'w', encoding='utf-8') as fh:
                fh.write('\n'.join(res['lines']) + '\n')
            p2 = os.path.join(a.outdir, 'wd_flow.json')
            with open(p2, 'w', encoding='utf-8') as fh:
                json.dump({'stats': res['stats'], 'kinds': res['kinds'],
                           'leaves': res['leaves'], 'entry_leaf': res['entry_leaf']},
                          fh, ensure_ascii=False, indent=1)
            print('saved -> %s ; %s' % (p1, p2))
        return 0
    ap.error('use --test or --sample')


# --------------------------------------------------------------------------- #
# self-test (pure emitter on hand-built nodes)
# --------------------------------------------------------------------------- #

def _n(kind, succ=None, cond='', body=None, indirect=''):
    if kind == 'straight':
        sl = succ[0] if succ else None
    elif kind == 'cond':
        sl = list(succ) if succ else [None, None]
    else:
        sl = None
    return {'kind': kind, 'cond': cond, 'succ': succ if succ else [],
            'succ_leaf': sl, 'indirect': indirect,
            'body': body or [], 'states': [], 'lo': None, 'hi': None,
            'resolved_states': []}


def _selftest():
    fails = []

    def chk(tag, cond, extra=''):
        print(('[OK] ' if cond else '[XX] ') + tag + (' ' + extra if extra else ''))
        if not cond:
            fails.append(tag)

    # T1 straight chain joined (no goto inside, single region, entry label)
    nodes = {0: _n('straight', [1], body=['a = 1']),
             1: _n('straight', [2], body=['b = 2']),
             2: _n('halt', body=['c = 3'])}
    lines, st = emit_flow(nodes, 0)
    txt = '\n'.join(lines)
    chk('T1 straight chain joined',
        st['regions'] == 3 and st['gotos'] == 0 and 'a = 1' in txt
        and txt.index('a = 1') < txt.index('b = 2') < txt.index('c = 3'),
        'regions=%d gotos=%d' % (st['regions'], st['gotos']))

    # T2 cond -> if/else with both branches
    nodes = {0: _n('cond', [1, 2], cond='x', body=[]),
             1: _n('halt', body=['t = 1']),
             2: _n('halt', body=['f = 1'])}
    lines, st = emit_flow(nodes, 0)
    txt = '\n'.join(lines)
    chk('T2 cond if/else', st['ifs'] == 1 and 'if x then' in txt
        and '-- true branch' in txt and '-- false branch' in txt
        and txt.index('t = 1') < txt.index('else') < txt.index('f = 1')
        and txt.rstrip().endswith('end'), 'ifs=%d' % st['ifs'])

    # T3 join: two preds -> label + goto
    nodes = {0: _n('cond', [2, 1], cond='x'),
             1: _n('straight', [2], body=['p = 1']),
             2: _n('halt', body=['j = 1'])}
    lines, st = emit_flow(nodes, 0)
    txt = '\n'.join(lines)
    chk('T3 join labeled',
        st['labels'] >= 1 and 'goto L2' in txt and 'L2:' in txt
        and st['gotos'] == 1, 'gotos=%d' % st['gotos'])

    # T4 indirect stays honest marker
    nodes = {0: _n('indirect', indirect='V[m(-7016)]', body=[])}
    lines, st = emit_flow(nodes, 0)
    txt = '\n'.join(lines)
    chk('T4 indirect marker', '-- indirect: Q = V[m(-7016)]' in txt
        and st['indirects'] == 1, '')

    # T5 cycle -> back-goto, no infinite loop
    nodes = {0: _n('straight', [1], body=['i = 0']),
             1: _n('cond', [0, 2], cond='i < 9'),
             2: _n('halt', body=[])}
    lines, st = emit_flow(nodes, 0)
    txt = '\n'.join(lines)
    chk('T5 cycle back-goto', 'goto L0' in txt and st['gotos'] == 1
        and st['ifs'] == 1, 'gotos=%d' % st['gotos'])

    # T6 cond with equal targets degenerates to straight (no if)
    nodes = {0: _n('cond', [1, 1], cond='x'),
             1: _n('halt', body=[])}
    lines, st = emit_flow(nodes, 0)
    chk('T6 equal targets no if', st['ifs'] == 0 and st['regions'] == 2,
        'ifs=%d' % st['ifs'])

    # T7 bool-build through temps: `Q=l and L; Q=Q or l` resolves both states
    code = 'L=6798405 l=1048603 Q=l and L Q=Q or l'
    toks = tokenize(code)
    toks, _ = fold_constants(toks)
    p = Parser(toks, 0)
    body = p.parse_block(set())
    kind, cond, tn, fn, ind = _transition_of(body, {})
    chk('T7 temp bool-build cond', kind == 'cond' and tn == 6798405
        and fn == 1048603, '%s %s->%s,%s' % (kind, cond, tn, fn))

    # T8 sequential env is version-correct: reads capture values at read time
    code = 'l=5 x=l l=7 Q=x'
    toks = tokenize(code)
    toks, _ = fold_constants(toks)
    p = Parser(toks, 0)
    body = p.parse_block(set())
    kind, cond, tn, fn, ind = _transition_of(body, {})
    chk('T8 version-correct dataflow', kind == 'straight' and tn == 5,
        '%s %s' % (kind, tn))

    print('')
    print('Result: %d/8' % (8 - len(fails)))
    if fails:
        print('[XX] FAILURES: %d' % len(fails))
        return 1
    print('[OK] ALL PASSED')
    return 0


if __name__ == '__main__':
    sys.exit(main())
