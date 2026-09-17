"""
NZL STUDIO - Sprint 4b: lifter VM-байткода в Lua AST
====================================================
Обратная операция к obfuscator/vm/compiler.py: регистровая машина ->
Lua-выражения/стейтменты.

Принципы:
  * регистры держат символьные Expr;
  * регистры, перезаписываемые внутри цикла, материализуются в локальные
    переменные (init-снапшот до цикла + присваивания в теле) — это даёт
    динамически точный код даже для аккумуляторов;
  * контрол-поток восстанавливается структурно по шаблонам компилятора:
      if/else        JMPIFNOT -> body -> [JMP -> else]
      and/or         JMPIFNOT/JMPIF + чистый expr-сегмент, пишущий тот же регистр
      while          cond-seg; JMPIFNOT -> end; body; JMP -> cond-seg
      repeat         body; JMPIFNOT -> назад на начало сегмента
      numeric for    FORPREP .. FORLOOP
      generic for    JMP -> TFORCALL; TFORLOOP -> назад
      break/continue JMP на loop_end / continue_pc текущего цикла
  * всё, что не подходит под шаблоны -> LiftError (функция остаётся
    виртуализированной — честно);
  * upvalues читаются по значению на момент CLOSURE (трансформер Sprint 4
    не виртуализирует функции, пишущие во внешние локальные);
  * семантика библиотечных опкодов зеркалит runtime_lua.py побайтово.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from obfuscator.ast_nodes import (
    AssignStat, BinaryOp, Block, BoolLit, BreakStat, CallExpr, CallStat,
    ContinueStat, Expr, FunctionExpr, GenericForStat, IfStat, IndexExpr,
    LocalAssignStat, LocalFunctionStat, MethodCallExpr, NameExpr, NilLit,
    NumberLit,
    NumericForStat, RepeatStat, ReturnStat, Stat, StringLit, TableExpr,
    TableField, UnaryOp, VarargLit, WhileStat,
)
from obfuscator.vm.opcodes import ConstantType, Opcode, Proto


class LiftError(ValueError):
    """Байткод не поднимается в Lua структурно."""


_BINOPS = {
    Opcode.ADD: '+', Opcode.SUB: '-', Opcode.MUL: '*', Opcode.DIV: '/',
    Opcode.MOD: '%', Opcode.POW: '^', Opcode.IDIV: '//', Opcode.CONCAT: '..',
    Opcode.EQ: '==', Opcode.NEQ: '~=', Opcode.LT: '<', Opcode.LE: '<=',
    Opcode.GT: '>', Opcode.GE: '>=',
}

_BITOPS = {
    Opcode.BAND: 'band', Opcode.BOR: 'bor', Opcode.BXOR: 'bxor',
    Opcode.SHL: 'lshift', Opcode.SHR: 'rshift',
    Opcode.LROT: 'lrotate', Opcode.RROT: 'rrotate',
}

_UNOPS = {Opcode.UNM: '-', Opcode.NOT: 'not', Opcode.LEN: '#'}

_LIB1 = {
    Opcode.ABS: ('math', 'abs'), Opcode.FLOOR: ('math', 'floor'),
    Opcode.CEIL: ('math', 'ceil'), Opcode.SQRT: ('math', 'sqrt'),
    Opcode.TYPEOF: ('', 'type'), Opcode.TONUM: ('', 'tonumber'),
    Opcode.TOSTR: ('', 'tostring'),
    Opcode.UPPER: ('string', 'upper'), Opcode.LOWER: ('string', 'lower'),
}

# семантические алиасы (см. opmap_recovery.SEMANTIC_EQ)
_ALIAS = {
    Opcode.DUP: Opcode.MOVE,
    Opcode.RAWGET: Opcode.GETTABLE,
    Opcode.RAWSET: Opcode.SETTABLE,
    Opcode.STRLEN: Opcode.LEN,
    Opcode.GETTABLE_K: Opcode.GETFIELD,
    Opcode.SETTABLE_K: Opcode.SETFIELD,
    Opcode.YIELDK: Opcode.SELECT,
}

_JUMPS = (Opcode.JMP, Opcode.JMPBACK, Opcode.JMPIF, Opcode.JMPIFNOT,
          Opcode.FORPREP, Opcode.FORLOOP, Opcode.TFORCALL, Opcode.TFORLOOP)

# опкоды, НЕ пишущие r[a] (стейтменты / служебные)
_NO_A_WRITE = set(_JUMPS) | {
    Opcode.RETURN, Opcode.TAILCALL, Opcode.SETGLOBAL, Opcode.SETUPVAL,
    Opcode.NOP, Opcode.CLOSE, Opcode.CHECKSUM,
    Opcode.SETTABLE, Opcode.SETFIELD, Opcode.SETLIST,
    Opcode.TBLINSERT, Opcode.APPEND,
}


def _dot(obj_name: str, field: str) -> IndexExpr:
    return IndexExpr(obj=NameExpr(name=obj_name),
                     index=NameExpr(name=field), is_dot=True)


def _lib_call(lib: str, fn: str, args: List[Expr]) -> CallExpr:
    func: Expr = _dot(lib, fn) if lib else NameExpr(name=fn)
    return CallExpr(func=func, args=args)


class _Ctx:
    __slots__ = ('loop_end', 'cont_pc', 'depth')

    def __init__(self, loop_end=None, cont_pc=None, depth=0):
        self.loop_end = loop_end
        self.cont_pc = cont_pc
        self.depth = depth


def _written_regs(code, s: int, e: int) -> set:
    W = set()
    for q in range(s, min(e, len(code))):
        ins = code[q]
        op = _ALIAS.get(ins.op, ins.op)
        if op in _NO_A_WRITE:
            continue
        if op == Opcode.LOADNIL:
            W.update(range(ins.a, ins.a + ins.b + 1))
        else:
            W.add(ins.a)
        if op == Opcode.SELF:
            W.add(ins.a + 1)
    return W


_TABLE_MUTATORS = (Opcode.SETTABLE, Opcode.SETFIELD, Opcode.SETLIST,
                   Opcode.APPEND, Opcode.TBLINSERT)


def _mutated_table_regs(code, s: int, e: int, snap) -> set:
    """Если в диапазоне есть мутаторы таблиц — материализуем ВСЕ
    регистры, держащие TableExpr-литералы на входе в цикл: литерал,
    мутируемый из тела, обязан стать локальной переменной, иначе
    in-place append статически неправилен (тело исполняется N раз)."""
    has_mut = any(
        _ALIAS.get(code[q].op, code[q].op) in _TABLE_MUTATORS
        for q in range(s, min(e, len(code))))
    if not has_mut:
        return set()
    return {q for q, v in snap.items() if isinstance(v, TableExpr)}


class Lifter:
    def __init__(self, proto: Proto, upval_exprs: Optional[List[Expr]] = None,
                 counter: Optional[List[int]] = None):
        self.proto = proto
        self.upvals = list(upval_exprs or [])
        self.regs: Dict[int, Expr] = {}
        self._mats: List[Dict[int, str]] = []
        self._snaps: Dict[int, Dict[int, Expr]] = {}
        # ОБЩИЙ счётчик имён: параметры вложенной функции не должны
        # совпадать с параметрами/upvalues внешней (теней быть не должно)
        self._cnt = counter if counter is not None else [0]

    # ── helpers ────────────────────────────────────────────────
    def name(self, prefix: str) -> str:
        self._cnt[0] += 1
        return f'{prefix}_{self._cnt[0]}'

    def const_expr(self, kidx: int) -> Expr:
        c = self.proto.constants[kidx]
        if c.type == ConstantType.NIL:
            return NilLit()
        if c.type == ConstantType.BOOL:
            return BoolLit(value=bool(c.value))
        if c.type == ConstantType.NUMBER:
            return NumberLit(value=c.value)
        if c.type == ConstantType.STRING:
            return StringLit(value=str(c.value))
        raise LiftError(f'const #{kidx} is not a value')

    def reg(self, i: int) -> Expr:
        e = self.regs.get(i)
        if e is None:
            raise LiftError(f'register r{i} read before set')
        return e

    def wreg(self, a: int, expr: Expr) -> Optional[Stat]:
        """Запись регистра; если он материализован — AssignStat."""
        m = self._mats[-1] if self._mats else {}
        if a in m:
            self.regs[a] = NameExpr(name=m[a])
            return AssignStat(targets=[NameExpr(name=m[a])], values=[expr])
        self.regs[a] = expr
        return None

    def _materialize(self, snap: Dict[int, Expr],
                     W: set) -> Tuple[List[Stat], Dict[int, str]]:
        m: Dict[int, str] = {}
        inits: List[Stat] = []
        for q in sorted(W):
            nm = self.name('R')
            m[q] = nm
            inits.append(LocalAssignStat(
                names=[nm], values=[snap.get(q) or NilLit()],
                attribs=[None]))
        self._mats.append(m)
        for q, nm in m.items():
            self.regs[q] = NameExpr(name=nm)
        return inits, m

    def _dematerialize(self, m: Dict[int, str]) -> List[Stat]:
        self._mats.pop()
        back: List[Stat] = []
        if self._mats:
            outer = self._mats[-1]
            for q in sorted(m):
                if q in outer:
                    back.append(AssignStat(
                        targets=[NameExpr(name=outer[q])],
                        values=[NameExpr(name=m[q])]))
        return back

    # ── proto -> FunctionExpr ──────────────────────────────────
    def lift_function(self) -> FunctionExpr:
        params = [self.name('a') for _ in range(self.proto.num_params)]
        for i, p in enumerate(params):
            self.regs[i] = NameExpr(name=p)
        body = self.lift_block(self.proto.code, 0, len(self.proto.code),
                               _Ctx())
        return FunctionExpr(params=params,
                            is_vararg=bool(self.proto.is_vararg),
                            body=body)

    # ── structured block ───────────────────────────────────────
    @staticmethod
    def _jump_target(code, i) -> int:
        return i + 1 + code[i].k

    def lift_block(self, code, start: int, end: int, ctx: _Ctx) -> Block:
        if ctx.depth > 40:
            raise LiftError('nesting too deep')
        out: List[Stat] = []
        out_pc: List[int] = []
        seg_pc = start
        i = start
        while i < end:
            self._snaps.setdefault(i, dict(self.regs))
            ins = code[i]
            op = _ALIAS.get(ins.op, ins.op)

            # ── JMP: generic-for prep / break / continue ──
            if op == Opcode.JMP or op == Opcode.JMPBACK:
                t = self._jump_target(code, i)
                # generic for: JMP -> TFORCALL; TFORLOOP -> body
                if (op == Opcode.JMP and t + 1 < end
                        and code[t].op == Opcode.TFORCALL
                        and code[t + 1].op == Opcode.TFORLOOP):
                    res = self._lift_generic_for(code, i, t, end, ctx)
                    if res is not None:
                        stats, new_i, pc0 = res
                        out.extend(stats)
                        out_pc.extend([pc0] * len(stats))
                        seg_pc = new_i
                        i = new_i
                        continue
                if ctx.loop_end is not None and t == ctx.loop_end:
                    out.append(BreakStat())
                    out_pc.append(i)
                    i += 1
                    continue
                if ctx.cont_pc is not None and t == ctx.cont_pc:
                    out.append(ContinueStat())
                    out_pc.append(i)
                    i += 1
                    continue
                raise LiftError(f'unstructured JMP at {i} -> {t}')

            # ── JMPIF / JMPIFNOT ──
            if op == Opcode.JMPIFNOT or op == Opcode.JMPIF:
                t = self._jump_target(code, i)

                # repeat: прыжок назад
                if t <= i:
                    if op != Opcode.JMPIFNOT or t >= i:
                        raise LiftError(f'backward {op.name} at {i}->{t}')
                    res = self._lift_repeat(code, out, out_pc, i, t, ctx)
                    out, out_pc, seg_pc, i = res
                    continue

                # while: cond-сегмент [t2, i), в конце тела JMP -> t2
                if op == Opcode.JMPIFNOT and i + 1 < t <= end and t - 1 > i:
                    back = t - 1
                    if code[back].op in (Opcode.JMP, Opcode.JMPBACK):
                        t2 = self._jump_target(code, back)
                        if (start <= t2 <= i
                                and all(p < t2 or p >= i
                                        for p in out_pc)):
                            res = self._lift_while(code, out, out_pc,
                                                   i, t, t2, ins, ctx)
                            out, out_pc, seg_pc, i = res
                            continue

                # and/or short-circuit: сегмент пишет тот же регистр
                w_seg = _written_regs(code, i + 1, t)
                if ins.a in w_seg:
                    left = self.reg(ins.a)
                    blk = self.lift_block(code, i + 1, t,
                                          _Ctx(None, None, ctx.depth + 1))
                    if not blk.statements:
                        # статический мердж: a and b / a or b
                        right = self.reg(ins.a)
                        merged = BinaryOp(
                            op='or' if op == Opcode.JMPIF else 'and',
                            left=left, right=right)
                        st = self.wreg(ins.a, merged)
                        if st is not None:
                            out.append(st)
                            out_pc.append(i)
                    else:
                        # сегмент внутри цикла (материализованные локальные):
                        # динамический if — справа присваивания R-локалам
                        cond = left
                        if op == Opcode.JMPIF:
                            cond = UnaryOp(op='not', operand=cond)
                        out.append(IfStat(branches=[(cond, blk)]))
                        out_pc.append(i)
                    i = t
                    continue

                if op == Opcode.JMPIF:
                    raise LiftError(f'bare JMPIF at {i}')

                # if ... [else ...] end
                if i + 1 < t <= end:
                    e = None
                    if (t - 1 > i
                            and code[t - 1].op in (Opcode.JMP,
                                                   Opcode.JMPBACK)):
                        e0 = self._jump_target(code, t - 1)
                        if (t < e0 <= end
                                and e0 != ctx.loop_end
                                and e0 != ctx.cont_pc):
                            e = e0
                    if e is not None:
                        then_b = self.lift_block(
                            code, i + 1, t - 1,
                            _Ctx(ctx.loop_end, ctx.cont_pc, ctx.depth + 1))
                        else_b = self.lift_block(
                            code, t, e,
                            _Ctx(ctx.loop_end, ctx.cont_pc, ctx.depth + 1))
                        out.append(IfStat(
                            branches=[(self.reg(ins.a), then_b)],
                            else_block=else_b))
                        out_pc.append(i)
                        seg_pc = e
                        i = e
                        continue
                    then_b = self.lift_block(
                        code, i + 1, t,
                        _Ctx(ctx.loop_end, ctx.cont_pc, ctx.depth + 1))
                    out.append(IfStat(branches=[(self.reg(ins.a), then_b)]))
                    out_pc.append(i)
                    seg_pc = t
                    i = t
                    continue

                raise LiftError(f'unstructured JMPIF at {i}')

            # ── numeric for ──
            if op == Opcode.FORPREP:
                j = None
                for q in range(i + 1, end):
                    if code[q].op == Opcode.FORLOOP and code[q].a == ins.a:
                        j = q
                        break
                if j is None:
                    raise LiftError('FORPREP without FORLOOP')
                a = ins.a
                start_e, stop_e = self.reg(a), self.reg(a + 1)
                step_e = self.reg(a + 2)
                W = _written_regs(code, i + 1, j) - {a, a + 1, a + 2, a + 3}
                W |= _mutated_table_regs(code, i + 1, j, self._snaps[i])
                inits, m = self._materialize(self._snaps[i], W)
                var = self.name('i')
                self.regs[a + 3] = NameExpr(name=var)
                # FORLOOP держит счётчик r[a] == var на всём теле
                self.regs[a] = NameExpr(name=var)
                fbody = self.lift_block(
                    code, i + 1, j,
                    _Ctx(loop_end=j + 1, cont_pc=j, depth=ctx.depth + 1))
                back = self._dematerialize(m)
                step_arg = None
                if not (isinstance(step_e, NumberLit) and step_e.value == 1):
                    step_arg = step_e
                stats = inits + [NumericForStat(
                    var=var, start=start_e, stop=stop_e, step=step_arg,
                    body=fbody)] + back
                out.extend(stats)
                out_pc.extend([i] * len(stats))
                seg_pc = j + 1
                i = j + 1
                continue

            # ── plain instruction ──
            stmts = self.lift_instr(ins)
            out.extend(stmts)
            out_pc.extend([i] * len(stmts))
            if any(isinstance(s, (ReturnStat,)) for s in stmts):
                i += 1
                break
            i += 1

        return Block(statements=out)

    # ── while ──────────────────────────────────────────────────
    def _lift_while(self, code, out, out_pc, i, t, t2, ins,
                    ctx) -> Tuple[List[Stat], List[int], int, int]:
        # continue внутри while = JMP на t2 (пересчёт cond) — в repeat-форме
        # Luau-continue его пропустит, поэтому честно отказываемся
        for q in range(i + 1, t - 1):
            if (code[q].op in (Opcode.JMP, Opcode.JMPBACK)
                    and self._jump_target(code, q) == t2):
                raise LiftError('continue inside while unsupported')
        W = _written_regs(code, t2, t)
        snap = self._snaps.get(t2, {})
        W |= _mutated_table_regs(code, t2, t, snap)
        inits, m = self._materialize(snap, W)
        cond1 = self.lift_block(code, t2, i,
                                _Ctx(None, None, ctx.depth + 1)).statements
        cond_expr = self.reg(ins.a)
        body = self.lift_block(code, i + 1, t - 1,
                               _Ctx(loop_end=t, cont_pc=None,
                                    depth=ctx.depth + 1)).statements
        cond2 = self.lift_block(code, t2, i,
                                _Ctx(None, None, ctx.depth + 1)).statements
        back = self._dematerialize(m)
        if body and isinstance(body[-1], (BreakStat, ReturnStat)):
            body = body  # cond2 не нужен — цикл в любом случае выходит
        else:
            body = body + cond2
        stats = inits + cond1 + [WhileStat(
            cond=cond_expr, body=Block(statements=body))] + back
        out.extend(stats)
        out_pc.extend([t2] * len(stats))
        return out, out_pc, t, t

    # ── repeat ─────────────────────────────────────────────────
    def _lift_repeat(self, code, out, out_pc, i, t,
                     ctx) -> Tuple[List[Stat], List[int], int, int]:
        split = len(out)
        for idx, pc in enumerate(out_pc):
            if pc >= t:
                split = idx
                break
        W = _written_regs(code, t, i)
        snap = self._snaps.get(t, {})
        W |= _mutated_table_regs(code, t, i, snap)
        self.regs = dict(snap)
        inits, m = self._materialize(snap, W)
        body = self.lift_block(code, t, i,
                               _Ctx(loop_end=i + 1, cont_pc=i,
                                    depth=ctx.depth + 1))
        cond_expr = self.reg(code[i].a)
        back = self._dematerialize(m)
        stats = inits + [RepeatStat(body=body, cond=cond_expr)] + back
        new_out = out[:split] + stats
        new_pc = out_pc[:split] + [t] * len(stats)
        return new_out, new_pc, i + 1, i + 1

    # ── generic for ────────────────────────────────────────────
    def _lift_generic_for(self, code, i, t, end,
                          ctx) -> Optional[Tuple[List[Stat], int, int]]:
        call = code[t]
        a = call.a
        nvars = call.b
        exprs = [self.reg(a), self.reg(a + 1), self.reg(a + 2)]
        while exprs and isinstance(exprs[-1], NilLit):
            exprs.pop()
        names = [self.name('v') for _ in range(nvars)]
        var_regs = {a + 3 + q for q in range(nvars)}
        W = (_written_regs(code, i + 1, t)
             - {a, a + 1, a + 2} - var_regs)
        W |= _mutated_table_regs(code, i + 1, t, self._snaps[i])
        inits, m = self._materialize(self._snaps[i], W)
        for q, nm in enumerate(names):
            self.regs[a + 3 + q] = NameExpr(name=nm)
        body = self.lift_block(code, i + 1, t,
                               _Ctx(loop_end=t + 2, cont_pc=t,
                                    depth=ctx.depth + 1))
        back = self._dematerialize(m)
        stats = inits + [GenericForStat(names=names, exprs=exprs,
                                        body=body)] + back
        return stats, t + 2, i

    # ── one instruction ────────────────────────────────────────
    def lift_instr(self, ins) -> List[Stat]:
        op = _ALIAS.get(ins.op, ins.op)
        a, b, c, k = ins.a, ins.b, ins.c, ins.k
        out: List[Stat] = []

        def w(idx: int, expr: Expr) -> None:
            st = self.wreg(idx, expr)
            if st is not None:
                out.append(st)

        if op == Opcode.LOADK:
            w(a, self.const_expr(k))
        elif op == Opcode.LOADN:
            w(a, NumberLit(value=b - 256 if b >= 128 else b))
        elif op == Opcode.LOADBOOL:
            w(a, BoolLit(value=b != 0))
        elif op == Opcode.LOADNIL:
            for q in range(a, a + b + 1):
                w(q, NilLit())
        elif op == Opcode.MOVE:
            w(a, self.reg(b))
        elif op in _BINOPS:
            w(a, BinaryOp(op=_BINOPS[op], left=self.reg(b),
                          right=self.reg(c)))
        elif op in _BITOPS:
            w(a, _lib_call('bit32', _BITOPS[op],
                           [self.reg(b), self.reg(c)]))
        elif op == Opcode.BNOT:
            w(a, _lib_call('bit32', 'bnot', [self.reg(b)]))
        elif op in _UNOPS:
            w(a, UnaryOp(op=_UNOPS[op], operand=self.reg(b)))
        elif op in _LIB1:
            lib, fn = _LIB1[op]
            w(a, _lib_call(lib, fn, [self.reg(b)]))
        elif op == Opcode.MMIN:
            w(a, _lib_call('math', 'min', [self.reg(b), self.reg(c)]))
        elif op == Opcode.MMAX:
            w(a, _lib_call('math', 'max', [self.reg(b), self.reg(c)]))
        elif op == Opcode.GETGLOBAL:
            w(a, NameExpr(name=str(self.const_expr(k).value)))
        elif op == Opcode.SETGLOBAL:
            out.append(AssignStat(
                targets=[NameExpr(name=str(self.const_expr(k).value))],
                values=[self.reg(a)]))
        elif op == Opcode.GETUPVAL:
            if b >= len(self.upvals):
                raise LiftError(f'upvalue {b} not captured')
            w(a, self.upvals[b])
        elif op == Opcode.SETUPVAL:
            tgt = self.upvals[b] if b < len(self.upvals) else None
            if not isinstance(tgt, NameExpr):
                raise LiftError('write to non-name upvalue')
            out.append(AssignStat(targets=[NameExpr(name=tgt.name)],
                                  values=[self.reg(a)]))
        elif op == Opcode.NEWTABLE:
            w(a, TableExpr(fields=[]))
        elif op == Opcode.SETFIELD:
            key = StringLit(value=str(self.const_expr(k).value))
            tbl = self.regs.get(a)
            if isinstance(tbl, TableExpr):
                tbl.fields.append(TableField(key=key, value=self.reg(b),
                                             is_name=True))
            else:
                out.append(AssignStat(
                    targets=[IndexExpr(obj=self.reg(a), index=key,
                                       is_dot=True)],
                    values=[self.reg(b)]))
        elif op == Opcode.SETTABLE:
            key_e = self.reg(b)
            tbl = self.regs.get(a)
            if isinstance(tbl, TableExpr):
                if (isinstance(key_e, NumberLit)
                        and float(key_e.value).is_integer()):
                    tbl.fields.append(TableField(key=None,
                                                 value=self.reg(c)))
                else:
                    tbl.fields.append(TableField(key=key_e,
                                                 value=self.reg(c),
                                                 is_name=False))
            else:
                out.append(AssignStat(
                    targets=[IndexExpr(obj=self.reg(a), index=key_e,
                                       is_dot=False)],
                    values=[self.reg(c)]))
        elif op == Opcode.SETLIST:
            tbl = self.regs.get(a)
            if isinstance(tbl, TableExpr):
                for q in range(1, b + 1):
                    tbl.fields.append(TableField(key=None,
                                                 value=self.reg(a + q)))
            else:
                for q in range(1, b + 1):
                    out.append(AssignStat(
                        targets=[IndexExpr(
                            obj=self.reg(a),
                            index=BinaryOp(op='+', left=NumberLit(value=c),
                                           right=NumberLit(value=q)),
                            is_dot=False)],
                        values=[self.reg(a + q)]))
        elif op == Opcode.GETTABLE:
            w(a, IndexExpr(obj=self.reg(b), index=self.reg(c),
                           is_dot=False))
        elif op == Opcode.GETFIELD:
            w(a, IndexExpr(obj=self.reg(b),
                           index=StringLit(
                               value=str(self.const_expr(k).value)),
                           is_dot=True))
        elif op == Opcode.SELF:
            idx = self.reg(c)
            obj = self.reg(b)
            w(a + 1, obj)
            if isinstance(idx, StringLit):
                w(a, IndexExpr(obj=obj, index=idx, is_dot=True))
            else:
                w(a, IndexExpr(obj=obj, index=idx, is_dot=False))
        elif op == Opcode.CALL:
            n_args = b - 1
            n_rets = c - 1
            if n_rets not in (0, 1):
                raise LiftError('multi-result CALL unsupported')
            call = self._make_call(self.reg(a),
                                   [self.reg(a + 1 + q)
                                    for q in range(n_args)])
            if n_rets == 1:
                w(a, call)
            else:
                out.append(CallStat(call=call))
        elif op == Opcode.TAILCALL:
            n_args = b - 1
            call = self._make_call(self.reg(a),
                                   [self.reg(a + 1 + q)
                                    for q in range(n_args)])
            out.append(ReturnStat(values=[call]))
        elif op == Opcode.RETURN:
            if b == 0:
                out.append(ReturnStat(values=[]))
            else:
                out.append(ReturnStat(
                    values=[self.reg(a + q) for q in range(b)]))
        elif op == Opcode.CLOSURE:
            cidx = self._proto_ref(k)
            child = self.proto.protos[cidx]
            # self-рекурсия: closure захватывает регистр, в который
            # сама же и пишется -> local function fn_N (рекурсия через
            # собственное имя, как в исходнике)
            self_rec = any(instack and index == a
                           for instack, index in child.upvalues)
            fname = self.name('fn') if self_rec else None
            up_exprs: List[Expr] = []
            for instack, index in child.upvalues:
                if instack:
                    if self_rec and index == a:
                        up_exprs.append(NameExpr(name=fname))
                    else:
                        up_exprs.append(self.reg(index))
                else:
                    if index >= len(self.upvals):
                        raise LiftError('nested upvalue out of range')
                    up_exprs.append(self.upvals[index])
            sub_fn = Lifter(child, up_exprs, self._cnt).lift_function()
            if self_rec:
                out.append(LocalFunctionStat(name=fname, func=sub_fn))
                w(a, NameExpr(name=fname))
            else:
                w(a, sub_fn)
        elif op == Opcode.VARARG:
            packed = TableExpr(fields=[TableField(key=None,
                                                  value=VarargLit())])
            if b == 1:
                w(a, IndexExpr(obj=packed, index=NumberLit(value=1),
                               is_dot=False))
            else:
                w(a, packed)
        elif op in (Opcode.TBLCONCAT,):
            w(a, _lib_call('table', 'concat',
                           [self.reg(b), self.reg(c)]))
        elif op == Opcode.TBLFIND:
            w(a, _lib_call('table', 'find', [self.reg(b), self.reg(c)]))
        elif op == Opcode.TBLREMOVE:
            args = [self.reg(b)]
            try:
                rc = self.reg(c)
                if not isinstance(rc, NilLit):
                    args.append(rc)
            except LiftError:
                pass
            w(a, _lib_call('table', 'remove', args))
        elif op in (Opcode.TBLINSERT, Opcode.APPEND):
            tgt = self.reg(b) if op == Opcode.TBLINSERT else self.reg(a)
            val = self.reg(c) if op == Opcode.TBLINSERT else self.reg(b)
            out.append(CallStat(call=_lib_call('table', 'insert',
                                               [tgt, val])))
        elif op == Opcode.CHAR:
            w(a, _lib_call('string', 'char',
                           [self.reg(q) for q in range(b, c + 1)]))
        elif op == Opcode.BYTE:
            try:
                pos: Expr = BinaryOp(op='or', left=self.reg(c),
                                     right=NumberLit(value=1))
            except LiftError:
                pos = NumberLit(value=1)
            w(a, _lib_call('string', 'byte', [self.reg(b), pos]))
        elif op == Opcode.SUBSTR:
            rc = self.reg(c)
            w(a, _lib_call('string', 'sub', [
                self.reg(b), rc,
                BinaryOp(op='+', left=rc, right=NumberLit(value=1))]))
        elif op == Opcode.REP:
            w(a, _lib_call('string', 'rep', [self.reg(b), self.reg(c)]))
        elif op == Opcode.STRFMT:
            w(a, _lib_call('string', 'format', [self.reg(b), self.reg(c)]))
        elif op in (Opcode.NOP, Opcode.CLOSE, Opcode.CHECKSUM):
            return []
        else:
            raise LiftError(f'unsupported opcode {ins.op.name}')
        return out

    def _make_call(self, fn: Expr, args: List[Expr]) -> Expr:
        return CallExpr(func=fn, args=args)

    def _proto_ref(self, kidx: int) -> int:
        c = self.proto.constants[kidx]
        if c.type != ConstantType.PROTO:
            raise LiftError(f'const #{kidx} is not a proto ref')
        return int(c.value)


def lift_proto(proto: Proto,
               upval_exprs: Optional[List[Expr]] = None) -> FunctionExpr:
    return Lifter(proto, upval_exprs).lift_function()


def _test() -> None:
    import os
    import sys
    root = os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))))
    if root not in sys.path:
        sys.path.insert(0, root)

    from obfuscator.ast_unparser import unparse
    from obfuscator.deobfuscator.core.lua_sandbox import LuaSandbox
    from obfuscator.lexer import Lexer
    from obfuscator.parser import Parser
    from obfuscator.vm.compiler import compile_function

    passed = failed = 0

    def check(label: str, ok: bool, extra: str = '') -> None:
        nonlocal passed, failed
        if ok:
            passed += 1
            print(f'  [OK] {label}' + (f'  {extra}' if extra else ''))
        else:
            failed += 1
            print(f'  [XX] {label}' + (f'  {extra}' if extra else ''))

    print('=' * 60)
    print('  vm_decompile.lifter — tests')
    print('=' * 60)

    cases = [
        ("local function f(a, b) local x = a + b * 2 return x - 1 end",
         "result = f(6, 3)", 11),
        ("local function g(n) if n <= 1 then return 1 end "
         "return n * g(n - 1) end", "result = g(5)", 120),
        ("local function h() local t = {} for i = 1, 4 do t[i] = i * i end "
         "return t[3] end", "result = h()", 9),
        ("local function c(...) local t = {...} local n = 0 "
         "for i = 1, #t do n = n + t[i] end return n end",
         "result = c(1,2,3,4)", 10),
        ("local function ip(t) local n = 0 for i, v in ipairs(t) do "
         "n = n + v end return n end", "result = ip({1,2,3})", 6),
        ("local function w(n) local s = 0 while n > 0 do s = s + n % 10 "
         "n = n // 10 end return s end", "result = w(12345)", 15),
        ("local function mm(t) local mx = t[1] for i = 2, #t do "
         "if t[i] > mx then mx = t[i] end end return mx end",
         "result = mm({3,9,2,7})", 9),
        ("local function sw(x) local r = 0 repeat r = r + 1 x = x - 1 "
         "until x <= 0 return r end", "result = sw(3)", 3),
        ("local function br(t) local n = 0 for i = 1, #t do "
         "if t[i] < 0 then break end n = n + 1 end return n end",
         "result = br({1,2,-3,4})", 2),
        ("local function ao(a, b) return a or 7 end",
         "result = ao(nil, 1)", 7),
        ("local function an(a) local b = a and a * 2 return b end",
         "result = an(4)", 8),
        ("local function wc(t) local n = 0 local i = 1 "
         "while i <= #t and t[i] > 0 do n = n + t[i] i = i + 1 end "
         "return n end", "result = wc({1,2,0,5})", 3),
        ("local function mt(o) return o:get(2) end",
         "local obj = {v = 10} obj.get = function(self, x) "
         "return self.v + x end result = mt(obj)", 12),
        ("local function st(t) t.x = 5 t[2] = 7 return t.x + t[2] end",
         "result = st({})", 12),
        ("local function fib(n) if n < 2 then return n end "
         "return fib(n-1) + fib(n-2) end", "result = fib(10)", 55),
        ("local function nest(t) local s = 0 for i = 1, #t do "
         "for j = 1, #t[i] do s = s + t[i][j] end end return s end",
         "result = nest({{1,2},{3,4}})", 10),
    ]

    sb = LuaSandbox()
    for src, call, want in cases:
        ast = Parser(Lexer(src).tokenize()).parse()
        lfs = ast.body.statements[0]
        fname = getattr(lfs, 'name', None) or 'f'
        proto = compile_function(lfs.func, name=fname)
        label = src[13:45].replace('\n', ' ')
        try:
            fn = lift_proto(proto)
            from obfuscator.ast_nodes import LocalFunctionStat
            lfs_node = LocalFunctionStat(name=fname, func=fn)
            lifted_src = unparse(lfs_node) + '\n' + call
            got = sb.execute(lifted_src).get('result')
            check(f'lift+run: {label}...', got == want,
                  f'want={want} got={got!r}')
        except LiftError as e:
            check(f'lift+run: {label}...', False, f'LiftError: {e}')
        except Exception as e:  # noqa: BLE001
            check(f'lift+run: {label}...', False,
                  f'{type(e).__name__}: {str(e)[:70]}')

    total = passed + failed
    print('=' * 60)
    print(f'  Result: {passed}/{total}')
    if failed:
        sys.exit(1)
    print('  [OK] ALL PASSED')


if __name__ == '__main__':
    _test()
