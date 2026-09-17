"""
NZL STUDIO - Sprint 6 (slice 4): карта опкодов VM Luraph v14.x
==============================================================
Продолжение vm_trace.py (slice 3). Образец v14.6 теперь ИСПОЛНЯЕТСЯ в
песочнице целиком (загрузчик ~2.2 млн шагов, далее бесконечный GUI-цикл),
поэтому карту опкодов снимаем динамически:

Диспетчер VM имеет форму (переменные образца v14.6):
    q = t[E]              -- опкод из массива инструкций t по счётчику E
    if q == 32 then ...   -- цепочка сравнений; ветка зовёт обработчик

Модуль инструментирует песочницу:
- _exec_if: если в env диспетчера opcode_var (q) — целое, ЗАПОМИНАЕМ
  (q, E, ссылку на t, сам env). Env-ы диспетчера определяются по тройке
  (q:int, E:number, t:table) и хранятся живыми ссылками (защита от
  переиспользования id() после сборки мусора);
- _call_function: ПЕРВЫЙ именованный вызов (имя из структурного парсера,
  идентификация по id(body)) после взведения — обработчик этого опкода.
  Вложенные вызовы обработчиков не атрибутируются (флаг снимается);
- по каждому опкоду: число диспетчеризаций, голоса за обработчики,
  набор значений E (адреса инструкций), окно массива t (операнды).

Результат (OpcodeResult):
    q -> {seen, dispatched, handlers {name: votes}, primary handler,
          E-values, окна операндов t[E..E+3]}

CLI:
    py -m obfuscator.deobfuscator.luraph.vm_opcodes <file.lua> \
        [--max-steps N] [--max-dispatches N] [--out map.json] \
        [--report report.txt] [--bodies]
"""
from __future__ import annotations

import time

if __package__ in (None, ''):  # запуск файлом: py obfuscator\...\vm_opcodes.py
    import os as _os
    import sys as _sys
    _sys.path.insert(0, _os.path.abspath(_os.path.join(
        _os.path.dirname(__file__), '..', '..', '..')))

__all__ = ['OpcodeResult', 'trace_opcodes', 'opcode_report', '_self_test']


class OpcodeResult:
    def __init__(self):
        # q -> {'seen': n, 'dispatched': n, 'handlers': {name: votes}}
        self.q_stats = {}
        # (q, E) -> count — частота исполнения конкретных инструкций
        self.qe_counts = {}
        # лента диспетчеризаций: (step, q, E, handler, [numeric args],
        #   [окно t[E-1..E+2]])
        self.dispatches = []
        self.steps = 0
        self.elapsed = 0.0
        self.error = None

    def primary(self, q):
        st = self.q_stats.get(q)
        if not st or not st['handlers']:
            return None
        return max(st['handlers'].items(), key=lambda kv: kv[1])[0]

    def hot(self, n=20):
        return sorted(self.q_stats.items(),
                      key=lambda kv: -kv[1]['dispatched'])[:n]

    def summary(self) -> str:
        tot = sum(s['dispatched'] for s in self.q_stats.values())
        lines = ['steps=%d dispatched=%d distinct_q=%d elapsed=%.1fs' % (
            self.steps, tot, len(self.q_stats), self.elapsed)]
        lines.append('  %-5s %-8s %-9s %-9s %s' % (
            'q', 'disp', 'seen', 'primary', 'handlers(votes)'))
        for q, st in self.hot(30):
            hs = ', '.join('%s:%d' % (k, v) for k, v in sorted(
                st['handlers'].items(), key=lambda kv: -kv[1])[:4])
            lines.append('  %-5s %-8d %-9d %-9s %s' % (
                q, st['dispatched'], st['seen'], self.primary(q) or '-', hs))
        if self.error:
            lines.append('error: %s' % self.error)
        return '\n'.join(lines)

    def to_json_obj(self):
        return {
            'steps': self.steps,
            'elapsed': round(self.elapsed, 1),
            'error': self.error,
            'q_stats': {str(q): s for q, s in self.q_stats.items()},
            'qe_counts': {'%d:%d' % k: v for k, v in self.qe_counts.items()},
            'dispatches': self.dispatches[:5000],
        }


def trace_opcodes(source: str, max_steps: int = 8_000_000,
                  opcode_var: str = 'q', pc_var: str = 'E',
                  instr_var: str = 't', max_dispatches: int = 50_000,
                  progress_every: int = 0) -> OpcodeResult:
    """Прогнать образец в песочнице и снять карту «опкод -> обработчик»."""
    import sys
    from obfuscator.lexer import Lexer
    from obfuscator.parser import Parser
    from obfuscator.deobfuscator.core.lua_sandbox import (
        LuaSandbox, LuaFunction, LuaTable)
    from obfuscator.deobfuscator.core import lua_sandbox as _ls
    from obfuscator.deobfuscator.luraph.parser import detect_source
    from obfuscator.deobfuscator.luraph.vm_trace import (
        build_handler_body_map_from_chunk)

    res = OpcodeResult()
    t0 = time.time()

    try:
        chunk = Parser(Lexer(source).tokenize()).parse()
    except Exception as e:  # noqa: BLE001
        res.error = 'ParseError: %s' % str(e)[:120]
        res.elapsed = time.time() - t0
        return res
    body_map = build_handler_body_map_from_chunk(chunk, detect_source(source))

    class _OpSB(LuaSandbox):
        def __init__(inner):
            super().__init__()
            # живые ссылки на env-ы диспетчера (защита от id-reuse)
            inner.disp_envs = []
            inner.armed = False
            inner.cur_q = None
            inner.cur_E = None
            inner.cur_t = None

        def _is_disp_env(inner, env):
            if not isinstance(env, dict):
                return False
            qv = env.get(opcode_var)
            ev = env.get(pc_var)
            tv = env.get(instr_var)
            return (isinstance(qv, (int, float)) and not isinstance(qv, bool)
                    and isinstance(ev, (int, float)) and not isinstance(ev, bool)
                    and isinstance(tv, LuaTable))

        def _exec_if(inner, stmt, env):
            qv = env.get(opcode_var) if isinstance(env, dict) else None
            if isinstance(qv, (int, float)) and not isinstance(qv, bool):
                q = int(qv)
                if any(env is e for e in inner.disp_envs):
                    inner.armed = True
                    inner.cur_q = q
                    ev = env.get(pc_var)
                    inner.cur_E = int(ev) if isinstance(
                        ev, (int, float)) and not isinstance(ev, bool) else None
                    tv = env.get(instr_var)
                    inner.cur_t = tv if isinstance(tv, LuaTable) else None
                    st = res.q_stats.setdefault(
                        q, {'seen': 0, 'dispatched': 0, 'handlers': {}})
                    st['seen'] += 1
                elif inner._is_disp_env(env):
                    inner.disp_envs.append(env)
                    inner.armed = True
                    inner.cur_q = q
                    ev = env.get(pc_var)
                    inner.cur_E = int(ev) if isinstance(
                        ev, (int, float)) and not isinstance(ev, bool) else None
                    tv = env.get(instr_var)
                    inner.cur_t = tv if isinstance(tv, LuaTable) else None
                    st = res.q_stats.setdefault(
                        q, {'seen': 0, 'dispatched': 0, 'handlers': {}})
                    st['seen'] += 1
            return super()._exec_if(stmt, env)

        def _call_function(inner, fn, args, env=None):
            if inner.armed and isinstance(fn, LuaFunction) and fn.body is not None:
                name = body_map.get(id(fn.body))
                if name is not None:
                    inner.armed = False
                    q, E = inner.cur_q, inner.cur_E
                    st = res.q_stats.setdefault(
                        q, {'seen': 0, 'dispatched': 0, 'handlers': {}})
                    st['dispatched'] += 1
                    st['handlers'][name] = st['handlers'].get(name, 0) + 1
                    if E is not None:
                        res.qe_counts[(q, E)] = res.qe_counts.get((q, E), 0) + 1
                    if len(res.dispatches) < max_dispatches:
                        nums = [a for a in args
                                if isinstance(a, (int, float))
                                and not isinstance(a, bool)]
                        win = None
                        if isinstance(inner.cur_t, LuaTable) and E is not None:
                            win = [inner.cur_t.rawget(E + k) for k in range(4)]
                            win = [w if isinstance(w, (int, float, str))
                                   and not isinstance(w, bool) else None
                                   for w in win]
                        res.dispatches.append(
                            (inner._steps, q, E, name,
                             [str(x)[:14] for x in nums[:5]], win))
            return super()._call_function(fn, args, env)

        if progress_every:
            def _step(inner):
                super()._step()
                if inner._steps % progress_every == 0:
                    sys.stdout.write('  ... %d steps (%.0fs)\n'
                                     % (inner._steps, time.time() - t0))
                    sys.stdout.flush()

    sb = _OpSB()
    sb.MAX_STEPS = max_steps
    env = dict(sb._globals)
    env['_G'] = _ls._EnvTable(env)
    try:
        sb._exec_chunk(chunk, env)
    except _ls.LuaReturn:
        pass
    except Exception as e:  # noqa: BLE001
        res.error = '%s: %s' % (type(e).__name__, str(e)[:160])
    res.steps = getattr(sb, '_steps', 0)
    res.elapsed = time.time() - t0
    return res


def opcode_report(res: OpcodeResult, source: str = None,
                  with_bodies: bool = False) -> str:
    """Текстовая карта опкодов; при with_bodies — тела обработчиков."""
    lines = ['=== Luraph opcode map (dynamic) ===',
             'steps=%d distinct_q=%d' % (
                 res.steps, len(res.q_stats)), '']
    bodies = {}
    if with_bodies and source is not None:
        from obfuscator.deobfuscator.luraph.parser import parse_source
        from obfuscator.ast_unparser import ASTUnparser
        try:
            rep = parse_source(source)
            up = ASTUnparser(minified=False)
            for name, fn in (rep.handlers or {}).items():
                b = getattr(fn, 'body', None)
                if b is not None:
                    try:
                        bodies[name] = up.unparse(b)
                    except Exception:  # noqa: BLE001
                        bodies[name] = '<unparse error>'
        except Exception as e:  # noqa: BLE001
            lines.append('(bodies unavailable: %s)' % str(e)[:80])
    for q, st in sorted(res.q_stats.items()):
        prim = res.primary(q)
        lines.append('opcode %-4d dispatched=%-7d seen=%-8d primary=%s' % (
            q, st['dispatched'], st['seen'], prim or '-'))
        for name, votes in sorted(st['handlers'].items(),
                                  key=lambda kv: -kv[1]):
            lines.append('    %-10s %d' % (name, votes))
        es = sorted({E for (qq, E) in res.qe_counts if qq == q})[:12]
        if es:
            lines.append('    E: %s' % es)
        if with_bodies and prim and prim in bodies:
            lines.append('    --- body of %s ---' % prim)
            for bl in bodies[prim].splitlines():
                lines.append('    | ' + bl)
        lines.append('')
    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# Slice 4b: СТАТИЧЕСКАЯ карта опкодов из AST диспетчера.
# Диспетчер v14.6 — бинарное дерево поиска `if q>=N ...` по q=t[E]; «листья»
# — встроенные стейт-машины (вызовов именованных обработчиков нет, поэтому
# динамическая атрибуция вызовов их не ловит — dispatched=0 при seen>0).
# Статический проход даёт карту «опкод -> тело-обработчик» МГНОВЕННО.
# ---------------------------------------------------------------------------

class DispatchChain:
    def __init__(self):
        self.opcode_var = None
        self.instr_var = None
        self.pc_var = None
        self.root_if = None       # корневой IfStat дерева по q
        self.leaves = []          # [{'iv': (lo,hi), 'stmts': [...], 'text': str}]

    def opcodes_for(self, q):
        """Листья, покрывающие опкод q."""
        return [lf for lf in self.leaves
                if lf['iv'][0] <= q <= lf['iv'][1]]

    def text_for(self, q):
        lvs = self.opcodes_for(q)
        return lvs[0]['text'] if lvs else None


def _ast_children(node):
    from obfuscator.ast_nodes import Node
    for _k, v in vars(node).items():
        if isinstance(v, Node):
            yield v
        elif isinstance(v, (list, tuple)):
            for x in v:
                if isinstance(x, Node):
                    yield x
                elif isinstance(x, (list, tuple)):
                    for y in x:
                        if isinstance(y, Node):
                            yield y


def _expr_has_name(expr, name):
    from obfuscator.ast_nodes import NameExpr
    stack = [expr]
    while stack:
        n = stack.pop()
        if n is None:
            continue
        if isinstance(n, NameExpr) and n.name == name:
            return True
        stack.extend(_ast_children(n))
    return False


def _cond_constraints(cond, varname):
    """Список ограничений (op, int) из условия; `not` инвертирует.
    and -> объединяем; or -> пропускаем (нестрого)."""
    from obfuscator.ast_nodes import BinaryOp, UnaryOp, NameExpr, NumberLit
    out = []
    flip = {'<': '>=', '>=': '<', '<=': '>', '>': '<=', '==': '~=', '~=': '=='}
    mirror = {'<': '>', '>': '<', '<=': '>=', '>=': '<=', '==': '==', '~=': '~='}

    def rec(n, neg):
        if n is None:
            return
        inner = getattr(n, 'inner', None) if type(n).__name__ == 'ParenExpr' else None
        if inner is not None:
            return rec(inner, neg)
        if isinstance(n, UnaryOp) and n.op == 'not':
            return rec(n.operand, not neg)
        if isinstance(n, BinaryOp):
            if n.op in ('and', 'or'):
                if n.op == 'and':
                    rec(n.left, neg)
                    rec(n.right, neg)
                return
            if n.op in ('<', '<=', '>', '>=', '==', '~='):
                l, r = n.left, n.right
                v = None
                op = n.op
                if (isinstance(l, NameExpr) and l.name == varname
                        and isinstance(r, NumberLit)):
                    v = r.value
                elif (isinstance(r, NameExpr) and r.name == varname
                      and isinstance(l, NumberLit)):
                    v = l.value
                    op = mirror[n.op]
                if v is not None and isinstance(v, int) and not isinstance(v, bool):
                    if neg:
                        op = flip[op]
                    out.append((op, v))
    rec(cond, False)
    return out


def _apply_constraints(iv, cons):
    lo, hi = iv
    for op, v in cons:
        if op == '<':
            hi = min(hi, v - 1)
        elif op == '<=':
            hi = min(hi, v)
        elif op == '>':
            lo = max(lo, v + 1)
        elif op == '>=':
            lo = max(lo, v)
        elif op == '==':
            lo = max(lo, v)
            hi = min(hi, v)
        # '~=' игнорируем (требует множественной арифметики)
    return (lo, hi)


def find_dispatch_chain(chunk, opcode_var=None, instr_var=None,
                        pc_var=None) -> DispatchChain:
    """Найти `q = t[E]` (авто-детект имён) и корневое if-дерево по q."""
    from obfuscator.ast_nodes import (
        AssignStat, LocalAssignStat, IfStat, NameExpr, IndexExpr)
    dc = DispatchChain()

    from obfuscator.ast_nodes import ParenExpr

    def _unparen(e):
        while isinstance(e, ParenExpr):
            e = e.inner
        return e

    def _find_root_if(varname):
        stack = [chunk]
        while stack:
            n = stack.pop(0)
            if isinstance(n, IfStat) and any(
                    _expr_has_name(c, varname) for c, _b in n.branches):
                return n
            kids = list(_ast_children(n))
            stack = kids + stack  # pre-order: гарантированно самый верхний
        return None

    def _count_dispatch_nodes(root, varname):
        if root is None:
            return 0
        cnt = 0
        stack = [root]
        while stack:
            n = stack.pop()
            if isinstance(n, IfStat) and any(
                    _expr_has_name(c, varname) for c, _b in n.branches):
                cnt += 1
            stack.extend(_ast_children(n))
        return cnt

    # 1) авто-детект: присваивание X = T[P] (имена; скобки разворачиваем).
    #    Кандидатов несколько (в декодере есть локальные q и т.п.) — поэтому
    #    привязываемся к МЕСТУ присваивания: if-дерево ищем в том же блоке
    #    ПОСЛЕ оператора; побеждает кандидат с самым глубоким деревом.
    if opcode_var is None:
        from obfuscator.ast_nodes import (
            Block, WhileStat, RepeatStat, DoBlockStat)

        # (x, t, p, block, idx)
        cands = []

        def scan_block(block):
            for idx, st in enumerate(block.statements):
                if isinstance(st, AssignStat):
                    pairs = [(tg.name, vl)
                             for tg, vl in zip(st.targets, st.values)
                             if isinstance(tg, NameExpr)]
                elif isinstance(st, LocalAssignStat):
                    pairs = list(zip(st.names, st.values))
                else:
                    pairs = []
                for tname, vl in pairs:
                    vl = _unparen(vl)
                    if (isinstance(vl, IndexExpr)
                            and isinstance(vl.obj, NameExpr)
                            and isinstance(vl.index, NameExpr)
                            and tname != vl.obj.name):
                        trip = (tname, vl.obj.name, vl.index.name)
                        if not any(c[:3] == trip for c in cands):
                            cands.append(trip + (block, idx))
                # вложенные блоки
                for sub in (getattr(st, 'body', None),
                            getattr(st, 'block', None)):
                    if isinstance(sub, Block):
                        scan_block(sub)
                for _c, blk in getattr(st, 'branches', []) or []:
                    if isinstance(blk, Block):
                        scan_block(blk)
                if getattr(st, 'else_block', None) is not None:
                    scan_block(st.else_block)
            return

        def find_all_blocks(node):
            stack = [node]
            while stack:
                n = stack.pop()
                if isinstance(n, Block):
                    yield n
                stack.extend(_ast_children(n))

        for blk in find_all_blocks(chunk):
            for idx, st in enumerate(blk.statements):
                if isinstance(st, AssignStat):
                    pairs = [(tg.name, vl)
                             for tg, vl in zip(st.targets, st.values)
                             if isinstance(tg, NameExpr)]
                elif isinstance(st, LocalAssignStat):
                    pairs = list(zip(st.names, st.values))
                else:
                    pairs = []
                for tname, vl in pairs:
                    vl = _unparen(vl)
                    if (isinstance(vl, IndexExpr)
                            and isinstance(vl.obj, NameExpr)
                            and isinstance(vl.index, NameExpr)
                            and tname != vl.obj.name):
                        trip = (tname, vl.obj.name, vl.index.name)
                        if not any(c[:3] == trip for c in cands):
                            cands.append(trip + (blk, idx))

        def root_after(block, idx, varname):
            """Первый dispatch-if по varname среди statements[idx:]."""
            for st in block.statements[idx:]:
                if isinstance(st, IfStat) and any(
                        _expr_has_name(c, varname) for c, _b in st.branches):
                    return st
                # if может быть обёрнут в while/repeat/do того же блока?
                for sub in (getattr(st, 'body', None),
                            getattr(st, 'block', None)):
                    if isinstance(sub, Block):
                        r = root_after(sub, 0, varname)
                        if r is not None:
                            return r
            return None

        best = None
        best_score = 0
        best_root = None
        for trip in cands[:60]:
            x, t, p, blk, idx = trip
            root = root_after(blk, idx, x) or _find_root_if(x)
            score = _count_dispatch_nodes(root, x)
            if score > best_score:
                best, best_score, best_root = trip, score, root
        if best is not None and best_score >= 2:
            opcode_var, instr_var, pc_var = best[:3]
            dc.root_if = best_root
        elif cands:
            opcode_var, instr_var, pc_var = cands[0][:3]
            dc.root_if = _find_root_if(opcode_var)
    dc.opcode_var, dc.instr_var, dc.pc_var = (
        opcode_var or 'q', instr_var or 't', pc_var or 'E')

    # 2) корневой IfStat дерева по opcode_var (если не найден на шаге 1)
    if dc.root_if is None:
        dc.root_if = _find_root_if(dc.opcode_var)
    return dc


def extract_opcode_leaves(dc: DispatchChain, source: str = None,
                          unparse: bool = True):
    """Пройти if-дерево от dc.root_if; собрать листья (интервал + stmts)."""
    from obfuscator.ast_nodes import IfStat, Block
    varname = dc.opcode_var
    BIG = 1 << 30

    def is_dispatch_if(st):
        return isinstance(st, IfStat) and any(
            _expr_has_name(c, varname) for c, _b in st.branches)

    flip = {'<': '>=', '>=': '<', '<=': '>', '>': '<=', '==': '~=', '~=': '=='}

    def walk_block(block, iv, incoming, seg_offset=0):
        segs = []
        for st in block.statements:
            segs.append(('if', st) if is_dispatch_if(st) else ('stmt', st))
        if getattr(block, 'return_stat', None) is not None:
            segs.append(('stmt', block.return_stat))

        def rec(i, content):
            if i >= len(segs):
                if content:
                    dc.leaves.append({'iv': iv, 'stmts': content})
                return
            kind, payload = segs[i]
            if kind == 'stmt':
                rec(i + 1, content + [payload])
            else:
                walk_if(payload, iv, content)
                if i + 1 < len(segs):
                    rec(i + 1, content)  # хвостовые операторы — отдельный лист

        rec(seg_offset, list(incoming))

    def walk_if(st, iv, content):
        neg_all = []
        for cond, blk in st.branches:
            cons = _cond_constraints(cond, varname)
            neg_all += [(flip[op], v) for op, v in cons]
            civ = _apply_constraints(iv, cons)
            walk_block(blk, civ, content)
        if st.else_block is not None:
            eiv = _apply_constraints(iv, neg_all)
            walk_block(st.else_block, eiv, content)

    if dc.root_if is None:
        return dc
    walk_block(Block(statements=[dc.root_if]), (0, BIG), [])

    if unparse:
        from obfuscator.ast_unparser import ASTUnparser
        up = ASTUnparser(minified=True)
        for lf in dc.leaves:
            try:
                lf['text'] = ' '.join(up.unparse(s) for s in lf['stmts'])
            except Exception:  # noqa: BLE001
                lf['text'] = '<unparse error>'
    return dc


def static_opcode_map(source: str):
    """Полный статический анализ: DispatchChain по исходнику."""
    from obfuscator.lexer import Lexer
    from obfuscator.parser import Parser
    chunk = Parser(Lexer(source).tokenize()).parse()
    dc = find_dispatch_chain(chunk)
    extract_opcode_leaves(dc, source)
    return dc


# ---------------------------------------------------------------------------
# self-test: синтетическая мини-VM диспетчерной формы q=t[E]; if q==N ...
# ---------------------------------------------------------------------------

def _self_test() -> int:
    passed = failed = 0

    def check(name, cond, extra=''):
        nonlocal passed, failed
        if cond:
            passed += 1
            print('[OK] %s %s' % (name, extra))
        else:
            failed += 1
            print('[XX] %s %s' % (name, extra))

    mini = (
        '-- This file was protected using Luraph Obfuscator v14.6\n'
        'return({\n'
        '  S = function(L)\n'
        '    local t = {1, 2, 1, 3, 1}\n'
        '    local E = 1\n'
        '    local q\n'
        '    while E <= 5 do\n'
        '      q = t[E]\n'
        '      if q == 1 then\n'
        '        L:ADD(E, t[E])\n'
        '        E = E + 1\n'
        '      elseif q == 2 then\n'
        '        L:MULV()\n'
        '        E = E + 1\n'
        '      else\n'
        '        L:SUBV()\n'
        '        E = E + 1\n'
        '      end\n'
        '    end\n'
        '    return E\n'
        '  end,\n'
        '  ADD = function(L, a, b) return a + b end,\n'
        '  MULV = function(L) return 2 end,\n'
        '  SUBV = function(L) return 3 end\n'
        '}):S()()\n'
    )
    r = trace_opcodes(mini, max_steps=500_000)
    check('T1 mini opcode trace runs', r.error is None and r.steps > 0,
          'steps=%d err=%r' % (r.steps, r.error))
    check('T2 q=1 -> ADD', r.primary(1) == 'ADD',
          'got %r' % r.primary(1))
    check('T3 q=2 -> MULV, q=3 -> SUBV',
          r.primary(2) == 'MULV' and r.primary(3) == 'SUBV',
          'got %r %r' % (r.primary(2), r.primary(3)))
    d1 = r.q_stats.get(1, {}).get('dispatched', 0)
    d2 = r.q_stats.get(2, {}).get('dispatched', 0)
    d3 = r.q_stats.get(3, {}).get('dispatched', 0)
    check('T4 dispatch counts 3/1/1', (d1, d2, d3) == (3, 1, 1),
          'got %r' % ((d1, d2, d3),))
    disp_add = [d for d in r.dispatches if d[1] == 1 and d[3] == 'ADD']
    check('T5 operand window captured',
          bool(disp_add) and disp_add[0][5] is not None
          and disp_add[0][5][0] == 1,
          'first=%r' % ((disp_add[0] if disp_add else None),))
    rep = opcode_report(r)
    check('T6 report contains mapping',
          'opcode 1' in rep and 'ADD' in rep, '')

    # статическая карта на мини-диспетчере (дерево, а не цепочка ==)
    mini2 = (
        'return({\n'
        '  S = function(L)\n'
        '    local t = {1, 2, 5}\n'
        '    local E = 1\n'
        '    local q\n'
        '    while E <= 3 do\n'
        '      q = t[E]\n'
        '      if not(q >= 3) then\n'
        '        if q < 2 then\n'
        '          L:ADD()\n'
        '        else\n'
        '          L:MULV()\n'
        '        end\n'
        '      else\n'
        '        L:SUBV()\n'
        '      end\n'
        '      E = E + 1\n'
        '    end\n'
        '    return E\n'
        '  end,\n'
        '  ADD = function(L) return 1 end,\n'
        '  MULV = function(L) return 2 end,\n'
        '  SUBV = function(L) return 3 end\n'
        '}):S()()\n'
    )
    dc = static_opcode_map(mini2)
    check('T7 dispatcher autodetected (q,t,E)',
          (dc.opcode_var, dc.instr_var, dc.pc_var) == ('q', 't', 'E')
          and dc.root_if is not None,
          'vars=%r root=%r' % ((dc.opcode_var, dc.instr_var, dc.pc_var),
                               dc.root_if is not None))
    t1 = dc.text_for(1) or ''
    t2 = dc.text_for(2) or ''
    t5 = dc.text_for(5) or ''
    check('T8 static leaves: q=1 -> ADD, q=2 -> MULV, q>=3 -> SUBV',
          'ADD' in t1 and 'MULV' in t2 and 'SUBV' in t5,
          't1=%r t2=%r t5=%r' % (t1[:30], t2[:30], t5[:30]))
    check('T9 intervals exact',
          len(dc.opcodes_for(1)) == 1 and dc.opcodes_for(1)[0]['iv'] == (0, 1)
          and dc.opcodes_for(2)[0]['iv'] == (2, 2)
          and dc.opcodes_for(5)[0]['iv'][0] == 3,
          'ivs=%r' % [lf['iv'] for lf in dc.leaves])

    print('\nResult: %d/%d' % (passed, passed + failed))
    print('[OK] ALL PASSED' if failed == 0 else '[XX] FAILURES: %d' % failed)
    return 0 if failed == 0 else 1


def main(argv=None) -> int:
    import argparse
    import json
    ap = argparse.ArgumentParser(
        prog='py -m obfuscator.deobfuscator.luraph.vm_opcodes')
    ap.add_argument('file', nargs='?')
    ap.add_argument('--max-steps', type=int, default=8_000_000)
    ap.add_argument('--max-dispatches', type=int, default=50_000)
    ap.add_argument('--progress-every', type=int, default=0)
    ap.add_argument('--out', help='сохранить карту в JSON')
    ap.add_argument('--report', help='сохранить текстовую карту опкодов')
    ap.add_argument('--bodies', action='store_true',
                    help='в отчёт — тела обработчиков')
    ap.add_argument('--static', action='store_true',
                    help='только статическая карта (без прогона, мгновенно)')
    ap.add_argument('--static-json', help='сохранить статическую карту в JSON')
    ap.add_argument('--test', action='store_true')
    a = ap.parse_args(argv)

    if a.test or not a.file:
        return _self_test()

    with open(a.file, encoding='utf-8', errors='replace') as f:
        src = f.read()

    if a.static:
        dc = static_opcode_map(src)
        print('dispatcher vars: q=%s t=%s E=%s; root_if=%s; leaves=%d' % (
            dc.opcode_var, dc.instr_var, dc.pc_var,
            dc.root_if is not None, len(dc.leaves)))
        seen_ops = set()
        for lf in dc.leaves:
            lo, hi = lf['iv']
            if hi - lo <= 400:
                ops = list(range(lo, hi + 1))
                seen_ops.update(ops)
                print('  ops %-14s len(text)=%d' % (
                    ('%d..%d' % (lo, hi)) if lo != hi else str(lo),
                    len(lf.get('text') or '')))
            else:
                print('  ops %d..%d (unbounded?) len(text)=%d' % (
                    lo, hi, len(lf.get('text') or '')))
        if a.report:
            import os
            d = os.path.dirname(os.path.abspath(a.report))
            if d and not os.path.isdir(d):
                os.makedirs(d, exist_ok=True)
            with open(a.report, 'w', encoding='utf-8') as f:
                f.write('=== Luraph static opcode map ===\n\n')
                for lf in dc.leaves:
                    lo, hi = lf['iv']
                    f.write('opcode(s) %s\n%s\n\n' % (
                        ('%d..%d' % (lo, hi)) if lo != hi else str(lo),
                        lf.get('text') or ''))
            print('report -> %s' % a.report)
        if a.static_json:
            import os
            import json
            d = os.path.dirname(os.path.abspath(a.static_json))
            if d and not os.path.isdir(d):
                os.makedirs(d, exist_ok=True)
            obj = {
                'vars': {'opcode': dc.opcode_var, 'instr': dc.instr_var,
                         'pc': dc.pc_var},
                'leaves': [{'lo': lf['iv'][0],
                            'hi': None if lf['iv'][1] >= (1 << 30)
                            else lf['iv'][1],
                            'text': lf.get('text') or ''}
                           for lf in dc.leaves],
            }
            with open(a.static_json, 'w', encoding='utf-8') as f:
                json.dump(obj, f, ensure_ascii=False, indent=1)
            print('static json -> %s' % a.static_json)
        return 0

    print('tracing opcodes: %s (max_steps=%d)' % (a.file, a.max_steps))
    r = trace_opcodes(src, max_steps=a.max_steps,
                      max_dispatches=a.max_dispatches,
                      progress_every=a.progress_every or 2_000_000)
    print(r.summary())
    if a.out:
        import os
        d = os.path.dirname(os.path.abspath(a.out))
        if d and not os.path.isdir(d):
            os.makedirs(d, exist_ok=True)
        with open(a.out, 'w', encoding='utf-8') as f:
            json.dump(r.to_json_obj(), f, ensure_ascii=False, indent=1)
        print('saved -> %s' % a.out)
    if a.report:
        import os
        d = os.path.dirname(os.path.abspath(a.report))
        if d and not os.path.isdir(d):
            os.makedirs(d, exist_ok=True)
        with open(a.report, 'w', encoding='utf-8') as f:
            f.write(opcode_report(r, src, with_bodies=a.bodies))
        print('report -> %s' % a.report)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
