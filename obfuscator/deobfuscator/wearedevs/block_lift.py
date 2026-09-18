"""WeAreDevs v1 block-level lift (Sprint 7, slice 2c-3).

Renders the dispatch-tree leaves (slice 2c-1) as readable pseudo-Lua with
the runtime vocabulary decoded (slice 2c-2): every ``m(<magic int>)`` call
site becomes the decoded string/name literal; constant arithmetic is
folded; assignments/calls/index-chains are rendered structurally.  A leaf
plus its transition IS a basic block of the original program, so the
output is a block-level decompilation of the whole flattened program:

    --[L2829 | states 4633616..4637399 | straight -> 13048532 (L1234)]
    l = W[S[4]]
    ...

Also emits wd_cfg.json: per-leaf state range, kind, state targets and the
resolved successor leaf ids (the control-flow graph of the program).

Usage:
    py -m obfuscator.deobfuscator.wearedevs.block_lift --test
    py -m obfuscator.deobfuscator.wearedevs.block_lift --sample path\\wearedevs.lua --outdir out [--leaf 2829]
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
    tokenize, fold_constants, Parser, analyze_source, resolve_target,
    fold_render)
from obfuscator.deobfuscator.wearedevs.rt_names import (
    build_final_array, name_of, collect_magic_ints)

_IDENT_RE = re.compile(r'^[A-Za-z_][A-Za-z_0-9]*$')


def _lit(s):
    """Render a decoded string as a Lua literal (printable -> quoted)."""
    if s and all(32 <= ord(c) < 127 for c in s):
        return '"%s"' % s.replace('\\', '\\\\').replace('"', '\\"')
    try:
        return "x'%s'" % s.encode('latin1').hex()
    except Exception:
        return '"?"'


def render_expr(ast, mtab):
    k = ast[0]
    if k == 'num':
        v = ast[1]
        if isinstance(v, float) and v.is_integer():
            return str(int(v))
        return repr(v)
    if k == 'str':
        return _lit(ast[1])
    if k in ('name', 'kw'):
        return str(ast[1])
    if k == 'vararg':
        return '...'
    if k == 'paren':
        return '(%s)' % render_expr(ast[1], mtab)
    if k == 'un':
        return '%s%s' % (ast[1], render_expr(ast[2], mtab))
    if k == 'bin':
        return '%s %s %s' % (render_expr(ast[2], mtab), ast[1],
                             render_expr(ast[3], mtab))
    if k == 'call':
        callee = ast[1]
        args = ast[2]
        if callee[0] == 'name' and callee[1] == 'm' and len(args) == 1 \
                and args[0][0] == 'num':
            n = int(args[0][1])
            s = mtab.get(n)
            if s is not None:
                return _lit(s)
        return '%s(%s)' % (render_expr(callee, mtab),
                           ', '.join(render_expr(a, mtab) for a in args))
    if k == 'index':
        return '%s[%s]' % (render_expr(ast[1], mtab), render_expr(ast[2], mtab))
    if k == 'table':
        if not ast[1]:
            return '{}'
        fields = []
        for key, val in ast[1]:
            if key is None:
                fields.append(render_expr(val, mtab))
            elif key[0] == 'str' and _IDENT_RE.match(key[1]):
                fields.append('%s = %s' % (key[1], render_expr(val, mtab)))
            else:
                fields.append('[%s] = %s' % (render_expr(key, mtab),
                                             render_expr(val, mtab)))
        return '{%s}' % ', '.join(fields)
    if k == 'function':
        params = ', '.join(str(x[1]) for x in ast[1])
        body = '; '.join(render_stmt(s, mtab) for s in ast[2])
        return 'function(%s) %s end' % (params, body)
    return '<%s>' % k


def render_stmt(st, mtab):
    k = st[0]
    if k == 'assign':
        tg = ', '.join(render_expr(t, mtab) for t in st[1])
        vals = ', '.join(render_expr(v, mtab) for v in st[2])
        return '%s = %s' % (tg, vals)
    if k == 'local':
        names = ', '.join(st[1])
        if st[2]:
            return 'local %s = %s' % (names,
                                      ', '.join(render_expr(v, mtab) for v in st[2]))
        return 'local %s' % names
    if k == 'callstat':
        return render_expr(st[1], mtab)
    if k == 'return':
        if not st[1]:
            return 'return'
        return 'return %s' % ', '.join(render_expr(v, mtab) for v in st[1])
    if k == 'break':
        return 'break'
    if k == 'do':
        return 'do %s end' % '; '.join(render_stmt(s, mtab) for s in st[1])
    if k == 'while':
        body = '; '.join(render_stmt(s, mtab) for s in st[2])
        return 'while %s do %s end' % (render_expr(st[1], mtab), body)
    if k == 'repeat':
        body = '; '.join(render_stmt(s, mtab) for s in st[1])
        return 'repeat %s until %s' % (body, render_expr(st[2], mtab))
    if k == 'for':
        names = ', '.join(st[1])
        head = ', '.join(render_expr(h, mtab) for h in st[2])
        body = '; '.join(render_stmt(s, mtab) for s in st[3])
        return 'for %s in %s do %s end' % (names, head, body)
    if k == 'localfunc':
        params = ', '.join(str(x[1]) for x in st[2])
        body = '; '.join(render_stmt(s, mtab) for s in st[3])
        return 'local function %s(%s) %s end' % (st[1], params, body)
    if k == 'if':
        parts = []
        for i, (cond, body) in enumerate(st[1]):
            kw = 'if' if i == 0 else 'elseif'
            inner = '; '.join(render_stmt(s, mtab) for s in body)
            parts.append('%s %s then %s' % (kw, render_expr(cond, mtab), inner))
        if st[2]:
            parts.append('else %s' % '; '.join(render_stmt(s, mtab) for s in st[2]))
        return '%s end' % ' '.join(parts)
    return '-- <%s>' % k


def render_leaf_body(src, leaf, mtab):
    """Parse + render one leaf's body.  Returns (lines, m_subs)."""
    s, e = leaf['span']
    if s < 0 or e is None or e <= s:
        return [], 0
    text = src[s:e]
    toks = tokenize(text, base=s)
    toks, _ = fold_constants(toks)
    p = Parser(toks, 0)
    body = p.parse_block(set())
    before = mtab is not None
    lines = []
    subs = 0
    for st in body:
        rendered = render_stmt(st, mtab)
        subs += rendered.count('"') // 1  # refined below via AST walk count
        lines.append(rendered)
    return lines, _count_msubs(body, mtab)


def _count_msubs(body, mtab):
    """Count m(<int>) sites that resolved to a name in this body."""
    n = 0

    def walk(a):
        nonlocal n
        if not isinstance(a, tuple):
            return
        if a[0] == 'call' and a[1][0] == 'name' and a[1][1] == 'm' \
                and len(a[2]) == 1 and a[2][0][0] == 'num':
            if int(a[2][0][1]) in mtab:
                n += 1
        for x in a:
            if isinstance(x, tuple):
                walk(x)
            elif isinstance(x, list):
                for y in x:
                    if isinstance(y, tuple):
                        walk(y)

    for st in body:
        for x in st:
            if isinstance(x, tuple):
                walk(x)
            elif isinstance(x, list):
                for y in x:
                    if isinstance(y, tuple):
                        walk(y)
    return n


def build_names(src):
    """(mtab, final_array) for a sample: magic int -> decoded name."""
    final = build_final_array(src)
    info = analyze_source(src)
    fpos, tail = info['region']
    folded = fold_render(src[fpos:tail])
    mtab = {}
    for n in collect_magic_ints(folded):
        s = name_of(final, n)
        if s is not None:
            mtab[n] = s
    return mtab, final, info


def lift(src):
    """Full block lift.  Returns dict with blocks text lines + cfg."""
    mtab, final, info = build_names(src)
    src_full = src
    leaves = info['leaves']
    bounded = sorted(leaves,
                     key=lambda lf: lf['lo'] if lf['lo'] is not None else -(1 << 62))
    los = [lf['lo'] if lf['lo'] is not None else -(1 << 62) for lf in bounded]
    nxt = {}   # leaf id -> successor leaf ids (resolved)
    total_subs = 0
    rendered_n = 0
    lines = ['-- WeAreDevs block lift (slice 2c-3) ; leaves=%d ; entry=%s -> leaf %s'
             % (len(leaves), info['entry'], info['entry_leaf'])]
    cfg = []
    for lf in leaves:
        succ = []
        for tg in lf['targets']:
            rid = resolve_target(bounded, los, tg)
            if rid is not None:
                succ.append(rid)
        nxt[lf['id']] = succ
        body_lines, subs = render_leaf_body(src_full, lf, mtab)
        total_subs += subs
        if body_lines:
            rendered_n += 1
        tg_txt = ', '.join(str(t) if t is not None else 'indirect'
                           for t in lf['targets']) or '-'
        succ_txt = ','.join('L%d' % s for s in succ) if succ else '-'
        lines.append('')
        lines.append('--[L%d | states %s..%s | %s | -> %s (%s)]'
                     % (lf['id'], lf['lo'], lf['hi'], lf['kind'], tg_txt, succ_txt))
        if lf['path']:
            lines.append('-- path: %s'
                         % ' '.join('(%s)%s' % (p, b) for p, b in lf['path']))
        lines.extend(body_lines)
        cfg.append({'id': lf['id'], 'lo': lf['lo'], 'hi': lf['hi'],
                    'kind': lf['kind'], 'states': lf['targets'],
                    'next': succ, 'n_stmts': lf['n_stmts']})
    return {
        'lines': lines,
        'cfg': cfg,
        'leaves': len(leaves),
        'rendered': rendered_n,
        'm_subs': total_subs,
        'names': len(mtab),
        'entry': info['entry'],
        'entry_leaf': info['entry_leaf'],
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description='WeAreDevs block-level lift')
    ap.add_argument('--test', action='store_true')
    ap.add_argument('--sample', default=None)
    ap.add_argument('--outdir', default=None)
    ap.add_argument('--show', type=int, default=4)
    ap.add_argument('--leaf', type=int, default=None)
    a = ap.parse_args(argv)
    if a.test:
        return _selftest()
    if a.sample:
        src = open(a.sample, encoding='utf-8', errors='replace').read()
        res = lift(src)
        print('leaves=%d ; rendered=%d ; m-subs=%d ; names=%d ; entry=%s -> L%s'
              % (res['leaves'], res['rendered'], res['m_subs'], res['names'],
                 res['entry'], res['entry_leaf']))
        if a.leaf is not None:
            cfg = {c['id']: c for c in res['cfg']}
            c = cfg[a.leaf]
            print('--[L%d | states %s..%s | %s | -> %s (%s)]'
                  % (c['id'], c['lo'], c['hi'], c['kind'],
                     ','.join(str(x) for x in c['states']),
                     ','.join('L%d' % s for s in c['next'])))
            idx = [i for i, l in enumerate(res['lines'])
                   if l.startswith('--[L%d |' % a.leaf)]
            if idx:
                i = idx[0] + (1 if res['lines'][idx[0] + 1].startswith('-- path') else 1)
                for l in res['lines'][i:]:
                    if l.startswith('--[L'):
                        break
                    print(l)
        else:
            shown = 0
            for i, l in enumerate(res['lines']):
                if l.startswith('--[L') and shown >= a.show:
                    break
                if l.startswith('--[L'):
                    shown += 1
                print(l)
        if a.outdir:
            if not os.path.isdir(a.outdir):
                os.makedirs(a.outdir)
            p1 = os.path.join(a.outdir, 'wd_blocks.lua')
            with open(p1, 'w', encoding='utf-8') as fh:
                fh.write('\n'.join(res['lines']) + '\n')
            p2 = os.path.join(a.outdir, 'wd_cfg.json')
            with open(p2, 'w', encoding='utf-8') as fh:
                json.dump({'entry': res['entry'], 'entry_leaf': res['entry_leaf'],
                           'cfg': res['cfg']}, fh, ensure_ascii=False, indent=1)
            print('saved -> %s ; %s' % (p1, p2))
        return 0
    ap.error('use --test or --sample')


# --------------------------------------------------------------------------- #
# self-test
# --------------------------------------------------------------------------- #

def _fold(code):
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

    chk('T1 fold_render', fold_render('226420+6114915') == '6341335',
        fold_render('226420+6114915'))

    body = _fold('x=m(259459+-266860)')
    out = render_stmt(body[0], {-7401: 'FireServer'})
    chk('T2 m() substitution', out == 'x = "FireServer"', out)

    body = _fold('q[S[2]](x)')
    out = render_stmt(body[0], {})
    chk('T3 index/call chain', out == 'q[S[2]](x)', out)

    body = _fold('l,h=-265961+265961,q')
    out = render_stmt(body[0], {})
    chk('T4 multi-assign', out == 'l, h = 0, q', out)

    body = _fold('t={n=1}')
    out = render_stmt(body[0], {})
    chk('T5 table constructor', out == 't = {n = 1}', out)

    body = _fold('x=m(42)')
    out = render_stmt(body[0], {})
    chk('T6 m() miss kept verbatim', out == 'x = m(42)', out)

    print('')
    print('Result: %d/6' % (6 - len(fails)))
    if fails:
        print('[XX] FAILURES: %d' % len(fails))
        return 1
    print('[OK] ALL PASSED')
    return 0


if __name__ == '__main__':
    sys.exit(main())
