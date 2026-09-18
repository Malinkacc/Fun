"""WeAreDevs v1 dispatch-tree extractor (Sprint 7, slice 2c-1).

The real sample is NOT a bytecode VM: after the string-array decrypt it
runs a Prometheus-style flattened program.  One dispatcher function

    function(Q,q,S,A) local ... while Q do
        if Q>C then ... else ... end   -- nested binary search on Q
    end ... end

routes a numeric state variable Q through a tree of folded-constant
comparisons (``Q>699130+7433818``, ``2804890624%12750735>Q``).  Leaves are
linear basic blocks ending in a state update: ``Q=<const>`` (straight),
``Q=x and <const> or <const>`` (conditional branch), ``Q=nil`` (halt) or
``Q=<table lookup>`` (indirect).  The ~1.58 MB tree IS the program.

This module folds all constant arithmetic on the token stream, parses the
tree structurally, derives every leaf's [lo,hi] state range from its
comparison path, extracts the leaf transitions and validates that every
transition target lands in exactly one leaf range.

Usage:
    py -m obfuscator.deobfuscator.wearedevs.dispatch_map --test
    py -m obfuscator.deobfuscator.wearedevs.dispatch_map --sample path\\wearedevs.lua --outdir out
"""

import os
import re
import sys
import json
import bisect
import argparse

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

_KEYWORDS = {'and', 'break', 'do', 'else', 'elseif', 'end', 'false', 'for',
             'function', 'if', 'in', 'local', 'nil', 'not', 'or', 'repeat',
             'return', 'then', 'true', 'until', 'while'}
_MULTI_OPS = ('==', '~=', '<=', '>=', '..')
_SINGLE_OPS = set('+-*/%^#<>=(){}[];:,.')
_NUM_RE = re.compile(r'\d+\.\d+(?:[eE][+-]?\d+)?|\.\d+(?:[eE][+-]?\d+)?|\d+')
_NAME_RE = re.compile(r'[A-Za-z_][A-Za-z_0-9]*')


class ParseError(Exception):
    pass


def _s(ast):
    """Start offset of an AST node (nodes end with (..., start, end))."""
    return ast[-2]


def _e(ast):
    """End offset (exclusive) of an AST node."""
    return ast[-1]


# --------------------------------------------------------------------------- #
# 1. lexer
# --------------------------------------------------------------------------- #

def tokenize(text, base=0):
    """Lua-ish lexer.  Returns list of (kind, value, start, end) with
    kind in {name, num, str, kw, op}; positions relative to `base`."""
    toks = []
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if c in ' \t\r\n':
            i += 1
            continue
        if text.startswith('--', i):
            j = text.find('\n', i)
            i = n if j < 0 else j + 1
            continue
        m = _NAME_RE.match(text, i)
        if m:
            w = m.group(0)
            toks.append(('kw' if w in _KEYWORDS else 'name', w, base + i, base + m.end()))
            i = m.end()
            continue
        m = _NUM_RE.match(text, i)
        if m:
            w = m.group(0)
            val = int(w) if re.match(r'^\d+$', w) else float(w)
            toks.append(('num', val, base + i, base + m.end()))
            i = m.end()
            continue
        if c in '"\'':
            j = i + 1
            while j < n and text[j] != c:
                j += 2 if text[j] == '\\' else 1
            toks.append(('str', text[i + 1:j], base + i, base + min(j + 1, n)))
            i = j + 1
            continue
        for op in _MULTI_OPS:
            if text.startswith(op, i):
                toks.append(('op', op, base + i, base + i + 2))
                i += 2
                break
        else:
            if c in _SINGLE_OPS:
                toks.append(('op', c, base + i, base + i + 1))
                i += 1
            else:
                raise ParseError('lex: unexpected %r at %d' % (c, base + i))
    return toks


# --------------------------------------------------------------------------- #
# 2. constant folding on the token stream
# --------------------------------------------------------------------------- #

def _is_fold_tok(t):
    return t[0] == 'num' or (t[0] == 'op' and t[1] in '+-%()')


def fold_constants(toks):
    """Fold maximal runs of numeric/+-/%()/ tokens into single num tokens.

    A run may start at '-' or '(' only in prefix position (previous emitted
    token is a keyword or an op other than ')' / ']' -- i.e. NOT a call's
    argument parens after a name); otherwise it must start at a number.
    Trailing ')' beyond the run's paren balance are trimmed first so that
    e.g. ``m(-830474-(-823157))`` folds to ``m(-7317)`` without eating the
    call parens.  Returns (new_toks, folds)."""
    out = []
    folds = []
    i = 0
    n = len(toks)
    while i < n:
        t = toks[i]
        ok_start = False
        if _is_fold_tok(t):
            if t[0] == 'num':
                ok_start = True
            elif t[1] in ('-', '('):
                prev = out[-1] if out else None
                if prev is None or prev[0] == 'kw' or \
                        (prev[0] == 'op' and prev[1] not in (')', ']')):
                    ok_start = True
        if not ok_start:
            out.append(t)
            i += 1
            continue
        j = i
        while j < n and _is_fold_tok(toks[j]):
            j += 1
        # foldable prefix = longest run segment with balanced parens:
        # depth may return to 0 (include that ')'), never go negative
        # (that ')' closes an outer construct -- exclude it)
        end = None
        depth = 0
        for k in range(i, j):
            tk = toks[k]
            if tk[0] == 'op' and tk[1] == '(':
                depth += 1
            elif tk[0] == 'op' and tk[1] == ')':
                depth -= 1
                if depth < 0:
                    end = k - 1
                    break
                if depth == 0:
                    end = k
                    break
        if end is None:
            end = j - 1 if depth == 0 else None
        if end is None:
            out.extend(toks[i:j])
            i = j
            continue
        run = toks[i:end + 1]
        has_op = any(x[0] == 'op' and x[1] in '+-%' for x in run)
        has_num = any(x[0] == 'num' for x in run)
        val = None
        if has_op and has_num:
            expr = ''.join(str(x[1]) for x in run)
            try:
                val = eval(expr, {'__builtins__': {}}, {})
            except Exception:
                val = None
            if val is not None and abs(val) > 2 ** 53:
                val = None
        if val is not None:
            out.append(('num', val, run[0][2], run[-1][3]))
            folds.append((i, end + 1, val))
            i = end + 1
        else:
            out.extend(run)
            i = end + 1
    return out, folds


# --------------------------------------------------------------------------- #
# 3. structural parser (statements + expressions)
# --------------------------------------------------------------------------- #

_CMP_OPS = {'<', '>', '<=', '>=', '==', '~='}


class Parser(object):
    def __init__(self, toks, i=0, end=None):
        self.toks = toks
        self.i = i
        self.end = len(toks) if end is None else end
        self.if_nodes = 0

    def peek(self, k=0):
        j = self.i + k
        return self.toks[j] if j < self.end else None

    def at(self, kind, val=None, k=0):
        t = self.peek(k)
        return t is not None and t[0] == kind and (val is None or t[1] == val)

    def take(self):
        t = self.peek()
        if t is None:
            raise ParseError('unexpected EOF')
        self.i += 1
        return t

    def expect(self, kind, val=None):
        t = self.take()
        if t[0] != kind or (val is not None and t[1] != val):
            raise ParseError('expected %s %r got %r at %d' % (kind, val, t[1], t[2]))
        return t

    # ----- expressions (precedence climbing) ----- #
    def parse_expr(self):
        return self._binary(1)

    def _binary(self, lvl):
        if lvl > 6:
            return self._unary()
        ops = {1: ('or',), 2: ('and',), 3: _CMP_OPS, 4: ('..',),
               5: ('+', '-'), 6: ('*', '/', '%')}[lvl]
        left = self._binary(lvl + 1)
        while True:
            t = self.peek()
            if t is None:
                return left
            if t[0] == 'op':
                if t[1] not in ops:
                    return left
            elif lvl == 1 and t[0] == 'kw' and t[1] == 'or':
                pass
            elif lvl == 2 and t[0] == 'kw' and t[1] == 'and':
                pass
            else:
                return left
            self.take()
            right = self._binary(lvl + 1)
            left = ('bin', t[1], left, right, _s(left), _e(right))

    def _unary(self):
        t = self.peek()
        if t is not None and ((t[0] == 'op' and t[1] in ('-', '#'))
                              or (t[0] == 'kw' and t[1] == 'not')):
            self.take()
            e = self._unary()
            return ('un', t[1], e, t[2], _e(e))
        return self._pow()

    def _pow(self):
        base = self._postfix()
        t = self.peek()
        if t is not None and t[0] == 'op' and t[1] == '^':
            self.take()
            e = self._unary()
            return ('bin', '^', base, e, _s(base), _e(e))
        return base

    def _postfix(self):
        e = self._primary()
        while True:
            t = self.peek()
            if t is None:
                return e
            if t[0] == 'op' and t[1] == '(':
                self.take()
                args = []
                if not self.at('op', ')'):
                    args = self.parse_explist()
                close = self.expect('op', ')')
                e = ('call', e, args, _s(e), close[3])
            elif t[0] == 'op' and t[1] == '[':
                self.take()
                k = self.parse_expr()
                close = self.expect('op', ']')
                e = ('index', e, k, _s(e), close[3])
            elif t[0] == 'op' and t[1] == '.':
                self.take()
                nm = self.expect('name')
                e = ('index', e, ('str', nm[1], nm[2], nm[3]), _s(e), nm[3])
            else:
                return e

    def _table(self):
        o = self.expect('op', '{')
        fields = []
        if not self.at('op', '}'):
            while True:
                if self.at('op', '['):
                    self.take()
                    k = self.parse_expr()
                    self.expect('op', ']')
                    self.expect('op', '=')
                    v = self.parse_expr()
                    fields.append((k, v))
                elif self.at('name') and self.at('op', '=', 1):
                    nm = self.take()
                    self.take()
                    v = self.parse_expr()
                    fields.append((('str', nm[1], nm[2], nm[3]), v))
                else:
                    fields.append((None, self.parse_expr()))
                t = self.peek()
                if t is not None and t[0] == 'op' and t[1] in (',', ';'):
                    self.take()
                    if self.at('op', '}'):
                        break
                else:
                    break
        close = self.expect('op', '}')
        return ('table', fields, o[2], close[3])

    def _primary(self):
        t = self.peek()
        if t is None:
            raise ParseError('expr: EOF')
        if t[0] == 'name':
            self.take()
            return ('name', t[1], t[2], t[3])
        if t[0] == 'num':
            self.take()
            return ('num', t[1], t[2], t[3])
        if t[0] == 'str':
            self.take()
            return ('str', t[1], t[2], t[3])
        if t[0] == 'kw' and t[1] in ('nil', 'true', 'false'):
            self.take()
            return ('kw', t[1], t[2], t[3])
        if t[0] == 'op' and t[1] == '(':
            self.take()
            e = self.parse_expr()
            close = self.expect('op', ')')
            return ('paren', e, t[2], close[3])
        if t[0] == 'op' and t[1] == '{':
            return self._table()
        raise ParseError('expr: unexpected %r at %d' % (t[1], t[2]))

    def parse_explist(self):
        out = [self.parse_expr()]
        while self.at('op', ','):
            self.take()
            out.append(self.parse_expr())
        return out

    # ----- statements ----- #
    def parse_block(self, stops):
        """Parse statements until a stop keyword (not consumed) or EOF."""
        stmts = []
        while True:
            t = self.peek()
            if t is None:
                return stmts
            if t[0] == 'kw' and t[1] in stops:
                return stmts
            stmts.append(self.parse_statement())

    def parse_statement(self):
        t = self.peek()
        start = t[2]
        if t[0] == 'kw':
            if t[1] == 'local':
                self.take()
                names = [self.expect('name')]
                while self.at('op', ','):
                    self.take()
                    names.append(self.expect('name'))
                vals = []
                if self.at('op', '='):
                    self.take()
                    vals = self.parse_explist()
                end = _e(vals[-1]) if vals else names[-1][3]
                return ('local', [n[1] for n in names], vals, start, end)
            if t[1] == 'return':
                self.take()
                vals = []
                nt = self.peek()
                if nt is not None and not (nt[0] == 'kw' and nt[1] in ('end', 'else', 'elseif')) \
                        and not (nt[0] == 'op' and nt[1] == ';'):
                    vals = self.parse_explist()
                if self.at('op', ';'):
                    self.take()
                end = _e(vals[-1]) if vals else t[3]
                return ('return', vals, start, end)
            if t[1] == 'break':
                self.take()
                return ('break', start, t[3])
            raise ParseError('stmt: unexpected keyword %r at %d' % (t[1], t[2]))
        e = self.parse_expr()
        if self.at('op', ',') or self.at('op', '='):
            targets = [e]
            while self.at('op', ','):
                self.take()
                targets.append(self.parse_expr())
            self.expect('op', '=')
            vals = self.parse_explist()
            return ('assign', targets, vals, start, _e(vals[-1]))
        if e[0] != 'call':
            raise ParseError('stmt: expression statement is not a call at %d' % start)
        return ('callstat', e, start, _e(e))


# --------------------------------------------------------------------------- #
# 4. dispatch-tree walk
# --------------------------------------------------------------------------- #

def _q_target_idx(stmt):
    """Index of plain-name 'Q' target in an assign statement, else -1."""
    if stmt[0] != 'assign':
        return -1
    for k, tg in enumerate(stmt[1]):
        if tg[0] == 'name' and tg[1] == 'Q':
            return k
    return -1


def _count_state_assigns(stmts):
    return sum(1 for s in stmts if _q_target_idx(s) >= 0)


def _render(ast):
    k = ast[0]
    if k == 'num':
        return str(ast[1])
    if k in ('name', 'str', 'kw'):
        return str(ast[1])
    if k == 'bin':
        return '%s %s %s' % (_render(ast[2]), ast[1], _render(ast[3]))
    if k == 'un':
        return '%s%s' % (ast[1], _render(ast[2]))
    if k == 'paren':
        return '(%s)' % _render(ast[1])
    if k == 'call':
        return '%s(%s)' % (_render(ast[1]), ', '.join(_render(a) for a in ast[2]))
    if k == 'index':
        return '%s[%s]' % (_render(ast[1]), _render(ast[2]))
    if k == 'table':
        return '{...}'
    return k


def _classify_value(ast):
    """Classify a transition value AST -> (kind, targets, cond-note)."""
    if ast[0] == 'num':
        return ('straight', [ast[1]], '')
    if ast[0] == 'kw' and ast[1] == 'nil':
        return ('nil', [], '')
    if ast[0] == 'bin' and ast[1] == 'or':
        a, b = ast[2], ast[3]
        cond = ''
        xa = a
        if a[0] == 'bin' and a[1] == 'and':
            cond, xa = _render(a[2]), a[3]
        tg = []
        for side in (xa, b):
            tg.append(side[1] if side[0] == 'num' else None)
        if tg[0] is None and tg[1] is None:
            return ('indirect', tg, cond)
        return ('cond', tg, cond)
    if ast[0] in ('call', 'index', 'name', 'table', 'str'):
        return ('indirect', [None], '')
    return ('other', [None], _render(ast)[:40])


def _narrow(bounds, var, op, const, taken):
    """Narrow (lo, hi) after following branch `taken` of `var op const`."""
    lo, hi = bounds
    if var != 'Q' or const is None:
        return bounds

    def lo_at(v):
        return v if lo is None else max(lo, v)

    def hi_at(v):
        return v if hi is None else min(hi, v)

    if op == '>':
        return (lo_at(const + 1), hi) if taken else (lo, hi_at(const))
    if op == '<':
        return (lo, hi_at(const - 1)) if taken else (lo_at(const), hi)
    if op == '>=':
        return (lo_at(const), hi) if taken else (lo, hi_at(const - 1))
    if op == '<=':
        return (lo, hi_at(const)) if taken else (lo_at(const + 1), hi)
    if op == '==':
        return (const, const) if taken else bounds
    return bounds


def _pred_parts(pred):
    """Predicate token list -> (var, op, const|None).

    For the `CONST > Q` form the operator is flipped so that `op` always
    reads as `Q <op> CONST`."""
    if len(pred) == 3 and pred[1][0] == 'op':
        flip = {'>': '<', '<': '>', '>=': '<=', '<=': '>='}
        if pred[0][0] == 'name' and pred[2][0] == 'num':
            return (pred[0][1], pred[1][1], pred[2][1])
        if pred[2][0] == 'name' and pred[0][0] == 'num':
            return (pred[2][1], flip.get(pred[1][1], pred[1][1]), pred[0][1])
    return (None, '?', None)


def walk_tree(p, bounds, path, folded, leaves, stats):
    """Parse one if/elseif chain; record leaves with ranges + transitions."""
    p.expect('kw', 'if')
    cur_bounds = bounds
    cur_path = path
    while True:
        p.if_nodes += 1
        pred = []
        depth = 0
        while True:
            t = p.peek()
            if t is None:
                raise ParseError('pred: EOF')
            if t[0] == 'kw' and t[1] == 'then' and depth == 0:
                break
            if t[0] == 'op' and t[1] == '(':
                depth += 1
            elif t[0] == 'op' and t[1] == ')':
                depth -= 1
            pred.append(p.take())
        p.expect('kw', 'then')
        var, op, const = _pred_parts(pred)
        pred_txt = folded[pred[0][2]:pred[-1][3]]
        _walk_block(p, _narrow(cur_bounds, var, op, const, True),
                    cur_path + [(pred_txt, 'Y')], folded, leaves, stats)
        t = p.peek()
        if t is not None and t[0] == 'kw' and t[1] == 'elseif':
            p.take()
            cur_bounds = _narrow(cur_bounds, var, op, const, False)
            cur_path = cur_path + [(pred_txt, 'N')]
            continue
        break
    if t is not None and t[0] == 'kw' and t[1] == 'else':
        p.take()
        _walk_block(p, _narrow(cur_bounds, var, op, const, False),
                    cur_path + [(pred_txt, 'N')], folded, leaves, stats)
        p.expect('kw', 'end')
    else:
        p.expect('kw', 'end')
        nxt = p.peek()
        start_pos = nxt[2] if nxt is not None else pred[0][2]
        _record_leaf([], _narrow(cur_bounds, var, op, const, False),
                     cur_path + [(pred_txt, 'N')], folded, leaves, stats, start_pos)


def _walk_block(p, bounds, path, folded, leaves, stats):
    start = p.peek()
    if start is None:
        _record_leaf([], bounds, path, folded, leaves, stats, -1)
        return
    if start[0] == 'kw' and start[1] == 'if':
        walk_tree(p, bounds, path, folded, leaves, stats)
        return
    body = p.parse_block({'elseif', 'else', 'end'})
    end_tok = p.toks[p.i - 1] if p.i > 0 else None
    _record_leaf(body, bounds, path, folded, leaves, stats,
                 start[2], end_pos=(end_tok[3] if end_tok else start[3]))


def _record_leaf(body, bounds, path, folded, leaves, stats, start_pos, end_pos=None):
    li = len(leaves)
    lo, hi = bounds
    kinds = stats['kinds']
    n_q = _count_state_assigns(body)
    kind = 'empty'
    targets = []
    note = ''
    rhs = ''
    trans = None
    for st in reversed(body):
        if _q_target_idx(st) >= 0:
            trans = st  # transition = LAST assignment to Q in the block
            break
    if trans is not None:
        qi = _q_target_idx(trans)
        vals = trans[2]
        if qi < len(vals):
            val = vals[qi]
        elif vals and vals[-1][0] == 'call':
            val = vals[-1]  # expanding call feeds trailing targets
        else:
            val = ('kw', 'nil', trans[3], trans[3])  # extra target -> nil
        kind, targets, note = _classify_value(val)
        rhs = folded[_s(val):_e(val)][:80]
    elif body and body[-1][0] == 'return':
        kind = 'ret'
    elif body:
        kind = 'noq'
    else:
        kind = 'empty'
    kinds[kind] = kinds.get(kind, 0) + 1
    leaves.append({
        'id': li,
        'span': [start_pos, end_pos],
        'lo': lo,
        'hi': hi,
        'path': path,
        'kind': kind,
        'targets': targets,
        'note': note[:60],
        'rhs': rhs,
        'n_q': n_q,
        'n_stmts': len(body),
    })


def resolve_target(leaves_sorted, los, target):
    if target is None:
        return None
    k = bisect.bisect_right(los, target) - 1
    if k < 0:
        return None
    leaf = leaves_sorted[k]
    if leaf['hi'] is not None and target > leaf['hi']:
        return None
    return leaf['id']


def extract_entry(text):
    """Entry state from the tail: `return(NAME(CONST,{}))( ... )`.

    CONST may be unfolded arithmetic (``5260728-625368``) -- it is then
    evaluated (digits/operators only, safe)."""
    ms = list(re.finditer(r'(\w+)\((-?[\d%+()-]+),\{\}\)\)\(', text))
    if not ms:
        return None, None
    m = ms[-1]
    raw = m.group(2)
    if re.match(r'^-?\d+$', raw):
        return m.group(1), int(raw)
    try:
        return m.group(1), int(eval(raw, {'__builtins__': {}}, {}))
    except Exception:
        return m.group(1), None


# --------------------------------------------------------------------------- #
# 5. sample driver
# --------------------------------------------------------------------------- #

def analyze_source(src):
    """Full analysis of an obfuscated WeAreDevs sample.  Returns info dict."""
    wpos = src.rfind('while Q do')
    if wpos < 0:
        raise ValueError('dispatch loop not found')
    fpos = src.rfind('function(', 0, wpos)
    if fpos < 0:
        raise ValueError('dispatcher function not found')
    tail_anchor = src.find('end)(setmetatable', fpos)
    if tail_anchor < 0:
        tail_anchor = len(src)
    toks = tokenize(src[fpos:tail_anchor], base=fpos)
    toks, folds = fold_constants(toks)

    # folded text: gaps verbatim, folded num tokens printed as values
    pieces = []
    last = fpos
    for t in toks:
        pieces.append(src[last:t[2]])
        pieces.append(str(t[1]) if t[0] == 'num' else src[t[2]:t[3]])
        last = t[3]
    pieces.append(src[last:tail_anchor])
    folded_text = ''.join(pieces)

    p = Parser(toks, 0)
    # skip the dispatcher function header + locals up to the while loop
    while not p.at('kw', 'while'):
        if p.peek() is None:
            raise ValueError('while not found in dispatcher')
        p.take()
    p.expect('kw', 'while')
    cond = p.parse_expr()
    p.expect('kw', 'do')
    while not p.at('kw', 'if'):
        if p.peek() is None:
            raise ValueError('if-tree not found in dispatcher')
        p.parse_statement()
    leaves = []
    stats = {'kinds': {}}
    walk_tree(p, (None, None), [], folded_text, leaves, stats)
    trailing = p.parse_block({'end'})
    if p.at('kw', 'end'):
        p.take()

    bounded = sorted(leaves,
                     key=lambda lf: (lf['lo'] if lf['lo'] is not None else -(1 << 62)))
    los = [lf['lo'] if lf['lo'] is not None else -(1 << 62) for lf in bounded]
    total_t = 0
    resolved_t = 0
    for lf in leaves:
        for tg in lf['targets']:
            if tg is None:
                continue
            total_t += 1
            if resolve_target(bounded, los, tg) is not None:
                resolved_t += 1

    fname, entry = extract_entry(folded_text)
    entry_leaf = resolve_target(bounded, los, entry) if entry is not None else None

    distinct = set()
    for lf in leaves:
        for tg in lf['targets']:
            if tg is not None:
                distinct.add(tg)

    return {
        'region': [fpos, tail_anchor],
        'region_chars': tail_anchor - fpos,
        'fold_ops': len(folds),
        'if_nodes': p.if_nodes,
        'leaves': leaves,
        'trailing_stmts': [s[0] for s in trailing],
        'while_cond': _render(cond),
        'kinds': stats['kinds'],
        'total_targets': total_t,
        'resolved_targets': resolved_t,
        'resolve_pct': (100.0 * resolved_t / total_t) if total_t else 0.0,
        'distinct_states': len(distinct),
        'entry_fn': fname,
        'entry': entry,
        'entry_leaf': entry_leaf,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description='WeAreDevs dispatch-tree extractor')
    ap.add_argument('--test', action='store_true')
    ap.add_argument('--sample', default=None)
    ap.add_argument('--outdir', default=None)
    ap.add_argument('--show', type=int, default=12)
    a = ap.parse_args(argv)
    if a.test:
        return _selftest()
    if a.sample:
        src = open(a.sample, encoding='utf-8', errors='replace').read()
        info = analyze_source(src)
        print('region=%d chars ; fold ops=%d ; if nodes=%d ; while cond: %s' %
              (info['region_chars'], info['fold_ops'], info['if_nodes'],
               info['while_cond']))
        print('leaves=%d ; distinct states=%d ; entry=%s (fn %s) -> leaf %s' %
              (len(info['leaves']), info['distinct_states'], info['entry'],
               info['entry_fn'], info['entry_leaf']))
        print('kinds: %s' % ', '.join('%s=%d' % kv for kv in sorted(info['kinds'].items())))
        print('transitions: %d ; resolved in-range: %d (%.1f%%)' %
              (info['total_targets'], info['resolved_targets'], info['resolve_pct']))
        print('trailing after tree: %s' % info['trailing_stmts'])
        for lf in info['leaves'][:a.show]:
            print('  leaf %-5d [%s..%s] %-8s -> %s %s' %
                  (lf['id'], lf['lo'], lf['hi'], lf['kind'], lf['targets'],
                   ('; ' + lf['rhs']) if lf['rhs'] else ''))
        if a.outdir:
            if not os.path.isdir(a.outdir):
                os.makedirs(a.outdir)
            path = os.path.join(a.outdir, 'wd_dispatch.json')
            with open(path, 'w', encoding='utf-8') as fh:
                json.dump(info, fh, ensure_ascii=False, indent=1)
            print('saved -> %s' % path)
        return 0
    ap.error('use --test or --sample')


# --------------------------------------------------------------------------- #
# self-test
# --------------------------------------------------------------------------- #

def _walk_mini(code):
    toks = tokenize(code)
    toks, _ = fold_constants(toks)
    p = Parser(toks, 0)
    while not p.at('kw', 'if') and p.peek() is not None:
        if p.at('kw', 'while'):
            p.take()
            p.parse_expr()
            p.expect('kw', 'do')
            continue
        if p.at('kw', 'function'):
            p.take()
            while not p.at('op', ')'):
                p.take()
            p.take()
            continue
        p.parse_statement()
    leaves = []
    stats = {'kinds': {}}
    folded = code
    walk_tree(p, (None, None), [], folded, leaves, stats)
    return leaves, stats, folded


def _selftest():
    fails = []

    def chk(tag, cond, extra=''):
        print(('[OK] ' if cond else '[XX] ') + tag + (' ' + extra if extra else ''))
        if not cond:
            fails.append(tag)

    # T1 token-stream constant folding
    toks = tokenize('x and -220732+3143016 or m(-830474-(-823157)) q[645193-645191] x2 Q[l]')
    ft, folds = fold_constants(toks)
    nums = [t[1] for t in ft if t[0] == 'num']
    chk('T1 fold consts', nums == [2922284, -7317, 2], str(nums))

    # T2 + T3 tree parse: 4 leaves, ranges, transition kinds
    code = ('while Q do if Q>10 then if 15>Q then A=1 Q=12 else A=2 Q=nil end '
            'else if Q<5 then Q=x and 3 or 7 else Q=1 end end end')
    leaves, stats, _ = _walk_mini(code)
    rng = [(lf['lo'], lf['hi']) for lf in leaves]
    want = [(11, 14), (15, None), (None, 4), (5, 10)]
    chk('T2 leaf ranges', len(leaves) == 4 and rng == want,
        '%d leaves %s' % (len(leaves), rng))
    kinds = {lf['id']: lf['kind'] for lf in leaves}
    tg = {lf['id']: lf['targets'] for lf in leaves}
    chk('T3 transition kinds',
        kinds == {0: 'straight', 1: 'nil', 2: 'cond', 3: 'straight'}
        and tg[0] == [12] and tg[2] == [3, 7] and tg[3] == [1],
        str((kinds, tg)))

    # T4 range resolution: full coverage of the sample tree + a bounded miss
    bounded = sorted(leaves, key=lambda lf: lf['lo'] if lf['lo'] is not None else -(1 << 62))
    los = [lf['lo'] if lf['lo'] is not None else -(1 << 62) for lf in bounded]
    res = [resolve_target(bounded, los, v) for v in (12, 3, 7, 1, 999)]
    miss = resolve_target([{'id': 9, 'lo': 11, 'hi': 14}], [11], 999)
    chk('T4 target resolution',
        res == [0, 2, 3, 2, 1] and miss is None, '%s miss=%s' % (res, miss))

    # T5 entry extraction
    fn, en = extract_entry('end return(B(5260728-625368,{}))(Y(l))end')
    chk('T5 entry extraction', fn == 'B' and en == 4635360, '%s %s' % (fn, en))

    # T6 mini end-to-end: straight + multi-assign tail + indirect lookup
    mini = ('function(Q,q,S,A)local yS={} while Q do '
            'if Q>20 then if 30>Q then Q=25 else l,Q=g,x end '
            'else Q=W[S[4]] end end end return(B(25,{}))(Y(l))')
    leaves, stats, _ = _walk_mini(mini)
    kinds6 = sorted(lf['kind'] for lf in leaves)
    tg6 = sorted(t for lf in leaves for t in lf['targets'] if t is not None)
    fn6, en6 = extract_entry('return(B(25,{}))(Y(l))')
    chk('T6 mini tree multi-assign/indirect',
        len(leaves) == 3 and kinds6 == ['indirect', 'indirect', 'straight']
        and tg6 == [25] and fn6 == 'B' and en6 == 25,
        '%d leaves %s tg=%s entry=%s' % (len(leaves), kinds6, tg6, en6))

    print('')
    print('Result: %d/6' % (6 - len(fails)))
    if fails:
        print('[XX] FAILURES: %d' % len(fails))
        return 1
    print('[OK] ALL PASSED')
    return 0


if __name__ == '__main__':
    sys.exit(main())
