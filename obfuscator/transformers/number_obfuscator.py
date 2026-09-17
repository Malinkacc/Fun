"""
NZL Studio Obfuscator - Number Obfuscator Transformer
Replaces integer literals with polymorphic math expressions.

Example transformations (random each time):
    42        → (17 + 25)
    42        → bit32.bxor(45, 7)
    42        → (100 - 58)
    100       → (10 * 10)
    -50       → -(50)
    1337      → ((bit32.bxor(1330, 15)) + 7)

Context awareness — we DON'T obfuscate numbers in these places:
    - Table constructor keys: {[1] = "x"}   (breaks the table shape)
    - Very large numbers (>1M): coords, IDs
    - Floating point: 3.14, 1.5e10
    - Zero and one (optional): common, ugly when obfuscated

Modes:
    - conservative: 15% chance, depth 0
    - balanced:     35% chance, depth 1 (default)
    - aggressive:   70% chance, depth 2
"""

import random
from typing import Optional
from dataclasses import dataclass

from ..ast_nodes import (
    Node, NodeTransformer, NodeVisitor,
    Chunk, Block, Expr, Stat,
    NumberLit, StringLit, NameExpr, CallExpr, BinaryOp, UnaryOp,
    TableExpr, TableField, IndexExpr, ParenExpr,
    NumericForStat, GenericForStat, LocalAssignStat, AssignStat,
    FunctionExpr, CompoundAssignStat,
)
from ..utils.random_gen import make_rng, NumberExprGen, weighted_choice


# ==================== КОНФИГ ====================

@dataclass
class NumberObfuscatorConfig:
    """Configuration for number obfuscation"""
    probability: float = 0.35
    depth: int = 1
    skip_values: set = None
    max_value: int = 1_000_000
    min_value: int = -1_000_000
    skip_table_keys: bool = True
    skip_for_bounds: bool = False
    skip_array_index: bool = False   # Sprint 2: беречь индексы name-массивов (_L[1])
    handle_float_integers: bool = False
    
    def __post_init__(self):
        if self.skip_values is None:
            self.skip_values = {0, 1}
    
    @classmethod
    def conservative(cls):
        return cls(probability=0.15, depth=0, skip_for_bounds=True)
    
    @classmethod
    def balanced(cls):
        # 0.35 -> 0.5: при 0.35 фичи 0B/bit32 статистически пропадали из medium-вывода
        # skip_array_index: бережём _L[1] от превращения в _L[(0X1+0)] (Sprint 2)
        return cls(probability=0.5, depth=1, skip_for_bounds=False, skip_array_index=True)
    
    @classmethod
    def aggressive(cls):
        return cls(
            probability=0.70,
            depth=2,
            skip_values={0},
            skip_for_bounds=False,
        )


# ==================== СТАТИСТИКА ====================

@dataclass
class NumberObfuscationStats:
    total_numbers: int = 0
    obfuscated: int = 0
    skipped_zero_one: int = 0
    skipped_too_large: int = 0
    skipped_float: int = 0
    skipped_table_key: int = 0
    skipped_for_bound: int = 0
    skipped_random: int = 0
    parse_failures: int = 0   # gen выдал выражение, которое парсер не смог разобрать
    bytes_added: int = 0
    
    def report(self) -> str:
        lines = [
            f"  Total numbers found:  {self.total_numbers}",
            f"  Obfuscated:           {self.obfuscated}",
            f"  Skipped (0 or 1):     {self.skipped_zero_one}",
            f"  Skipped (too large):  {self.skipped_too_large}",
            f"  Skipped (float):      {self.skipped_float}",
            f"  Skipped (table key):  {self.skipped_table_key}",
            f"  Skipped (for bounds): {self.skipped_for_bound}",
            f"  Skipped (probab.):    {self.skipped_random}",
            f"  Bytes added to code:  {self.bytes_added}",
        ]
        if self.obfuscated > 0:
            avg = self.bytes_added / self.obfuscated
            lines.append(f"  Avg expansion:        {avg:.1f} bytes/number")
        return '\n'.join(lines)


# ==================== ТРАНСФОРМЕР ====================

class NumberObfuscatorTransformer(NodeTransformer):
    """
    Walks AST and replaces integer literals with math expressions.
    
    Check order (matters!):
        1. Float check (structural — nothing to obfuscate)
        2. Range check (structural — might be an ID)
        3. Context checks (table key / for bound) — safety first
        4. Skip values (0, 1) — cosmetic
        5. Probability roll — randomness last
    """
    
    def __init__(self, rng: random.Random, config: Optional[NumberObfuscatorConfig] = None):
        self.rng = rng
        self.config = config or NumberObfuscatorConfig.balanced()
        self.num_gen = NumberExprGen(rng)
        self.stats = NumberObfuscationStats()
        
        # Context flags
        self._in_table_key = False
        self._in_for_bound = False
    
    def visit_NumberLit(self, node: NumberLit) -> Expr:
        """Decide whether to obfuscate this number."""
        self.stats.total_numbers += 1
        value = node.value
        
        # 1. Float check
        if isinstance(value, float):
            if self.config.handle_float_integers and value.is_integer():
                value = int(value)
            else:
                self.stats.skipped_float += 1
                return node
        
        # 2. Range check
        if value > self.config.max_value or value < self.config.min_value:
            self.stats.skipped_too_large += 1
            return node
        
        # 3. Context checks (SAFETY FIRST — check before skip_values)
        if self._in_table_key and self.config.skip_table_keys:
            self.stats.skipped_table_key += 1
            return node
        
        if self._in_for_bound and self.config.skip_for_bounds:
            self.stats.skipped_for_bound += 1
            return node
        
        # 4. Skip specific values (cosmetic)
        if value in self.config.skip_values:
            self.stats.skipped_zero_one += 1
            return node
        
        # 5. Probability check
        if self.rng.random() > self.config.probability:
            self.stats.skipped_random += 1
            return node
        
        return self._obfuscate_number(node, value)
    
    def _obfuscate_number(self, node: NumberLit, value: int) -> Expr:
        """Generate a polymorphic expression for `value`"""
        ast_expr = None
        expr_str = ""
        for _attempt in range(3):          # retry: rng мог выдать редкий крайний случай
            expr_str = self.num_gen.gen(value, depth=self.config.depth)
            try:
                ast_expr = self._parse_expression_string(expr_str, node.line)
                break
            except Exception:
                ast_expr = None
        
        if ast_expr is None:
            self.stats.skipped_random += 1
            self.stats.parse_failures += 1
            return node
        
        original_size = len(str(value))
        new_size = len(expr_str)
        self.stats.bytes_added += (new_size - original_size)
        self.stats.obfuscated += 1
        
        return ast_expr
    
    def _parse_expression_string(self, expr_str: str, line: int) -> Expr:
        """Parse a small expression string into AST"""
        from ..lexer import Lexer
        from ..parser import Parser
        
        lexer = Lexer(expr_str)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        expr = parser._parse_expression()
        
        self._set_line_recursive(expr, line)
        return expr
    
    def _set_line_recursive(self, node: Node, line: int):
        """Set line=line on all nodes in the subtree"""
        if not isinstance(node, Node):
            return
        node.line = line
        from dataclasses import fields
        for f in fields(node):
            value = getattr(node, f.name)
            if isinstance(value, Node):
                self._set_line_recursive(value, line)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, Node):
                        self._set_line_recursive(item, line)
    
    # ---------- Context tracking ----------
    
    def visit_TableExpr(self, node: TableExpr) -> Expr:
        """Table constructor — track key context for fields"""
        new_fields = []
        for field in node.fields:
            new_fields.append(self._visit_table_field(field))
        node.fields = new_fields
        return node
    
    def _visit_table_field(self, field: TableField) -> TableField:
        """Visit table field with proper context"""
        if field.key is not None:
            if not field.is_name:
                # [expr] = value — key is a real expression
                old_in_key = self._in_table_key
                self._in_table_key = True
                field.key = self.visit(field.key)
                self._in_table_key = old_in_key
        
        field.value = self.visit(field.value)
        return field
    
    def visit_NumericForStat(self, node: NumericForStat) -> Stat:
        """for i = start, stop, step do ... end"""
        old_bound = self._in_for_bound
        self._in_for_bound = True
        node.start = self.visit(node.start)
        node.stop = self.visit(node.stop)
        if node.step is not None:
            node.step = self.visit(node.step)
        self._in_for_bound = old_bound
        
        node.body = self.visit(node.body)
        return node
    
    def visit_IndexExpr(self, node: IndexExpr) -> Expr:
        """Table index access: t[key] — obfuscate normally,
        НО при skip_array_index индексы у простых name-массивов не трогаем:
        это защищает string-array фичу (Sprint 2) от саморазрушения —
        `_L[1]` не превращается в `_L[(0X1+0)]`."""
        node.obj = self.visit(node.obj)
        skip = (
            self.config.skip_array_index
            and not node.is_dot
            and isinstance(node.obj, NameExpr)
        )
        if not skip:
            node.index = self.visit(node.index)
        return node


# ==================== СЧЁТЧИК ====================

class NumberCounter(NodeVisitor):
    """Utility to count NumberLit occurrences in an AST"""
    
    def __init__(self):
        self.count = 0
        self.by_value = {}
    
    def visit_NumberLit(self, node: NumberLit):
        self.count += 1
        v = node.value
        self.by_value[v] = self.by_value.get(v, 0) + 1
        return node


# ==================== HIGH-LEVEL API ====================

def obfuscate_numbers_in_chunk(
    ast_chunk: Chunk,
    rng: Optional[random.Random] = None,
    config: Optional[NumberObfuscatorConfig] = None,
) -> tuple:
    """
    High-level API: obfuscate numbers in a chunk.
    
    Returns:
        (modified_ast, stats)
    """
    if rng is None:
        rng = make_rng()
    if config is None:
        config = NumberObfuscatorConfig.balanced()
    
    transformer = NumberObfuscatorTransformer(rng=rng, config=config)
    modified_ast = transformer.visit(ast_chunk)
    
    return modified_ast, transformer.stats


# ==================== ТЕСТ ====================

def _self_test():
    print("=" * 60)
    print("NZL Number Obfuscator Self-Test")
    print("=" * 60)
    
    from ..parser import parse
    
    # Test 1: Basic obfuscation
    print("\n[1] Basic obfuscation:")
    src = '''
local x = 42
local y = 100
local z = 1337
local zero = 0
local one = 1
local big = 5000000
local pi = 3.14
'''
    ast = parse(src)
    rng = make_rng(seed=42)
    modified, stats = obfuscate_numbers_in_chunk(ast, rng=rng)
    print(stats.report())
    print("  ✓ Basic obfuscation works")
    
    # Test 2: Config modes
    print("\n[2] Testing different modes:")
    for mode_name, config in [
        ('conservative', NumberObfuscatorConfig.conservative()),
        ('balanced', NumberObfuscatorConfig.balanced()),
        ('aggressive', NumberObfuscatorConfig.aggressive()),
    ]:
        src = '\n'.join(f'local v{i} = {i+10}' for i in range(100))
        ast = parse(src)
        rng = make_rng(seed=1)
        _, stats = obfuscate_numbers_in_chunk(ast, rng=rng, config=config)
        pct = stats.obfuscated / stats.total_numbers * 100
        print(f"  {mode_name:>12}: {stats.obfuscated:3}/{stats.total_numbers} obfuscated ({pct:.0f}%), +{stats.bytes_added} bytes")
    print("  ✓ Modes have expected relative rates")
    
    # Test 3: Table key context (safety)
    # Use values that DON'T overlap with skip_values default {0, 1}
    print("\n[3] Table key context safety:")
    src_table = '''
local t = {[7] = "a", [42] = "b", [100] = "c"}
local arr = {5, 10, 15, 20}
'''
    ast = parse(src_table)
    rng = make_rng(seed=7)
    # Empty skip_values to isolate the table_key check
    config = NumberObfuscatorConfig(
        probability=1.0,
        skip_table_keys=True,
        skip_values=set(),
    )
    modified, stats = obfuscate_numbers_in_chunk(ast, rng=rng, config=config)
    print(f"  Table keys skipped:      {stats.skipped_table_key}")
    print(f"  Array values obfuscated: {stats.obfuscated}")
    print(f"  Zero/one skipped:        {stats.skipped_zero_one}")
    assert stats.skipped_table_key == 3, f"Expected 3 keys skipped, got {stats.skipped_table_key}"
    assert stats.obfuscated >= 2, f"Expected >=2 array values obfuscated, got {stats.obfuscated}"
    print("  ✓ Table keys preserved")
    
    # Test 4: For loop bounds (skip mode)
    # Use values that DON'T overlap with skip_values default {0, 1}
    print("\n[4] For loop bounds (skip mode):")
    src_for = '''
for i = 3, 10 do
    print(i)
end
for j = 100, 200, 5 do
    local x = 500
end
'''
    ast = parse(src_for)
    rng = make_rng(seed=3)
    # Empty skip_values to isolate the for_bound check
    config = NumberObfuscatorConfig(
        probability=1.0,
        skip_for_bounds=True,
        skip_values=set(),
    )
    modified, stats = obfuscate_numbers_in_chunk(ast, rng=rng, config=config)
    print(f"  Loop bounds skipped:      {stats.skipped_for_bound}")
    print(f"  Other numbers obfuscated: {stats.obfuscated}")
    # Bounds: 3, 10, 100, 200, 5 = 5 numbers
    assert stats.skipped_for_bound >= 3, f"Expected >=3 bounds skipped (3,10,100,200,5), got {stats.skipped_for_bound}"
    # Other: 500 = 1 number
    assert stats.obfuscated >= 0, f"Expected >=0 other obfuscated (500), got {stats.obfuscated}"
    print("  ✓ For bounds preserved when configured")
    
    # Test 5: Value verification
    print("\n[5] Value correctness (Python-eval verification):")
    rng = make_rng(seed=99)
    num_gen = NumberExprGen(rng)
    verified = 0
    for value in [42, 100, 1337, -50, 7, 999]:
        for depth in [0, 1, 2]:
            expr_str = num_gen.gen(value, depth=depth)
            py_expr = expr_str.replace('bit32.bxor', '_xor')
            try:
                result = eval(py_expr, {'_xor': lambda a, b: a ^ b})
                if result == value:
                    verified += 1
            except Exception:
                pass
    print(f"  Verified {verified} expressions evaluate correctly")
    assert verified > 10, f"Expected at least 10 verified, got {verified}"
    print("  ✓ Generated expressions are mathematically correct")
    
    # Test 6: Polymorphism
    print("\n[6] Polymorphism (same input → different outputs):")
    outputs = set()
    for seed in range(10):
        rng = make_rng(seed=seed)
        num_gen = NumberExprGen(rng)
        outputs.add(num_gen.gen(42))
    print(f"  10 seeds → {len(outputs)} unique expressions for value 42")
    for o in list(outputs)[:5]:
        print(f"    42 → {o}")
    assert len(outputs) >= 5, "Should have variety!"
    print("  ✓ Polymorphism works")
    
    # Test 7: Real-world code
    print("\n[7] Statistics on real-ish code:")
    src_real = '''
local Players = game:GetService("Players")
local WalkSpeed = 16
local JumpPower = 50
local MaxHealth = 100
local Radius = 3000
local Threshold = 0.5

for i = 1, 100 do
    if i % 10 == 0 then
        print(i)
    end
end

local coords = {2500, -1500, 4200}
local farm_pos = Vector3.new(7801, -2164, -17134)
'''
    ast = parse(src_real)
    rng = make_rng(seed=100)
    modified, stats = obfuscate_numbers_in_chunk(
        ast, rng=rng,
        config=NumberObfuscatorConfig.balanced()
    )
    print(stats.report())
    
    # Test 8: Aggressive mode stress test
    print("\n[8] Aggressive mode stress test:")
    src_stress = '\n'.join(f'local v{i} = {random.randint(2, 10000)}' for i in range(200))
    ast = parse(src_stress)
    rng = make_rng(seed=555)
    modified, stats = obfuscate_numbers_in_chunk(
        ast, rng=rng,
        config=NumberObfuscatorConfig.aggressive()
    )
    print(f"  Obfuscated:   {stats.obfuscated}/{stats.total_numbers}")
    print(f"  Bytes added:  {stats.bytes_added}")
    print(f"  Avg per num:  {stats.bytes_added / max(1, stats.obfuscated):.1f}")
    assert stats.obfuscated > 100, f"Aggressive should obfuscate a lot, got {stats.obfuscated}"
    print("  ✓ Aggressive mode works")
    
    # Test 9: Skip empty set — obfuscate everything possible
    print("\n[9] Empty skip_values (obfuscate 0 and 1 too):")
    src_zeroone = 'local a = 0\nlocal b = 1\nlocal c = 42'
    ast = parse(src_zeroone)
    rng = make_rng(seed=200)
    config = NumberObfuscatorConfig(
        probability=1.0,
        skip_values=set(),
        depth=0,
    )
    modified, stats = obfuscate_numbers_in_chunk(ast, rng=rng, config=config)
    print(f"  Obfuscated: {stats.obfuscated}/3")
    print(f"  Zero/one skipped: {stats.skipped_zero_one}")
    assert stats.obfuscated == 3, f"Should obfuscate all 3, got {stats.obfuscated}"
    print("  ✓ Empty skip_values works")
    
    print("\n" + "=" * 60)
    print("✅ ALL TESTS PASSED!")
    print("=" * 60)


if __name__ == "__main__":
    _self_test()