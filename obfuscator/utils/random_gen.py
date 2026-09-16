"""
NZL Studio Obfuscator - Polymorphic Random Generator v2.1

v2.1 FIXES:
    - _rrotate/_lrotate: n is always small int (was breaking under nesting)
    - _lshift: proper trailing zeros detection
    - Depth 2+ safe (no more math errors)
"""

import random
import string
import struct
from typing import List, Optional, Set, Any, Callable


CONFUSING_CHARS = 'IlIl1O0oO'
IDENT_START_CHARS = string.ascii_letters + '_'
IDENT_BODY_CHARS = string.ascii_letters + string.digits + '_'

LUA_RESERVED = {
    'and', 'break', 'do', 'else', 'elseif', 'end', 'false', 'for',
    'function', 'goto', 'if', 'in', 'local', 'nil', 'not', 'or',
    'repeat', 'return', 'then', 'true', 'until', 'while',
    'continue', 'export', 'type', 'typeof',
}


class NameGenerator:
    def __init__(self, rng: Optional[random.Random] = None, style: str = 'mixed'):
        self.rng = rng or random.Random()
        self.style = style
        self.used_names: Set[str] = set()
    
    def reset(self):
        self.used_names.clear()
    
    def reserve(self, name: str):
        self.used_names.add(name)
    
    def reserve_many(self, names):
        self.used_names.update(names)
    
    def generate(self, min_length: int = 8, max_length: int = 16) -> str:
        style = self.style
        if style == 'mixed':
            style = self.rng.choice(['confusing', 'hex', 'underscore'])
        
        for _ in range(100):
            length = self.rng.randint(min_length, max_length)
            if style == 'confusing':
                name = self._gen_confusing(length)
            elif style == 'hex':
                name = self._gen_hex(length)
            elif style == 'underscore':
                name = self._gen_underscore(length)
            else:
                name = self._gen_confusing(length)
            if name not in self.used_names and name not in LUA_RESERVED:
                self.used_names.add(name)
                return name
        
        counter = len(self.used_names)
        name = f"_nzl_{counter:x}"
        while name in self.used_names:
            counter += 1
            name = f"_nzl_{counter:x}"
        self.used_names.add(name)
        return name
    
    def _gen_confusing(self, length: int) -> str:
        first = self.rng.choice(['_', 'I', 'l'])
        rest = ''.join(self.rng.choice(CONFUSING_CHARS) for _ in range(length - 1))
        return first + rest
    
    def _gen_hex(self, length: int) -> str:
        hex_len = self.rng.randint(3, 5)
        hex_val = ''.join(self.rng.choice('0123456789ABCDEF') for _ in range(hex_len))
        tail_len = max(4, length - hex_len - 3)
        tail = ''.join(self.rng.choice(CONFUSING_CHARS) for _ in range(tail_len))
        return f"_0x{hex_val}_{tail}"
    
    def _gen_underscore(self, length: int) -> str:
        result = ['_']
        for _ in range(length - 1):
            if self.rng.random() < 0.4:
                result.append('_')
            else:
                result.append(self.rng.choice('0123456789'))
        return ''.join(result)


def make_rng(seed: Optional[int] = None) -> random.Random:
    if seed is None:
        rng = random.Random()
        rng.seed()
    else:
        rng = random.Random(seed)
    return rng


def gen_build_id(rng: random.Random) -> str:
    return ''.join(rng.choice('0123456789abcdef') for _ in range(8))


def weighted_choice(rng: random.Random, choices):
    if not choices:
        raise ValueError("weighted_choice: empty choices")
    total = sum(w for _, w in choices)
    if total <= 0:
        raise ValueError("weighted_choice: total weight must be positive")
    r = rng.uniform(0, total)
    upto = 0
    for item, weight in choices:
        upto += weight
        if r <= upto:
            return item
    return choices[-1][0]


# ==================== NUMBER EXPRESSIONS v2.1 ====================

_MASK32 = 0xFFFFFFFF


class NumberExprGen:
    """
    v2.1 — Luraph-level polymorphic number expressions.
    
    IMPORTANT: rotate/shift counts (n) are ALWAYS plain integers,
    never recursive expressions, otherwise Lua evaluates them
    with the wrong precedence/type.
    """
    
    def __init__(self, rng: random.Random):
        self.rng = rng
    
    def gen(self, value, depth: int = 0) -> str:
        if not isinstance(value, int):
            return str(value)
        if abs(value) > 0xFFFFFFFF:
            return str(value)
        
        methods = [
            # Arithmetic (30%)
            ('addition', 12),
            ('subtraction', 10),
            ('multiplication', 5),
            ('unary_minus', 3),
            # Literals (15%)
            ('hex_literal', 8),
            ('binary_literal', 7),
            # bit32 magic (55%)
            ('bxor', 12),
            ('rrotate', 10),
            ('lrotate', 8),
            ('lshift', 6),
            ('rshift', 6),
            ('band', 5),
            ('bor', 5),
            ('bnot', 3),
        ]
        
        method = weighted_choice(self.rng, methods)
        
        try:
            if method == 'addition':
                return self._addition(value, depth)
            elif method == 'subtraction':
                return self._subtraction(value, depth)
            elif method == 'multiplication':
                return self._multiplication(value, depth)
            elif method == 'unary_minus':
                return self._unary_minus(value, depth)
            elif method == 'hex_literal':
                return self._hex_literal(value)
            elif method == 'binary_literal':
                return self._binary_literal(value)
            elif method == 'bxor':
                return self._bxor(value, depth)
            elif method == 'rrotate':
                return self._rrotate(value, depth)
            elif method == 'lrotate':
                return self._lrotate(value, depth)
            elif method == 'lshift':
                return self._lshift(value, depth)
            elif method == 'rshift':
                return self._rshift(value, depth)
            elif method == 'band':
                return self._band(value, depth)
            elif method == 'bor':
                return self._bor(value, depth)
            elif method == 'bnot':
                return self._bnot(value)
        except Exception:
            return str(value)
        return str(value)
    
    def _fmt_int(self, n: int) -> str:
        """Random hex/binary/decimal format for polymorphism"""
        if n < 0 or n > _MASK32:
            return str(n)
        r = self.rng.random()
        if r < 0.40:
            return f"0X{n:X}"
        elif r < 0.65:
            bits = max(4, n.bit_length())
            if bits > 32:
                return f"0X{n:X}"
            return f"0B{n:0{bits}b}"
        else:
            return str(n)
    
    def _sub(self, value: int, depth: int) -> str:
        """Recursive sub-expression at reduced depth"""
        if depth > 0:
            return self.gen(value, depth - 1)
        return self._fmt_int(value) if value >= 0 else f"({value})"
    
    # ---------- Arithmetic ----------
    
    def _addition(self, value: int, depth: int) -> str:
        a = self.rng.randint(-abs(value) - 100, abs(value) + 100)
        b = value - a
        a_str = self._sub(a, depth)
        b_str = self._sub(b, depth) if b >= 0 else f"({b})"
        return f"({a_str}+{b_str})"
    
    def _subtraction(self, value: int, depth: int) -> str:
        offset = self.rng.randint(1, 1000)
        a = value + offset
        b = offset
        return f"({self._sub(a, depth)}-{self._sub(b, depth)})"
    
    def _multiplication(self, value: int, depth: int) -> str:
        if value == 0:
            return f"(0*{self.rng.randint(1, 100)})"
        small_divisors = [d for d in range(2, min(20, abs(value) + 1)) if value % d == 0]
        if not small_divisors:
            return self._addition(value, depth)
        divisor = self.rng.choice(small_divisors)
        other = value // divisor
        return f"({divisor}*{self._sub(other, depth)})"
    
    def _unary_minus(self, value: int, depth: int) -> str:
        return f"(-{self._sub(-value, depth)})"
    
    # ---------- Pure literals ----------
    
    def _hex_literal(self, value: int) -> str:
        if value < 0:
            return f"(-0X{abs(value):X})"
        return f"0X{value:X}"
    
    def _binary_literal(self, value: int) -> str:
        if value < 0:
            return f"(-0B{abs(value):b})"
        bits = max(4, value.bit_length())
        if bits > 32:
            return f"0X{value:X}"
        return f"0B{value:0{bits}b}"
    
    # ---------- bit32 magic ----------
    
    def _bxor(self, value: int, depth: int) -> str:
        if value < 0 or value > _MASK32:
            return self._addition(value, depth)
        k = self.rng.randint(1, 0xFFFF)
        x = (value ^ k) & _MASK32
        return f"bit32.bxor({self._sub(x, depth)},{self._sub(k, depth)})"
    
    def _rrotate(self, value: int, depth: int) -> str:
        """rrotate(x, n) rotates right by n. To get value: x = lrotate(value, n)"""
        if value < 0 or value > _MASK32:
            return self._addition(value, depth)
        n = self.rng.randint(1, 15)
        v32 = value & _MASK32
        x = ((v32 << n) | (v32 >> (32 - n))) & _MASK32
        # FIX v2.1: n is ALWAYS plain int, never recursive!
        return f"bit32.rrotate({self._sub(x, depth)},{n})"
    
    def _lrotate(self, value: int, depth: int) -> str:
        if value < 0 or value > _MASK32:
            return self._addition(value, depth)
        n = self.rng.randint(1, 15)
        v32 = value & _MASK32
        x = ((v32 >> n) | (v32 << (32 - n))) & _MASK32
        return f"bit32.lrotate({self._sub(x, depth)},{n})"
    
    def _lshift(self, value: int, depth: int) -> str:
        """value = bit32.lshift(x, n) — needs trailing zeros"""
        if value <= 0 or value > _MASK32:
            return self._bxor(value, depth) if value >= 0 else self._addition(value, depth)
        # Count trailing zeros
        tz = 0
        v = value
        while v > 0 and (v & 1) == 0 and tz < 8:
            v >>= 1
            tz += 1
        if tz == 0:
            return self._bxor(value, depth)
        n = self.rng.randint(1, tz)
        x = value >> n
        # FIX v2.1: n is plain int
        return f"bit32.lshift({self._sub(x, depth)},{n})"
    
    def _rshift(self, value: int, depth: int) -> str:
        if value < 0 or value > _MASK32:
            return self._addition(value, depth)
        n = self.rng.randint(1, 4)
        x = (value << n) & _MASK32
        noise = self.rng.randint(0, (1 << n) - 1) if n > 0 else 0
        x = x | noise
        # FIX v2.1: n is plain int
        return f"bit32.rshift({self._sub(x, depth)},{n})"
    
    def _band(self, value: int, depth: int) -> str:
        if value < 0 or value > _MASK32:
            return self._addition(value, depth)
        extra = self.rng.randint(0, 0xFF)
        mask = value | extra
        noise = self.rng.randint(0, _MASK32) & (~mask & _MASK32)
        x = value | noise
        return f"bit32.band({self._sub(x, depth)},{self._sub(mask, depth)})"
    
    def _bor(self, value: int, depth: int) -> str:
        if value < 0 or value > _MASK32:
            return self._addition(value, depth)
        split_mask = self.rng.randint(0, _MASK32)
        a = value & split_mask
        b = value & (~split_mask & _MASK32)
        return f"bit32.bor({self._sub(a, depth)},{self._sub(b, depth)})"
    
    def _bnot(self, value: int) -> str:
        if value < 0 or value > _MASK32:
            return str(value)
        x = (~value) & _MASK32
        return f"bit32.bnot(0X{x:X})"


# ==================== STRINGS ====================

class StringExprGen:
    def __init__(self, rng: random.Random):
        self.rng = rng
    
    def split_string(self, s: str, min_parts: int = 2, max_parts: int = 4) -> List[str]:
        if len(s) < min_parts:
            return [s]
        num_parts = self.rng.randint(min_parts, min(max_parts, len(s)))
        splits = sorted(self.rng.sample(range(1, len(s)), num_parts - 1))
        parts = []
        prev = 0
        for split in splits:
            parts.append(s[prev:split])
            prev = split
        parts.append(s[prev:])
        return parts


# ==================== BOOLEANS ====================

class BoolExprGen:
    def __init__(self, rng: random.Random):
        self.rng = rng
    
    def gen_true(self) -> str:
        options = ['true', '(1==1)', '(0==0)', '(1~=0)', 'not false', '(1==1)']
        return self.rng.choice(options)
    
    def gen_false(self) -> str:
        options = ['false', '(1==0)', '(0==1)', '(1~=1)', 'not true']
        return self.rng.choice(options)


# ==================== JUNK CODE ====================

class JunkGen:
    def __init__(self, rng: random.Random, name_gen: NameGenerator):
        self.rng = rng
        self.name_gen = name_gen
        self.num_gen = NumberExprGen(rng)
        self.bool_gen = BoolExprGen(rng)
    
    def gen_statement(self) -> str:
        options = [
            ('dead_local', 25),
            ('dead_if', 20),
            ('dead_loop', 15),
            ('dead_function', 15),
            ('dead_table', 15),
            ('nested_paren', 10),
        ]
        method = weighted_choice(self.rng, options)
        try:
            if method == 'dead_local':
                return self._dead_local()
            elif method == 'dead_if':
                return self._dead_if()
            elif method == 'dead_loop':
                return self._dead_loop()
            elif method == 'dead_function':
                return self._dead_function()
            elif method == 'dead_table':
                return self._dead_table()
            elif method == 'nested_paren':
                return self._nested_paren()
        except Exception:
            return f"local {self.name_gen.generate()} = {self.rng.randint(1, 999)};"
        return ""
    
    def _dead_local(self) -> str:
        name = self.name_gen.generate()
        val = self.num_gen.gen(self.rng.randint(1, 99999))
        return f"local {name}={val};"
    
    def _dead_if(self) -> str:
        cond = self.bool_gen.gen_false()
        name = self.name_gen.generate()
        return f"if {cond} then local {name}={self.rng.randint(1, 999)} end;"
    
    def _dead_loop(self) -> str:
        var = self.name_gen.generate()
        return f"for {var}=1,0 do break end;"
    
    def _dead_function(self) -> str:
        name = self.name_gen.generate()
        val = self.rng.randint(1, 999)
        return f"local {name}=function() return {val} end;"
    
    def _dead_table(self) -> str:
        name = self.name_gen.generate()
        vals = [str(self.rng.randint(1, 99)) for _ in range(self.rng.randint(2, 5))]
        return f"local {name}={{{','.join(vals)}}};"
    
    def _nested_paren(self) -> str:
        name = self.name_gen.generate()
        depth = self.rng.randint(3, 6)
        val = self.rng.randint(1, 999)
        return f"local {name}={'(' * depth}{val}{')' * depth};"


def shuffle_list(rng: random.Random, lst: list) -> list:
    result = lst.copy()
    rng.shuffle(result)
    return result


def random_permutation(rng: random.Random, n: int) -> List[int]:
    result = list(range(n))
    rng.shuffle(result)
    return result


# ==================== SELF-TEST ====================

def _self_test():
    print("=" * 60)
    print("NZL Random Generator v2.1 Self-Test")
    print("=" * 60)
    
    print("\n[1] NameGenerator (all styles):")
    for style in ['confusing', 'hex', 'underscore', 'mixed']:
        gen = NameGenerator(style=style)
        names = [gen.generate() for _ in range(3)]
        assert len(set(names)) == 3
        print(f"  {style:12}: {names}")
    print("  [OK]")
    
    print("\n[2] Uniqueness stress (1000 names):")
    gen = NameGenerator()
    names = set(gen.generate() for _ in range(1000))
    assert len(names) == 1000
    print(f"  [OK] 1000/1000 unique")
    
    print("\n[3] Seeded reproducibility:")
    names1 = [NameGenerator(rng=make_rng(seed=42)).generate() for _ in range(3)]
    names2 = [NameGenerator(rng=make_rng(seed=42)).generate() for _ in range(3)]
    assert names1 == names2
    print("  [OK]")
    
    print("\n[5] NumberExprGen v2.1 showcase:")
    rng = make_rng(seed=42)
    num_gen = NumberExprGen(rng)
    for val in [0, 1, 42, 100, 1337, 65536, -50, 255, 0xDEAD]:
        expr = num_gen.gen(val)
        print(f"  {val:>7} -> {expr}")
    
    print("\n[6] NumberExprGen depth=2 nesting:")
    for val in [42, 1337]:
        for _ in range(3):
            expr = num_gen.gen(val, depth=2)
            print(f"  {val} -> {expr}")
    
    print("\n[7] MATH CORRECTNESS (this is the important one!):")
    _env = {
        '_bxor': lambda a, b: (int(a) ^ int(b)) & _MASK32,
        '_band': lambda a, b: (int(a) & int(b)) & _MASK32,
        '_bor':  lambda a, b: (int(a) | int(b)) & _MASK32,
        '_bnot': lambda a: (~int(a)) & _MASK32,
        '_rrotate': lambda x, n: (((int(x) & _MASK32) >> int(n)) | ((int(x) & _MASK32) << (32 - int(n)))) & _MASK32,
        '_lrotate': lambda x, n: (((int(x) & _MASK32) << int(n)) | ((int(x) & _MASK32) >> (32 - int(n)))) & _MASK32,
        '_lshift':  lambda x, n: (int(x) << int(n)) & _MASK32,
        '_rshift':  lambda x, n: (int(x) & _MASK32) >> int(n),
    }
    
    def _lua_to_py(expr: str) -> str:
        e = expr
        e = e.replace('bit32.bxor', '_bxor')
        e = e.replace('bit32.band', '_band')
        e = e.replace('bit32.bor', '_bor')
        e = e.replace('bit32.bnot', '_bnot')
        e = e.replace('bit32.rrotate', '_rrotate')
        e = e.replace('bit32.lrotate', '_lrotate')
        e = e.replace('bit32.lshift', '_lshift')
        e = e.replace('bit32.rshift', '_rshift')
        return e
    
    verified = 0
    failed = []
    total = 0
    for seed in range(50):
        rng = make_rng(seed=seed)
        ng = NumberExprGen(rng)
        for val in [42, 100, 255, 0xDEAD, 1337, 7, 0, 1, 65535]:
            for depth in [0, 1, 2, 3]:
                total += 1
                expr = ng.gen(val, depth=depth)
                try:
                    py = _lua_to_py(expr)
                    result = eval(py, _env)
                    expected = (val & _MASK32) if val >= 0 else val
                    if result == expected:
                        verified += 1
                    else:
                        failed.append((val, expr, result, expected))
                except Exception as e:
                    failed.append((val, expr, str(e), None))
    
    print(f"  Total tested: {total}")
    print(f"  Verified:     {verified}")
    print(f"  Failed:       {len(failed)}")
    if failed[:5]:
        print(f"  First 5 failures:")
        for v, e, r, exp in failed[:5]:
            print(f"    val={v}: expr={e[:80]}")
            print(f"      -> got {r}, expected {exp}")
    accuracy = verified / total * 100
    print(f"  Accuracy: {accuracy:.2f}%")
    assert accuracy >= 99.0, f"Expected 99%+ accuracy, got {accuracy:.2f}%"
    print("  [OK] Math correctness verified (99%+)")
    
    print("\n[8] Polymorphism (30 seeds -> unique outputs for 42):")
    outputs = set()
    for seed in range(30):
        rng = make_rng(seed=seed)
        outputs.add(NumberExprGen(rng).gen(42))
    print(f"  Unique: {len(outputs)}")
    for o in list(outputs)[:6]:
        print(f"    42 -> {o}")
    assert len(outputs) >= 15
    print("  [OK]")
    
    print("\n[9] Method diversity (200 samples of 0xABCD):")
    from collections import Counter
    hits = Counter()
    for seed in range(200):
        expr = NumberExprGen(make_rng(seed=seed)).gen(0xABCD)
        for m in ['rrotate', 'lrotate', 'lshift', 'rshift', 'bxor', 'band', 'bor', 'bnot']:
            if f'bit32.{m}' in expr:
                hits[m] += 1
                break
        else:
            if expr.startswith('0B'):
                hits['binary'] += 1
            elif expr.startswith('0X'):
                hits['hex'] += 1
            else:
                hits['arithmetic'] += 1
    for method, count in hits.most_common():
        pct = count / 200 * 100
        print(f"  {method:12} : {count:3} ({pct:.0f}%)")
    print("  [OK]")
    
    print("\n[10] BoolExprGen:")
    rng = make_rng()
    bool_gen = BoolExprGen(rng)
    for _ in range(3):
        print(f"  true  -> {bool_gen.gen_true()}")
        print(f"  false -> {bool_gen.gen_false()}")
    
    print("\n[11] StringExprGen:")
    parts = StringExprGen(rng).split_string("Hello, World!", 3, 5)
    assert ''.join(parts) == "Hello, World!"
    print(f"  Split OK: {parts}")
    
    print("\n[12] Weighted choice:")
    counts = {'common': 0, 'rare': 0, 'epic': 0}
    for _ in range(10000):
        r = weighted_choice(rng, [('common', 70), ('rare', 25), ('epic', 5)])
        counts[r] += 1
    print(f"  {counts}")
    assert counts['common'] > counts['rare'] > counts['epic']
    
    print("\n[13] JunkGen samples:")
    junk_gen = JunkGen(rng, NameGenerator())
    for _ in range(3):
        print(f"  {junk_gen.gen_statement()}")
    
    print("\n[14] Build IDs:")
    for _ in range(3):
        print(f"  -> {gen_build_id(make_rng())}")
    
    print("\n" + "=" * 60)
    print("[OK] ALL TESTS PASSED!")
    print("=" * 60)


if __name__ == "__main__":
    _self_test()