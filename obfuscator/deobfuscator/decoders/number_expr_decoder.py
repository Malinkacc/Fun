"""
NZL Deobfuscator - Number Expression Decoder (Sprint 1, Part 2)
===============================================================
Сворачивает обфусцированные числовые выражения обратно в литералы:

    bit32.rrotate(0X54, 1)              ->  42
    bit32.bxor(37493, 37134)            ->  391
    bit32.band(1503006264, bit32.rshift(1389, 3))  ->  8
    (898 - bit32.bxor(37493, 37134))    ->  507
    0XFFFF                              ->  65535   (стиль литерала нормализуется)

Зачем: NumberExprGen v2.1 (obfuscator/utils/random_gen.py) генерирует
14 видов выражений на всех bit32-операциях + hex/bin литералах.
Этот декодер — вторая половина adversarial-пары: обфускатор добавил,
деобфускатор обязан уметь снять.

Как:
  1. bottom-up обход AST (generic_visit до логики, как в constant_fold);
  2. CallExpr вида bit32.<op>(...) / math.<op>(...) с КОНСТАНТНЫМИ
     числовыми аргументами вычисляется внутренней Lua-семантикой;
  3. результат заменяется на NumberLit(value) — без raw, т.е. десятичный;
  4. по желанию результат сверяется с LuaSandbox.eval_expr (тесты).

НЕ трогает: строки, string.char, не-константные аргументы (где есть
NameExpr/CallExpr с переменными) — их берёт sandbox_decoder.
"""

import math
from functools import reduce

from obfuscator.deobfuscator.core.base import (
    NumberLit,
    CallExpr,
    IndexExpr,
    NameExpr,
    UnaryOp,
)
from .base_decoder import BaseDecoder


# ============================================================
# Lua-семантика bit32 / math на Python (чистые функции)
# ============================================================

def _u32(x: int) -> int:
    return int(x) & 0xFFFFFFFF


def _rot32(x: int, n: int) -> int:
    x = _u32(x)
    n %= 32
    return ((x << n) | (x >> (32 - n))) & 0xFFFFFFFF


def _s32(x: int) -> int:
    x = _u32(x)
    return x - 0x100000000 if x >= 0x80000000 else x


_BIT32 = {
    'band':    lambda a: reduce(lambda x, y: x & y, [_u32(v) for v in a]),
    'bor':     lambda a: reduce(lambda x, y: x | y, [_u32(v) for v in a]),
    'bxor':    lambda a: reduce(lambda x, y: x ^ y, [_u32(v) for v in a]),
    'bnot':    lambda a: _u32(~_u32(a[0])),
    'lshift':  lambda a: _u32(_u32(a[0]) << (int(a[1]) & 31)) if 0 <= int(a[1]) < 32 else 0,
    'rshift':  lambda a: _u32(a[0]) >> (int(a[1]) & 31) if 0 <= int(a[1]) < 32 else 0,
    'arshift': lambda a: _u32(_s32(a[0]) >> min(max(int(a[1]), 0), 32)),
    'lrotate': lambda a: _rot32(a[0], int(a[1])),
    'rrotate': lambda a: _rot32(a[0], -int(a[1])),
    'extract': lambda a: (_u32(a[0]) >> max(0, min(31, int(a[1])))) & (
        (1 << max(1, min(32 - max(0, min(31, int(a[1]))), int(a[2]) if len(a) > 2 else 1))) - 1),
}


def _math_fn(name: str, args: list):
    if name == 'floor' and len(args) >= 1:
        return math.floor(args[0])
    if name == 'ceil' and len(args) >= 1:
        return math.ceil(args[0])
    if name == 'abs' and len(args) >= 1:
        return abs(args[0])
    if name == 'sqrt' and len(args) >= 1:
        return math.sqrt(args[0])
    if name == 'fmod' and len(args) >= 2 and args[1] != 0:
        return math.fmod(args[0], args[1])
    if name == 'pow' and len(args) >= 2:
        return args[0] ** args[1]
    if name == 'max' and args:
        return max(args)
    if name == 'min' and args:
        return min(args)
    if name == 'exp' and len(args) >= 1:
        return math.exp(args[0])
    return None


class NumberExprDecoder(BaseDecoder):
    """
    Сворачивает константные bit32.*/math.* выражения в NumberLit.

    Работает bottom-up: вложенные bit32.band(bit32.rshift(...)) сворачиваются
    за один проход, потому что дети посещаются раньше родителей.
    """

    NAME = "number expr fold"

    # библиотеки, чьи вызовы мы умеем считать
    LIBS = ('bit32', 'math')

    def __init__(self, cross_check_sandbox=None):
        super().__init__()
        # если передать LuaSandbox — каждое свёрнутое значение сверяется с ним
        self._sandbox = cross_check_sandbox

    # ------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------

    @staticmethod
    def _is_number(node) -> bool:
        return isinstance(node, NumberLit) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool)

    @staticmethod
    def _lib_call(node):
        """
        Распознаёт bit32.op(...) / math.op(...).
        Возвращает (lib, op) или (None, None).
        """
        if not isinstance(node, CallExpr):
            return None, None
        func = node.func
        if not isinstance(func, IndexExpr):
            return None, None
        obj = func.obj
        if not isinstance(obj, NameExpr) or obj.name not in NumberExprDecoder.LIBS:
            return None, None
        # t.op  (is_dot) или t["op"]
        idx = func.index
        if isinstance(idx, str):
            op = idx
        else:
            from obfuscator.ast_nodes import StringLit
            if isinstance(idx, StringLit):
                op = idx.value
            else:
                return None, None
        return obj.name, op

    def _fold_call(self, node: CallExpr):
        lib, op = self._lib_call(node)
        if lib is None:
            return None
        args = []
        for a in node.args:
            if not self._is_number(a):
                return None          # не константа — не трогаем, это к sandbox_decoder
            args.append(a.value)
        if not args:
            return None
        try:
            if lib == 'bit32':
                fn = _BIT32.get(op)
                if fn is None:
                    return None
                value = fn([int(v) for v in args])
            else:
                value = _math_fn(op, args)
            if value is None:
                return None
            if isinstance(value, float) and value != int(value):
                return None          # float-результаты не сворачиваем в int-литерал
            value = int(value)
        except (ValueError, OverflowError, ZeroDivisionError, IndexError):
            return None
        return value

    # ------------------------------------------------------------
    # visitors
    # ------------------------------------------------------------

    def visit_CallExpr(self, node):
        node = self.generic_visit(node)      # bottom-up: дети уже свёрнуты
        self.stats.scanned += 1
        value = self._fold_call(node)
        if value is None:
            return node
        if self._sandbox is not None:
            try:
                from obfuscator.ast_unparser import unparse
                checked = self._sandbox.eval_expr(unparse(node))
                if isinstance(checked, (int, float)) and int(checked) != value:
                    self.stats.errors += 1
                    self.stats.details.append(f"sandbox mismatch: {value} vs {checked}")
                    return node
            except Exception as e:                       # noqa: BLE001
                self.stats.details.append(f"sandbox check skipped: {type(e).__name__}")
        self.stats.replaced += 1
        return NumberLit(line=getattr(node, 'line', 0), value=value)

    def visit_BinaryOp(self, node):
        node = self.generic_visit(node)
        if not (self._is_number(node.left) and self._is_number(node.right)):
            return node
        a, b = node.left.value, node.right.value
        try:
            if node.op == '+':
                value = a + b
            elif node.op == '-':
                value = a - b
            elif node.op == '*':
                value = a * b
            elif node.op == '/':
                if b == 0:
                    return node
                value = a / b
            elif node.op == '//':
                if b == 0:
                    return node
                value = math.floor(a / b)
            elif node.op == '%':
                if b == 0:
                    return node
                value = a - math.floor(a / b) * b
            elif node.op == '^':
                value = a ** b
            else:
                return node
        except (OverflowError, ZeroDivisionError, ValueError):
            return node
        if isinstance(value, float) and value == int(value) and abs(value) < 1e15:
            value = int(value)
        self.stats.replaced += 1
        return NumberLit(line=getattr(node, 'line', 0), value=value)

    def visit_ParenExpr(self, node):
        node = self.generic_visit(node)
        # (42) -> 42 : скобки вокруг литерала бессмысленны
        if self._is_number(node.inner):
            self.stats.replaced += 1
            return node.inner
        return node

    def visit_UnaryOp(self, node):
        node = self.generic_visit(node)
        operand = node.operand
        from obfuscator.ast_nodes import ParenExpr as _Paren
        if isinstance(operand, _Paren) and self._is_number(operand.inner):
            operand = operand.inner
        # -(0X2A) -> -42 ; убираем минус у уже свёрнутого литерала
        if node.op == '-' and self._is_number(operand):
            self.stats.replaced += 1
            return NumberLit(line=getattr(node, 'line', 0), value=-operand.value)
        if node.op == 'not' and self._is_number(operand):
            self.stats.replaced += 1
            return NumberLit(line=getattr(node, 'line', 0), value=0)   # в Lua любое число truthy
        return node

    def visit_NumberLit(self, node):
        # нормализация стиля: 0XFFFF / 0B1010 -> десятичный литерал
        raw = getattr(node, 'raw', '') or ''
        if raw[:2].lower() in ('0x', '0b'):
            self.stats.scanned += 1
            self.stats.replaced += 1
            return NumberLit(line=getattr(node, 'line', 0), value=node.value)
        return node


# ============================================================
# SELF-TEST
# ============================================================

if __name__ == '__main__':
    from obfuscator.lexer import Lexer
    from obfuscator.parser import Parser
    from obfuscator.ast_unparser import unparse

    passed = failed = 0

    def check(name, src, expect_value=None, expect_contains=None, expect_not_contains=None):
        global passed, failed
        try:
            chunk = Parser(Lexer(src).tokenize()).parse()
            dec = NumberExprDecoder()
            new_chunk, stats = dec.run(chunk)
            out = unparse(new_chunk)
            ok = True
            if expect_contains is not None and expect_contains not in out:
                ok = False
            if expect_not_contains is not None and expect_not_contains in out:
                ok = False
            if expect_value is not None:
                nums = []
                from dataclasses import fields, is_dataclass
                def walk(n):
                    if n is None or isinstance(n, (str, int, float, bool, bytes)):
                        return
                    if isinstance(n, NumberLit):
                        nums.append(n.value)
                    if not is_dataclass(n):
                        return
                    for f in fields(n):
                        v = getattr(n, f.name, None)
                        if isinstance(v, (list, tuple)):
                            for it in v:
                                walk(it)
                        else:
                            walk(v)
                walk(new_chunk)
                if expect_value not in nums:
                    ok = False
            if ok:
                passed += 1
                print(f"[OK] {name}: {src.strip()!r} -> {out.strip()!r}")
            else:
                failed += 1
                print(f"[XX] {name}: got {out.strip()!r}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"[XX] {name} crashed: {type(e).__name__}: {e}")

    check("rrotate",      "local a = bit32.rrotate(0X54, 1)",        expect_value=42)
    check("bxor",         "local a = bit32.bxor(37493, 37134)",      expect_value=37493 ^ 37134)
    check("nested",       "local a = bit32.band(1503006264, bit32.rshift(1389, 3))",
                          expect_value=1503006264 & (1389 >> 3))
    check("arith wrap",   "local a = (898 - bit32.bxor(37493, 37134))",
                          expect_value=898 - (37493 ^ 37134))
    check("lrotate",      "local a = bit32.lrotate(0B101, 29)",      expect_value=_rot32(5, 29))
    check("bnot",         "local a = bit32.bnot(0)",                 expect_value=0xFFFFFFFF)
    check("hex norm",     "local a = 0XFFFF",                        expect_value=65535,
          expect_not_contains="0XFFFF")
    check("bin norm",     "local a = 0B101010",                      expect_value=42,
          expect_not_contains="0B101010")
    check("math.floor",   "local a = math.floor(7.9)",               expect_value=7)
    check("unary minus",  "local a = -(0X2A)",                       expect_value=-42)
    check("non-const untouched", "local a = bit32.bxor(x, 5)",       expect_not_contains=None,
          expect_contains="bit32.bxor(x, 5)")
    check("string untouched",    'local a = string.char(72, 101)',   expect_contains="string.char(72, 101)")
    check("deep nest",    "local a = bit32.bxor(bit32.band(bit32.bor(12, 3), 0XF), bit32.lshift(1, 2))",
                          expect_value=((12 | 3) & 0xF) ^ (1 << 2))
    check("extract",      "local a = bit32.extract(0B110100, 2, 3)", expect_value=(0b110100 >> 2) & 0b111)
    check("plain code",   "local a = 1 + 2 print(a)",                expect_contains="print(a)")

    print()
    print(f"NumberExprDecoder tests: {passed}/{passed + failed}")
    if failed:
        raise SystemExit(1)
    print("All number expr decoder tests passed!")
