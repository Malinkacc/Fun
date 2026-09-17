"""
NZL Studio Obfuscator — Variable Renamer v3
Scope-aware переименование локальных переменных Luau.

⚡ v3 фиксы:
- NamePool ГАРАНТИРУЕТ уникальность имён (нет коллизий!)
- Fallback при исчерпании пула тоже проверяет уникальность
- Все выданные имена трекаются глобально в NameGenerator
"""

from __future__ import annotations
import random
from typing import Dict, List, Optional, Set, Tuple, Any

from ..ast_nodes import (
    Node, NodeTransformer, NodeVisitor,
    Chunk, Block, Expr, Stat,
    NameExpr, IndexExpr, CallExpr, MethodCallExpr,
    FunctionExpr, FunctionDeclStat, LocalFunctionStat, LocalAssignStat,
    AssignStat, CompoundAssignStat,
    NumericForStat, GenericForStat, DoBlockStat,
    WhileStat, RepeatStat, IfStat,
    ReturnStat, BreakStat, ContinueStat, GotoStat, LabelStat,
    ParenExpr, TableExpr, TableField,
    NilLit, BoolLit, NumberLit, StringLit, VarargLit,
    BinaryOp, UnaryOp, CallStat,
)
from ..utils.random_gen import NameGenerator, make_rng, LUA_RESERVED


PROTECTED_IDENTIFIERS: Set[str] = {
    'game', 'workspace', 'script', 'shared', 'plugin', 'Enum', 'Instance',
    'Vector2', 'Vector3', 'CFrame', 'Color3', 'UDim', 'UDim2', 'BrickColor',
    'Ray', 'Region3', 'NumberRange', 'NumberSequence', 'NumberSequenceKeypoint',
    'ColorSequence', 'ColorSequenceKeypoint', 'TweenInfo', 'RaycastParams',
    'PhysicalProperties', 'Rect', 'Axes', 'Faces', 'Random', 'DateTime',
    'PathWaypoint',
    'Players', 'Workspace', 'RunService', 'TweenService', 'UserInputService',
    'ContextActionService', 'ReplicatedStorage', 'TeleportService', 'HttpService',
    'VirtualInputManager', 'VirtualUser', 'CoreGui', 'StarterGui', 'Lighting',
    'ServerStorage', 'ServerScriptService', 'SoundService', 'Debris',
    'MarketplaceService', 'GuiService', 'StatsService', 'LogService', 'Chat',
    'TextService',
    'print', 'warn', 'error', 'assert', 'pcall', 'xpcall', 'select', 'type',
    'tostring', 'tonumber', 'pairs', 'ipairs', 'next', 'unpack', 'rawget',
    'rawset', 'rawequal', 'rawlen', 'setmetatable', 'getmetatable', 'require',
    'loadstring', 'load', 'collectgarbage', 'wait', 'delay', 'spawn', 'tick',
    'time', 'os', 'math', 'string', 'table', 'coroutine', 'debug', 'io',
    'bit32', 'utf8', 'buffer', 'task',
    'getgenv', 'getrenv', 'getgc', 'getreg', 'getconstants', 'getconstant',
    'getupvalues', 'getupvalue', 'setupvalue', 'getprotos', 'getproto',
    'setconstant', 'islclosure', 'iscclosure', 'checkcaller', 'hookfunction',
    'hookmetamethod', 'newcclosure', 'newlclosure', 'clonefunction',
    'getnamecallmethod', 'setnamecallmethod', 'setreadonly', 'isreadonly',
    'setrawmetatable', 'getrawmetatable', 'fireclickdetector',
    'fireproximityprompt', 'firetouchinterest', 'getconnections', 'getsenv',
    'getcallingscript', 'getcustomasset', 'getsynasset', 'getobjects',
    'getnilinstances', 'getinstances', 'lz4compress', 'lz4decompress', 'crypt',
    'base64', 'httpget', 'httppost', 'request', 'syn', 'protectgui',
    'isnetworkowner', 'firesignal', 'replicatesignal', 'queue_on_teleport',
    'queueonteleport', 'setclipboard', 'toclipboard', 'setfflag', 'getfflag',
    'identifyexecutor', 'messagebox', 'setfpscap', 'readfile', 'writefile',
    'appendfile', 'loadfile', 'listfiles', 'isfile', 'isfolder', 'makefolder',
    'delfile', 'delfolder', 'saveinstance', 'gethui',
    'self', '_G', '_ENV', '_VERSION',
}
PROTECTED_IDENTIFIERS.update(LUA_RESERVED)


# ═══════════════════════════════════════════════════════════════════════
#  UNIQUE NAME GENERATOR — гарантирует уникальность
# ═══════════════════════════════════════════════════════════════════════

MAX_NAMES_PER_FUNCTION = 150


class UniqueNameSource:
    """
    Обёртка над NameGenerator, которая ГАРАНТИРУЕТ уникальность имён.
    Все выданные имена хранятся в глобальном множестве.
    """
    __slots__ = ('gen', 'issued')

    def __init__(self, name_gen: NameGenerator):
        self.gen = name_gen
        self.issued: Set[str] = set()

    def next(self) -> str:
        """Вернуть новое уникальное имя, никогда не выданное ранее."""
        for _ in range(1000):
            name = self.gen.generate()
            if name in PROTECTED_IDENTIFIERS:
                continue
            if name in self.issued:
                continue
            self.issued.add(name)
            return name
        # Крайний случай: генератор не может дать уникальное — суффикс
        base = self.gen.generate()
        i = 0
        while True:
            candidate = f"{base}_{i}"
            if candidate not in self.issued and candidate not in PROTECTED_IDENTIFIERS:
                self.issued.add(candidate)
                return candidate
            i += 1


class NamePool:
    """
    Пул имён на уровне функции.
    Переиспользует имена между непересекающимися scope.
    ГАРАНТИЯ: все имена в пуле уникальны, fallback тоже уникален.
    """
    __slots__ = ('source', 'pool', 'in_use_stack')

    def __init__(self, source: UniqueNameSource):
        self.source = source
        self.pool: List[str] = []
        self.in_use_stack: List[Set[str]] = [set()]

    def _ensure_pool_size(self, needed: int) -> None:
        while len(self.pool) < min(needed, MAX_NAMES_PER_FUNCTION):
            self.pool.append(self.source.next())

    def push_scope(self) -> None:
        self.in_use_stack.append(set(self.in_use_stack[-1]))

    def pop_scope(self) -> None:
        if len(self.in_use_stack) > 1:
            self.in_use_stack.pop()

    def acquire(self) -> str:
        """Взять свободное имя из пула (или уникальный fallback)."""
        in_use = self.in_use_stack[-1]
        # Ищем свободное имя в пуле
        for i in range(MAX_NAMES_PER_FUNCTION):
            self._ensure_pool_size(i + 1)
            if i >= len(self.pool):
                break
            name = self.pool[i]
            if name not in in_use:
                in_use.add(name)
                return name
        # Пул исчерпан → берём НОВОЕ уникальное имя из источника
        new_name = self.source.next()
        in_use.add(new_name)
        return new_name


# ═══════════════════════════════════════════════════════════════════════
#  SCOPE
# ═══════════════════════════════════════════════════════════════════════

class Scope:
    __slots__ = ('parent', 'is_function', 'mappings', 'name_pool', '_id')
    _counter = 0

    def __init__(
        self,
        parent: Optional['Scope'] = None,
        is_function: bool = False,
        name_pool: Optional[NamePool] = None,
    ):
        self.parent = parent
        self.is_function = is_function
        self.mappings: Dict[str, str] = {}
        if is_function or name_pool is not None:
            self.name_pool = name_pool
        else:
            self.name_pool = parent.name_pool if parent else None
        Scope._counter += 1
        self._id = Scope._counter

    def define(self, original: str, renamed: str) -> None:
        self.mappings[original] = renamed

    def resolve(self, name: str) -> Optional[str]:
        scope: Optional[Scope] = self
        while scope is not None:
            if name in scope.mappings:
                return scope.mappings[name]
            scope = scope.parent
        return None

    def is_protected(self, name: str) -> bool:
        return name in PROTECTED_IDENTIFIERS

    def __repr__(self) -> str:
        return f'<Scope#{self._id} fn={self.is_function} vars={list(self.mappings.keys())}>'


# ═══════════════════════════════════════════════════════════════════════
#  PASS 1 — ScopeBuilder
# ═══════════════════════════════════════════════════════════════════════

class ScopeBuilder(NodeVisitor):

    def __init__(self, source: UniqueNameSource):
        self.source = source
        root_pool = NamePool(source)
        self.root_scope = Scope(parent=None, is_function=True, name_pool=root_pool)
        self.current = self.root_scope

    def _push(self, is_function: bool = False) -> Scope:
        if is_function:
            new_pool = NamePool(self.source)
            s = Scope(parent=self.current, is_function=True, name_pool=new_pool)
        else:
            s = Scope(parent=self.current, is_function=False)
            if s.name_pool is not None:
                s.name_pool.push_scope()
        self.current = s
        return s

    def _pop(self) -> Scope:
        old = self.current
        assert old.parent is not None
        if not old.is_function and old.name_pool is not None:
            old.name_pool.pop_scope()
        self.current = old.parent
        return old

    def _new_name(self, original: str) -> str:
        if original in PROTECTED_IDENTIFIERS:
            return original
        pool = self.current.name_pool
        if pool is None:
            return self.source.next()
        return pool.acquire()

    def _define(self, original: str) -> str:
        new = self._new_name(original)
        self.current.define(original, new)
        return new

    def _attach(self, node: Node, scope: Scope) -> None:
        object.__setattr__(node, '_scope', scope)

    def visit_Chunk(self, node: Chunk) -> None:
        self._attach(node.body, self.current)
        self.visit(node.body)

    def visit_Block(self, node: Block) -> None:
        for stat in node.statements:
            self.visit(stat)
        if node.return_stat:
            self.visit(node.return_stat)

    def visit_LocalAssignStat(self, node: LocalAssignStat) -> None:
        for val in node.values:
            self.visit(val)
        new_names: List[str] = []
        for name in node.names:
            new_names.append(self._define(name))
        object.__setattr__(node, '_new_names', new_names)

    def visit_LocalFunctionStat(self, node: LocalFunctionStat) -> None:
        new_name = self._define(node.name)
        object.__setattr__(node, '_new_name', new_name)
        fn_scope = self._push(is_function=True)
        self._attach(node.func, fn_scope)
        for param in node.func.params:
            self._define(param)
        if node.func.body:
            self._attach(node.func.body, fn_scope)
            self.visit(node.func.body)
        self._pop()

    def visit_FunctionDeclStat(self, node: FunctionDeclStat) -> None:
        self.visit(node.target)
        fn_scope = self._push(is_function=True)
        self._attach(node.func, fn_scope)
        effective_params = list(node.func.params)
        if node.method_name is not None:
            if not effective_params or effective_params[0] != 'self':
                effective_params.insert(0, 'self')
        for param in effective_params:
            self._define(param)
        if node.func.body:
            self._attach(node.func.body, fn_scope)
            self.visit(node.func.body)
        self._pop()

    def visit_FunctionExpr(self, node: FunctionExpr) -> None:
        fn_scope = self._push(is_function=True)
        self._attach(node, fn_scope)
        for param in node.params:
            self._define(param)
        if node.body:
            self._attach(node.body, fn_scope)
            self.visit(node.body)
        self._pop()

    def visit_NumericForStat(self, node: NumericForStat) -> None:
        self.visit(node.start)
        self.visit(node.stop)
        if node.step:
            self.visit(node.step)
        loop_scope = self._push(is_function=False)
        new_var = self._define(node.var)
        object.__setattr__(node, '_new_var', new_var)
        if node.body:
            self._attach(node.body, loop_scope)
            self.visit(node.body)
        self._pop()

    def visit_GenericForStat(self, node: GenericForStat) -> None:
        for expr in node.exprs:
            self.visit(expr)
        loop_scope = self._push(is_function=False)
        new_names: List[str] = []
        for name in node.names:
            new_names.append(self._define(name))
        object.__setattr__(node, '_new_names', new_names)
        if node.body:
            self._attach(node.body, loop_scope)
            self.visit(node.body)
        self._pop()

    def visit_DoBlockStat(self, node: DoBlockStat) -> None:
        blk_scope = self._push(is_function=False)
        if node.body:
            self._attach(node.body, blk_scope)
            self.visit(node.body)
        self._pop()

    def visit_WhileStat(self, node: WhileStat) -> None:
        self.visit(node.cond)
        blk_scope = self._push(is_function=False)
        if node.body:
            self._attach(node.body, blk_scope)
            self.visit(node.body)
        self._pop()

    def visit_RepeatStat(self, node: RepeatStat) -> None:
        blk_scope = self._push(is_function=False)
        if node.body:
            self._attach(node.body, blk_scope)
            self.visit(node.body)
        self.visit(node.cond)
        self._pop()

    def visit_IfStat(self, node: IfStat) -> None:
        for cond, block in node.branches:
            self.visit(cond)
            blk_scope = self._push(is_function=False)
            self._attach(block, blk_scope)
            self.visit(block)
            self._pop()
        if node.else_block:
            blk_scope = self._push(is_function=False)
            self._attach(node.else_block, blk_scope)
            self.visit(node.else_block)
            self._pop()

    def visit_AssignStat(self, node: AssignStat) -> None:
        for t in node.targets:
            self.visit(t)
        for v in node.values:
            self.visit(v)

    def visit_CompoundAssignStat(self, node: CompoundAssignStat) -> None:
        self.visit(node.target)
        self.visit(node.value)

    def visit_CallStat(self, node: CallStat) -> None:
        self.visit(node.call)

    def visit_ReturnStat(self, node: ReturnStat) -> None:
        for v in node.values:
            self.visit(v)

    def visit_CallExpr(self, node: CallExpr) -> None:
        self.visit(node.func)
        for a in node.args:
            self.visit(a)

    def visit_MethodCallExpr(self, node: MethodCallExpr) -> None:
        self.visit(node.obj)
        for a in node.args:
            self.visit(a)

    def visit_IndexExpr(self, node: IndexExpr) -> None:
        self.visit(node.obj)
        if not node.is_dot:
            self.visit(node.index)

    def visit_BinaryOp(self, node: BinaryOp) -> None:
        self.visit(node.left)
        self.visit(node.right)

    def visit_UnaryOp(self, node: UnaryOp) -> None:
        self.visit(node.operand)

    def visit_ParenExpr(self, node: ParenExpr) -> None:
        self.visit(node.inner)

    def visit_TableExpr(self, node: TableExpr) -> None:
        for field in node.fields:
            self._visit_table_field(field)

    def _visit_table_field(self, field: TableField) -> None:
        if not field.is_name and field.key is not None:
            self.visit(field.key)
        if field.value is not None:
            self.visit(field.value)

    def visit_NameExpr(self, node: NameExpr) -> None: pass
    def visit_NilLit(self, node: NilLit) -> None: pass
    def visit_BoolLit(self, node: BoolLit) -> None: pass
    def visit_NumberLit(self, node: NumberLit) -> None: pass
    def visit_StringLit(self, node: StringLit) -> None: pass
    def visit_VarargLit(self, node: VarargLit) -> None: pass
    def visit_BreakStat(self, node: BreakStat) -> None: pass
    def visit_ContinueStat(self, node: ContinueStat) -> None: pass
    def visit_GotoStat(self, node: GotoStat) -> None: pass
    def visit_LabelStat(self, node: LabelStat) -> None: pass

    def generic_visit(self, node: Node) -> None:
        pass


# ═══════════════════════════════════════════════════════════════════════
#  PASS 2 — RenameApplier
# ═══════════════════════════════════════════════════════════════════════

class RenameApplier(NodeTransformer):

    def __init__(self, root_scope: Scope):
        self._scope_stack: List[Scope] = [root_scope]

    @property
    def current(self) -> Scope:
        return self._scope_stack[-1]

    def _push(self, scope: Scope) -> None:
        self._scope_stack.append(scope)

    def _pop(self) -> None:
        self._scope_stack.pop()

    def _resolve(self, name: str) -> str:
        result = self.current.resolve(name)
        return result if result is not None else name

    def _get_scope(self, node: Node) -> Optional[Scope]:
        return getattr(node, '_scope', None)

    def visit_Chunk(self, node: Chunk) -> Chunk:
        node.body = self.visit(node.body)
        return node

    def visit_Block(self, node: Block) -> Block:
        scope = self._get_scope(node)
        if scope is not None:
            self._push(scope)
        node.statements = [self.visit(s) for s in node.statements]
        if node.return_stat:
            node.return_stat = self.visit(node.return_stat)
        if scope is not None:
            self._pop()
        return node

    def visit_NameExpr(self, node: NameExpr) -> NameExpr:
        node.name = self._resolve(node.name)
        return node

    def visit_LocalAssignStat(self, node: LocalAssignStat) -> LocalAssignStat:
        node.values = [self.visit(v) for v in node.values]
        new_names = getattr(node, '_new_names', None)
        if new_names is not None:
            node.names = new_names
        return node

    def visit_LocalFunctionStat(self, node: LocalFunctionStat) -> LocalFunctionStat:
        new_name = getattr(node, '_new_name', None)
        if new_name is not None:
            node.name = new_name
        node.func = self.visit(node.func)
        return node

    def visit_FunctionDeclStat(self, node: FunctionDeclStat) -> FunctionDeclStat:
        node.target = self.visit(node.target)
        node.func = self.visit(node.func)
        return node

    def visit_FunctionExpr(self, node: FunctionExpr) -> FunctionExpr:
        fn_scope = self._get_scope(node)
        if fn_scope is not None:
            self._push(fn_scope)
        new_params: List[str] = []
        for p in node.params:
            new_params.append(self._resolve(p))
        node.params = new_params
        if node.body:
            node.body = self.visit(node.body)
        if fn_scope is not None:
            self._pop()
        return node

    def visit_NumericForStat(self, node: NumericForStat) -> NumericForStat:
        node.start = self.visit(node.start)
        node.stop = self.visit(node.stop)
        if node.step:
            node.step = self.visit(node.step)
        body_scope = self._get_scope(node.body) if node.body else None
        if body_scope is not None:
            self._push(body_scope)
        new_var = getattr(node, '_new_var', None)
        if new_var is not None:
            node.var = new_var
        if node.body:
            node.body = self.visit(node.body)
        if body_scope is not None:
            self._pop()
        return node

    def visit_GenericForStat(self, node: GenericForStat) -> GenericForStat:
        node.exprs = [self.visit(e) for e in node.exprs]
        body_scope = self._get_scope(node.body) if node.body else None
        if body_scope is not None:
            self._push(body_scope)
        new_names = getattr(node, '_new_names', None)
        if new_names is not None:
            node.names = new_names
        if node.body:
            node.body = self.visit(node.body)
        if body_scope is not None:
            self._pop()
        return node

    def visit_DoBlockStat(self, node: DoBlockStat) -> DoBlockStat:
        if node.body:
            node.body = self.visit(node.body)
        return node

    def visit_WhileStat(self, node: WhileStat) -> WhileStat:
        node.cond = self.visit(node.cond)
        if node.body:
            node.body = self.visit(node.body)
        return node

    def visit_RepeatStat(self, node: RepeatStat) -> RepeatStat:
        if node.body:
            node.body = self.visit(node.body)
        body_scope = self._get_scope(node.body) if node.body else None
        if body_scope is not None:
            self._push(body_scope)
        node.cond = self.visit(node.cond)
        if body_scope is not None:
            self._pop()
        return node

    def visit_IfStat(self, node: IfStat) -> IfStat:
        new_branches: List[Tuple[Expr, Block]] = []
        for cond, block in node.branches:
            new_cond = self.visit(cond)
            new_block = self.visit(block)
            new_branches.append((new_cond, new_block))
        node.branches = new_branches
        if node.else_block:
            node.else_block = self.visit(node.else_block)
        return node

    def visit_AssignStat(self, node: AssignStat) -> AssignStat:
        node.targets = [self.visit(t) for t in node.targets]
        node.values = [self.visit(v) for v in node.values]
        return node

    def visit_CompoundAssignStat(self, node: CompoundAssignStat) -> CompoundAssignStat:
        node.target = self.visit(node.target)
        node.value = self.visit(node.value)
        return node

    def visit_CallStat(self, node: CallStat) -> CallStat:
        node.call = self.visit(node.call)
        return node

    def visit_ReturnStat(self, node: ReturnStat) -> ReturnStat:
        node.values = [self.visit(v) for v in node.values]
        return node

    def visit_CallExpr(self, node: CallExpr) -> CallExpr:
        node.func = self.visit(node.func)
        node.args = [self.visit(a) for a in node.args]
        return node

    def visit_MethodCallExpr(self, node: MethodCallExpr) -> MethodCallExpr:
        node.obj = self.visit(node.obj)
        node.args = [self.visit(a) for a in node.args]
        return node

    def visit_IndexExpr(self, node: IndexExpr) -> IndexExpr:
        node.obj = self.visit(node.obj)
        if not node.is_dot:
            node.index = self.visit(node.index)
        return node

    def visit_BinaryOp(self, node: BinaryOp) -> BinaryOp:
        node.left = self.visit(node.left)
        node.right = self.visit(node.right)
        return node

    def visit_UnaryOp(self, node: UnaryOp) -> UnaryOp:
        node.operand = self.visit(node.operand)
        return node

    def visit_ParenExpr(self, node: ParenExpr) -> ParenExpr:
        node.inner = self.visit(node.inner)
        return node

    def visit_TableExpr(self, node: TableExpr) -> TableExpr:
        new_fields: List[TableField] = []
        for field in node.fields:
            new_fields.append(self._visit_table_field(field))
        node.fields = new_fields
        return node

    def _visit_table_field(self, field: TableField) -> TableField:
        if not field.is_name and field.key is not None:
            field.key = self.visit(field.key)
        if field.value is not None:
            field.value = self.visit(field.value)
        return field

    def visit_NilLit(self, node: NilLit) -> NilLit: return node
    def visit_BoolLit(self, node: BoolLit) -> BoolLit: return node
    def visit_NumberLit(self, node: NumberLit) -> NumberLit: return node
    def visit_StringLit(self, node: StringLit) -> StringLit: return node
    def visit_VarargLit(self, node: VarargLit) -> VarargLit: return node
    def visit_BreakStat(self, node: BreakStat) -> BreakStat: return node
    def visit_ContinueStat(self, node: ContinueStat) -> ContinueStat: return node
    def visit_GotoStat(self, node: GotoStat) -> GotoStat: return node
    def visit_LabelStat(self, node: LabelStat) -> LabelStat: return node

    def generic_visit(self, node: Node) -> Node:
        return node


# ═══════════════════════════════════════════════════════════════════════
#  PUBLIC CLASS
# ═══════════════════════════════════════════════════════════════════════

class VariableRenamer:
    """
    Переименовывает локальные переменные Luau.
    v3: гарантирует уникальность имён (нет коллизий).
    """

    def __init__(self, seed: Optional[int] = None, style: str = 'confusing'):
        if seed is None:
            seed = random.randint(0, 2**32 - 1)
        self.seed = seed
        self.style = style
        self._rng = make_rng(seed)
        self._name_gen = NameGenerator(rng=self._rng, style=style)
        self._source = UniqueNameSource(self._name_gen)
        self._names_generated = 0

    def transform(self, ast: Chunk) -> Chunk:
        Scope._counter = 0
        builder = ScopeBuilder(source=self._source)
        builder.visit(ast)
        applier = RenameApplier(root_scope=builder.root_scope)
        result = applier.visit(ast)
        self._names_generated = len(self._source.issued)
        return result

    @property
    def stats(self) -> Dict[str, Any]:
        return {
            'seed': self.seed,
            'style': self.style,
            'names_generated': self._names_generated,
        }


# ═══════════════════════════════════════════════════════════════════════
#  SELF-TEST
# ═══════════════════════════════════════════════════════════════════════

def _test():
    import sys
    import os

    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if root not in sys.path:
        sys.path.insert(0, root)

    from obfuscator.lexer import Lexer
    from obfuscator.parser import Parser

    def parse(code: str) -> Chunk:
        tokens = Lexer(code).tokenize()
        return Parser(tokens).parse()

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
    print('  NZL Variable Renamer v3 (unique pool) — Tests')
    print('═' * 56)

    print('\n[1] Простой local rename')
    ast = parse('local x = 10')
    ast = VariableRenamer(seed=1, style='hex').transform(ast)
    stat = ast.body.statements[0]
    check('x переименован', stat.names[0] != 'x', stat.names[0])

    print('\n[2] Upvalue')
    code = 'local counter = 0\nlocal function inc() counter = counter + 1 end'
    ast = parse(code)
    ast = VariableRenamer(seed=2, style='hex').transform(ast)
    counter_new = ast.body.statements[0].names[0]
    assign = ast.body.statements[1].func.body.statements[0]
    check('counter переименован', counter_new != 'counter')
    check('upvalue = то же имя', assign.targets[0].name == counter_new)

    print('\n[3] Pool переиспользование (< 200 имён на функцию)')
    code_parts = ['local function foo()\n']
    for i in range(300):
        code_parts.append(f'    do local v{i} = {i} end\n')
    code_parts.append('end\n')
    code = ''.join(code_parts)
    ast = parse(code)
    ast = VariableRenamer(seed=3, style='hex').transform(ast)
    foo_body = ast.body.statements[0].func.body
    all_names = set()
    for stat in foo_body.statements:
        if hasattr(stat, 'body') and stat.body is not None:
            for inner in stat.body.statements:
                if hasattr(inner, 'names'):
                    for n in inner.names:
                        all_names.add(n)
    check(
        f'уникальных имён ≤ {MAX_NAMES_PER_FUNCTION}',
        len(all_names) <= MAX_NAMES_PER_FUNCTION,
        f'got {len(all_names)}',
    )

    print('\n[4] self не переименовывается')
    code = 'local obj = {}\nfunction obj:method(x) return self.value + x end'
    ast = parse(code)
    ast = VariableRenamer(seed=7, style='confusing').transform(ast)
    params = ast.body.statements[1].func.params
    check('self остался self', params[0] == 'self')

    print('\n[5] Globals не трогаются')
    code = 'MyGlobal = 42\nprint(MyGlobal)'
    ast = parse(code)
    ast = VariableRenamer(seed=9, style='hex').transform(ast)
    check('MyGlobal остался', ast.body.statements[0].targets[0].name == 'MyGlobal')

    print('\n[6] Protected identifiers (game)')
    code = 'local p = game:GetService("Players")'
    ast = parse(code)
    ast = VariableRenamer(seed=10, style='hex').transform(ast)
    method_call = ast.body.statements[0].values[0]
    check('game не переименован', method_call.obj.name == 'game')

    # НОВЫЙ ТЕСТ v3 — критичный
    print('\n[7] Гарантия уникальности: 500 локалов в 1 scope — все имена разные')
    code_parts = ['local function big()\n']
    for i in range(500):
        code_parts.append(f'    local var_{i} = {i}\n')
    code_parts.append('end\n')
    code = ''.join(code_parts)
    ast = parse(code)
    ast = VariableRenamer(seed=42, style='confusing').transform(ast)
    big_body = ast.body.statements[0].func.body
    names_in_order = []
    for stat in big_body.statements:
        if hasattr(stat, 'names'):
            for n in stat.names:
                names_in_order.append(n)
    check(
        f'все 500 имён УНИКАЛЬНЫ (без коллизий)',
        len(names_in_order) == len(set(names_in_order)),
        f'total={len(names_in_order)} unique={len(set(names_in_order))}',
    )

    total = passed + failed
    print('\n' + '═' * 56)
    print(f'  Результат: {passed}/{total} тестов прошло', end='')
    print(' 🎉' if failed == 0 else f' ({failed} провалено) ❌')
    print('═' * 56 + '\n')
    return failed == 0


if __name__ == '__main__':
    import sys
    success = _test()
    sys.exit(0 if success else 1)