"""
NZL Deobfuscator - Symbol Table
================================
Трекинг переменных, scope'ов, использований.

Используется для:
- Rename переменных (a1b2c3 -> localVar)
- Удаление мёртвого кода
- Constant folding (если переменная = const литерал и не переопределяется)
- Type inference (в будущем)
"""

from dataclasses import dataclass, field
from typing import Optional, Any
from .base import (
    NodeVisitor, Node,
    NameExpr, LocalAssignStat, AssignStat,
    FunctionExpr, LocalFunctionStat, FunctionDeclStat,
    NumericForStat, GenericForStat,
    Block, Chunk, IfStat, WhileStat, RepeatStat, DoBlockStat,
)


@dataclass
class Symbol:
    """Одна переменная в scope'е."""
    name: str
    scope_id: int
    is_local: bool = True
    is_const: bool = False           # attribs = <const>
    is_close: bool = False           # attribs = <close>
    declared_line: int = 0
    write_count: int = 0             # сколько раз присваивалось
    read_count: int = 0              # сколько раз читалось
    constant_value: Any = None       # если известно (для fold'а)
    has_constant_value: bool = False
    
    def __repr__(self):
        flags = []
        if self.is_const: flags.append("const")
        if self.is_close: flags.append("close")
        if self.has_constant_value: flags.append(f"={self.constant_value!r}")
        f = f"[{','.join(flags)}]" if flags else ""
        return f"Symbol({self.name}@scope{self.scope_id} r={self.read_count} w={self.write_count} {f})"


class Scope:
    """Один scope (block, function, for-loop)."""
    
    _next_id = 0
    
    def __init__(self, parent: Optional['Scope'] = None, kind: str = "block"):
        self.id = Scope._next_id
        Scope._next_id += 1
        self.parent = parent
        self.kind = kind                    # "chunk" | "function" | "block" | "for" | "repeat"
        self.symbols: dict[str, Symbol] = {}
        self.children: list['Scope'] = []
        if parent:
            parent.children.append(self)
    
    def declare(self, name: str, line: int = 0, is_const: bool = False, is_close: bool = False) -> Symbol:
        """Объявить локальную переменную в этом scope'е."""
        sym = Symbol(
            name=name,
            scope_id=self.id,
            is_local=True,
            is_const=is_const,
            is_close=is_close,
            declared_line=line,
        )
        self.symbols[name] = sym
        return sym
    
    def lookup(self, name: str) -> Optional[Symbol]:
        """Найти символ (сначала здесь, потом в родителях)."""
        if name in self.symbols:
            return self.symbols[name]
        if self.parent:
            return self.parent.lookup(name)
        return None
    
    def lookup_local(self, name: str) -> Optional[Symbol]:
        """Найти символ ТОЛЬКО в этом scope'е (без родителей)."""
        return self.symbols.get(name)
    
    def __repr__(self):
        return f"Scope#{self.id}({self.kind}, syms={list(self.symbols.keys())})"


class SymbolTableBuilder(NodeVisitor):
    """
    Строит symbol table по AST.
    
    Использование:
        builder = SymbolTableBuilder()
        table = builder.build(chunk)
        # table - root Scope
    """
    
    def __init__(self):
        self.root: Optional[Scope] = None
        self.current: Optional[Scope] = None
        # Список глобалов (не найдены в scope'ах)
        self.globals: dict[str, Symbol] = {}
    
    def build(self, chunk: Chunk) -> Scope:
        """Точка входа."""
        Scope._next_id = 0
        self.root = Scope(parent=None, kind="chunk")
        self.current = self.root
        self.visit(chunk)
        return self.root
    
    def _push_scope(self, kind: str) -> Scope:
        s = Scope(parent=self.current, kind=kind)
        self.current = s
        return s
    
    def _pop_scope(self):
        if self.current.parent:
            self.current = self.current.parent
    
    # ==================== VISITORS ====================
    
    def visit_Chunk(self, node):
        # Body — Block, но обрабатываем без нового scope (уже в root)
        self.visit(node.body)
        return node
    
    def visit_Block(self, node):
        # Block не создаёт scope сам по себе — его создаёт родитель
        # (function/if/while/for). Просто идём по statements.
        for stat in node.statements:
            self.visit(stat)
        if node.return_stat:
            self.visit(node.return_stat)
        return node
    
    def visit_LocalAssignStat(self, node):
        # Сначала visit values (они видят СТАРЫЕ переменные)
        for v in node.values:
            self.visit(v)
        # Затем объявляем новые
        for i, name in enumerate(node.names):
            attribs = node.attribs[i] if i < len(node.attribs) else None
            sym = self.current.declare(
                name=name,
                line=node.line,
                is_const=(attribs == "const"),
                is_close=(attribs == "close"),
            )
            sym.write_count += 1
        return node
    
    def visit_AssignStat(self, node):
        # Сначала values
        for v in node.values:
            self.visit(v)
        # Targets — считаем write
        for tgt in node.targets:
            if isinstance(tgt, NameExpr):
                sym = self.current.lookup(tgt.name)
                if sym:
                    sym.write_count += 1
                else:
                    # Глобал
                    if tgt.name not in self.globals:
                        self.globals[tgt.name] = Symbol(
                            name=tgt.name,
                            scope_id=-1,
                            is_local=False,
                            declared_line=node.line,
                        )
                    self.globals[tgt.name].write_count += 1
            else:
                self.visit(tgt)  # IndexExpr и т.д.
        return node
    
    def visit_NameExpr(self, node):
        sym = self.current.lookup(node.name)
        if sym:
            sym.read_count += 1
        else:
            if node.name not in self.globals:
                self.globals[node.name] = Symbol(
                    name=node.name,
                    scope_id=-1,
                    is_local=False,
                    declared_line=node.line,
                )
            self.globals[node.name].read_count += 1
        return node
    
    def visit_FunctionExpr(self, node):
        self._push_scope("function")
        for p in node.params:
            sym = self.current.declare(p, node.line)
            sym.write_count += 1
        self.visit(node.body)
        self._pop_scope()
        return node
    
    def visit_LocalFunctionStat(self, node):
        # local function foo() ... end
        # Имя объявляется ДО обхода тела (для рекурсии)
        sym = self.current.declare(node.name, node.line)
        sym.write_count += 1
        self.visit(node.func)  # войдёт в visit_FunctionExpr
        return node
    
    def visit_FunctionDeclStat(self, node):
        # function foo() end  или  function a.b.c() end
        # Target - это NameExpr или IndexExpr - трактуем как AssignStat
        self.visit(node.target)  # засчитает write если это NameExpr глобал
        self.visit(node.func)
        return node
    
    def visit_NumericForStat(self, node):
        self.visit(node.start)
        self.visit(node.stop)
        if node.step:
            self.visit(node.step)
        self._push_scope("for")
        sym = self.current.declare(node.var, node.line)
        sym.write_count += 1
        self.visit(node.body)
        self._pop_scope()
        return node
    
    def visit_GenericForStat(self, node):
        for e in node.exprs:
            self.visit(e)
        self._push_scope("for")
        for name in node.names:
            sym = self.current.declare(name, node.line)
            sym.write_count += 1
        self.visit(node.body)
        self._pop_scope()
        return node
    
    def visit_IfStat(self, node):
        for cond, block in node.branches:
            self.visit(cond)
            self._push_scope("block")
            self.visit(block)
            self._pop_scope()
        if node.else_block:
            self._push_scope("block")
            self.visit(node.else_block)
            self._pop_scope()
        return node
    
    def visit_WhileStat(self, node):
        self.visit(node.cond)
        self._push_scope("block")
        self.visit(node.body)
        self._pop_scope()
        return node
    
    def visit_RepeatStat(self, node):
        # В repeat...until условие видит переменные тела!
        self._push_scope("repeat")
        self.visit(node.body)
        self.visit(node.cond)
        self._pop_scope()
        return node
    
    def visit_DoBlockStat(self, node):
        self._push_scope("block")
        self.visit(node.body)
        self._pop_scope()
        return node


# ============================================================
# УТИЛИТЫ
# ============================================================

def collect_all_symbols(scope: Scope) -> list[Symbol]:
    """Рекурсивно собирает все символы во всех scope'ах."""
    result = list(scope.symbols.values())
    for child in scope.children:
        result.extend(collect_all_symbols(child))
    return result


def find_unused_locals(scope: Scope) -> list[Symbol]:
    """Находит локалы, которые НИКОГДА не читаются."""
    return [s for s in collect_all_symbols(scope) if s.is_local and s.read_count == 0]


# ============================================================
# ТЕСТЫ
# ============================================================

if __name__ == "__main__":
    from .base import parse_code
    
    print("=== Тест SymbolTable ===\n")
    passed = failed = 0
    def test(name, cond):
        global passed, failed
        if cond: print(f"  [OK] {name}"); passed += 1
        else:    print(f"  [XX] {name}"); failed += 1
    
    # Test 1: простое объявление
    ast = parse_code("local x = 5 local y = x + 1")
    builder = SymbolTableBuilder()
    root = builder.build(ast)
    test("root scope kind == chunk", root.kind == "chunk")
    test("x declared", "x" in root.symbols)
    test("y declared", "y" in root.symbols)
    test("x read_count == 1", root.symbols["x"].read_count == 1)
    test("x write_count == 1", root.symbols["x"].write_count == 1)
    test("y read_count == 0 (unused)", root.symbols["y"].read_count == 0)
    
    # Test 2: unused
    unused = find_unused_locals(root)
    test("find_unused_locals найдёт y", any(s.name == "y" for s in unused))
    
    # Test 3: scope изоляция
    ast2 = parse_code("""
        local outer = 1
        do
            local inner = 2
            outer = outer + inner
        end
    """)
    builder2 = SymbolTableBuilder()
    root2 = builder2.build(ast2)
    test("outer в root", "outer" in root2.symbols)
    test("inner НЕ в root", "inner" not in root2.symbols)
    test("outer write=2 (init + assign)", root2.symbols["outer"].write_count == 2)
    test("outer read=1 (в присваивании)", root2.symbols["outer"].read_count == 1)
    
    # Test 4: function scope
    ast3 = parse_code("""
        local function foo(a, b)
            return a + b
        end
        foo(1, 2)
    """)
    builder3 = SymbolTableBuilder()
    root3 = builder3.build(ast3)
    test("foo в root", "foo" in root3.symbols)
    test("foo read=1", root3.symbols["foo"].read_count == 1)
    test("a,b в дочернем scope", any("a" in c.symbols and "b" in c.symbols for c in root3.children))
    
    # Test 5: for scope
    ast4 = parse_code("for i = 1, 10 do print(i) end")
    builder4 = SymbolTableBuilder()
    root4 = builder4.build(ast4)
    test("i НЕ в root", "i" not in root4.symbols)
    test("i в for-scope", any(c.kind == "for" and "i" in c.symbols for c in root4.children))
    test("print — глобал", "print" in builder4.globals)
    
    # Test 6: const attrib
    ast5 = parse_code("local x <const> = 42")
    root5 = SymbolTableBuilder().build(ast5)
    test("x is_const", root5.symbols["x"].is_const)
    
    print(f"\n=== ИТОГО: {passed}/{passed+failed} ===")
    if failed == 0: print("[!!] Все тесты прошли!")