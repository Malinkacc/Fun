"""MoonSec V3 opcode semantics (slice 2b-9 part 2).

Turns the VM dispatch guard tree (msvm_dispatch) into per-opcode CANONICAL
register-transfer effects and Lua 5.1 style mnemonics.

Why a second module: inside composite handlers the obfuscator REUSES the
opcode variable for state-machine unrollers (``f=0; while f>-1 do ... end``)
and single-iteration dummy for-selectors, so a plain opcode-guard walk would
mistake state guards for opcode guards.  The pipeline here is context-aware:

1. op-walk: conditions with subject ``f`` split the candidate opcode set
   (fall-through/elif/``repeat if f~=K then BODY;break;end FALL`` semantics
   identical to msvm_dispatch); ``VAR=0; while VAR>-1 do`` headers become SM
   markers; runtime conditions are opaque raw (as in the source).
2. per opcode, each SM marker is expanded with a state walker: conditions on
   the state var split the STATE set (states 0,1,2,... execute in order,
   ``VAR=-2`` terminates the machine), conditions on anything else are
   RUNTIME choices and BOTH branches are kept (marked ALT).
3. the ordered statement stream is run through a symbolic ALIAS EXECUTOR:
   obfuscated temporaries (``f=e; r=d; h=c; t=f[r]; h=s[f[o]]; l[t]=h``)
   resolve to canonical operands (A/B/C fields, R[x], K[x], G[x], U[x]...),
   producing register-transfer effects (R[A] := R[B], R[A][B] := R[C], ...).
4. effects are classified into Lua 5.1 style mnemonics; superinstructions
   (fused chains) keep their full effect list; anything unresolved stays
   COMPLEX/ALT -- nothing is guessed.

Results on the real sample (commit 3239547 tree): all 160 dispatch
opcodes resolve with ZERO unresolved markers (159 "fully-named" + op 152's
phantom-tail group); the 90 opcodes actually used by the embedded program
(516 instructions) map to Lua 5.1 families:

    JMP(x37) MOVE LOADK SETGLOBAL GETUPVAL FORLOOP FORPREP CLOSE_UV
    RETURN_1/_m/_0 GETGLOBAL GETTABLE SETTABLE NEWTABLE LOADBOOL LOADNIL
    TEST TESTN TESTSET EQ_C/EQ_K NE_C/NE_R LT/LE CALL_0 CALLC TAILCALL
    VARARG SELF CONCAT CLOSURE ADD/SUB/MUL/MOD/POW LEN NOP

plus SUPERINSTRUCTIONS (fused chains), e.g. op 122 =
LOADK x5 + GETTABLE, op 9 = 5x LOADIMM + CALL, op 18 =
LOADBOOL+SETUPVAL+GETUPVAL+NEWTABLE x3+LOADIMM, op 88/144 =
MOVE+GETUPVAL+CALL(+SELF...).  Opcode 24 records in the sample are all
CLOSURE upvalue descriptors (positional; its dispatch body is unused).

Usage:"""

import os
import re
import sys
import json
import argparse
from collections import defaultdict

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from obfuscator.deobfuscator.moonsec.msvm_dispatch import (
    stage2_constants, tokenize, VM_HEAD, FETCH, FLIP,
)

MAX_STATES = 11


# --------------------------------------------------------------------------- #
# extended structural parser (if / raw / while / for nodes)
# --------------------------------------------------------------------------- #

class Opq(Exception):
    pass


class XParser(object):
    """Items:
      ('if', node)                    node={'cond':(op,c),'subj':var,'then','elif','else'}
      ('raw', a, b)                   flat token span
      ('while', var, a, b, items)     state-machine header  VAR > -1
      ('whileq', a, b)                other while (flat)
      ('for', var, lo, hi, a, b, items)  numeric for, literal bounds
      ('forq', a, b)                  other for (flat)
    """

    def __init__(self, toks, consts=None):
        self.toks = toks
        self.consts = consts or {}

    def skip_to_matching_end(self, i):
        toks = self.toks
        depth = expect_do = rep = 0
        j = i
        while j < len(toks):
            k, v = toks[j]
            if k == 'name':
                if v in ('for', 'while'):
                    depth += 1
                    expect_do += 1
                elif v == 'function':
                    depth += 1
                elif v == 'do':
                    if expect_do > 0:
                        expect_do -= 1
                    else:
                        depth += 1
                elif v == 'if':
                    depth += 1
                elif v == 'repeat':
                    rep += 1
                elif v == 'until':
                    rep -= 1
                elif v == 'end':
                    depth -= 1
                    if depth == 0 and rep <= 0 and expect_do <= 0:
                        return j + 1
            j += 1
        raise SyntaxError('no matching end from %d' % i)

    def parse_block(self, i, stop):
        toks = self.toks
        items = []
        depth = expect_do = rep = 0
        i0 = i
        while i < len(toks):
            k, v = toks[i]
            if depth == 0 and rep == 0 and expect_do == 0 and k == 'name' and v in stop:
                if i > i0:
                    items.append(('raw', i0, i))
                return items, i, v
            if k == 'name':
                if v in ('for', 'while'):
                    node, i2 = self.parse_loop(i)
                    if node is None:
                        i2 = self.skip_to_matching_end(i)
                        items.append(('whileq' if v == 'while' else 'forq', i, i2))
                    else:
                        items.append(node)
                    i = i2
                    i0 = i
                    continue
                elif v == 'function':
                    depth += 1
                elif v == 'do':
                    if expect_do > 0:
                        expect_do -= 1
                    else:
                        depth += 1
                elif v == 'repeat':
                    rep += 1
                elif v == 'until':
                    rep -= 1
                elif v == 'end':
                    if depth > 0:
                        depth -= 1
                elif v == 'if':
                    try:
                        node, i2 = self.parse_if(i)
                    except Opq:
                        i2 = self.skip_to_matching_end(i)
                        items.append(('raw', i, i2))
                        i = i2
                        i0 = i
                        continue
                    items.append(('if', node))
                    i = i2
                    i0 = i
                    continue
            i += 1
        raise SyntaxError('unclosed block from token %d' % i0)

    def cond_subject(self, j0, j):
        ct = self.toks[j0:j]
        if 3 <= len(ct) <= 4:
            oi = None
            for i in range(len(ct)):
                k, v = ct[i]
                if k == 'op' and v in FLIP:
                    oi = i
                    break
            if oi is None:
                return None
            opv = ct[oi][1]
            lhs = ct[:oi]
            rhs = ct[oi + 1:]

            def as_var(part):
                if len(part) == 1 and part[0][0] == 'name':
                    return part[0][1]
                return None

            def as_const(part):
                if len(part) == 1:
                    k, v = part[0]
                    if k == 'num':
                        return int(float(v))
                    if k == 'hname' and v[2:] in self.consts:
                        return self.consts[v[2:]]
                if len(part) == 2 and part[0][1] == '-' and part[1][0] == 'num':
                    return -int(float(part[1][1]))
                return None
            lv = as_var(lhs)
            if lv is not None:
                cv = as_const(rhs)
                if cv is not None:
                    return lv, opv, cv
            rv = as_var(rhs)
            if rv is not None:
                cv = as_const(lhs)
                if cv is not None:
                    return rv, FLIP[opv], cv
        return None

    def parse_loop(self, i):
        toks = self.toks
        v = toks[i][1]
        j = i + 1
        if v == 'while':
            j0 = j
            while not (toks[j][0] == 'name' and toks[j][1] == 'do'):
                j += 1
            seg = toks[j0:j]
            if (len(seg) == 4 and seg[0][0] == 'name' and seg[1][1] == '>'
                    and seg[2][1] == '-' and seg[3][1] == '1'):
                var = seg[0][1]
                items, j2, _kw = self.parse_block(j + 1, ('end',))
                return ('while', var, i, j2 + 1, items), j2 + 1
            return None, i
        if v == 'for':
            if toks[j][0] != 'name' or toks[j + 1][1] != '=' or toks[j + 2][0] != 'num':
                return None, i
            var = toks[j][1]
            lo = int(float(toks[j + 2][1]))
            if toks[j + 3][1] != ',' or toks[j + 4][0] != 'num':
                return None, i
            hi = int(float(toks[j + 4][1]))
            if not (toks[j + 5][0] == 'name' and toks[j + 5][1] == 'do'):
                return None, i
            items, j2, _kw = self.parse_block(j + 6, ('end',))
            return ('for', var, lo, hi, i, j2 + 1, items), j2 + 1
        return None, i

    def parse_if(self, i):
        toks = self.toks
        j = i + 1
        j0 = j
        while not (toks[j][0] == 'name' and toks[j][1] == 'then'):
            j += 1
        subj = self.cond_subject(j0, j)
        if subj is None:
            raise Opq(toks[j0:j])
        j += 1
        items, j, kw = self.parse_block(j, ('else', 'elseif', 'end'))
        node = {'cond': (subj[1], subj[2]), 'subj': subj[0], 'then': items,
                'elif': None, 'else': None, 'pos': i}
        if kw == 'elseif':
            node['elif'], j = self.parse_if(j)
        elif kw == 'else':
            eitems, j, _kw2 = self.parse_block(j + 1, ('end',))
            node['else'] = eitems
            j += 1
        else:
            j += 1
        return node, j


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #

def _split_set(S, op, c):
    st = set()
    for x in S:
        if ((op == '<' and x < c) or (op == '<=' and x <= c)
                or (op == '>' and x > c) or (op == '>=' and x >= c)
                or (op == '==' and x == c) or (op == '~=' and x != c)):
            st.add(x)
    return st, S - st


_TOKS = []


def item_tokens(items):
    out = []
    for it in items:
        if it[0] == 'raw':
            out.extend(t[1] for t in _TOKS[it[1]:it[2]])
        elif it[0] == 'if':
            nd = it[1]
            out.extend(item_tokens(nd['then']))
            if nd['elif']:
                out.extend(item_tokens([('if', nd['elif'])]))
            if nd['else']:
                out.extend(item_tokens(nd['else']))
        elif it[0] in ('while', 'for'):
            out.extend(item_tokens(it[-1]))
    return out


def falls_through(items):
    tt = item_tokens(items)
    return not ('break' in tt or 'return' in tt)


def split_statements(toks, a, b):
    """Split a token span into statements at depth-0 ';' boundaries."""
    stmts = []
    cur = []
    depth = 0
    expect_do = 0
    rep = 0
    for i in range(a, b):
        k, v = toks[i]
        if depth == 0 and rep == 0 and expect_do == 0 and v == ';' and k == 'op':
            if cur:
                stmts.append(cur)
            cur = []
            continue
        if k == 'name':
            if v in ('for', 'while'):
                depth += 1
                expect_do += 1
            elif v == 'function':
                depth += 1
            elif v == 'if':
                depth += 1
            elif v == 'do':
                if expect_do > 0:
                    expect_do -= 1
                else:
                    depth += 1
            elif v == 'repeat':
                rep += 1
            elif v == 'until':
                rep -= 1
            elif v == 'end':
                depth -= 1
        cur.append((k, v))
    if cur:
        stmts.append(cur)
    return stmts


# --------------------------------------------------------------------------- #
# pass 1: opcode-context walk -> per-op ordered stream (with SM markers)
# --------------------------------------------------------------------------- #

def op_walk(items, S, out):
    S = set(S)
    for it in items:
        if not S:
            break
        kind = it[0]
        if kind == 'raw':
            for stmt in split_statements(_TOKS, it[1], it[2]):
                for op in sorted(S):
                    out[op].append(list(stmt))
        elif kind in ('whileq', 'forq'):
            for stmt in split_statements(_TOKS, it[-2], it[-1]):
                for op in sorted(S):
                    out[op].append(list(stmt))
        elif kind == 'while':
            _, var, _a, _b, witems = it
            for op in sorted(S):
                out[op].append(('SM', var, witems))
        elif kind == 'for':
            _, _fv, _lo, _hi, _a, _b, fitems = it
            op_walk(fitems, S, out)
        elif kind == 'if':
            nd = it[1]
            op_, c = nd['cond']
            st, se = _split_set(S, op_, c)
            op_walk(nd['then'], st, out)
            cur = se
            nd2 = nd['elif']
            while nd2 is not None:
                st2, se2 = _split_set(cur, nd2['cond'][0], nd2['cond'][1])
                op_walk(nd2['then'], st2, out)
                if nd2['else'] is not None:
                    op_walk(nd2['else'], se2, out)
                    cur = set()
                elif not st2:
                    cur = se2
                else:
                    cur = se2 | (st2 if falls_through(nd2['then']) else set())
                nd2 = nd2['elif']
            if nd['else'] is not None:
                op_walk(nd['else'], cur, out)
                cur = set()
            else:
                if falls_through(nd['then']):
                    cur = cur | st
            S = cur


# --------------------------------------------------------------------------- #
# pass 2: state-machine expansion
# --------------------------------------------------------------------------- #

def sm_expand(var, items, out_by_state, S):
    """Attribute statements to states; conditions on `var` split states."""
    S = set(S)
    for it in items:
        if not S:
            break
        kind = it[0]
        if kind == 'raw':
            stmts = split_statements(_TOKS, it[1], it[2])
            for op_state in sorted(S):
                for stmt in stmts:
                    out_by_state[op_state].append(list(stmt))
        elif kind in ('whileq', 'forq'):
            stmts = split_statements(_TOKS, it[-2], it[-1])
            for op_state in sorted(S):
                for stmt in stmts:
                    out_by_state[op_state].append(list(stmt))
        elif kind == 'while':
            _, var2, _a, _b, witems = it
            # nested state machine: expand fully (states 0..MAX) at this point
            inner = defaultdict(list)
            sm_expand(var2, witems, inner, set(range(0, MAX_STATES + 1)))
            merged = _merge_states(inner)
            for op_state in sorted(S):
                out_by_state[op_state].extend(merged)
        elif kind == 'for':
            _, _fv, _lo, _hi, _a, _b, fitems = it
            sm_expand(var, fitems, out_by_state, S)
        elif kind == 'if':
            nd = it[1]
            op_, c = nd['cond']
            if nd['subj'] == var:
                st, se = _split_set(S, op_, c)
                sm_expand(var, nd['then'], out_by_state, st)
                cur = se
                nd2 = nd['elif']
                while nd2 is not None:
                    st2, se2 = _split_set(cur, nd2['cond'][0], nd2['cond'][1])
                    sm_expand(var, nd2['then'], out_by_state, st2)
                    if nd2['else'] is not None:
                        sm_expand(var, nd2['else'], out_by_state, se2)
                        cur = set()
                    elif not st2:
                        cur = se2
                    else:
                        cur = se2 | (st2 if falls_through(nd2['then']) else set())
                    nd2 = nd2['elif']
                if nd['else'] is not None:
                    sm_expand(var, nd['else'], out_by_state, cur)
                    cur = set()
                else:
                    if falls_through(nd['then']):
                        cur = cur | st
                S = cur
            else:
                # runtime condition: keep both branches (source order)
                for op_state in sorted(S):
                    out_by_state[op_state].append(['ALT'])
                sm_expand(var, nd['then'], out_by_state, S)
                cur = S
                nd2 = nd['elif']
                while nd2 is not None:
                    for op_state in sorted(S):
                        out_by_state[op_state].append(['ALT'])
                    sm_expand(var, nd2['then'], out_by_state, cur)
                    if nd2['else'] is not None:
                        for op_state in sorted(S):
                            out_by_state[op_state].append(['ALT'])
                        sm_expand(var, nd2['else'], out_by_state, cur)
                    cur = cur | (set() if nd2['else'] is not None
                                 else _kept(cur, nd2['cond'], nd2['then']))
                    nd2 = nd2['elif']
                if nd['else'] is not None:
                    for op_state in sorted(S):
                        out_by_state[op_state].append(['ALT'])
                    sm_expand(var, nd['else'], out_by_state, cur)
                S = cur


def _kept(S, cond, items):
    st, _se = _split_set(S, cond[0], cond[1])
    return st if falls_through(items) else set()


def _merge_states(inner):
    """Ordered statements across states 0..MAX; stop after VAR=-2 state."""
    out = []
    for state in sorted(inner):
        stmts = inner[state]
        out.extend(stmts)
        if any(_is_terminator(s) for s in stmts):
            break
    return out


def sm_states(var, items, max_state=MAX_STATES):
    """Dynamic per-state expansion: walk ONE state at a time (no phantom
    states -> no duplicated fall-through tails).  Returns the ordered
    statement stream and the number of real states seen."""
    full = []
    seen = 0
    for state in range(0, max_state + 1):
        inner = defaultdict(list)
        sm_expand(var, items, inner, {state})
        stmts = inner.get(state, [])
        if not stmts and state > 0:
            break
        full.extend(stmts)
        seen = state + 1
        if any(_is_terminator(s) for s in stmts):
            break
    return full, seen


def _is_terminator(stmt_tokens):
    # pattern: VAR = - 2
    t = [x[1] for x in stmt_tokens]
    return len(t) >= 4 and t[1] == '=' and t[2] == '-' and t[3] == '2'


# --------------------------------------------------------------------------- #
# pass 3: alias executor
# --------------------------------------------------------------------------- #

class Expr(object):
    __slots__ = ('kind', 'a', 'b', 'c')

    def __init__(self, kind, a=None, b=None, c=None):
        self.kind = kind
        self.a = a
        self.b = b
        self.c = c

    def __repr__(self):
        return 'Expr(%r,%r,%r,%r)' % (self.kind, self.a, self.b, self.c)


def render_expr(x):
    k = x.kind
    if k == 'name':
        return str(x.a)
    if k == 'num':
        return str(x.a)
    if k == 'str':
        return repr(x.a)
    if k == 'idx':
        return '%s[%s]' % (render_expr(x.a), render_expr(x.b))
    if k == 'bin':
        return '(%s %s %s)' % (render_expr(x.a), x.b, render_expr(x.c))
    if k == 'un':
        return '%s%s' % (x.b, render_expr(x.a))
    if k == 'call':
        return '%s(%s)' % (render_expr(x.a), ','.join(render_expr(z) for z in (x.b or [])))
    if k == 'nil':
        return 'nil'
    if k == 'tbl':
        return str(x.a)
    if k == 'fld':
        return str(x.a)
    if k == 'reg':
        return str(x.a)
    if k == 'fn':
        return str(x.a)
    return '?%s' % k


class Executor(object):
    """Resolves aliases and emits canonical effects for one opcode."""

    def __init__(self):
        self.env = {
            'e': Expr('reg', 'INSTR'),
            'd': Expr('fld', 'A'),
            'c': Expr('fld', 'B'),
            'r': Expr('fld', 'C'),
            'g': Expr('fld', 'OP'),
            'l': Expr('tbl', 'R'),
            'o': Expr('tbl', 'G'),
            'm': Expr('tbl', 'U'),
            'k': Expr('tbl', 'K'),
            't': Expr('tbl', 'T'),
            'n': Expr('reg', 'pc'),
            's': Expr('fn', 'unpack'),
            'a': Expr('num', -1),
            'b': Expr('tbl', 'OPENUP'),
            'j': Expr('num', 'J'),
            'p': Expr('reg', 'ARGC'),
            'y': Expr('tbl', 'VARARGS'),
            'ne': Expr('num', 0),
        }
        self.effects = []
        self.unresolved = 0
        self.alts = 0
        self.steps = 0
        self.shadow = False
        self._pending_step = False

    # ---- expression parser over statement tokens ----
    def parse(self, tk, i=0, minp=0):
        tok = tk[i] if i < len(tk) else (None, None)
        BINP = {'or': 1, 'and': 2, '<': 3, '<=': 3, '>': 3, '<=': 3, '>=': 3,
                '==': 3, '~=': 3, '..': 5, '+': 6, '-': 6, '*': 7, '/': 7,
                '%': 7, '^': 9}
        x, i = self.parse_unary(tk, i)
        while i < len(tk):
            k, v = tk[i]
            if k == 'op' and v in BINP and BINP[v] >= minp and BINP[v] > 2:
                p = BINP[v]
                y, i = self.parse(tk, i + 1, p + 1)
                x = Expr('bin', x, v, y)
                continue
            break
        return x, i

    def parse_unary(self, tk, i):
        k, v = tk[i] if i < len(tk) else (None, None)
        if k == 'op' and v in ('-', '#', 'not'):
            y, i = self.parse_unary(tk, i + 1)
            return Expr('un', y, v), i
        return self.parse_postfix(tk, i)

    def parse_postfix(self, tk, i):
        x, i = self.parse_primary(tk, i)
        while i < len(tk):
            k, v = tk[i]
            if v == '[':
                y, i = self.parse(tk, i + 1, 0)
                if i < len(tk) and tk[i][1] == ']':
                    i += 1
                x = Expr('idx', x, y)
            elif v == '(':
                args = []
                if i + 1 < len(tk) and tk[i + 1][1] == ')':
                    i += 2
                else:
                    while True:
                        y, i = self.parse(tk, i + 1, 0)
                        args.append(y)
                        if i < len(tk) and tk[i][1] == ',':
                            continue
                        break
                    if i < len(tk) and tk[i][1] == ')':
                        i += 1
                x = Expr('call', x, args)
            else:
                break
        return x, i

    def parse_primary(self, tk, i):
        k, v = tk[i] if i < len(tk) else (None, None)
        if k == 'name':
            return self.resolve_name(v), i + 1
        if k == 'num':
            return Expr('num', int(float(v))), i + 1
        if k == 'str':
            return Expr('str', v), i + 1
        if k == 'op' and v == '(':
            x, i = self.parse(tk, i + 1, 0)
            if i < len(tk) and tk[i][1] == ')':
                i += 1
            return x, i
        if k == 'op' and v == '{':
            return Expr('tblcons'), i + 1
        return Expr('nil'), i

    def resolve_name(self, name):
        return self.env.get(name, Expr('name', name))

    # ---- statement processing ----
    def run_stmt(self, tk):
        t = [x[1] for x in tk]
        if not t:
            return
        if t[0] == 'local':
            if len(tk) >= 3 and tk[1][0] == 'name' and tk[2][1] == '=':
                try:
                    val, _i2 = self.parse(tk, 3, 0)
                except Exception:
                    val = Expr('nil')
                if tk[1][1] in ('n', 'e'):
                    self.shadow = True
                    self.env[tk[1][1]] = val
                else:
                    self.assign_name(tk[1][1], val)
            return
        if t[0] in ('until', 'end', 'else', 'elseif', 'then'):
            return
        if t[0] == 'do' and 'return' not in t:
            return
        if t == ['break'] or t == ['ALT']:
            if t == ['ALT']:
                self.alts += 1
            return
        if t[0] == 'do' and 'return' in t:
            self.effects.append(('RETURN', list(tk)))
            return
        if t[0] == 'return':
            self.effects.append(('RETURN', list(tk)))
            return
        if t[0] == 'if':
            self.effects.append(('TESTRAW', list(tk)))
            return
        if t[0] == 'for':
            self.effects.append(('FORRAW', list(tk)))
            return
        if t[0] == 'while':
            self.effects.append(('WHILERAW', list(tk)))
            return
        # assignment/call statement
        # LHS = single name -> alias assignment
        if len(tk) >= 2 and tk[0][0] == 'name' and tk[1][1] == '=':
            name = tk[0][1]
            try:
                val, _i2 = self.parse(tk, 2, 0)
            except Exception:
                val = Expr('nil')
            self.assign_name(name, val)
            return
        try:
            x, i = self.parse(tk, 0, 0)
        except Exception:
            x, i = Expr('nil'), 0
        if i < len(tk) and tk[i][1] == '=':
            if x.kind == 'idx' and x.a.kind == 'tbl' and x.a.a in ('R', 'G', 'U'):
                try:
                    val, _i2 = self.parse(tk, i + 1, 0)
                except Exception:
                    val = Expr('nil')
                self.emit_store(x, val)
                return
            if x.kind == 'idx':
                try:
                    val, _i2 = self.parse(tk, i + 1, 0)
                except Exception:
                    val = Expr('nil')
                self.effects.append(('SETIDX', x, val))
                return
        # bare expression statement: proxy call l(a,b) / l(a) etc.
        self.bare_expr(x, tk)

    def assign_name(self, name, val):
        if self.shadow and name in ('n', 'e'):
            self.env[name] = val
            return
        # special registers tracked by canonical identity
        if name == 'n':
            if val.kind == 'bin' and val.b == '+' and render_expr(val.a) == 'pc' \
                    and render_expr(val.c) == '1':
                self._pending_step = True
                return
            if val.kind == 'un' and val.b == '-' and val.a.kind == 'num' \
                    and val.a.a == 2:
                return  # state-machine terminator
            if val.kind == 'num' and val.a == -2:
                return  # terminator
            if val.kind == 'fld':
                self.effects.append(('JMP', val))
                return
            if (val.kind == 'idx' and val.a.kind == 'reg'
                    and val.a.a == 'INSTR' and val.b.kind == 'fld'):
                self.effects.append(('JMP', val))
                return
            rv = render_expr(val)
            if '==' in rv or '~=' in rv:
                self.effects.append(('EQX', val))
                return
            self.effects.append(('PC', val))
            return
        if name == 'e':
            if val.kind == 'idx' and render_expr(val.a) == 'T' \
                    and render_expr(val.b) == 'pc':
                if self._pending_step:
                    self.effects.append(('STEP',))
                    self.steps += 1
                    self._pending_step = False
                    return
            self._pending_step = False
            self.effects.append(('LOADNEXT', val))
            return
        self.env[name] = val

    def assign(self, dst, val):
        # legacy path (kept for tests)
        if dst.kind == 'reg' and dst.a == 'pc':
            if val.kind == 'bin' and val.b == '+' and render_expr(val.a) == 'pc' and render_expr(val.c) == '1':
                self._pending_step = True
                return
            if render_expr(val) .startswith('fld'):
                self.effects.append(('JMP', val))
                return
            self.effects.append(('PC', val))
            return
        if dst.kind == 'reg' and dst.a == 'INSTR':
            if val.kind == 'idx' and render_expr(val.a) == 'T' and render_expr(val.b) == 'pc':
                if self._pending_step:
                    self.effects.append(('STEP',))
                    self.steps += 1
                    self._pending_step = False
                    return
            self._pending_step = False
            self.effects.append(('LOADNEXT', val))
            return
        # plain alias assignment
        key = None
        if dst.kind == 'name':
            key = dst.a
        elif dst.kind == 'reg':
            key = dst.a
        if key:
            self.env[key] = val
        return

    def emit_store(self, x, val):
        base = x.a.a  # 'R' | 'G' | 'U'
        if base == 'R':
            self.effects.append(('SET', x.b, val))
        elif base == 'G':
            self.effects.append(('SETG', x.b, val))
        elif base == 'U':
            self.effects.append(('SETU', x.b, val))

    def bare_expr(self, x, tk):
        # l(a,b) / l(a) proxy calls == register writes
        if x.kind == 'call' and x.a.kind == 'tbl' and x.a.a == 'R':
            args = x.b or []
            if len(args) == 2:
                self.effects.append(('SET', args[0], args[1]))
                return
            if len(args) == 1:
                self.effects.append(('SET', args[0], Expr('nil')))
                return
            if len(args) == 3:
                self.effects.append(('SET', args[0], args[2]))
                return
        if x.kind == 'call':
            self.effects.append(('CALLRAW', list(tk)))
            return
        if x.kind in ('tbl', 'fn', 'reg', 'fld', 'nil'):
            return  # bare table/function reference: nothing to record
        self.unresolved += 1


def exec_effects(stream):
    ex = Executor()
    for stmt in stream:
        if isinstance(stmt, tuple) and stmt[0] == 'SM':
            continue
        ex.run_stmt(stmt)
    return ex


# --------------------------------------------------------------------------- #
# pass 4: classifier
# --------------------------------------------------------------------------- #

def F(x):
    return x.a if x.kind == 'fld' else None


def cls_expr(x):
    """Classify an RHS expression -> (lua-op-name-parts) tuple or None."""
    if x.kind == 'idx':
        base = x.a
        if base.kind == 'reg' and base.a == 'INSTR' and x.b.kind == 'fld':
            return ('imm', x.b.a)  # instruction field VALUE (e[c] etc.)
        if base.kind == 'tbl' and base.a == 'R':
            return ('R', x.b)
        if base.kind == 'tbl' and base.a == 'G':
            return ('G', x.b)
        if base.kind == 'tbl' and base.a == 'U':
            return ('U', x.b)
        if base.kind == 'tbl' and base.a == 'K':
            return ('K', x.b)
        if base.kind == 'idx':
            b2 = cls_expr(base)
            i2 = cls_expr(x.b)
            if b2 and i2:
                return ('GET', b2, i2)
        return None
    if x.kind == 'fld':
        return ('imm', x.a)
    if x.kind == 'num':
        return ('imm', str(x.a))
    if x.kind == 'bin':
        l = cls_expr(x.a)
        r = cls_expr(x.c)
        if l and r:
            return ('ARITH', x.b, l, r)
        return None
    if x.kind == 'un':
        y = cls_expr(x.a)
        if y:
            return ('UN', x.b, y)
        return None
    if x.kind == 'tblcons':
        return ('TBL',)
    if x.kind == 'call':
        fn = x.a
        if fn.kind == 'name' and fn.a == 'unpack':
            return ('PACK', x.b)
        if fn.kind == 'name' and fn.a == '_':
            return ('CLOSURE', x.b)
        if fn.kind == 'idx':
            b2 = cls_expr(fn.a)
            if b2:
                return ('CALLV', b2, x.b)
    if x.kind == 'name' and x.a in ('l',):
        return ('R',)
    return None


ARITH_OP = {'+': 'ADD', '-': 'SUB', '*': 'MUL', '/': 'DIV', '%': 'MOD',
            '^': 'POW', '..': 'CONCAT'}
UN_OP = {'-': 'UNM', '#': 'LEN', 'not': 'NOT'}


def _slot(x):
    """'A'/'B'/'C' if x is Expr fld, else None."""
    if x is not None and x.kind == 'fld':
        return x.a
    return None


def _slot_of_dst_plus1(x):
    """'A' if x is (INSTR[A]+1) or R[(INSTR[A]+1)] style (SELF dest)."""
    if x.kind == 'idx':
        x = x.b
    if (x.kind == 'bin' and x.b == '+' and x.a.kind == 'idx'
            and x.a.a.kind == 'reg' and x.a.a.a == 'INSTR'
            and x.a.b.kind == 'fld' and x.c.kind == 'num' and x.c.a == 1):
        return x.a.b.a
    return None


def _slot_of(x):
    """Slot letter from an operand expression: e[d] forms or plain fld."""
    if x is None:
        return None
    if x.kind == 'fld':
        return x.a
    if (x.kind == 'idx' and x.a.kind == 'reg' and x.a.a == 'INSTR'
            and x.b.kind == 'fld'):
        return x.b.a
    return None


def name_effects(effects):
    """Return list of (mnemonic, detail) per effect."""
    names = []
    for ei, eff in enumerate(effects):
        k = eff[0]
        if k == 'SET':
            dst, val = eff[1], eff[2]
            dslot = _slot_of(dst)
            c = cls_expr(val)
            if dslot is None and _slot_of_dst_plus1(dst) is not None:
                dslot = _slot_of_dst_plus1(dst)
                if c is not None and c[0] == 'R':
                    names.append(('SELF_P1', 'R[%s+1]:=R[%s]' % (dslot, _slot_of(c[1]))))
                    continue
            if dslot is None or c is None:
                if (ei > 0 and effects[ei - 1][0] == 'FORRAW'
                        and '..' in ''.join(x[1] for x in effects[ei - 1][1])
                        and val.kind in ('name', 'tbl', 'reg', 'fn')):
                    names.append(('CONCAT', 'R[%s]:=concat(...)' % dslot))
                elif (ei > 0 and effects[ei - 1][0] == 'FORRAW'
                        and '..' in ''.join(x[1] for x in effects[ei - 1][1])):
                    names.append(('CONCAT?', 'R[%s]=%s' % (render_expr(dst), _e(val))))
                else:
                    names.append(('SET?', 'R[%s]=%s' % (render_expr(dst), _e(val))))
                continue
            if c[0] == 'R':
                s = _slot_of(c[1])
                if s:
                    names.append(('MOVE', 'R[%s]:=R[%s]' % (dslot, s)))
                else:
                    names.append(('MOVE?', 'R[%s]:=%s' % (dslot, render_expr(val))))
            elif c[0] == 'imm':
                if (val.kind == 'name' and ei > 0
                        and effects[ei - 1][0] == 'FORRAW'
                        and '..' in ''.join(x[1] for x in effects[ei - 1][1])):
                    names.append(('CONCAT', 'R[%s]:=concat(...)' % dslot))
                else:
                    names.append(('LOADK', 'R[%s]:=%s' % (dslot, c[1])))
            elif c[0] == 'K':
                s = _slot_of(c[1])
                names.append(('LOADK', 'R[%s]:=K[%s]' % (dslot, s or render_expr(c[1]))))
            elif c[0] == 'G':
                s = _slot_of(c[1])
                names.append(('GETGLOBAL', 'R[%s]:=G[%s]' % (dslot, s or render_expr(c[1]))))
            elif c[0] == 'U':
                s = _slot_of(c[1])
                names.append(('GETUPVAL', 'R[%s]:=U[%s]' % (dslot, s or render_expr(c[1]))))
            elif c[0] == 'GET':
                names.append(('GETTABLE', 'R[%s]:=%s[%s]' % (dslot, _e(c[1]), _e(c[2]))))
            elif c[0] == 'ARITH':
                if c[1] == '~=' and c[3] == ('imm', '0'):
                    names.append(('LOADBOOL', 'R[%s]:=(B~=0)' % dslot))
                else:
                    opn = ARITH_OP.get(c[1], c[1] + '?')
                    names.append((opn, 'R[%s]:=%s %s %s' % (dslot, _e(c[2]), c[1], _e(c[3]))))
            elif c[0] == 'UN':
                opn = UN_OP.get(c[1], c[1])
                names.append((opn, 'R[%s]:=%s%s' % (dslot, c[1], _e(c[2]))))
            elif c[0] == 'TBL':
                names.append(('NEWTABLE', 'R[%s]:={}' % dslot))
            elif c[0] == 'PACK':
                names.append(('PACK?', 'R[%s]=unpack(...)' % dslot))
            elif c[0] == 'CALLV':
                names.append(('CALL?', 'R[%s]=%s' % (dslot, render_expr(val))))
            elif c[0] == 'CLOSURE':
                names.append(('CLOSURE', 'R[%s]:=proto(%s)' % (dslot, _e(c[1][0]) if c[1] else '?')))
            else:
                names.append(('SET?', 'R[%s]=%s' % (render_expr(dst), render_expr(val))))
        elif k == 'SETG':
            s = _slot_of(eff[1])
            v = cls_expr(eff[2])
            if s and v and v[0] == 'R':
                names.append(('SETGLOBAL', 'G[%s]:=R[%s]' % (s, _slot_of(v[1]))))
            else:
                names.append(('SETGLOBAL?', render_expr(eff[1]) + '=' + render_expr(eff[2])))
        elif k == 'SETU':
            s = _slot_of(eff[1])
            v = cls_expr(eff[2])
            if s and v and v[0] == 'R':
                names.append(('SETUPVAL', 'U[%s]:=R[%s]' % (s, _slot_of(v[1]))))
            else:
                names.append(('SETUPVAL?', render_expr(eff[1]) + '=' + render_expr(eff[2])))
        elif k == 'SETIDX':
            x = eff[1]
            if x.a.kind == 'idx':
                names.append(('SETTABLE', '%s[%s]:=%s' % (_e(x.a), _e(x.b), _e(eff[2]))))
            else:
                names.append(('SETIDX?', render_expr(x) + '=' + _e(eff[2])))
        elif k == 'JMP':
            names.append(('JMP', 'pc:=%s' % (_slot_of(eff[1]) or render_expr(eff[1]))))
        elif k == 'EQX':
            names.append(('EQ_K', render_expr(eff[1])[:60]))
        elif k == 'STEP':
            names.append(('STEP', ''))
        elif k == 'LOADNEXT':
            names.append(('LOADNEXT', ''))
        elif k == 'PC':
            names.append(('PC?', render_expr(eff[1])))
        elif k == 'RETURN':
            tt = [x[1] for x in eff[1]]
            txt = ''.join(tt)
            if 'unpack' in txt or re.search(r'returns\(l,', txt):
                names.append(('RETURN_m', txt))
            elif 'l' in tt and txt.count('[') >= 2:
                names.append(('RETURN_1', txt))
            elif txt.replace('do', '').replace('return', '').replace('end', '') == '':
                names.append(('RETURN_0', ''))
            else:
                names.append(('RETURN?', txt))
        elif k == 'TESTRAW':
            txt = ''.join(x[1] for x in eff[1])
            m = None
            if re.search(r'if\(?l\[e\[d\]\]\)?thenn=n\+1;?elsen=e\[c\];?end', txt):
                m = ('TEST', 'skip-if-true')
            elif re.search(r'ifnot\(?l\[e\[d\]\]\)?thenn=n\+1;?elsen=e\[c\];?end', txt):
                m = ('TESTN', 'skip-if-false')
            elif re.search(r'ifnot.?thenn=n\+1;?elsel\[e\[d\]\]=t;n=e\[c\];?end', txt):
                m = ('TESTSET', 'skip-if-true/else R[A]:=t,jmp')
            elif re.search(r'if\(?l\[e\[d\]\]==l\[e\[r\]\]\)?then', txt):
                m = ('EQ_R', 'skip-if-eq-R')
            elif re.search(r'if\(?l\[e\[d\]\]~=l\[e\[r\]\]\)?then', txt):
                m = ('NE_R', 'skip-if-ne-R')
            elif re.search(r'if\(?l\[e\[d\]\]==e\[r\]\)?then', txt):
                m = ('EQ_C', 'skip-if-eq-C')
            elif re.search(r'if\(?l\[e\[d\]\]~=e\[r\]\)?then', txt):
                m = ('NE_C', 'skip-if-ne-C')
            elif re.search(r'if\(?l\[e\[d\]\]<e\[r\]\)?then', txt):
                m = ('LT_C', 'skip-if-lt-C')
            elif re.search(r'if\(?l\[e\[d\]\]<=e\[r\]\)?then', txt):
                m = ('LE_C', 'skip-if-le-C')
            elif re.search(r'if\(?l\[e\[d\]\]<l\[e\[r\]\]\)?then', txt):
                m = ('LT_R', 'skip-if-lt-R')
            elif re.search(r'if\(?l\[e\[d\]\]<=l\[e\[r\]\]\)?then', txt):
                m = ('LE_R', 'skip-if-le-R')
            elif re.search(r'ifl\[e\[d\]\]thenn=e\[c\]', txt):
                m = ('TEST_J', '')
            elif re.search(r'if\(?.>0\)?thenif\(.>l\[.+1\]\)thenn=e\[c\];elsel\[.+3\]=.;endelseif\(.<l\[.+1\]\)thenn=e\[c\];elsel\[.+3\]=.;end(?:end)?', txt):
                m = ('FORLOOP', '')
            elif re.search(r'if\(?.>0\)?thenif\(.<=l\[.+1\]\)thenn=e\[c\];l\[.+3\]=.;endelseif\(.>=l\[.+1\]\)thenn=e\[c\];l\[.+3\]=.;end(?:end)?', txt):
                m = ('FORPREP', '')
            else:
                m = ('TEST?', txt[:60])
            names.append(m)
        elif k == 'FORRAW':
            txt = ''.join(x[1] for x in eff[1])
            if '#b' in txt:
                names.append(('CLOSE_UV', txt[:40]))
            elif '..' in txt:
                names.append(('CONCAT_LOOP', txt[:40]))
            elif re.search(r'dol\[.=\]nil', txt) or '=nil' in txt:
                names.append(('LOADNIL', txt[:40]))
            elif 'h.KxJvyxZi' in txt:
                names.append(('CLOSE_UV', txt[:40]))
            elif re.search(r'.=.+1;l\[.\]=.\[.\];', txt):
                names.append(('VARARG', txt[:40]))
            elif 'ife[g]==' in txt:
                names.append(('CLOSURE_DESC', txt[:40]))
            else:
                names.append(('FOR?', txt[:40]))
        elif k == 'CALLRAW':
            txt = ''.join(x[1] for x in eff[1])
            if txt.replace(' ', '') == 'l[e[d]]()':
                names.append(('CALL_0', 'R[A]()'))
            elif 'unpack' in txt or re.search(r's\(l,', txt):
                names.append(('CALLC', txt[:50]))
            else:
                names.append(('CALL?', txt[:50]))
        elif k == 'WHILERAW':
            txt = ''.join(x[1] for x in eff[1])
            names.append(('WHILE?', txt[:40]))
        else:
            names.append((k, ''))
    return names


def _e(x):
    """Compact render from Expr or cls-tuple: R[A], K[B], imm C, arith."""
    if isinstance(x, tuple):
        c = x
    else:
        c = cls_expr(x) if x.kind != 'fld' else ('imm', x.a)
    if c is None:
        return render_expr(x)
    if c[0] == 'R':
        s = _slot_of(c[1])
        return 'R[%s]' % (s if s else render_expr(c[1]))
    if c[0] == 'imm':
        return str(c[1])
    if c[0] == 'K':
        s = _slot_of(c[1])
        return 'K[%s]' % (s if s else render_expr(c[1]))
    if c[0] == 'G':
        s = _slot_of(c[1])
        return 'G[%s]' % (s if s else render_expr(c[1]))
    if c[0] == 'U':
        s = _slot_of(c[1])
        return 'U[%s]' % (s if s else render_expr(c[1]))
    if c[0] == 'GET':
        return '%s[%s]' % (_e2(c[1]), _e2(c[2]))
    if c[0] == 'ARITH':
        return '(%s %s %s)' % (_e2(c[2]), c[1], _e2(c[3]))
    if c[0] == 'UN':
        return '%s%s' % (c[1], _e2(c[2]))
    if c[0] == 'TBL':
        return '{}'
    return render_expr(x)


def _e2(c):
    if c[0] == 'R':
        s = _slot_of(c[1])
        return 'R[%s]' % (s if s else render_expr(c[1]))
    if c[0] == 'imm':
        return str(c[1])
    if c[0] == 'GET':
        return '%s[%s]' % (_e2(c[1]), _e2(c[2]))
    if c[0] == 'ARITH':
        return '(%s %s %s)' % (_e2(c[2]), c[1], _e2(c[3]))
    if c[0] == 'K':
        s = _slot_of(c[1])
        return 'K[%s]' % (s if s else render_expr(c[1]))
    if c[0] == 'G':
        return 'G[%s]' % _slot_of(c[1])
    if c[0] == 'U':
        return 'U[%s]' % _slot_of(c[1])
    if c[0] == 'UN':
        return '%s%s' % (c[1], _e2(c[2]))
    return '?'


# --------------------------------------------------------------------------- #
# top-level extraction
# --------------------------------------------------------------------------- #

def extract(sample_src, domain_max=160):
    global _TOKS
    consts = stage2_constants(sample_src)
    vm = sample_src.find(VM_HEAD)
    if vm < 0:
        raise ValueError('VM interpreter head not found')
    toks = tokenize(sample_src[vm:])
    _TOKS = toks
    fi = None
    for idx in range(len(toks) - len(FETCH)):
        if tuple(t[1] for t in toks[idx:idx + len(FETCH)]) == FETCH:
            fi = idx
            break
    if fi is None:
        raise ValueError('instruction fetch pattern not found')
    xp = XParser(toks, consts)
    tree, _j = xp.parse_if(fi + len(FETCH))

    streams = defaultdict(list)
    op_walk([('if', tree)], set(range(1, domain_max + 1)), streams)

    ops = {}
    for op in sorted(streams):
        stream = streams[op]
        # expand SM markers in order
        full = []
        for item in stream:
            if isinstance(item, tuple) and item[0] == 'SM':
                _tag, var, witems = item
                stmts, _nstates = sm_states(var, witems)
                full.extend(stmts)
            else:
                full.append(item)
        ex = exec_effects(full)
        names = name_effects(ex.effects)
        # SELF pairing: SELF_P1 (R[A+1]:=R[B]) + GETTABLE (R[A]:=R[B][C])
        i = 0
        paired = []
        while i < len(names):
            if (i + 1 < len(names)
                    and names[i][0] == 'SELF_P1'
                    and names[i + 1][0] in ('GETTABLE',)):
                paired.append(('SELF', '%s ; %s' % (names[i][1], names[i + 1][1])))
                i += 2
                continue
            paired.append(names[i])
            i += 1
        names = paired
        core = [n for n, _d in names if n not in ('STEP', 'LOADNEXT')]
        if not core:
            names = [('NOP', 'only pc step')] + [
                (n, d) for n, d in names if n in ('STEP', 'LOADNEXT')]
        # slot consumption: 1 + #refetch pairs (n=n+1 ; e=t[n]) in the stream
        refetches = 0
        prev_step = False
        for st in full:
            tt = [x[1] for x in st]
            if tt[:1] == ['n'] and len(tt) >= 2 and ''.join(tt) .startswith('n=n+1'):
                prev_step = True
                continue
            if prev_step and tt[:3] == ['e', '=', 't']:
                refetches += 1
                prev_step = False
            elif tt[:1] == ['e'] and tt[:3] == ['e', '=', 't']:
                refetches += 1
                prev_step = False
            else:
                prev_step = False
        # sub-op chain: partition effects at refetch markers, per partition
        # keep resolved (non '?') names, collapse consecutive duplicates
        chain = []
        cur = []
        ei = 0
        eff_names = [n for n, _d in names]
        eff_kinds = [e[0] for e in ex.effects]
        marks = []
        prev_step = False
        for st in full:
            tt = [x[1] for x in st]
            joined = ''.join(tt)
            if tt[:1] == ['n'] and joined.startswith('n=n+1'):
                prev_step = True
                continue
            if prev_step and tt[:3] == ['e', '=', 't']:
                marks.append(len(chain))
                chain.append([])
                prev_step = False
                continue
            if tt[:1] == ['e'] and tt[:3] == ['e', '=', 't']:
                marks.append(len(chain))
                chain.append([])
                prev_step = False
                continue
            prev_step = False
        # walk effects in order, splitting at refetch boundaries recorded
        # during execution: rebuild via executor effects and STEP/LOADNEXT
        eff_pairs = list(zip(eff_names, ['%s %s' % (n, d) if d else n
                                         for n, d in names]))
        part = []
        parts = [part]
        for nm, det in eff_pairs:
            if nm in ('STEP', 'LOADNEXT'):
                part = []
                parts.append(part)
                continue
            part.append(det)
        chain = []
        for prt in parts:
            clean = []
            for det in prt:
                nm = det.split(' ')[0]
                if nm.endswith('?') and len(clean) \
                        and clean[-1][0] == nm[:-1]:
                    continue
                clean.append((nm[:-1] if nm.endswith('?') else nm, det))
            ded = []
            for item in clean:
                if ded and ded[-1][0] == item[0]:
                    ded[-1] = item
                    continue
                ded.append(list(item))
            if ded:
                chain.append(ded)
        consumed = 1 + refetches
        ops[op] = {
            'names': [n for n, _d in names],
            'details': ['%s %s' % (n, d) if d else n for n, d in names],
            'unresolved': ex.unresolved,
            'alts': ex.alts,
            'n_stmts': len(full),
            'consumed': consumed,
            'chain': chain,
        }
    return {'ops': ops, 'covered': sorted(ops)}


# --------------------------------------------------------------------------- #
# self-test
# --------------------------------------------------------------------------- #

_SYNTH = (
    'function ne(...)local t,k,j,ne,u,n,a,ee,y,p,b,l;'
    'local e=0;while le do end '
    'e=t[n];f=e[g];'
    'if f<2 then l[e[d]]=l[e[c]]; '
    'else if f<3 then l(e[d],e[c]); '
    'else local f,r,o,s,h,t;local n=0;'
    'while n>-1 do if n<=3 then if n>1 then if n<3 then o=c; else s=l; end '
    'elseif 0==n then f=e; else r=d; end '
    'elseif n<=5 then if 2<n then repeat if n>4 then t=f[r]; break; end; '
    'h=s[f[o]]; until true; else t=f[r]; end '
    'elseif n>=2 then repeat if n~=7 then l[t]=h; break; end; n=-2; until true; '
    'else l[t]=h; end '
    'n=n+1 end '
    'end end '
    'n=1+n;'
    'end;'
)


def _selftest():
    fails = []

    def chk(tag, cond, extra=''):
        print('[%s] %s%s' % ('OK' if cond else 'XX', tag, (' -- ' + str(extra)) if extra and not cond else ''))
        if not cond:
            fails.append(tag)

    # T1: statement splitting keeps for..end whole
    toks = tokenize('a=1;for e=1,#b do f=f..l[e];end;l[h]=f;')
    stmts = split_statements(toks, 0, len(toks))
    chk('T1 depth-aware split', len(stmts) == 3, [ [x[1] for x in s] for s in stmts])

    # T2: synthetic dispatch: op1 MOVE, op2 LOADIMM, op3 unrolled MOVE
    _TOKS_OLD = _TOKS[:]
    m = extract(_SYNTH, domain_max=4)
    ops = m['ops']
    n1 = ops.get(1, {}).get('names', [])
    n2 = ops.get(2, {}).get('names', [])
    n3 = ops.get(3, {}).get('names', [])
    chk('T2 op1 MOVE', n1 == ['MOVE'], (n1, ops.get(1)))
    chk('T3 op2 LOADIMM (proxy write B imm)', n2 and n2[0] == 'LOADK', (n2, ops.get(2)))
    chk('T4 op3 unrolled MOVE', n3 == ['MOVE'], (n3, ops.get(3)))

    # T5: detail strings carry operand slots
    d3 = ops.get(3, {}).get('details', [])
    chk('T5 unrolled MOVE detail R[A]:=R[B]', any('R[A]:=R[B]' in x for x in d3), d3)

    # T6: executor resolves aliases chain f=e,r=d,o=c,s=l
    ex = Executor()
    ex.run_stmt(tokenize('f=e;'))
    ex.run_stmt(tokenize('r=d;'))
    chk('T6 alias assign', render_expr(ex.env.get('f', Expr('nil'))) == 'reg:INSTR'
        or getattr(ex.env.get('f'), 'a', None) == 'INSTR', ex.env.get('f'))

    globals()['_TOKS'] = _TOKS_OLD
    print('')
    print('Result: %d/6' % (6 - len(fails)))
    if fails:
        print('[XX] FAILURES: %d' % len(fails))
        return 1
    print('[OK] ALL PASSED')
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description='MoonSec V3 opcode semantics')
    ap.add_argument('--test', action='store_true')
    ap.add_argument('--sample', default=None)
    ap.add_argument('--outdir', default='out')
    ap.add_argument('--show', type=int, default=40)
    a = ap.parse_args(argv)
    if a.test:
        return _selftest()
    if not a.sample:
        print('need --sample path (or --test)')
        return 2
    src = open(a.sample, encoding='utf-8', errors='replace').read()
    m = extract(src)
    os.makedirs(a.outdir, exist_ok=True)
    p = os.path.join(a.outdir, 'msvm_semantics.json')
    with open(p, 'w', encoding='utf-8') as fh:
        json.dump(m, fh, indent=1)
    named = sum(1 for v in m['ops'].values()
                if v['names'] and all(not n.endswith('?') for n in v['names']))
    print('ops: %d ; fully-named: %d' % (len(m['ops']), named))
    shown = 0
    for op in sorted(m['ops']):
        if shown >= a.show:
            break
        v = m['ops'][op]
        print('op %3d: %s' % (op, ' | '.join(v['details'])[:150]))
        shown += 1
    print('saved ->', p)
    return 0


if __name__ == '__main__':
    sys.exit(main())
