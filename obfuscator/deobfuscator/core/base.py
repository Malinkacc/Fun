"""
NZL Deobfuscator - Core Base
============================
Реэкспорт базовых классов + утилиты для работы с AST.

NodeVisitor и NodeTransformer уже реализованы в obfuscator.ast_nodes,
здесь просто удобные обёртки и helper'ы для декодеров.
"""

from obfuscator.ast_nodes import (
    NodeVisitor,
    NodeTransformer,
    Node,
    # Expressions
    NumberLit, StringLit, BoolLit, NilLit, VarargLit, InterpStringLit,
    NameExpr, IndexExpr, CallExpr, MethodCallExpr,
    BinaryOp, UnaryOp, ParenExpr,
    TableExpr, TableField, FunctionExpr,
    # Statements
    AssignStat, LocalAssignStat, CallStat, DoBlockStat,
    IfStat, WhileStat, RepeatStat,
    NumericForStat, GenericForStat,
    FunctionDeclStat, LocalFunctionStat,
    ReturnStat, BreakStat, ContinueStat,
    GotoStat, LabelStat, TypeAliasStat,
    CompoundAssignStat,
    # Root
    Chunk, Block,
)

from obfuscator.lexer import tokenize
from obfuscator.parser import Parser
from obfuscator.ast_unparser import unparse


# ============================================================
# УТИЛИТЫ ДЛЯ AST
# ============================================================

def parse_code(source: str) -> Chunk:
    """Парсит Lua-код в AST. Быстрый helper."""
    tokens = tokenize(source)
    return Parser(tokens).parse()


def ast_to_code(chunk: Chunk) -> str:
    """Обратное преобразование AST -> Lua-код."""
    return unparse(chunk)


def is_literal(node) -> bool:
    """True если узел — литерал (число/строка/bool/nil)."""
    return isinstance(node, (NumberLit, StringLit, BoolLit, NilLit))


def get_literal_value(node):
    """Извлекает значение литерала. Для nil возвращает None."""
    if isinstance(node, NilLit):
        return None
    if isinstance(node, (NumberLit, StringLit, BoolLit)):
        return node.value
    raise ValueError(f"Not a literal: {type(node).__name__}")


def make_literal(value, line: int = 0):
    """Создаёт литерал из Python-значения."""
    if value is None:
        return NilLit(line=line)
    if isinstance(value, bool):
        return BoolLit(line=line, value=value)
    if isinstance(value, (int, float)):
        return NumberLit(line=line, value=value)
    if isinstance(value, str):
        return StringLit(line=line, value=value)
    raise ValueError(f"Cannot make literal from {type(value).__name__}: {value!r}")


def is_call_to(node, func_path: str) -> bool:
    """
    Проверяет что node - это вызов конкретной функции по пути.
    
    Примеры:
        is_call_to(node, "string.char")       -> string.char(...)
        is_call_to(node, "table.concat")      -> table.concat(...)
        is_call_to(node, "print")             -> print(...)
    """
    if not isinstance(node, CallExpr):
        return False
    return _matches_path(node.func, func_path)


def _matches_path(expr, path: str) -> bool:
    """Проверяет что expr соответствует пути вида 'a.b.c'"""
    parts = path.split('.')
    # Простое имя: print
    if len(parts) == 1:
        return isinstance(expr, NameExpr) and expr.name == parts[0]
    # Составное: string.char
    if not isinstance(expr, IndexExpr) or not expr.is_dot:
        return False
    if not isinstance(expr.index, StringLit) or expr.index.value != parts[-1]:
        return False
    return _matches_path(expr.obj, '.'.join(parts[:-1]))


# ============================================================
# ТЕСТЫ
# ============================================================

if __name__ == "__main__":
    print("=== Тест core/base.py ===\n")
    
    passed = 0
    failed = 0
    
    def test(name, cond):
        global passed, failed
        if cond:
            print(f"  [OK] {name}")
            passed += 1
        else:
            print(f"  [XX] {name}")
            failed += 1
    
    # Test 1: parse + unparse
    src = "local x = 42"
    ast = parse_code(src)
    test("parse_code возвращает Chunk", isinstance(ast, Chunk))
    test("ast_to_code round-trip", "42" in ast_to_code(ast))
    
    # Test 2: is_literal
    n_num = NumberLit(line=0, value=5)
    n_str = StringLit(line=0, value="hi")
    n_nil = NilLit(line=0)
    n_bool = BoolLit(line=0, value=True)
    n_name = NameExpr(line=0, name="x")
    test("is_literal(NumberLit)", is_literal(n_num))
    test("is_literal(StringLit)", is_literal(n_str))
    test("is_literal(NilLit)", is_literal(n_nil))
    test("is_literal(BoolLit)", is_literal(n_bool))
    test("NOT is_literal(NameExpr)", not is_literal(n_name))
    
    # Test 3: get_literal_value
    test("get_literal_value(Num)==5", get_literal_value(n_num) == 5)
    test("get_literal_value(Nil) is None", get_literal_value(n_nil) is None)
    test("get_literal_value(Bool)==True", get_literal_value(n_bool) is True)
    
    # Test 4: make_literal
    test("make_literal(42) -> NumberLit", isinstance(make_literal(42), NumberLit))
    test("make_literal('x') -> StringLit", isinstance(make_literal("x"), StringLit))
    test("make_literal(None) -> NilLit", isinstance(make_literal(None), NilLit))
    test("make_literal(True) -> BoolLit", isinstance(make_literal(True), BoolLit))
    
    # Test 5: is_call_to
    ast2 = parse_code("string.char(72, 101)")
    call_node = ast2.body.statements[0].call
    test("is_call_to(node, 'string.char')", is_call_to(call_node, "string.char"))
    test("NOT is_call_to(node, 'table.concat')", not is_call_to(call_node, "table.concat"))
    
    ast3 = parse_code("print('hi')")
    call3 = ast3.body.statements[0].call
    test("is_call_to(print) works", is_call_to(call3, "print"))
    
    ast4 = parse_code("a.b.c.d(1)")
    call4 = ast4.body.statements[0].call
    test("is_call_to deep path 'a.b.c.d'", is_call_to(call4, "a.b.c.d"))
    test("NOT is_call_to path 'a.b.c'", not is_call_to(call4, "a.b.c"))
    
    print(f"\n=== ИТОГО: {passed}/{passed+failed} ===")
    if failed == 0:
        print("[!!] Все тесты прошли!")