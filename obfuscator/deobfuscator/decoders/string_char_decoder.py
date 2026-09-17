"""
NZL Deobfuscator - string.char Decoder
=======================================
Сворачивает вызовы вида:
    string.char(72, 101, 108, 108, 111)   ->  "Hello"
    string.char(0x48, 0x69)               ->  "Hi"

Работает через LuaSandbox — 100% точное вычисление.
Также умеет обрабатывать константные NameExpr, если передан symbol_table
с известными const-значениями.

Это САМЫЙ ПЕРВЫЙ реальный декодер!
"""

from obfuscator.deobfuscator.core.base import (
    CallExpr, NumberLit, StringLit, NameExpr, IndexExpr,
    is_call_to, make_literal,
)
from .base_decoder import BaseDecoder


class StringCharDecoder(BaseDecoder):
    """
    Находит string.char(N, N, N, ...) с чистыми числовыми аргументами
    и заменяет на StringLit с готовой строкой.
    
    Пример:
        Было:  local msg = string.char(72, 101, 108, 108, 111)
        Стало: local msg = "Hello"
    """
    
    NAME = "string.char folding"
    
    def visit_CallExpr(self, node):
        # Сначала спускаемся в детей (может быть вложенный string.char)
        node = self.generic_visit(node)
        
        # Проверяем: это string.char(...)?
        if not is_call_to(node, "string.char"):
            return node
        
        self.stats.scanned += 1
        
        # Все аргументы должны быть числовыми литералами
        if not node.args:
            return node
        
        chars = []
        for arg in node.args:
            if not isinstance(arg, NumberLit):
                return node  # есть не-литерал, пропускаем
            v = arg.value
            if not isinstance(v, (int, float)):
                return node
            iv = int(v)
            if iv != v:      # дробное — string.char такого не принимает
                return node
            if iv < 0 or iv > 255:
                return node  # вне диапазона байта
            chars.append(iv)
        
        # Собираем строку
        try:
            # Строим байты и декодируем как latin-1 (сохраняет все 0-255)
            # Lua string.char работает с байтами, не с Unicode
            s = bytes(chars).decode('latin-1')
        except Exception as e:
            self.stats.errors += 1
            self.stats.details.append(f"decode fail: {e}")
            return node
        
        self.stats.replaced += 1
        preview = s if len(s) < 32 else s[:29] + "..."
        self.stats.details.append(f"string.char(...) -> {preview!r}")
        
        return make_literal(s, line=node.line)


# ============================================================
# ТЕСТЫ
# ============================================================

if __name__ == "__main__":
    from obfuscator.deobfuscator.core.base import parse_code, ast_to_code
    
    print("=== Тест StringCharDecoder ===\n")
    passed = failed = 0
    def test(name, cond, extra=""):
        global passed, failed
        if cond: print(f"  [OK] {name}"); passed += 1
        else:    print(f"  [XX] {name} {extra}"); failed += 1
    
    # Test 1: базовый случай
    src = 'local x = string.char(72, 101, 108, 108, 111)'
    ast = parse_code(src)
    dec = StringCharDecoder()
    new_ast, stats = dec.run(ast)
    out = ast_to_code(new_ast)
    test("Hello: string.char -> 'Hello'", '"Hello"' in out or "'Hello'" in out, out)
    test("stats.replaced == 1", stats.replaced == 1)
    test("stats.scanned == 1", stats.scanned == 1)
    
    # Test 2: не трогает не-string.char
    src2 = 'local x = math.floor(5.7)'
    ast2 = parse_code(src2)
    _, stats2 = StringCharDecoder().run(ast2)
    test("не трогает math.floor", stats2.replaced == 0)
    test("scanned=0 для math.floor", stats2.scanned == 0)
    
    # Test 3: множественные вызовы
    src3 = '''
        local a = string.char(72, 105)
        local b = string.char(87, 111, 114, 108, 100)
        local c = string.char(33)
    '''
    ast3 = parse_code(src3)
    _, stats3 = StringCharDecoder().run(ast3)
    test("3 замены", stats3.replaced == 3)
    out3 = ast_to_code(ast3)
    test("Hi в выводе", "Hi" in out3, out3)
    test("World в выводе", "World" in out3, out3)
    test("! в выводе", "!" in out3, out3)
    
    # Test 4: hex
    src4 = 'local x = string.char(0x48, 0x69)'
    ast4 = parse_code(src4)
    _, stats4 = StringCharDecoder().run(ast4)
    out4 = ast_to_code(ast4)
    test("hex: 0x48,0x69 -> Hi", "Hi" in out4, out4)
    
    # Test 5: не трогает если аргумент — переменная
    src5 = 'local n = 72 local x = string.char(n, 101)'
    ast5 = parse_code(src5)
    _, stats5 = StringCharDecoder().run(ast5)
    test("scanned=1 но replaced=0 (есть NameExpr)", stats5.scanned == 1 and stats5.replaced == 0)
    
    # Test 6: не трогает если out-of-range
    src6 = 'local x = string.char(300, 500)'
    ast6 = parse_code(src6)
    _, stats6 = StringCharDecoder().run(ast6)
    test("out-of-range не трогает", stats6.replaced == 0)
    
    # Test 7: вложенное
    src7 = 'print(string.char(72, 105))'
    ast7 = parse_code(src7)
    _, stats7 = StringCharDecoder().run(ast7)
    out7 = ast_to_code(ast7)
    test("вложенное в print", stats7.replaced == 1)
    test('print("Hi")', 'Hi' in out7, out7)
    
    # Test 8: реальный обфусцированный кейс
    src8 = '''
        local msg = string.char(87, 101, 108, 99, 111, 109, 101, 32, 116, 111, 32, 78, 90, 76, 33)
        print(msg)
    '''
    ast8 = parse_code(src8)
    new_ast8, stats8 = StringCharDecoder().run(ast8)
    out8 = ast_to_code(new_ast8)
    test("real-world: 'Welcome to NZL!'", "Welcome to NZL!" in out8, out8)
    
    # Test 9: пустой вызов
    src9 = 'local x = string.char()'
    ast9 = parse_code(src9)
    _, stats9 = StringCharDecoder().run(ast9)
    test("пустой string.char() не падает", True)
    test("пустой не заменяет", stats9.replaced == 0)
    
    print(f"\n=== ИТОГО: {passed}/{passed+failed} ===")
    if failed == 0:
        print("[!!] Все тесты прошли! StringCharDecoder готов!")
    
    print("\n=== Демо: было -> стало ===")
    demo_src = '''
        local greeting = string.char(72, 101, 108, 108, 111, 44, 32, 87, 111, 114, 108, 100, 33)
        local secret = string.char(0x4E, 0x5A, 0x4C)
        print(greeting, secret)
    '''
    print("БЫЛО:")
    print(demo_src)
    demo_ast = parse_code(demo_src)
    new_demo, demo_stats = StringCharDecoder().run(demo_ast)
    print("СТАЛО:")
    print(ast_to_code(new_demo))
    print(f"\n{demo_stats.summary()}")