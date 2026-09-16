"""
NZL Studio Obfuscator — Part 10b: VM Compiler

Компилирует AST функции в байткод (Proto).

Ключевой фикс:
- local function fn() ... fn() ... end
  теперь компилируется корректно:
  имя функции forward-declare'ится в родительском scope,
  а внутри вложенной функции резолвится как UPVALUE, а не GETGLOBAL.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from ..ast_nodes import (
    Expr,
    Stat,
    NameExpr,
    IndexExpr,
    CallExpr,
    MethodCallExpr,
    FunctionExpr,
    FunctionDeclStat,
    LocalFunctionStat,
    LocalAssignStat,
    AssignStat,
    CompoundAssignStat,
    CallStat,
    NumericForStat,
    GenericForStat,
    DoBlockStat,
    WhileStat,
    RepeatStat,
    IfStat,
    ReturnStat,
    BreakStat,
    ContinueStat,
    GotoStat,
    LabelStat,
    ParenExpr,
    TableExpr,
    NilLit,
    BoolLit,
    NumberLit,
    StringLit,
    VarargLit,
    BinaryOp,
    UnaryOp,
    Block,
)
from .opcodes import Opcode, Proto


# ╔══════════════════════════════════════════════════════════════════════════╗
#  EXCEPTIONS
# ╚══════════════════════════════════════════════════════════════════════════╝

class CompileError(Exception):
    """Ошибка компиляции — функция не может быть VM'изирована."""
    pass


class UnsupportedFeature(CompileError):
    """Функция использует фичу, которую VM пока не поддерживает."""
    pass


# ╔══════════════════════════════════════════════════════════════════════════╗
#  REGISTER ALLOCATOR
# ╚══════════════════════════════════════════════════════════════════════════╝

class RegisterAllocator:
    """
    Простой стековый allocator регистров.

    Регистры используются по номерам 0..255.
    Локальные переменные "прикручены" к конкретным регистрам,
    временные — освобождаются после использования.
    """

    MAX_REGISTERS = 250

    def __init__(self):
        self.next_free: int = 0
        self.max_used: int = 0

    def allocate(self) -> int:
        """Выделить один регистр."""
        if self.next_free >= self.MAX_REGISTERS:
            raise CompileError(f'Слишком много регистров (>{self.MAX_REGISTERS})')
        r = self.next_free
        self.next_free += 1
        if self.next_free > self.max_used:
            self.max_used = self.next_free
        return r

    def allocate_range(self, count: int) -> int:
        """Выделить N последовательных регистров, вернуть первый."""
        first = self.next_free
        for _ in range(count):
            self.allocate()
        return first

    def free_to(self, level: int) -> None:
        """Освободить все регистры выше/равно level."""
        if level < self.next_free:
            self.next_free = level

    def current_level(self) -> int:
        return self.next_free


# ╔══════════════════════════════════════════════════════════════════════════╗
#  LOCAL SCOPE
# ╚══════════════════════════════════════════════════════════════════════════╝

class LocalScope:
    """
    Один scope внутри функции.

    Отслеживает какая локальная переменная в каком регистре.
    """

    def __init__(self, parent: Optional['LocalScope'] = None, reg_level: int = 0):
        self.parent = parent
        self.locals: Dict[str, int] = {}
        self.reg_level = reg_level

    def define(self, name: str, reg: int) -> None:
        self.locals[name] = reg

    def resolve(self, name: str) -> Optional[int]:
        """Вернуть регистр локальной переменной или None."""
        if name in self.locals:
            return self.locals[name]
        if self.parent:
            return self.parent.resolve(name)
        return None


# ╔══════════════════════════════════════════════════════════════════════════╗
#  COMPILER
# ╚══════════════════════════════════════════════════════════════════════════╝

class Compiler:
    """
    Компилятор AST функции в Proto.

    Использование:
        c = Compiler()
        proto = c.compile_function(func_expr, name='myFn')
    """

    def __init__(self, parent: Optional['Compiler'] = None):
        self._parent: Optional['Compiler'] = parent

        self._proto: Optional[Proto] = None
        self._regs: Optional[RegisterAllocator] = None
        self._scope: Optional[LocalScope] = None

        self._upvalues: Dict[str, int] = {}

        self._break_jumps: List[List[int]] = []
        self._continue_jumps: List[List[int]] = []
        self._loop_labels: List[int] = []

    # ──────────────────────────────────────────────────────────────────────
    # public API
    # ──────────────────────────────────────────────────────────────────────

    def compile_function(
        self,
        func: FunctionExpr,
        name: str = '<anonymous>',
    ) -> Proto:
        """Скомпилировать FunctionExpr в Proto."""
        proto = Proto(
            name=name,
            num_params=len(func.params),
            is_vararg=func.is_vararg,
            line=func.line,
        )

        self._proto = proto
        self._regs = RegisterAllocator()
        self._scope = LocalScope(parent=None, reg_level=0)
        self._upvalues = {}
        self._break_jumps = []
        self._continue_jumps = []
        self._loop_labels = []

        # Параметры функции
        for param in func.params:
            reg = self._regs.allocate()
            self._scope.define(param, reg)

        # Тело
        if func.body:
            self._compile_block(func.body)

        # Финальный RETURN 0, если функция не завершилась return/tailcall
        if not proto.code or proto.code[-1].op not in (Opcode.RETURN, Opcode.TAILCALL):
            proto.emit_op(Opcode.RETURN, a=0, b=0, line=func.line)

        proto.max_stack = self._regs.max_used
        self._sync_proto_upvalue_count()

        return proto

    # ──────────────────────────────────────────────────────────────────────
    # name resolution / upvalues
    # ──────────────────────────────────────────────────────────────────────

    def _lookup_local(self, name: str) -> Optional[int]:
        if self._scope is None:
            return None
        return self._scope.resolve(name)

    def _resolve_name_binding(self, name: str) -> Tuple[str, Optional[int]]:
        """
        Вернуть:
        - ('local', reg)
        - ('upvalue', up_idx)
        - ('global', None)
        """
        local_reg = self._lookup_local(name)
        if local_reg is not None:
            return 'local', local_reg

        up_idx = self._resolve_upvalue(name)
        if up_idx is not None:
            return 'upvalue', up_idx

        return 'global', None

    def _resolve_upvalue(self, name: str) -> Optional[int]:
        """
        Найти/создать upvalue для текущей функции.

        Логика стандартная:
        - если у родителя name = local -> child capture(instack=True, index=reg)
        - если у родителя name = upvalue -> child capture(instack=False, index=up_idx)
        """
        if self._parent is None:
            return None

        existing = self._upvalues.get(name)
        if existing is not None:
            return existing

        parent_local = self._parent._lookup_local(name)
        if parent_local is not None:
            return self._register_upvalue(name, instack=True, index=parent_local)

        parent_upvalue = self._parent._resolve_upvalue(name)
        if parent_upvalue is not None:
            return self._register_upvalue(name, instack=False, index=parent_upvalue)

        return None

    def _register_upvalue(self, name: str, instack: bool, index: int) -> int:
        existing = self._upvalues.get(name)
        if existing is not None:
            return existing

        upvalues = self._get_proto_upvalues()
        upvalue_names = self._get_proto_upvalue_names()

        up_idx = len(upvalues)
        upvalues.append((bool(instack), int(index)))
        upvalue_names.append(name)

        self._upvalues[name] = up_idx
        self._sync_proto_upvalue_count()
        return up_idx

    def _get_proto_upvalues(self) -> List[Tuple[bool, int]]:
        """
        Хранилище upvalues в proto.

        Формат: list[(instack: bool, index: int)]
        """
        upvalues = getattr(self._proto, 'upvalues', None)
        if upvalues is None:
            try:
                self._proto.upvalues = []
            except Exception as e:
                raise CompileError(f'Proto не поддерживает upvalues: {e}')
            upvalues = self._proto.upvalues
        return upvalues

    def _get_proto_upvalue_names(self) -> List[str]:
        names = getattr(self._proto, 'upvalue_names', None)
        if names is None:
            try:
                self._proto.upvalue_names = []
            except Exception:
                return []
            names = self._proto.upvalue_names
        return names

    def _sync_proto_upvalue_count(self) -> None:
        upvalues = getattr(self._proto, 'upvalues', None)
        if upvalues is None:
            return

        count = len(upvalues)

        for attr in ('num_upvalues', 'nups', 'upvalue_count'):
            try:
                setattr(self._proto, attr, count)
            except Exception:
                pass

    # ╔══════════════════════════════════════════════════════════════════════╗
    #  BLOCKS / STATEMENTS
    # ╚══════════════════════════════════════════════════════════════════════╝

    def _compile_block(self, block: Block) -> None:
        saved_level = self._regs.current_level()
        saved_scope = self._scope

        self._scope = LocalScope(parent=saved_scope, reg_level=saved_level)

        for stat in block.statements:
            self._compile_stat(stat)

        if block.return_stat:
            self._compile_return(block.return_stat)

        self._scope = saved_scope
        self._regs.free_to(saved_level)

    def _compile_stat(self, stat: Stat) -> None:
        if isinstance(stat, LocalAssignStat):
            self._compile_local_assign(stat)
        elif isinstance(stat, AssignStat):
            self._compile_assign(stat)
        elif isinstance(stat, CompoundAssignStat):
            self._compile_compound_assign(stat)
        elif isinstance(stat, CallStat):
            self._compile_call_stat(stat)
        elif isinstance(stat, IfStat):
            self._compile_if(stat)
        elif isinstance(stat, WhileStat):
            self._compile_while(stat)
        elif isinstance(stat, NumericForStat):
            self._compile_numeric_for(stat)
        elif isinstance(stat, GenericForStat):
            self._compile_generic_for(stat)
        elif isinstance(stat, RepeatStat):
            self._compile_repeat(stat)
        elif isinstance(stat, DoBlockStat):
            self._compile_do_block(stat)
        elif isinstance(stat, ReturnStat):
            self._compile_return(stat)
        elif isinstance(stat, BreakStat):
            self._compile_break()
        elif isinstance(stat, ContinueStat):
            self._compile_continue()
        elif isinstance(stat, LocalFunctionStat):
            self._compile_local_function(stat)
        elif isinstance(stat, FunctionDeclStat):
            self._compile_function_decl(stat)
        elif isinstance(stat, (LabelStat, GotoStat)):
            raise UnsupportedFeature('goto/labels пока не поддерживаются в VM')
        else:
            raise UnsupportedFeature(f'Statement {type(stat).__name__} не поддерживается')

    # ──────────────────────────────────────────────────────────────────────
    # local assign
    # ──────────────────────────────────────────────────────────────────────

    def _compile_local_assign(self, stat: LocalAssignStat) -> None:
        n_names = len(stat.names)
        n_vals = len(stat.values)

        target_regs: List[int] = []
        for name in stat.names:
            reg = self._regs.allocate()
            target_regs.append(reg)

        for i in range(max(n_names, n_vals)):
            if i < n_vals:
                val = stat.values[i]
                if i < n_names:
                    self._compile_expr_to_reg(val, target_regs[i])
                else:
                    tmp = self._regs.allocate()
                    self._compile_expr_to_reg(val, tmp)
                    self._regs.free_to(tmp)
            elif i < n_names:
                self._proto.emit_op(Opcode.LOADNIL, a=target_regs[i], b=0, line=stat.line)

        for name, reg in zip(stat.names, target_regs):
            self._scope.define(name, reg)

    # ──────────────────────────────────────────────────────────────────────
    # assign
    # ──────────────────────────────────────────────────────────────────────

    def _compile_assign(self, stat: AssignStat) -> None:
        n = len(stat.targets)
        v = len(stat.values)

        if n == 1 and v == 1:
            target = stat.targets[0]
            value = stat.values[0]

            if isinstance(target, NameExpr):
                kind, slot = self._resolve_name_binding(target.name)

                if kind == 'local':
                    self._compile_expr_to_reg(value, slot)
                elif kind == 'upvalue':
                    tmp = self._regs.allocate()
                    self._compile_expr_to_reg(value, tmp)
                    self._proto.emit_op(Opcode.SETUPVAL, a=tmp, b=slot, line=stat.line)
                    self._regs.free_to(tmp)
                else:
                    tmp = self._regs.allocate()
                    self._compile_expr_to_reg(value, tmp)
                    kidx = self._proto.constants.add_string(target.name)
                    self._proto.emit_op(Opcode.SETGLOBAL, a=tmp, k=kidx, line=stat.line)
                    self._regs.free_to(tmp)
                return

            if isinstance(target, IndexExpr):
                obj_reg = self._compile_expr(target.obj)
                if target.is_dot:
                    val_reg = self._compile_expr(value)
                    field_name = self._index_field_name(target.index)
                    kidx = self._proto.constants.add_string(field_name)
                    self._proto.emit_op(
                        Opcode.SETFIELD,
                        a=obj_reg,
                        b=val_reg,
                        k=kidx,
                        line=stat.line,
                    )
                else:
                    key_reg = self._compile_expr(target.index)
                    val_reg = self._compile_expr(value)
                    self._proto.emit_op(
                        Opcode.SETTABLE,
                        a=obj_reg,
                        b=key_reg,
                        c=val_reg,
                        line=stat.line,
                    )
                return

            raise UnsupportedFeature(f'Assign target {type(target).__name__} не поддерживается')

        # multiple assign
        val_regs: List[int] = []
        for val in stat.values:
            r = self._regs.allocate()
            self._compile_expr_to_reg(val, r)
            val_regs.append(r)

        while len(val_regs) < n:
            r = self._regs.allocate()
            self._proto.emit_op(Opcode.LOADNIL, a=r, b=0, line=stat.line)
            val_regs.append(r)

        for target, vreg in zip(stat.targets, val_regs):
            if isinstance(target, NameExpr):
                kind, slot = self._resolve_name_binding(target.name)

                if kind == 'local':
                    self._proto.emit_op(Opcode.MOVE, a=slot, b=vreg, line=stat.line)
                elif kind == 'upvalue':
                    self._proto.emit_op(Opcode.SETUPVAL, a=vreg, b=slot, line=stat.line)
                else:
                    kidx = self._proto.constants.add_string(target.name)
                    self._proto.emit_op(Opcode.SETGLOBAL, a=vreg, k=kidx, line=stat.line)

            elif isinstance(target, IndexExpr):
                obj_reg = self._compile_expr(target.obj)
                if target.is_dot:
                    field_name = self._index_field_name(target.index)
                    kidx = self._proto.constants.add_string(field_name)
                    self._proto.emit_op(
                        Opcode.SETFIELD,
                        a=obj_reg,
                        b=vreg,
                        k=kidx,
                        line=stat.line,
                    )
                else:
                    key_reg = self._compile_expr(target.index)
                    self._proto.emit_op(
                        Opcode.SETTABLE,
                        a=obj_reg,
                        b=key_reg,
                        c=vreg,
                        line=stat.line,
                    )
            else:
                raise UnsupportedFeature(f'Multi assign target {type(target).__name__}')

    # ──────────────────────────────────────────────────────────────────────
    # compound assign
    # ──────────────────────────────────────────────────────────────────────

    def _compile_compound_assign(self, stat: CompoundAssignStat) -> None:
        op_map = {
            '+=': '+',
            '-=': '-',
            '*=': '*',
            '/=': '/',
            '%=': '%',
            '^=': '^',
            '..=': '..',
            '//=': '//',
            '+': '+',
            '-': '-',
            '*': '*',
            '/': '/',
            '%': '%',
            '^': '^',
            '..': '..',
            '//': '//',
        }
        binop = op_map.get(stat.op)
        if binop is None:
            raise UnsupportedFeature(f'Compound op {stat.op}')

        equiv_value = BinaryOp(op=binop, left=stat.target, right=stat.value, line=stat.line)
        equiv = AssignStat(targets=[stat.target], values=[equiv_value], line=stat.line)
        self._compile_assign(equiv)

    # ──────────────────────────────────────────────────────────────────────
    # call stat
    # ──────────────────────────────────────────────────────────────────────

    def _compile_call_stat(self, stat: CallStat) -> None:
        self._compile_call(stat.call, want_results=0)

    # ──────────────────────────────────────────────────────────────────────
    # if
    # ──────────────────────────────────────────────────────────────────────

    def _compile_if(self, stat: IfStat) -> None:
        end_jumps: List[int] = []

        for i, (cond, block) in enumerate(stat.branches):
            cond_reg = self._compile_expr(cond)
            skip_idx = self._proto.emit_op(Opcode.JMPIFNOT, a=cond_reg, k=0, line=cond.line)

            self._compile_block(block)

            has_more = (i < len(stat.branches) - 1) or (stat.else_block is not None)
            if has_more:
                end_jump = self._proto.emit_op(Opcode.JMP, k=0, line=stat.line)
                end_jumps.append(end_jump)

            self._proto.patch_jump(skip_idx, self._proto.current_pc())

        if stat.else_block is not None:
            self._compile_block(stat.else_block)

        end_pc = self._proto.current_pc()
        for j in end_jumps:
            self._proto.patch_jump(j, end_pc)

    # ──────────────────────────────────────────────────────────────────────
    # while
    # ──────────────────────────────────────────────────────────────────────

    def _compile_while(self, stat: WhileStat) -> None:
        loop_start = self._proto.current_pc()

        cond_reg = self._compile_expr(stat.cond)
        exit_idx = self._proto.emit_op(Opcode.JMPIFNOT, a=cond_reg, k=0, line=stat.cond.line)

        self._break_jumps.append([])
        self._continue_jumps.append([])
        self._loop_labels.append(loop_start)

        self._compile_block(stat.body)

        back_jmp = self._proto.emit_op(Opcode.JMP, k=0, line=stat.line)
        self._proto.patch_jump(back_jmp, loop_start)

        loop_end = self._proto.current_pc()

        self._proto.patch_jump(exit_idx, loop_end)

        for j in self._break_jumps.pop():
            self._proto.patch_jump(j, loop_end)
        for j in self._continue_jumps.pop():
            self._proto.patch_jump(j, loop_start)

        self._loop_labels.pop()

    # ──────────────────────────────────────────────────────────────────────
    # numeric for
    # ──────────────────────────────────────────────────────────────────────

    def _compile_numeric_for(self, stat: NumericForStat) -> None:
        start_reg = self._regs.allocate()
        stop_reg = self._regs.allocate()
        step_reg = self._regs.allocate()

        self._compile_expr_to_reg(stat.start, start_reg)
        self._compile_expr_to_reg(stat.stop, stop_reg)

        if stat.step:
            self._compile_expr_to_reg(stat.step, step_reg)
        else:
            k_one = self._proto.constants.add_number(1.0)
            self._proto.emit_op(Opcode.LOADK, a=step_reg, k=k_one, line=stat.line)

        forprep_idx = self._proto.emit_op(Opcode.FORPREP, a=start_reg, k=0, line=stat.line)

        body_start = self._proto.current_pc()

        saved_scope = self._scope
        saved_level = self._regs.current_level()
        self._scope = LocalScope(parent=saved_scope, reg_level=saved_level)

        self._scope.define(stat.var, start_reg)

        self._break_jumps.append([])
        self._continue_jumps.append([])

        self._compile_block(stat.body)

        continue_pc = self._proto.current_pc()

        self._proto.emit_op(
            Opcode.FORLOOP,
            a=start_reg,
            k=body_start - continue_pc - 1,
            line=stat.line,
        )
        loop_end = self._proto.current_pc()

        self._proto.patch_jump(forprep_idx, continue_pc)

        for j in self._break_jumps.pop():
            self._proto.patch_jump(j, loop_end)
        for j in self._continue_jumps.pop():
            self._proto.patch_jump(j, continue_pc)

        self._scope = saved_scope
        self._regs.free_to(saved_level)

    # ──────────────────────────────────────────────────────────────────────
    # generic for
    # ──────────────────────────────────────────────────────────────────────

    def _compile_generic_for(self, stat: GenericForStat) -> None:
        iter_base = self._regs.allocate_range(3)

        n_exprs = len(stat.exprs)
        for i, expr in enumerate(stat.exprs):
            if i >= 3:
                break
            self._compile_expr_to_reg(expr, iter_base + i)

        for i in range(n_exprs, 3):
            self._proto.emit_op(Opcode.LOADNIL, a=iter_base + i, b=0, line=stat.line)

        n_vars = len(stat.names)
        var_base = self._regs.allocate_range(n_vars)

        prep_jmp = self._proto.emit_op(Opcode.JMP, k=0, line=stat.line)

        body_start = self._proto.current_pc()

        saved_scope = self._scope
        saved_level = self._regs.current_level()
        self._scope = LocalScope(parent=saved_scope, reg_level=saved_level)

        for i, name in enumerate(stat.names):
            self._scope.define(name, var_base + i)

        self._break_jumps.append([])
        self._continue_jumps.append([])

        self._compile_block(stat.body)

        continue_pc = self._proto.current_pc()
        self._proto.emit_op(Opcode.TFORCALL, a=iter_base, b=n_vars, line=stat.line)
        self._proto.emit_op(
            Opcode.TFORLOOP,
            a=iter_base,
            k=body_start - self._proto.current_pc() - 1,
            line=stat.line,
        )

        loop_end = self._proto.current_pc()

        self._proto.patch_jump(prep_jmp, continue_pc)

        for j in self._break_jumps.pop():
            self._proto.patch_jump(j, loop_end)
        for j in self._continue_jumps.pop():
            self._proto.patch_jump(j, continue_pc)

        self._scope = saved_scope
        self._regs.free_to(saved_level)

    # ──────────────────────────────────────────────────────────────────────
    # repeat
    # ──────────────────────────────────────────────────────────────────────

    def _compile_repeat(self, stat: RepeatStat) -> None:
        loop_start = self._proto.current_pc()

        self._break_jumps.append([])
        self._continue_jumps.append([])
        self._loop_labels.append(loop_start)

        saved_scope = self._scope
        saved_level = self._regs.current_level()
        self._scope = LocalScope(parent=saved_scope, reg_level=saved_level)

        for s in stat.body.statements:
            self._compile_stat(s)

        cond_reg = self._compile_expr(stat.cond)
        jmp_back = self._proto.emit_op(Opcode.JMPIFNOT, a=cond_reg, k=0, line=stat.cond.line)
        self._proto.patch_jump(jmp_back, loop_start)

        loop_end = self._proto.current_pc()

        self._scope = saved_scope
        self._regs.free_to(saved_level)

        for j in self._break_jumps.pop():
            self._proto.patch_jump(j, loop_end)
        for j in self._continue_jumps.pop():
            self._proto.patch_jump(j, loop_end - 1)

        self._loop_labels.pop()

    # ──────────────────────────────────────────────────────────────────────
    # do block
    # ──────────────────────────────────────────────────────────────────────

    def _compile_do_block(self, stat: DoBlockStat) -> None:
        self._compile_block(stat.body)

    # ──────────────────────────────────────────────────────────────────────
    # return
    # ──────────────────────────────────────────────────────────────────────

    def _compile_return(self, stat: ReturnStat) -> None:
        n = len(stat.values)
        if n == 0:
            self._proto.emit_op(Opcode.RETURN, a=0, b=0, line=stat.line)
            return

        first = self._regs.allocate_range(n)
        for i, val in enumerate(stat.values):
            self._compile_expr_to_reg(val, first + i)

        self._proto.emit_op(Opcode.RETURN, a=first, b=n, line=stat.line)
        self._regs.free_to(first)

    # ──────────────────────────────────────────────────────────────────────
    # break / continue
    # ──────────────────────────────────────────────────────────────────────

    def _compile_break(self) -> None:
        if not self._break_jumps:
            raise CompileError('break вне цикла')
        j = self._proto.emit_op(Opcode.JMP, k=0)
        self._break_jumps[-1].append(j)

    def _compile_continue(self) -> None:
        if not self._continue_jumps:
            raise CompileError('continue вне цикла')
        j = self._proto.emit_op(Opcode.JMP, k=0)
        self._continue_jumps[-1].append(j)

    # ──────────────────────────────────────────────────────────────────────
    # local function
    # ──────────────────────────────────────────────────────────────────────

    def _compile_local_function(self, stat: LocalFunctionStat) -> None:
        """
        local function fn(...) ... fn(...) ... end

        Важно:
        1. Сначала резервируем local в родительском scope
        2. Потом компилируем child-функцию с parent=self
        3. Внутри child имя fn резолвится как UPVALUE, а не GLOBAL
        """
        reg = self._regs.allocate()

        # forward declaration для recursion
        self._scope.define(stat.name, reg)

        sub_compiler = Compiler(parent=self)
        sub_proto = sub_compiler.compile_function(stat.func, name=stat.name)

        proto_idx = self._proto.add_proto(sub_proto)
        k_idx = self._proto.constants.add_proto(proto_idx)

        self._proto.emit_op(Opcode.CLOSURE, a=reg, k=k_idx, line=stat.line)

    # ──────────────────────────────────────────────────────────────────────
    # function declaration
    # ──────────────────────────────────────────────────────────────────────

    def _compile_function_decl(self, stat: FunctionDeclStat) -> None:
        # Пока поддерживаем только простой target: function name() ... end
        if isinstance(stat.target, NameExpr) and stat.method_name is None:
            sub_compiler = Compiler(parent=self)
            sub_proto = sub_compiler.compile_function(stat.func, name=stat.target.name)
            proto_idx = self._proto.add_proto(sub_proto)
            k_idx = self._proto.constants.add_proto(proto_idx)

            kind, slot = self._resolve_name_binding(stat.target.name)

            if kind == 'local':
                self._proto.emit_op(Opcode.CLOSURE, a=slot, k=k_idx, line=stat.line)
            elif kind == 'upvalue':
                tmp = self._regs.allocate()
                self._proto.emit_op(Opcode.CLOSURE, a=tmp, k=k_idx, line=stat.line)
                self._proto.emit_op(Opcode.SETUPVAL, a=tmp, b=slot, line=stat.line)
                self._regs.free_to(tmp)
            else:
                tmp = self._regs.allocate()
                self._proto.emit_op(Opcode.CLOSURE, a=tmp, k=k_idx, line=stat.line)
                gk = self._proto.constants.add_string(stat.target.name)
                self._proto.emit_op(Opcode.SETGLOBAL, a=tmp, k=gk, line=stat.line)
                self._regs.free_to(tmp)
        else:
            raise UnsupportedFeature('Сложные function declarations пока не поддерживаются в VM')

    # ╔══════════════════════════════════════════════════════════════════════╗
    #  EXPRESSIONS
    # ╚══════════════════════════════════════════════════════════════════════╝

    def _compile_expr(self, expr: Expr) -> int:
        """
        Скомпилировать выражение, вернуть регистр с результатом.
        """
        r = self._regs.allocate()
        self._compile_expr_to_reg(expr, r)
        return r

    def _compile_expr_to_reg(self, expr: Expr, target: int) -> None:
        """Скомпилировать выражение сразу в конкретный регистр."""
        if isinstance(expr, NilLit):
            self._proto.emit_op(Opcode.LOADNIL, a=target, b=0, line=expr.line)
            return

        if isinstance(expr, BoolLit):
            self._proto.emit_op(
                Opcode.LOADBOOL,
                a=target,
                b=1 if expr.value else 0,
                line=expr.line,
            )
            return

        if isinstance(expr, NumberLit):
            v = expr.value
            if isinstance(v, int) or (isinstance(v, float) and v.is_integer()):
                iv = int(v)
                if -128 <= iv <= 127:
                    b = iv if iv >= 0 else (iv + 256)
                    self._proto.emit_op(Opcode.LOADN, a=target, b=b, line=expr.line)
                    return

            k = self._proto.constants.add_number(float(v))
            self._proto.emit_op(Opcode.LOADK, a=target, k=k, line=expr.line)
            return

        if isinstance(expr, StringLit):
            k = self._proto.constants.add_string(expr.value)
            self._proto.emit_op(Opcode.LOADK, a=target, k=k, line=expr.line)
            return

        if isinstance(expr, VarargLit):
            self._proto.emit_op(Opcode.VARARG, a=target, b=1, line=expr.line)
            return

        if isinstance(expr, NameExpr):
            kind, slot = self._resolve_name_binding(expr.name)

            if kind == 'local':
                if slot != target:
                    self._proto.emit_op(Opcode.MOVE, a=target, b=slot, line=expr.line)
            elif kind == 'upvalue':
                self._proto.emit_op(Opcode.GETUPVAL, a=target, b=slot, line=expr.line)
            else:
                k = self._proto.constants.add_string(expr.name)
                self._proto.emit_op(Opcode.GETGLOBAL, a=target, k=k, line=expr.line)
            return

        if isinstance(expr, ParenExpr):
            self._compile_expr_to_reg(expr.inner, target)
            return

        if isinstance(expr, BinaryOp):
            self._compile_binop_to_reg(expr, target)
            return

        if isinstance(expr, UnaryOp):
            self._compile_unop_to_reg(expr, target)
            return

        if isinstance(expr, IndexExpr):
            self._compile_index_to_reg(expr, target)
            return

        if isinstance(expr, CallExpr):
            self._compile_call_to_reg(expr, target)
            return

        if isinstance(expr, MethodCallExpr):
            self._compile_method_call_to_reg(expr, target)
            return

        if isinstance(expr, TableExpr):
            self._compile_table_to_reg(expr, target)
            return

        if isinstance(expr, FunctionExpr):
            sub_compiler = Compiler(parent=self)
            sub_proto = sub_compiler.compile_function(expr, name='<anonymous>')
            proto_idx = self._proto.add_proto(sub_proto)
            k_idx = self._proto.constants.add_proto(proto_idx)
            self._proto.emit_op(Opcode.CLOSURE, a=target, k=k_idx, line=expr.line)
            return

        raise UnsupportedFeature(f'Expr {type(expr).__name__} не поддерживается')

    # ──────────────────────────────────────────────────────────────────────
    # binary op
    # ──────────────────────────────────────────────────────────────────────

    def _compile_binop_to_reg(self, expr: BinaryOp, target: int) -> None:
        op = expr.op

        if op == 'and':
            self._compile_expr_to_reg(expr.left, target)
            skip = self._proto.emit_op(Opcode.JMPIFNOT, a=target, k=0, line=expr.line)
            self._compile_expr_to_reg(expr.right, target)
            self._proto.patch_jump(skip, self._proto.current_pc())
            return

        if op == 'or':
            self._compile_expr_to_reg(expr.left, target)
            skip = self._proto.emit_op(Opcode.JMPIF, a=target, k=0, line=expr.line)
            self._compile_expr_to_reg(expr.right, target)
            self._proto.patch_jump(skip, self._proto.current_pc())
            return

        op_to_opcode = {
            '+': Opcode.ADD,
            '-': Opcode.SUB,
            '*': Opcode.MUL,
            '/': Opcode.DIV,
            '%': Opcode.MOD,
            '^': Opcode.POW,
            '//': Opcode.IDIV,
            '..': Opcode.CONCAT,
            '==': Opcode.EQ,
            '~=': Opcode.NEQ,
            '<': Opcode.LT,
            '<=': Opcode.LE,
            '>': Opcode.GT,
            '>=': Opcode.GE,
        }
        opcode = op_to_opcode.get(op)
        if opcode is None:
            raise UnsupportedFeature(f'BinaryOp {op}')

        left_reg = self._compile_expr(expr.left)
        right_reg = self._compile_expr(expr.right)

        self._proto.emit_op(opcode, a=target, b=left_reg, c=right_reg, line=expr.line)

        max_reg = max(left_reg, right_reg)
        if max_reg > target:
            self._regs.free_to(target + 1)

    # ──────────────────────────────────────────────────────────────────────
    # unary op
    # ──────────────────────────────────────────────────────────────────────

    def _compile_unop_to_reg(self, expr: UnaryOp, target: int) -> None:
        op_to_opcode = {
            '-': Opcode.UNM,
            'not': Opcode.NOT,
            '#': Opcode.LEN,
        }
        opcode = op_to_opcode.get(expr.op)
        if opcode is None:
            raise UnsupportedFeature(f'UnaryOp {expr.op}')

        operand_reg = self._compile_expr(expr.operand)
        self._proto.emit_op(opcode, a=target, b=operand_reg, line=expr.line)

        if operand_reg > target:
            self._regs.free_to(target + 1)

    # ──────────────────────────────────────────────────────────────────────
    # index
    # ──────────────────────────────────────────────────────────────────────

    def _compile_index_to_reg(self, expr: IndexExpr, target: int) -> None:
        obj_reg = self._compile_expr(expr.obj)

        if expr.is_dot:
            field_name = self._index_field_name(expr.index)
            kidx = self._proto.constants.add_string(field_name)
            self._proto.emit_op(Opcode.GETFIELD, a=target, b=obj_reg, k=kidx, line=expr.line)
        else:
            key_reg = self._compile_expr(expr.index)
            self._proto.emit_op(Opcode.GETTABLE, a=target, b=obj_reg, c=key_reg, line=expr.line)

        if obj_reg > target:
            self._regs.free_to(target + 1)

    def _index_field_name(self, index_node: Expr) -> str:
        if isinstance(index_node, StringLit):
            return index_node.value
        if isinstance(index_node, NameExpr):
            return index_node.name
        raise CompileError(f'Неизвестный тип index для is_dot: {type(index_node).__name__}')

    # ──────────────────────────────────────────────────────────────────────
    # call
    # ──────────────────────────────────────────────────────────────────────

    def _compile_call(self, expr: CallExpr, want_results: int = 1) -> int:
        """
        want_results:
        - 0 = результат игнорируем
        - 1 = один результат
        """
        n_args = len(expr.args)
        base = self._regs.allocate_range(1 + n_args)

        self._compile_expr_to_reg(expr.func, base)

        for i, arg in enumerate(expr.args):
            self._compile_expr_to_reg(arg, base + 1 + i)

        self._proto.emit_op(
            Opcode.CALL,
            a=base,
            b=n_args + 1,
            c=want_results + 1,
            line=expr.line,
        )

        self._regs.free_to(base + want_results)
        return base

    def _compile_call_to_reg(self, expr: CallExpr, target: int) -> None:
        result_base = self._compile_call(expr, want_results=1)
        if result_base != target:
            self._proto.emit_op(Opcode.MOVE, a=target, b=result_base, line=expr.line)

    # ──────────────────────────────────────────────────────────────────────
    # method call
    # ──────────────────────────────────────────────────────────────────────

    def _compile_method_call_to_reg(self, expr: MethodCallExpr, target: int) -> None:
        n_args = len(expr.args)
        base = self._regs.allocate_range(2 + n_args)

        obj_reg = self._compile_expr(expr.obj)

        kidx = self._proto.constants.add_string(expr.method)
        self._proto.emit_op(Opcode.MOVE, a=base + 1, b=obj_reg, line=expr.line)
        self._proto.emit_op(Opcode.GETFIELD, a=base, b=obj_reg, k=kidx, line=expr.line)

        for i, arg in enumerate(expr.args):
            self._compile_expr_to_reg(arg, base + 2 + i)

        self._proto.emit_op(Opcode.CALL, a=base, b=n_args + 2, c=2, line=expr.line)

        if base != target:
            self._proto.emit_op(Opcode.MOVE, a=target, b=base, line=expr.line)

        self._regs.free_to(target + 1)

    # ──────────────────────────────────────────────────────────────────────
    # table constructor
    # ──────────────────────────────────────────────────────────────────────

    def _compile_table_to_reg(self, expr: TableExpr, target: int) -> None:
        n_array = 0
        n_hash = 0

        for f in expr.fields:
            if f.is_name or f.key is not None:
                n_hash += 1
            else:
                n_array += 1

        self._proto.emit_op(
            Opcode.NEWTABLE,
            a=target,
            b=min(n_array, 255),
            c=min(n_hash, 255),
            line=expr.line,
        )

        array_index = 1
        for f in expr.fields:
            if f.is_name:
                val_reg = self._compile_expr(f.value)
                kidx = self._proto.constants.add_string(
                    str(f.key.value) if isinstance(f.key, StringLit)
                    else (f.key.name if isinstance(f.key, NameExpr) else str(f.key))
                )
                self._proto.emit_op(
                    Opcode.SETFIELD,
                    a=target,
                    b=val_reg,
                    k=kidx,
                    line=f.line if hasattr(f, 'line') else 0,
                )
                self._regs.free_to(target + 1)

            elif f.key is not None:
                key_reg = self._compile_expr(f.key)
                val_reg = self._compile_expr(f.value)
                self._proto.emit_op(
                    Opcode.SETTABLE,
                    a=target,
                    b=key_reg,
                    c=val_reg,
                    line=0,
                )
                self._regs.free_to(target + 1)

            else:
                val_reg = self._compile_expr(f.value)
                idx_reg = self._regs.allocate()
                kidx = self._proto.constants.add_number(float(array_index))
                self._proto.emit_op(Opcode.LOADK, a=idx_reg, k=kidx, line=0)
                self._proto.emit_op(
                    Opcode.SETTABLE,
                    a=target,
                    b=idx_reg,
                    c=val_reg,
                    line=0,
                )
                self._regs.free_to(target + 1)
                array_index += 1


# ╔══════════════════════════════════════════════════════════════════════════╗
#  PUBLIC API
# ╚══════════════════════════════════════════════════════════════════════════╝

def compile_function(func: FunctionExpr, name: str = '<anonymous>') -> Proto:
    """Скомпилировать одну функцию в Proto."""
    return Compiler().compile_function(func, name=name)


def can_compile(func: FunctionExpr) -> Tuple[bool, str]:
    """
    Проверить может ли функция быть скомпилирована в VM.
    Возвращает (можно_ли, причина_если_нет).
    """
    try:
        Compiler().compile_function(func)
        return True, ''
    except UnsupportedFeature as e:
        return False, str(e)
    except CompileError as e:
        return False, str(e)


# ╔══════════════════════════════════════════════════════════════════════════╗
#  SELF-TEST
# ╚══════════════════════════════════════════════════════════════════════════╝

def _test():
    import os
    import sys

    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if root not in sys.path:
        sys.path.insert(0, root)

    from obfuscator.lexer import Lexer
    from obfuscator.parser import Parser

    def parse_func(code: str) -> FunctionExpr:
        full = f'local function __test_fn__() {code} end'
        ast = Parser(Lexer(full).tokenize()).parse()
        lfn = ast.body.statements[0]
        return lfn.func

    def parse_func_with_params(params: str, body: str) -> FunctionExpr:
        full = f'local function __test_fn__({params}) {body} end'
        ast = Parser(Lexer(full).tokenize()).parse()
        return ast.body.statements[0].func

    passed = 0
    failed = 0

    def ok(label):
        nonlocal passed
        passed += 1
        print(f'  ✅ {label}')

    def fail(label, detail=''):
        nonlocal failed
        failed += 1
        print(f'  ❌ {label}' + (f' — {detail}' if detail else ''))

    def check(label, cond, detail=''):
        if cond:
            ok(label)
        else:
            fail(label, detail)

    print('\n' + '═' * 56)
    print('  NZL VM Compiler — Tests')
    print('═' * 56)

    print('\n[1] Пустая функция')
    fn = parse_func('')
    proto = compile_function(fn, 'empty')
    check('proto создан', isinstance(proto, Proto))
    check('есть RETURN', any(i.op == Opcode.RETURN for i in proto.code))

    print('\n[2] return 42')
    fn = parse_func('return 42')
    proto = compile_function(fn, 'fn')
    ops = [i.op for i in proto.code]
    check('содержит LOADN или LOADK', Opcode.LOADN in ops or Opcode.LOADK in ops)
    check('содержит RETURN', Opcode.RETURN in ops)

    print('\n[3] Арифметика: return a + b')
    fn = parse_func_with_params('a, b', 'return a + b')
    proto = compile_function(fn, 'add')
    ops = [i.op for i in proto.code]
    check('содержит ADD', Opcode.ADD in ops)
    check('num_params = 2', proto.num_params == 2)

    print('\n[4] Локальные: local x = 10; return x + 1')
    fn = parse_func('local x = 10\nreturn x + 1')
    proto = compile_function(fn, 'fn')
    check('несколько инструкций', len(proto.code) >= 3)

    print('\n[5] if statement')
    fn = parse_func_with_params('x', '''
if x > 0 then
    return "positive"
else
    return "negative"
end
''')
    proto = compile_function(fn, 'sign')
    ops = [i.op for i in proto.code]
    check('содержит JMPIFNOT', Opcode.JMPIFNOT in ops)
    check('содержит JMP', Opcode.JMP in ops or Opcode.JMPIFNOT in ops)
    check('содержит GT (>)', Opcode.GT in ops)

    print('\n[6] while loop')
    fn = parse_func('''
local i = 0
while i < 10 do
    i = i + 1
end
return i
''')
    proto = compile_function(fn, 'countTo10')
    ops = [i.op for i in proto.code]
    check('содержит LT', Opcode.LT in ops)
    check('содержит JMPIFNOT + JMP', Opcode.JMPIFNOT in ops and Opcode.JMP in ops)
    check('содержит ADD', Opcode.ADD in ops)

    print('\n[7] Function call: print("hi")')
    fn = parse_func('print("hi")')
    proto = compile_function(fn, 'fn')
    ops = [i.op for i in proto.code]
    check('содержит GETGLOBAL', Opcode.GETGLOBAL in ops)
    check('содержит LOADK', Opcode.LOADK in ops)
    check('содержит CALL', Opcode.CALL in ops)

    print('\n[8] Table: local t = {1, 2, 3}')
    fn = parse_func('local t = {1, 2, 3}\nreturn t')
    proto = compile_function(fn, 'fn')
    ops = [i.op for i in proto.code]
    check('содержит NEWTABLE', Opcode.NEWTABLE in ops)
    check('содержит SETTABLE или SETLIST', Opcode.SETTABLE in ops or Opcode.SETLIST in ops)

    print('\n[9] Table access: return t.x')
    fn = parse_func_with_params('t', 'return t.x')
    proto = compile_function(fn, 'fn')
    ops = [i.op for i in proto.code]
    check('содержит GETFIELD', Opcode.GETFIELD in ops)

    print('\n[10] Numeric for')
    fn = parse_func('''
local sum = 0
for i = 1, 10 do
    sum = sum + i
end
return sum
''')
    proto = compile_function(fn, 'fn')
    ops = [i.op for i in proto.code]
    check('содержит FORPREP', Opcode.FORPREP in ops)
    check('содержит FORLOOP', Opcode.FORLOOP in ops)

    print('\n[11] Nested function (closure)')
    fn = parse_func('''
local function inner()
    return 42
end
return inner()
''')
    proto = compile_function(fn, 'fn')
    ops = [i.op for i in proto.code]
    check('содержит CLOSURE', Opcode.CLOSURE in ops)
    check('proto содержит nested', len(proto.protos) >= 1)

    print('\n[12] Method call: obj:method(x)')
    fn = parse_func_with_params('obj', 'return obj:method(1, 2)')
    proto = compile_function(fn, 'fn')
    ops = [i.op for i in proto.code]
    check('содержит GETFIELD или SELF', Opcode.GETFIELD in ops or Opcode.SELF in ops)
    check('содержит CALL', Opcode.CALL in ops)

    print('\n[13] Compound assign: x += 5')
    fn = parse_func('''
local x = 10
x += 5
return x
''')
    proto = compile_function(fn, 'fn')
    ops = [i.op for i in proto.code]
    check('содержит ADD', Opcode.ADD in ops)

    print('\n[14] Unary: -x, not b, #t')
    fn = parse_func_with_params('x, b, t', 'return -x, not b, #t')
    proto = compile_function(fn, 'fn')
    ops = [i.op for i in proto.code]
    check('содержит UNM', Opcode.UNM in ops)
    check('содержит NOT', Opcode.NOT in ops)
    check('содержит LEN', Opcode.LEN in ops)

    print('\n[15] Concat: return a .. b')
    fn = parse_func_with_params('a, b', 'return a .. b')
    proto = compile_function(fn, 'fn')
    ops = [i.op for i in proto.code]
    check('содержит CONCAT', Opcode.CONCAT in ops)

    print('\n[16] break в while')
    fn = parse_func('''
local i = 0
while true do
    i = i + 1
    if i > 5 then break end
end
return i
''')
    proto = compile_function(fn, 'fn')
    check('proto компилируется', len(proto.code) > 5)

    print('\n[17] can_compile для goto')
    fn = parse_func('''
::start::
print("hi")
goto start
''')
    ok_flag, reason = can_compile(fn)
    check('goto не компилируется (unsupported)', not ok_flag, reason)

    print('\n[18] Multiple return values')
    fn = parse_func('return 1, 2, 3')
    proto = compile_function(fn, 'fn')
    ret_ops = [i for i in proto.code if i.op == Opcode.RETURN]
    check(
        'есть RETURN с несколькими values',
        any(r.b == 3 for r in ret_ops),
        f'RETURN.b values: {[r.b for r in ret_ops]}'
    )

    print('\n[19] Реальный пример: FizzBuzz-подобная функция')
    fn = parse_func('''
local result = ""
for i = 1, 15 do
    if i % 15 == 0 then
        result = result .. "FizzBuzz"
    elseif i % 3 == 0 then
        result = result .. "Fizz"
    elseif i % 5 == 0 then
        result = result .. "Buzz"
    else
        result = result .. i
    end
end
return result
''')
    try:
        proto = compile_function(fn, 'fizzbuzz')
        check('FizzBuzz компилируется', True)
        check(
            f'сгенерировано {len(proto.code)} инструкций',
            len(proto.code) > 15,
            f'{len(proto.code)} инструкций'
        )
        check(
            'есть FORPREP + FORLOOP',
            any(i.op == Opcode.FORPREP for i in proto.code) and
            any(i.op == Opcode.FORLOOP for i in proto.code)
        )
    except Exception as e:
        fail('FizzBuzz компилируется', str(e))

    print('\n[20] max_stack устанавливается')
    fn = parse_func_with_params('a, b, c', '''
local x = a + b
local y = x * c
return y
''')
    proto = compile_function(fn, 'fn')
    check(
        'max_stack >= num_params',
        proto.max_stack >= proto.num_params,
        f'max_stack={proto.max_stack}, num_params={proto.num_params}'
    )

    print('\n[21] Recursion: local function fn(n) return fn(n-1) end')
    fn = parse_func('''
local function fn(n)
    if n <= 1 then return 1 end
    return n * fn(n - 1)
end
return fn(5)
''')
    proto = compile_function(fn, 'fn')
    check('есть nested proto', len(proto.protos) >= 1, f'protos={len(proto.protos)}')

    sub = proto.protos[0]
    sub_ops = [i.op for i in sub.code]
    check('recursive body использует GETUPVAL', Opcode.GETUPVAL in sub_ops, f'ops={sub_ops}')

    sub_upvalues = getattr(sub, 'upvalues', [])
    check('recursive child имеет хотя бы 1 upvalue', len(sub_upvalues) >= 1, f'upvalues={sub_upvalues}')

    print('\n' + '═' * 56)
    total = passed + failed
    print(f'  Результат: {passed}/{total} тестов прошло', end='')
    if failed == 0:
        print(' 🎉')
    else:
        print(f' ({failed} провалено) ❌')
    print('═' * 56)

    print('\n📄 Пример скомпилированной функции:')
    fn = parse_func_with_params('n', '''
if n <= 1 then return 1 end
return n * n
''')
    proto = compile_function(fn, 'square_or_one')
    print(proto.dump())
    print()

    return failed == 0


if __name__ == '__main__':
    import sys
    success = _test()
    sys.exit(0 if success else 1)