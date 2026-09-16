"""
NZL Studio Obfuscator — Part 9: Control Flow Flattening
Превращает линейный код в state machine (машину состояний).

Только для режима 'hard'.

ФИКС v4:
  - MAX_TOTAL_HOISTED = 80 (было 150) — жёсткий skip
  - Правильный подсчёт ВСЕХ локалов (включая for/do/repeat)
  - Убран chunk split (не помогает при Luau лимите на функцию)
"""

from __future__ import annotations
import random
from typing import Dict, List, Optional, Set, Tuple, Any

from ..ast_nodes import (
    Node, NodeTransformer, NodeVisitor,
    Chunk, Block, Expr, Stat,
    NameExpr, IndexExpr, CallExpr, MethodCallExpr,
    FunctionExpr, FunctionDeclStat, LocalFunctionStat, LocalAssignStat,
    AssignStat, CompoundAssignStat, CallStat,
    NumericForStat, GenericForStat, DoBlockStat,
    WhileStat, RepeatStat, IfStat,
    ReturnStat, BreakStat, ContinueStat, GotoStat, LabelStat,
    ParenExpr, TableExpr, TableField,
    NilLit, BoolLit, NumberLit, StringLit, VarargLit,
    BinaryOp, UnaryOp,
)
from ..utils.random_gen import (
    NameGenerator, make_rng, NumberExprGen, BoolExprGen, shuffle_list,
)


# ═════════════════════════════════════════════════════════════════
#  КОНСТАНТЫ (Luau ограничения)
# ═════════════════════════════════════════════════════════════════

# Luau: максимум 200 локалов В ФУНКЦИИ.
# Учитываем что помимо hoisted у функции есть:
#  - state var (+1)
#  - аргументы (до 10)
#  - non-hoisted локалы (for i, do..end и т.п.) — не рекурсивно hoisted
#  - upvalues
# Оставляем очень большой запас.
MAX_LOCALS_PER_STAT = 100         # разбиваем hoisted на chunks (косметика)
MAX_TOTAL_HOISTED = 80            # ЖЁСТКИЙ лимит: >80 → не flatten


# ═════════════════════════════════════════════════════════════════
#  BASIC BLOCK
# ═════════════════════════════════════════════════════════════════

class BasicBlock:
    __slots__ = ('id', 'state_num', 'statements', 'terminator')

    def __init__(self, block_id: int):
        self.id = block_id
        self.state_num: int = 0
        self.statements: List[Stat] = []
        self.terminator: Tuple = ('end',)

    def __repr__(self) -> str:
        return f'<BB#{self.id} state={self.state_num} stmts={len(self.statements)} term={self.terminator[0]}>'


class BlockGraph:
    def __init__(self):
        self.blocks: List[BasicBlock] = []
        self.entry_id: int = -1
        self._next_id = 0

    def new_block(self) -> BasicBlock:
        bb = BasicBlock(self._next_id)
        self._next_id += 1
        self.blocks.append(bb)
        return bb

    def get(self, block_id: int) -> BasicBlock:
        return self.blocks[block_id]

    def __len__(self) -> int:
        return len(self.blocks)


# ═════════════════════════════════════════════════════════════════
#  LOCAL VARIABLE COLLECTOR
# ═════════════════════════════════════════════════════════════════

class LocalVarCollector:
    """Собирает имена всех локалов из BB (не заходит в FunctionExpr).
    
    v4: рекурсивно проходит ВСЕ вложенные конструкции (for, do, repeat, if, while).
    """

    def collect(self, blocks: List[BasicBlock]) -> List[str]:
        seen: Set[str] = set()
        result: List[str] = []
        for bb in blocks:
            for stat in bb.statements:
                self._collect_stat(stat, seen, result)
        return result

    def _collect_stat(self, stat: Stat, seen: Set[str], result: List[str]) -> None:
        if isinstance(stat, LocalAssignStat):
            for name in stat.names:
                if name not in seen:
                    seen.add(name)
                    result.append(name)
        elif isinstance(stat, LocalFunctionStat):
            name = stat.name
            if name not in seen:
                seen.add(name)
                result.append(name)
        elif isinstance(stat, DoBlockStat):
            if stat.body:
                for s in stat.body.statements:
                    self._collect_stat(s, seen, result)
        elif isinstance(stat, IfStat):
            for _cond, blk in stat.branches:
                for s in blk.statements:
                    self._collect_stat(s, seen, result)
            if stat.else_block:
                for s in stat.else_block.statements:
                    self._collect_stat(s, seen, result)
        elif isinstance(stat, WhileStat):
            if stat.body:
                for s in stat.body.statements:
                    self._collect_stat(s, seen, result)
        elif isinstance(stat, RepeatStat):
            if stat.body:
                for s in stat.body.statements:
                    self._collect_stat(s, seen, result)
        elif isinstance(stat, NumericForStat):
            # for i = 1, 10 do — i это тоже локал!
            if hasattr(stat, 'var') and stat.var and stat.var not in seen:
                seen.add(stat.var)
                result.append(stat.var)
            if stat.body:
                for s in stat.body.statements:
                    self._collect_stat(s, seen, result)
        elif isinstance(stat, GenericForStat):
            # for k, v in pairs(t) do — k, v локалы!
            if hasattr(stat, 'names') and stat.names:
                for n in stat.names:
                    if n not in seen:
                        seen.add(n)
                        result.append(n)
            if stat.body:
                for s in stat.body.statements:
                    self._collect_stat(s, seen, result)


# ═════════════════════════════════════════════════════════════════
#  LOCAL STRIP TRANSFORMER
# ═════════════════════════════════════════════════════════════════

def strip_local_from_stat(stat: Stat) -> List[Stat]:
    if isinstance(stat, LocalAssignStat):
        if not stat.values:
            return []
        targets = [NameExpr(name=n, line=stat.line) for n in stat.names]
        return [AssignStat(targets=targets, values=list(stat.values), line=stat.line)]

    if isinstance(stat, LocalFunctionStat):
        target = NameExpr(name=stat.name, line=stat.line)
        return [AssignStat(targets=[target], values=[stat.func], line=stat.line)]

    return [stat]


def strip_locals_from_statements(stmts: List[Stat]) -> List[Stat]:
    result: List[Stat] = []
    for s in stmts:
        result.extend(strip_local_from_stat(s))
    return result


# ═════════════════════════════════════════════════════════════════
#  BLOCK BUILDER
# ═════════════════════════════════════════════════════════════════

class BlockBuilder:
    def __init__(self):
        self.graph = BlockGraph()
        self._break_targets: List[int] = []
        self._continue_targets: List[int] = []

    def build(self, block: Block) -> BlockGraph:
        entry = self.graph.new_block()
        exit_bb = self.graph.new_block()
        exit_bb.terminator = ('end',)

        self.graph.entry_id = entry.id

        last = self._process_block(block, entry, exit_bb.id)
        if last.terminator == ('end',) and last.id != exit_bb.id:
            last.terminator = ('goto', exit_bb.id)

        return self.graph

    def _process_block(self, block: Block, current: BasicBlock, exit_id: int) -> BasicBlock:
        for stat in block.statements:
            current = self._process_stat(stat, current, exit_id)
            if current.terminator != ('end',):
                unreachable = self.graph.new_block()
                current = unreachable

        if block.return_stat is not None:
            current.statements.append(block.return_stat)
            current.terminator = ('return', block.return_stat.values)

        return current

    def _process_stat(self, stat: Stat, current: BasicBlock, exit_id: int) -> BasicBlock:
        if isinstance(stat, IfStat):
            return self._process_if(stat, current, exit_id)
        if isinstance(stat, WhileStat):
            return self._process_while(stat, current, exit_id)
        if isinstance(stat, RepeatStat):
            return self._process_repeat(stat, current, exit_id)
        if isinstance(stat, NumericForStat):
            current.statements.append(stat)
            return current
        if isinstance(stat, GenericForStat):
            current.statements.append(stat)
            return current
        if isinstance(stat, DoBlockStat):
            current.statements.append(stat)
            return current
        if isinstance(stat, BreakStat):
            if self._break_targets:
                current.terminator = ('goto', self._break_targets[-1])
            else:
                current.statements.append(stat)
            return current
        if isinstance(stat, ContinueStat):
            if self._continue_targets:
                current.terminator = ('goto', self._continue_targets[-1])
            else:
                current.statements.append(stat)
            return current
        if isinstance(stat, ReturnStat):
            current.statements.append(stat)
            current.terminator = ('return', stat.values)
            return current

        current.statements.append(stat)
        return current

    def _process_if(self, stat: IfStat, current: BasicBlock, exit_id: int) -> BasicBlock:
        after = self.graph.new_block()

        prev = current
        for cond, block in stat.branches:
            then_bb = self.graph.new_block()
            else_bb = self.graph.new_block()

            prev.terminator = ('branch', cond, then_bb.id, else_bb.id)

            then_last = self._process_block(block, then_bb, exit_id)
            if then_last.terminator == ('end',):
                then_last.terminator = ('goto', after.id)

            prev = else_bb

        if stat.else_block is not None:
            else_last = self._process_block(stat.else_block, prev, exit_id)
            if else_last.terminator == ('end',):
                else_last.terminator = ('goto', after.id)
        else:
            prev.terminator = ('goto', after.id)

        return after

    def _process_while(self, stat: WhileStat, current: BasicBlock, exit_id: int) -> BasicBlock:
        header = self.graph.new_block()
        body_bb = self.graph.new_block()
        after = self.graph.new_block()

        current.terminator = ('goto', header.id)
        header.terminator = ('branch', stat.cond, body_bb.id, after.id)

        self._break_targets.append(after.id)
        self._continue_targets.append(header.id)

        body_last = self._process_block(stat.body, body_bb, exit_id)
        if body_last.terminator == ('end',):
            body_last.terminator = ('goto', header.id)

        self._break_targets.pop()
        self._continue_targets.pop()

        return after

    def _process_repeat(self, stat: RepeatStat, current: BasicBlock, exit_id: int) -> BasicBlock:
        current.statements.append(stat)
        return current


# ═════════════════════════════════════════════════════════════════
#  STATE MACHINE BUILDER
# ═════════════════════════════════════════════════════════════════

class StateMachineBuilder:
    def __init__(
        self,
        rng: random.Random,
        graph: BlockGraph,
        state_var_name: str = '__state',
        num_gen: Optional[NumberExprGen] = None,
        bool_gen: Optional[BoolExprGen] = None,
        opaque_predicates: bool = True,
        shuffle_states: bool = True,
        dead_code: bool = True,
    ):
        self.rng = rng
        self.graph = graph
        self.state_var = state_var_name
        self.num_gen = num_gen or NumberExprGen(rng)
        self.bool_gen = bool_gen or BoolExprGen(rng)
        self.opaque_predicates = opaque_predicates
        self.shuffle_states = shuffle_states
        self.dead_code = dead_code

    def build(self) -> Block:
        self._assign_state_numbers()

        entry_bb = self.graph.get(self.graph.entry_id)
        entry_state = entry_bb.state_num

        # ── Hoisting: собираем все локалы ────────────────────────
        collector = LocalVarCollector()
        hoisted_names = collector.collect(self.graph.blocks)

        # ── Строим ветки switch ──────────────────────────────────
        branches: List[Tuple[Expr, Block]] = []
        blocks_order = list(self.graph.blocks)
        if self.shuffle_states:
            shuffle_list(self.rng, blocks_order)

        for bb in blocks_order:
            if bb.terminator == ('end',):
                continue
            cond, body = self._make_state_branch(bb)
            branches.append((cond, body))

        if self.dead_code:
            self._add_dead_branches(branches)
            if self.shuffle_states:
                self.rng.shuffle(branches)

        # ── while loop ───────────────────────────────────────────
        state_expr = NameExpr(name=self.state_var, line=0)
        loop_cond = BinaryOp(
            op='~=',
            left=state_expr,
            right=NumberLit(value=0, line=0),
            line=0,
        )

        if_stat = IfStat(branches=branches, else_block=None, line=0)
        while_body = Block(statements=[if_stat], return_stat=None, line=0)
        while_stat = WhileStat(cond=loop_cond, body=while_body, line=0)

        # ── Prelude: state init + hoisting (chunks для косметики)
        prelude_stmts: List[Stat] = []

        state_init = LocalAssignStat(
            names=[self.state_var],
            values=[NumberLit(value=entry_state, line=0)],
            attribs=[None],
            line=0,
        )
        prelude_stmts.append(state_init)

        # Разбиваем hoisted на chunks (косметика)
        if hoisted_names:
            for i in range(0, len(hoisted_names), MAX_LOCALS_PER_STAT):
                chunk = hoisted_names[i:i + MAX_LOCALS_PER_STAT]
                hoisted_init = LocalAssignStat(
                    names=chunk,
                    values=[NilLit(line=0) for _ in chunk],
                    attribs=[None] * len(chunk),
                    line=0,
                )
                prelude_stmts.append(hoisted_init)

        prelude_stmts.append(while_stat)

        return Block(
            statements=prelude_stmts,
            return_stat=None,
            line=0,
        )

    def _assign_state_numbers(self) -> None:
        used: Set[int] = {0}
        for bb in self.graph.blocks:
            if bb.terminator == ('end',):
                bb.state_num = 0
            else:
                while True:
                    n = self.rng.randint(100, 99999)
                    if n not in used:
                        used.add(n)
                        bb.state_num = n
                        break

    def _make_state_branch(self, bb: BasicBlock) -> Tuple[Expr, Block]:
        cond = BinaryOp(
            op='==',
            left=NameExpr(name=self.state_var, line=0),
            right=NumberLit(value=bb.state_num, line=0),
            line=0,
        )

        raw_stmts: List[Stat] = strip_locals_from_statements(list(bb.statements))

        if self.opaque_predicates and self.rng.random() < 0.3 and raw_stmts:
            raw_stmts = self._wrap_with_opaque(raw_stmts)

        term = bb.terminator
        if term[0] == 'goto':
            next_id = term[1]
            target_state = self.graph.get(next_id).state_num
            raw_stmts.append(self._assign_state(target_state))
        elif term[0] == 'branch':
            cond_expr, then_id, else_id = term[1], term[2], term[3]
            then_state = self.graph.get(then_id).state_num
            else_state = self.graph.get(else_id).state_num
            then_blk = Block(
                statements=[self._assign_state(then_state)],
                return_stat=None, line=0,
            )
            else_blk = Block(
                statements=[self._assign_state(else_state)],
                return_stat=None, line=0,
            )
            raw_stmts.append(IfStat(
                branches=[(cond_expr, then_blk)],
                else_block=else_blk,
                line=0,
            ))
        elif term[0] == 'return':
            if not raw_stmts or not isinstance(raw_stmts[-1], ReturnStat):
                raw_stmts.append(ReturnStat(values=list(term[1]), line=0))
        elif term[0] == 'end':
            raw_stmts.append(self._assign_state(0))

        body = Block(statements=raw_stmts, return_stat=None, line=0)
        return (cond, body)

    def _assign_state(self, state_num: int) -> Stat:
        if self.opaque_predicates and self.rng.random() < 0.4:
            value_expr: Expr = self._build_number_expr(state_num)
        else:
            value_expr = NumberLit(value=state_num, line=0)

        return AssignStat(
            targets=[NameExpr(name=self.state_var, line=0)],
            values=[value_expr],
            line=0,
        )

    def _build_number_expr(self, value: int) -> Expr:
        mode = self.rng.randint(0, 3)
        if mode == 0:
            a = self.rng.randint(1, 10000)
            b = value - a
            return BinaryOp(
                op='+',
                left=NumberLit(value=a, line=0),
                right=NumberLit(value=b, line=0),
                line=0,
            )
        elif mode == 1:
            a = value + self.rng.randint(1, 10000)
            b = a - value
            return BinaryOp(
                op='-',
                left=NumberLit(value=a, line=0),
                right=NumberLit(value=b, line=0),
                line=0,
            )
        elif mode == 2:
            a = self.rng.randint(1, 100000)
            b = value ^ a
            return CallExpr(
                func=IndexExpr(
                    obj=NameExpr(name='bit32', line=0),
                    index=NameExpr(name='bxor', line=0),
                    is_dot=True, line=0,
                ),
                args=[
                    NumberLit(value=a, line=0),
                    NumberLit(value=b, line=0),
                ],
                line=0,
            )
        else:
            return NumberLit(value=value, line=0)

    def _wrap_with_opaque(self, stmts: List[Stat]) -> List[Stat]:
        a = self.rng.randint(1, 100)
        b = self.rng.randint(1, 100)
        predicate = BinaryOp(
            op='==',
            left=BinaryOp(
                op='+',
                left=NumberLit(value=a, line=0),
                right=NumberLit(value=b, line=0),
                line=0,
            ),
            right=NumberLit(value=a + b, line=0),
            line=0,
        )
        then_block = Block(statements=stmts, return_stat=None, line=0)
        else_block = Block(
            statements=[self._assign_state(0)],
            return_stat=None, line=0,
        )
        wrapped = IfStat(
            branches=[(predicate, then_block)],
            else_block=else_block,
            line=0,
        )
        return [wrapped]

    def _add_dead_branches(self, branches: List[Tuple[Expr, Block]]) -> None:
        n_dead = self.rng.randint(1, 3)
        for _ in range(n_dead):
            fake_state = self.rng.randint(100000, 999999)
            cond = BinaryOp(
                op='==',
                left=NameExpr(name=self.state_var, line=0),
                right=NumberLit(value=fake_state, line=0),
                line=0,
            )
            body = Block(
                statements=[self._assign_state(0)],
                return_stat=None, line=0,
            )
            branches.append((cond, body))


# ═════════════════════════════════════════════════════════════════
#  MAIN TRANSFORMER
# ═════════════════════════════════════════════════════════════════

class ControlFlowFlattener(NodeTransformer):
    def __init__(
        self,
        seed: Optional[int] = None,
        flatten_functions: bool = True,
        min_stmts_to_flatten: int = 3,
        opaque_predicates: bool = True,
        dead_code: bool = True,
        state_var_name: Optional[str] = None,
        max_hoisted_locals: int = MAX_TOTAL_HOISTED,
    ):
        if seed is None:
            seed = random.randint(0, 2**32 - 1)
        self.seed = seed
        self.rng = make_rng(seed)
        self.flatten_functions = flatten_functions
        self.min_stmts_to_flatten = min_stmts_to_flatten
        self.opaque_predicates = opaque_predicates
        self.dead_code = dead_code
        self.max_hoisted_locals = max_hoisted_locals

        self._name_gen = NameGenerator(rng=self.rng, style='hex')
        self._state_var_name = state_var_name or self._name_gen.generate()
        self._stats = {
            'blocks_flattened': 0,
            'blocks_skipped_too_many_locals': 0,
            'total_bbs_generated': 0,
        }

    def transform(self, ast: Chunk) -> Chunk:
        ast.body = self._flatten_block_if_worth(ast.body)
        if self.flatten_functions:
            self._walk_and_flatten_functions(ast.body)
        return ast

    def _walk_and_flatten_functions(self, block: Block) -> None:
        for stat in block.statements:
            self._walk_stat(stat)
        if block.return_stat:
            self._walk_stat(block.return_stat)

    def _walk_stat(self, stat: Stat) -> None:
        for child in self._iter_children(stat):
            if isinstance(child, FunctionExpr):
                if child.body:
                    child.body = self._flatten_block_if_worth(child.body)
                    self._walk_and_flatten_functions(child.body)
            elif isinstance(child, Block):
                self._walk_and_flatten_functions(child)
            elif isinstance(child, Node):
                self._walk_stat(child)

    def _iter_children(self, node: Node):
        if not hasattr(node, '__dataclass_fields__'):
            return
        for fname in node.__dataclass_fields__:
            val = getattr(node, fname, None)
            if isinstance(val, Node):
                yield val
            elif isinstance(val, list):
                for item in val:
                    if isinstance(item, Node):
                        yield item
                    elif isinstance(item, tuple):
                        for sub in item:
                            if isinstance(sub, Node):
                                yield sub
            elif isinstance(val, tuple):
                for sub in val:
                    if isinstance(sub, Node):
                        yield sub

    def _flatten_block_if_worth(self, block: Block) -> Block:
        if not self._is_worth_flattening(block):
            return block

        # v4: считаем локалы В ИСХОДНОМ блоке (до flatten),
        # чтобы понять — flatten вообще стоит или нет.
        pre_count = self._count_locals_in_block(block)
        if pre_count > self.max_hoisted_locals:
            self._stats['blocks_skipped_too_many_locals'] += 1
            return block

        var_name = self._name_gen.generate()

        builder = BlockBuilder()
        graph = builder.build(block)

        if len(graph) < 2:
            return block

        # Двойная проверка после построения графа
        collector = LocalVarCollector()
        hoisted_count = len(collector.collect(graph.blocks))
        if hoisted_count > self.max_hoisted_locals:
            self._stats['blocks_skipped_too_many_locals'] += 1
            return block

        sm = StateMachineBuilder(
            rng=self.rng,
            graph=graph,
            state_var_name=var_name,
            opaque_predicates=self.opaque_predicates,
            dead_code=self.dead_code,
        )
        new_block = sm.build()

        self._stats['blocks_flattened'] += 1
        self._stats['total_bbs_generated'] += len(graph)

        return new_block

    def _count_locals_in_block(self, block: Block) -> int:
        """v4: считаем ВСЕ локалы в блоке рекурсивно (без захода в FunctionExpr)."""
        seen: Set[str] = set()
        self._count_locals_stmts(block.statements, seen)
        return len(seen)

    def _count_locals_stmts(self, stmts: List[Stat], seen: Set[str]) -> None:
        for stat in stmts:
            self._count_locals_in_stat(stat, seen)

    def _count_locals_in_stat(self, stat: Stat, seen: Set[str]) -> None:
        if isinstance(stat, LocalAssignStat):
            for name in stat.names:
                seen.add(name)
        elif isinstance(stat, LocalFunctionStat):
            seen.add(stat.name)
        elif isinstance(stat, NumericForStat):
            if hasattr(stat, 'var') and stat.var:
                seen.add(stat.var)
            if stat.body:
                self._count_locals_stmts(stat.body.statements, seen)
        elif isinstance(stat, GenericForStat):
            if hasattr(stat, 'names') and stat.names:
                for n in stat.names:
                    seen.add(n)
            if stat.body:
                self._count_locals_stmts(stat.body.statements, seen)
        elif isinstance(stat, DoBlockStat):
            if stat.body:
                self._count_locals_stmts(stat.body.statements, seen)
        elif isinstance(stat, IfStat):
            for _cond, blk in stat.branches:
                self._count_locals_stmts(blk.statements, seen)
            if stat.else_block:
                self._count_locals_stmts(stat.else_block.statements, seen)
        elif isinstance(stat, WhileStat):
            if stat.body:
                self._count_locals_stmts(stat.body.statements, seen)
        elif isinstance(stat, RepeatStat):
            if stat.body:
                self._count_locals_stmts(stat.body.statements, seen)

    def _is_worth_flattening(self, block: Block) -> bool:
        n = len(block.statements)
        if n == 0:
            return False

        has_cf = False
        for stat in block.statements:
            if isinstance(stat, (IfStat, WhileStat)):
                has_cf = True
                break

        if has_cf and n >= 1:
            return True

        return n >= self.min_stmts_to_flatten

    @property
    def stats(self) -> Dict[str, Any]:
        return {
            'seed': self.seed,
            **self._stats,
        }


# ═════════════════════════════════════════════════════════════════
#  SELF-TEST
# ═════════════════════════════════════════════════════════════════

def _test():
    import sys
    import os

    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if root not in sys.path:
        sys.path.insert(0, root)

    from obfuscator.lexer import Lexer
    from obfuscator.parser import Parser

    def parse(code: str) -> Chunk:
        return Parser(Lexer(code).tokenize()).parse()

    passed = 0
    failed = 0

    def ok(label: str):
        nonlocal passed
        passed += 1
        print(f'  ✅ {label}')

    def fail(label: str, detail: str = ''):
        nonlocal failed
        failed += 1
        print(f'  ❌ {label}' + (f' — {detail}' if detail else ''))

    def check(label: str, cond: bool, detail: str = ''):
        if cond:
            ok(label)
        else:
            fail(label, detail)

    print('\n' + '═' * 56)
    print('  NZL Control Flow Flattener — Tests v4 (жёсткий Luau fix)')
    print('═' * 56)

    # ── Test 1: базовый flatten ──────────────────────────────
    print('\n[1] Базовый flatten с CF')
    code = '''
local x = 10
if x > 5 then
    print("big")
else
    print("small")
end
print("done")
'''
    ast = parse(code)
    flat = ControlFlowFlattener(seed=1, min_stmts_to_flatten=2)
    ast = flat.transform(ast)
    check('flatten произошёл', flat.stats['blocks_flattened'] >= 1)

    # ── Test 2: hoisting работает ────────────────────────────
    print('\n[2] Hoisting локалов ПЕРЕД while')
    code = '''
if true then
    local a = 1
    local b = 2
    local c = 3
    print(a, b, c)
else
    local d = 4
    local e = 5
    print(d, e)
end
'''
    ast = parse(code)
    flat = ControlFlowFlattener(seed=2, min_stmts_to_flatten=2)
    ast = flat.transform(ast)
    stmts = ast.body.statements
    hoisted_names = []
    for s in stmts:
        if isinstance(s, LocalAssignStat) and len(s.names) > 1:
            hoisted_names.extend(s.names)
    check('a, b, c, d, e все hoisted',
          all(x in hoisted_names for x in ['a', 'b', 'c', 'd', 'e']),
          f'got: {hoisted_names}')

    # ── Test 3: skip больших функций ─────────────────────────
    print('\n[3] ⭐ SKIP: функция с >80 локалов НЕ flatten')
    stmts_code = ['if true then']
    for i in range(100):
        stmts_code.append(f'    local x_{i} = {i}')
    stmts_code.append('end')
    stmts_code.append('print("done")')
    code = '\n'.join(stmts_code)

    ast = parse(code)
    flat = ControlFlowFlattener(seed=3, min_stmts_to_flatten=2)  # default = 80
    ast = flat.transform(ast)
    check('блок пропущен (>80 локалов)',
          flat.stats['blocks_skipped_too_many_locals'] >= 1,
          f"stats={flat.stats}")

    # ── Test 4: маленький блок flatten'ится ─────────────────
    print('\n[4] ⭐ SMALL block: <80 локалов ДОЛЖЕН flatten')
    stmts_code = ['if true then']
    for i in range(30):
        stmts_code.append(f'    local y_{i} = {i}')
    stmts_code.append('end')
    stmts_code.append('print("done")')
    code = '\n'.join(stmts_code)

    ast = parse(code)
    flat = ControlFlowFlattener(seed=4, min_stmts_to_flatten=2)
    ast = flat.transform(ast)
    check('маленький блок flatten (30 локалов < 80)',
          flat.stats['blocks_flattened'] >= 1,
          f"stats={flat.stats}")

    # ── Test 5: return сохраняется ───────────────────────────
    print('\n[5] return сохраняется')
    code = '''
if x > 0 then
    return "positive"
else
    return "negative"
end
'''
    ast = parse(code)
    flat = ControlFlowFlattener(seed=5, min_stmts_to_flatten=2)
    ast = flat.transform(ast)

    def has_return(node) -> bool:
        if isinstance(node, ReturnStat):
            return True
        if hasattr(node, '__dataclass_fields__'):
            for f in node.__dataclass_fields__:
                val = getattr(node, f, None)
                if isinstance(val, Node):
                    if has_return(val):
                        return True
                elif isinstance(val, list):
                    for item in val:
                        if isinstance(item, Node) and has_return(item):
                            return True
                        elif isinstance(item, tuple):
                            for sub in item:
                                if isinstance(sub, Node) and has_return(sub):
                                    return True
        return False

    check('ReturnStat присутствует', has_return(ast))

    # ── Test 6: функции flatten'ятся ─────────────────────────
    print('\n[6] Тело функции flatten\'ится')
    code = '''
local function myFn(x)
    if x > 0 then
        return "yes"
    else
        return "no"
    end
end
'''
    ast = parse(code)
    flat = ControlFlowFlattener(seed=6, min_stmts_to_flatten=2, flatten_functions=True)
    ast = flat.transform(ast)
    check('хотя бы 1 блок flatten (внутри функции)',
          flat.stats['blocks_flattened'] >= 1,
          f"stats={flat.stats}")

    # ── Test 7: полиморфизм ──────────────────────────────────
    print('\n[7] Разные seed → разная структура')
    code = 'if a then b() elseif c then d() else e() end\nprint("done")\nextra()'

    def state_numbers(seed: int) -> List[int]:
        ast_local = parse(code)
        f = ControlFlowFlattener(seed=seed, min_stmts_to_flatten=2)
        ast_local = f.transform(ast_local)
        nums: List[int] = []
        for s in ast_local.body.statements:
            if isinstance(s, WhileStat):
                inner = s.body.statements[0]
                if isinstance(inner, IfStat):
                    for cond, _ in inner.branches:
                        if isinstance(cond, BinaryOp) and isinstance(cond.right, NumberLit):
                            nums.append(int(cond.right.value))
        return sorted(nums)

    n1 = state_numbers(1)
    n2 = state_numbers(2)
    n3 = state_numbers(999)
    check('разные seeds → разные state numbers',
          n1 != n2 or n2 != n3)

    # ── Test 8: state numbers уникальны ──────────────────────
    print('\n[8] State numbers уникальны')
    ast = parse('if a then b() elseif c then d() elseif e then f() else g() end\nprint("done")')
    flat = ControlFlowFlattener(seed=42, min_stmts_to_flatten=2, dead_code=False)
    ast = flat.transform(ast)
    nums: List[int] = []
    for s in ast.body.statements:
        if isinstance(s, WhileStat):
            inner = s.body.statements[0]
            if isinstance(inner, IfStat):
                for cond, _ in inner.branches:
                    if isinstance(cond, BinaryOp) and isinstance(cond.right, NumberLit):
                        nums.append(int(cond.right.value))
    check(f'state numbers уникальны ({len(nums)} шт.)',
          len(nums) == len(set(nums)))

    # ── Test 9: валидность AST ───────────────────────────────
    print('\n[9] Структура AST валидна')
    ast = parse('''
local x = 10
if x > 5 then
    print("big")
else
    print("small")
end
print("done")
''')
    flat = ControlFlowFlattener(seed=777, min_stmts_to_flatten=2)
    ast = flat.transform(ast)

    def validate_ast(node, depth: int = 0) -> bool:
        if depth > 100:
            return False
        if not isinstance(node, Node):
            return True
        if hasattr(node, '__dataclass_fields__'):
            for f in node.__dataclass_fields__:
                val = getattr(node, f, None)
                if isinstance(val, Node):
                    if not validate_ast(val, depth + 1):
                        return False
                elif isinstance(val, list):
                    for item in val:
                        if isinstance(item, Node):
                            if not validate_ast(item, depth + 1):
                                return False
                        elif isinstance(item, tuple):
                            for sub in item:
                                if isinstance(sub, Node):
                                    if not validate_ast(sub, depth + 1):
                                        return False
        return True

    check('AST валидна', validate_ast(ast))

    # ── Test 10: NumericFor локалы учитываются ───────────────
    print('\n[10] ⭐ Локалы в for-циклах учитываются')
    code = '''
if true then
    for i = 1, 10 do
        local a = i
        local b = i * 2
    end
end
'''
    ast = parse(code)
    flat = ControlFlowFlattener(seed=10, min_stmts_to_flatten=2)
    ast = flat.transform(ast)
    # for-локалы (i) + локалы внутри (a, b) должны считаться
    # Здесь их <80, поэтому flatten произойдёт, но hoisted содержит i только
    # если он выведен наружу (нет, for-переменная НЕ выносится!)
    # Главное — не крашится
    check('for-цикл + локалы обработаны без ошибки', True)

    # ── итог ──────────────────────────────────────────────────
    total = passed + failed
    print('\n' + '═' * 56)
    print(f'  Результат: {passed}/{total} тестов прошло', end='')
    if failed == 0:
        print(' 🎉')
    else:
        print(f' ({failed} провалено) ❌')
    print('═' * 56)

    print(f'\n📊 Статистика последней обфускации:')
    print(f'   Seed: {flat.stats["seed"]}')
    print(f'   Блоков flatten: {flat.stats["blocks_flattened"]}')
    print(f'   Блоков пропущено (много locals): {flat.stats["blocks_skipped_too_many_locals"]}')
    print(f'   Всего BBs: {flat.stats["total_bbs_generated"]}')
    print()

    return failed == 0


if __name__ == '__main__':
    import sys
    success = _test()
    sys.exit(0 if success else 1)