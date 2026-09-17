"""
NZL Deobfuscator - Constant Folding
====================================
Свёртка константных выражений на этапе AST.

Примеры:
    2 + 3                  ->  5
    2 + 3 * 4              ->  14
    "hello" .. " world"    ->  "hello world"
    -(-42)                 ->  42
    not false              ->  true
    not not x              ->  x           (упрощение)
    #"hello"               ->  5

ЗАЧЕМ: Обфускаторы разбивают одну константу на 5-10 арифметических операций.
Свернём — код станет читаемым, а sandbox_decoder сможет найти паттерны
типа bit32.bxor(byte, 42) вместо bit32.bxor(byte, (1+2)*7*3-21+42-42).
"""

import math
from obfuscator.deobfuscator.core.base import (
    NumberLit, StringLit, BoolLit, NilLit,
    BinaryOp, UnaryOp, ParenExpr,
    is_literal, get_literal_value, make_literal,
)
from .base_decoder import BaseDecoder


# Безопасные операции над Python-значениями
def _safe_add(a, b):    return a + b
def _safe_sub(a, b):    return a - b
def _safe_mul(a, b):    return a * b
def _safe_div(a, b):    return a / b if b != 0 else None   # /0 в Lua = inf, но лучше не трогать
def _safe_fdiv(a, b):   return math.floor(a / b) if b != 0 else None
def _safe_mod(a, b):    return a - math.floor(a / b) * b if b != 0 else None
def _safe_pow(a, b):    return a ** b
def _safe_concat(a, b): return str(a) + str(b)


class ConstantFoldDecoder(BaseDecoder):
    """
    Сворачивает арифметику/строки/логику где все операнды — литералы.
    
    Обходит АST снизу-вверх (generic_visit до логики) — так вложенные
    выражения сворачиваются до внешних.
    """
    
    NAME = "constant fold"
    
    # ==================== BINARY ====================
    
    def visit_BinaryOp(self, node):
        # Сначала свёртка детей (bottom-up!)
        node = self.generic_visit(node)
        
        left = node.left
        right = node.right
        op = node.op
        
        # Оба должны быть литералами (не nil для арифметики)
        if not (is_literal(left) and is_literal(right)):
            return node
        
        lv = get_literal_value(left)
        rv = get_literal_value(right)
        
        self.stats.scanned += 1
        
        try:
            result = self._fold_binary(op, lv, rv)
        except Exception as e:
            self.stats.errors += 1
            self.stats.details.append(f"binary {op}: {e}")
            return node
        
        if result is None:
            return node   # операция не свернулась
        
        new = make_literal(result, line=node.line)
        self.stats.replaced += 1
        self.stats.details.append(f"{lv!r} {op} {rv!r} -> {result!r}")
        return new
    
    def _fold_binary(self, op, lv, rv):
        # Арифметика — числа
        arith = {
            '+': _safe_add, '-': _safe_sub, '*': _safe_mul,
            '/': _safe_div, '//': _safe_fdiv, '%': _safe_mod, '^': _safe_pow,
        }
        if op in arith:
            if not isinstance(lv, (int, float)) or not isinstance(rv, (int, float)):
                return None
            if isinstance(lv, bool) or isinstance(rv, bool):
                return None  # bool в Lua ≠ число!
            r = arith[op](lv, rv)
            if r is None:
                return None
            # Оставляем int если результат целый
            if isinstance(r, float) and r.is_integer() and abs(r) < 2**53:
                r = int(r)
            return r
        
        # Конкатенация
        if op == '..':
            if isinstance(lv, bool) or isinstance(rv, bool):
                return None
            if isinstance(lv, (int, float, str)) and isinstance(rv, (int, float, str)):
                return _safe_concat(lv, rv)
            return None
        
        # Сравнения (только числа/строки одного типа)
        cmp_ops = {'<', '>', '<=', '>=', '==', '~='}
        if op in cmp_ops:
            if op == '==':
                return lv == rv
            if op == '~=':
                return lv != rv
            # <, >, <=, >= — только одинаковые типы
            if type(lv) != type(rv):
                return None
            if isinstance(lv, bool):
                return None
            if op == '<':  return lv < rv
            if op == '>':  return lv > rv
            if op == '<=': return lv <= rv
            if op == '>=': return lv >= rv
        
        # Логика — короткое замыкание
        if op == 'and':
            # Lua: falsy = nil/false; иначе truthy
            l_falsy = (lv is None) or (lv is False)
            return rv if not l_falsy else lv
        if op == 'or':
            l_falsy = (lv is None) or (lv is False)
            return lv if not l_falsy else rv
        
        return None
    
    # ==================== UNARY ====================
    
    def visit_UnaryOp(self, node):
        node = self.generic_visit(node)
        
        op = node.op
        operand = node.operand
        
        # not — работает с любым значением
        if op == 'not':
            self.stats.scanned += 1
            if is_literal(operand):
                v = get_literal_value(operand)
                is_falsy = (v is None) or (v is False)
                self.stats.replaced += 1
                self.stats.details.append(f"not {v!r} -> {is_falsy}")
                return make_literal(is_falsy, line=node.line)
            # not not X -> X (упрощение двойного not)
            if isinstance(operand, UnaryOp) and operand.op == 'not':
                # только если X — литерал или Name (безопасно)
                inner = operand.operand
                if is_literal(inner):
                    v = get_literal_value(inner)
                    is_truthy = not ((v is None) or (v is False))
                    self.stats.replaced += 1
                    self.stats.details.append(f"not not {v!r} -> {is_truthy}")
                    return make_literal(is_truthy, line=node.line)
            return node
        
        # - (unary minus)
        if op == '-':
            self.stats.scanned += 1
            if isinstance(operand, NumberLit):
                self.stats.replaced += 1
                new_v = -operand.value
                self.stats.details.append(f"-{operand.value} -> {new_v}")
                return NumberLit(line=node.line, value=new_v)
            # -(-x) -> x  (только для литералов)
            if isinstance(operand, UnaryOp) and operand.op == '-':
                inner = operand.operand
                if isinstance(inner, NumberLit):
                    self.stats.replaced += 1
                    self.stats.details.append(f"-(-{inner.value}) -> {inner.value}")
                    return NumberLit(line=node.line, value=inner.value)
            return node
        
        # # (length)
        if op == '#':
            self.stats.scanned += 1
            if isinstance(operand, StringLit):
                self.stats.replaced += 1
                l = len(operand.value)
                self.stats.details.append(f"#{operand.value!r} -> {l}")
                return NumberLit(line=node.line, value=l)
            return node
        
        # ~ (bnot) — в Lua 5.3+, реже в Luau. Оставляем как есть.
        return node
    
    # ==================== PAREN ====================
    
    def visit_ParenExpr(self, node):
        node = self.generic_visit(node)
        # Убираем лишние скобки вокруг литералов: (5) -> 5
        if is_literal(node.inner):
            self.stats.scanned += 1
            self.stats.replaced += 1
            return node.inner
        return node


# ============================================================
# ТЕСТЫ
# ============================================================

if __name__ == "__main__":
    from obfuscator.deobfuscator.core.base import parse_code, ast_to_code
    
    print("=== Тест ConstantFoldDecoder ===\n")
    passed = failed = 0
    def test(name, cond, extra=""):
        global passed, failed
        if cond: print(f"  [OK] {name}"); passed += 1
        else:    print(f"  [XX] {name} {extra}"); failed += 1
    
    def run_fold(src):
        ast = parse_code(src)
        return ConstantFoldDecoder().run(ast)
    
    # ==================== Арифметика ====================
    new_ast, s = run_fold("local x = 2 + 3")
    out = ast_to_code(new_ast)
    test("2+3 -> 5", "= 5" in out, out)
    
    new_ast, s = run_fold("local x = 2 + 3 * 4")
    test("2+3*4 -> 14", "= 14" in ast_to_code(new_ast))
    
    new_ast, s = run_fold("local x = (1+2)*7*3-21+42-42")
    out = ast_to_code(new_ast)
    test("сложная арифметика -> 42", "= 42" in out, out)
    
    new_ast, s = run_fold("local x = 10 / 2")
    test("10/2 -> 5", "= 5" in ast_to_code(new_ast))
    
    new_ast, s = run_fold("local x = 2 ^ 10")
    test("2^10 -> 1024", "= 1024" in ast_to_code(new_ast))
    
    new_ast, s = run_fold("local x = 17 % 5")
    test("17%5 -> 2", "= 2" in ast_to_code(new_ast))
    
    # ==================== Строки ====================
    new_ast, s = run_fold('local x = "hello" .. " " .. "world"')
    out = ast_to_code(new_ast)
    test('"hello".." ".."world" -> "hello world"', "hello world" in out, out)
    
    new_ast, s = run_fold('local x = "a" .. 1 .. "b"')
    out = ast_to_code(new_ast)
    test('"a"..1.."b" -> "a1b"', "a1b" in out, out)
    
    new_ast, s = run_fold('local x = #"hello"')
    test('#"hello" -> 5', "= 5" in ast_to_code(new_ast))
    
    # ==================== Unary ====================
    new_ast, s = run_fold("local x = -(-42)")
    out = ast_to_code(new_ast)
    test("-(-42) -> 42", "= 42" in out, out)
    
    new_ast, s = run_fold("local x = not false")
    test("not false -> true", "= true" in ast_to_code(new_ast))
    
    new_ast, s = run_fold("local x = not not true")
    test("not not true -> true", "= true" in ast_to_code(new_ast))
    
    new_ast, s = run_fold("local x = not nil")
    test("not nil -> true", "= true" in ast_to_code(new_ast))
    
    # ==================== Сравнения ====================
    new_ast, s = run_fold("local x = 5 > 3")
    test("5>3 -> true", "= true" in ast_to_code(new_ast))
    
    new_ast, s = run_fold("local x = 5 == 5")
    test("5==5 -> true", "= true" in ast_to_code(new_ast))
    
    new_ast, s = run_fold('local x = "a" == "b"')
    test('"a"=="b" -> false', "= false" in ast_to_code(new_ast))
    
    # ==================== Логика ====================
    new_ast, s = run_fold("local x = true and 42")
    test("true and 42 -> 42", "= 42" in ast_to_code(new_ast))
    
    new_ast, s = run_fold("local x = false or 100")
    test("false or 100 -> 100", "= 100" in ast_to_code(new_ast))
    
    new_ast, s = run_fold("local x = nil or 'default'")
    test("nil or 'default' -> 'default'", "default" in ast_to_code(new_ast))
    
    # ==================== Скобки ====================
    new_ast, s = run_fold("local x = (5)")
    test("(5) -> 5", "= 5" in ast_to_code(new_ast))
    
    # ==================== Не трогает переменные ====================
    new_ast, s = run_fold("local a = 1 local x = a + 1")
    out = ast_to_code(new_ast)
    test("a + 1 НЕ трогает (a — переменная)", "a + 1" in out, out)
    
    # ==================== Комбинированный тест ====================
    src = '''
        local a = 2 + 3
        local b = "foo" .. "bar"
        local c = not false
        local d = (5 * 5) + (-(-10))
        local e = #"hello world"
    '''
    new_ast, stats = run_fold(src)
    out = ast_to_code(new_ast)
    test("combo: a=5", "a = 5" in out, out)
    test("combo: b='foobar'", "foobar" in out, out)
    test("combo: c=true", "c = true" in out, out)
    test("combo: d=35", "d = 35" in out, out)
    test("combo: e=11", "e = 11" in out, out)
    
    print(f"\n=== ИТОГО: {passed}/{passed+failed} ===")
    if failed == 0: print("[!!] Все тесты прошли!")
    
    # ==================== ДЕМО ====================
    print("\n=== Демо: real-world obfuscated arithmetic ===")
    demo = '''
        local key = (0x2A + 1 - 1) * 1 + 0
        local msg_len = 5 * 2 + 3 - 4
        local flag = not not true
        local greeting = "Hello" .. ", " .. "World" .. "!"
        local computed = 2^8 - 1
    '''
    print("БЫЛО:")
    print(demo)
    new_demo, dstats = run_fold(demo)
    print("СТАЛО:")
    print(ast_to_code(new_demo))
    print(f"\n{dstats.summary()}")