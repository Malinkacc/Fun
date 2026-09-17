"""
NZL Studio Obfuscator - AST Nodes
Abstract Syntax Tree node definitions for Lua 5.1 + Luau

Every construct in Lua/Luau is represented as a node class.
Nodes are dataclasses for easy inspection and cloning.

Structure:
    - Statements (Stat)   : do nothing, don't return values (local, if, while, etc.)
    - Expressions (Expr)  : return values (numbers, strings, operations, calls)
    - Special             : Chunk (root), Block (list of statements)
"""

from dataclasses import dataclass, field
from typing import List, Optional, Union, Any


# ==================== БАЗОВЫЕ КЛАССЫ ====================

@dataclass
class Node:
    """Базовый класс для всех узлов AST"""
    line: int = 0        # строка в исходнике (для отладки)
    
    def clone(self):
        """Возвращает глубокую копию узла"""
        import copy
        return copy.deepcopy(self)


@dataclass
class Expr(Node):
    """Базовый класс для всех выражений"""
    pass


@dataclass
class Stat(Node):
    """Базовый класс для всех инструкций"""
    pass


# ==================== КОРЕНЬ И БЛОКИ ====================

@dataclass
class Block(Node):
    """Блок кода — последовательность инструкций.
    Используется внутри функций, if/else, while и т.д."""
    statements: List[Stat] = field(default_factory=list)
    return_stat: Optional['ReturnStat'] = None  # опциональный return в конце
    
    def __repr__(self):
        return f"Block({len(self.statements)} stmts)"


@dataclass
class Chunk(Node):
    """Корень AST — весь файл целиком"""
    body: Block = None
    
    def __repr__(self):
        return "Chunk(...)"


# ==================== ЛИТЕРАЛЫ ====================

@dataclass
class NilLit(Expr):
    """nil"""
    def __repr__(self):
        return "Nil"


@dataclass
class BoolLit(Expr):
    """true / false"""
    value: bool = False
    def __repr__(self):
        return f"Bool({self.value})"


@dataclass
class NumberLit(Expr):
    """Число: 123, 3.14, 0xFF, 0B101"""
    value: Union[int, float] = 0
    raw: str = ""   # исходный текст литерала ("0X54", "0B101") — чтобы unparser сохранял стиль
    def __repr__(self):
        return f"Num({self.value})"


@dataclass
class StringLit(Expr):
    """Строка: "abc", 'abc', [[abc]]"""
    value: str = ""
    def __repr__(self):
        s = self.value[:30] + "..." if len(self.value) > 30 else self.value
        return f"Str({s!r})"


@dataclass
class InterpStringLit(Expr):
    """Interpolated string: `hello ${x}`
    parts: список строк и выражений вперемешку.
    Пример: `hi ${name}!` → parts=["hi ", NameExpr("name"), "!"]"""
    parts: List[Union[str, Expr]] = field(default_factory=list)
    def __repr__(self):
        return f"IStr({len(self.parts)} parts)"


@dataclass
class VarargLit(Expr):
    """... (varargs)"""
    def __repr__(self):
        return "..."


# ==================== ПЕРЕМЕННЫЕ И ДОСТУП ====================

@dataclass
class NameExpr(Expr):
    """Просто имя переменной: foo, myVar"""
    name: str = ""
    def __repr__(self):
        return f"Name({self.name})"


@dataclass
class IndexExpr(Expr):
    """Доступ по индексу: t[key] или t.field
    is_dot=True для точечной нотации (t.x → индекс это StringLit("x"))"""
    obj: Expr = None
    index: Expr = None
    is_dot: bool = False   # различаем t.x от t["x"] визуально
    def __repr__(self):
        if self.is_dot and isinstance(self.index, StringLit):
            return f"Index({self.obj}.{self.index.value})"
        return f"Index({self.obj}[{self.index}])"


# ==================== ОПЕРАЦИИ ====================

@dataclass
class BinaryOp(Expr):
    """Бинарная операция: a + b, x == y, str1 .. str2
    op: '+', '-', '*', '/', '//', '%', '^', '..', '==', '~=', '<', '>', '<=', '>=', 'and', 'or'"""
    op: str = ""
    left: Expr = None
    right: Expr = None
    def __repr__(self):
        return f"BinOp({self.left} {self.op} {self.right})"


@dataclass
class UnaryOp(Expr):
    """Унарная операция: -x, not x, #t
    op: '-', 'not', '#'"""
    op: str = ""
    operand: Expr = None
    def __repr__(self):
        return f"UnOp({self.op}{self.operand})"


# ==================== ВЫЗОВЫ ФУНКЦИЙ ====================

@dataclass
class CallExpr(Expr):
    """Вызов функции: f(a, b, c)"""
    func: Expr = None
    args: List[Expr] = field(default_factory=list)
    def __repr__(self):
        return f"Call({self.func}({len(self.args)} args))"


@dataclass
class MethodCallExpr(Expr):
    """Вызов метода: obj:method(args)
    Отличается от obj.method(args) тем, что obj передаётся первым аргументом."""
    obj: Expr = None
    method: str = ""
    args: List[Expr] = field(default_factory=list)
    def __repr__(self):
        return f"MCall({self.obj}:{self.method}({len(self.args)} args))"


# ==================== ФУНКЦИИ ====================

@dataclass
class FunctionExpr(Expr):
    """Анонимная функция: function(a, b) ... end
    is_vararg=True если параметры содержат ..."""
    params: List[str] = field(default_factory=list)     # имена параметров
    is_vararg: bool = False
    body: Block = None
    def __repr__(self):
        return f"Func({len(self.params)} params{'...' if self.is_vararg else ''})"


# ==================== ТАБЛИЦЫ ====================

@dataclass
class TableField(Node):
    """Одно поле в конструкторе таблицы.
    key=None → массивный элемент: {1, 2, 3}
    key=StringLit(...), is_name=True → {x = 1}
    key=Expr, is_name=False → {[key] = value}"""
    key: Optional[Expr] = None
    value: Expr = None
    is_name: bool = False    # True если запись вида "x = value" (не "[x] = value")
    def __repr__(self):
        if self.key is None:
            return f"Field({self.value})"
        return f"Field({self.key}={self.value})"


@dataclass
class TableExpr(Expr):
    """Конструктор таблицы: {1, 2, x = 3, [k] = v}"""
    fields: List[TableField] = field(default_factory=list)
    def __repr__(self):
        return f"Table({len(self.fields)} fields)"


# ==================== ИНСТРУКЦИИ (STATEMENTS) ====================

@dataclass
class AssignStat(Stat):
    """Присваивание: a, b, c = x, y, z"""
    targets: List[Expr] = field(default_factory=list)   # NameExpr или IndexExpr
    values: List[Expr] = field(default_factory=list)
    def __repr__(self):
        return f"Assign({len(self.targets)} = {len(self.values)})"


@dataclass
class CompoundAssignStat(Stat):
    """Составное присваивание (Luau): x += 1, s ..= "!"
    op: '+', '-', '*', '/', '//', '%', '^', '..'"""
    target: Expr = None
    op: str = ""
    value: Expr = None
    def __repr__(self):
        return f"CompAssign({self.target} {self.op}= {self.value})"


@dataclass
class LocalAssignStat(Stat):
    """Локальное объявление: local a, b = 1, 2
    attribs (Luau): опциональные атрибуты типа <const>, <close>"""
    names: List[str] = field(default_factory=list)
    values: List[Expr] = field(default_factory=list)   # может быть пустым
    attribs: List[Optional[str]] = field(default_factory=list)   # параллельный names
    def __repr__(self):
        return f"LocalAssign({', '.join(self.names)} = {len(self.values)} vals)"


@dataclass
class LocalFunctionStat(Stat):
    """local function name(...) ... end"""
    name: str = ""
    func: FunctionExpr = None
    def __repr__(self):
        return f"LocalFunc({self.name})"


@dataclass
class FunctionDeclStat(Stat):
    """function name(...) ... end
    function a.b.c:d(...) ... end
    
    target: путь до функции (a.b.c)
    method_name: если через ':' — имя метода (тогда добавляется self)
    """
    target: Expr = None            # NameExpr или IndexExpr chain
    method_name: Optional[str] = None
    func: FunctionExpr = None
    def __repr__(self):
        return f"FuncDecl({self.target}{':' + self.method_name if self.method_name else ''})"


@dataclass
class CallStat(Stat):
    """Вызов функции как statement: f() или obj:method()"""
    call: Expr = None    # CallExpr или MethodCallExpr
    def __repr__(self):
        return f"CallStat({self.call})"


@dataclass
class DoBlockStat(Stat):
    """do ... end блок"""
    body: Block = None
    def __repr__(self):
        return "DoBlock"


@dataclass
class WhileStat(Stat):
    """while cond do ... end"""
    cond: Expr = None
    body: Block = None
    def __repr__(self):
        return f"While({self.cond})"


@dataclass
class RepeatStat(Stat):
    """repeat ... until cond"""
    body: Block = None
    cond: Expr = None
    def __repr__(self):
        return f"Repeat(until {self.cond})"


@dataclass
class IfStat(Stat):
    """if ... elseif ... else ... end
    
    branches: список пар (условие, блок)
    else_block: опциональный else"""
    branches: List[tuple] = field(default_factory=list)  # [(Expr, Block), ...]
    else_block: Optional[Block] = None
    def __repr__(self):
        return f"If({len(self.branches)} branches{', else' if self.else_block else ''})"


@dataclass
class NumericForStat(Stat):
    """for var = start, stop, step do ... end"""
    var: str = ""
    start: Expr = None
    stop: Expr = None
    step: Optional[Expr] = None       # опциональный шаг
    body: Block = None
    def __repr__(self):
        return f"NumFor({self.var}={self.start}, {self.stop})"


@dataclass
class GenericForStat(Stat):
    """for a, b, c in expr1, expr2 do ... end"""
    names: List[str] = field(default_factory=list)
    exprs: List[Expr] = field(default_factory=list)
    body: Block = None
    def __repr__(self):
        return f"GenFor({', '.join(self.names)} in {len(self.exprs)} exprs)"


@dataclass
class ReturnStat(Stat):
    """return a, b, c"""
    values: List[Expr] = field(default_factory=list)
    def __repr__(self):
        return f"Return({len(self.values)} values)"


@dataclass
class BreakStat(Stat):
    """break"""
    def __repr__(self):
        return "Break"


@dataclass
class ContinueStat(Stat):
    """continue (Luau)"""
    def __repr__(self):
        return "Continue"


@dataclass
class GotoStat(Stat):
    """goto label"""
    label: str = ""
    def __repr__(self):
        return f"Goto({self.label})"


@dataclass
class LabelStat(Stat):
    """::label::"""
    name: str = ""
    def __repr__(self):
        return f"Label({self.name})"


# ==================== LUAU: ТИПЫ (парсим но не обфусцируем) ====================

@dataclass
class TypeAliasStat(Stat):
    """type Foo = { x: number } или export type Foo = ..."""
    name: str = ""
    type_expr: str = ""       # храним как raw string, нам не нужна структура типов
    is_export: bool = False
    def __repr__(self):
        return f"TypeAlias({'export ' if self.is_export else ''}{self.name})"


# ==================== ВСПОМОГАТЕЛЬНЫЕ ====================

@dataclass
class ParenExpr(Expr):
    """Выражение в скобках: (expr)
    Иногда важно сохранить — в Lua (f()) даёт только 1 результат, а f() может дать много"""
    inner: Expr = None
    def __repr__(self):
        return f"Paren({self.inner})"


# ==================== VISITOR PATTERN ====================

class NodeVisitor:
    """Базовый класс для обхода AST.
    
    Использование:
        class MyVisitor(NodeVisitor):
            def visit_NumberLit(self, node):
                print(node.value)
                return node
        
        visitor = MyVisitor()
        visitor.visit(chunk)
    
    Метод visit() автоматически вызывает visit_<ClassName>.
    Если такого метода нет — вызывается generic_visit, который рекурсивно
    обходит все дочерние узлы.
    """
    
    def visit(self, node):
        """Вызывает подходящий visit_ метод"""
        if node is None:
            return None
        method_name = 'visit_' + type(node).__name__
        method = getattr(self, method_name, self.generic_visit)
        return method(node)
    
    def generic_visit(self, node):
        """Дефолтный обход: рекурсивно посещает все поля"""
        for field_name in dataclass_fields(node):
            value = getattr(node, field_name)
            if isinstance(value, Node):
                self.visit(value)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, Node):
                        self.visit(item)
                    elif isinstance(item, tuple):
                        for sub in item:
                            if isinstance(sub, Node):
                                self.visit(sub)
        return node


class NodeTransformer(NodeVisitor):
    """Как NodeVisitor, но модифицирует дерево.
    Каждый visit_ метод должен возвращать новый узел (или тот же).
    
    Использование:
        class RenameVars(NodeTransformer):
            def visit_NameExpr(self, node):
                node.name = "_x" + node.name
                return node
        
        transformer = RenameVars()
        new_chunk = transformer.visit(chunk)
    """
    
    def generic_visit(self, node):
        """Обходит и модифицирует все поля"""
        for field_name in dataclass_fields(node):
            value = getattr(node, field_name)
            if isinstance(value, Node):
                new_value = self.visit(value)
                setattr(node, field_name, new_value)
            elif isinstance(value, list):
                new_list = []
                for item in value:
                    if isinstance(item, Node):
                        new_item = self.visit(item)
                        if new_item is not None:
                            if isinstance(new_item, list):
                                new_list.extend(new_item)
                            else:
                                new_list.append(new_item)
                    elif isinstance(item, tuple):
                        # tuple с узлами внутри (например branches в IfStat)
                        new_tuple = tuple(
                            self.visit(sub) if isinstance(sub, Node) else sub
                            for sub in item
                        )
                        new_list.append(new_tuple)
                    else:
                        new_list.append(item)
                setattr(node, field_name, new_list)
        return node


# ==================== УТИЛИТЫ ====================

def dataclass_fields(obj):
    """Возвращает имена полей dataclass"""
    from dataclasses import fields
    return [f.name for f in fields(obj)]


def dump_ast(node, indent=0, max_depth=20):
    """Красиво печатает AST для отладки"""
    if indent > max_depth:
        return "  " * indent + "...\n"
    
    if node is None:
        return "  " * indent + "None\n"
    
    if not isinstance(node, Node):
        return "  " * indent + repr(node) + "\n"
    
    result = "  " * indent + type(node).__name__ + "\n"
    for field_name in dataclass_fields(node):
        if field_name == 'line':
            continue
        value = getattr(node, field_name)
        if isinstance(value, Node):
            result += "  " * (indent + 1) + f"{field_name}:\n"
            result += dump_ast(value, indent + 2, max_depth)
        elif isinstance(value, list):
            if not value:
                result += "  " * (indent + 1) + f"{field_name}: []\n"
            else:
                result += "  " * (indent + 1) + f"{field_name}:\n"
                for item in value:
                    if isinstance(item, Node):
                        result += dump_ast(item, indent + 2, max_depth)
                    else:
                        result += "  " * (indent + 2) + repr(item) + "\n"
        else:
            result += "  " * (indent + 1) + f"{field_name}: {value!r}\n"
    return result


# ==================== ТЕСТ ====================

if __name__ == "__main__":
    # Строим руками маленькое дерево и проверяем что всё работает
    # Эквивалент кода: local x = 1 + 2
    
    chunk = Chunk(
        body=Block(
            statements=[
                LocalAssignStat(
                    names=["x"],
                    values=[
                        BinaryOp(
                            op="+",
                            left=NumberLit(value=1),
                            right=NumberLit(value=2)
                        )
                    ]
                ),
                CallStat(
                    call=CallExpr(
                        func=NameExpr(name="print"),
                        args=[NameExpr(name="x")]
                    )
                )
            ]
        )
    )
    
    print("=" * 60)
    print("AST для: local x = 1 + 2; print(x)")
    print("=" * 60)
    print(dump_ast(chunk))
    
    # Тест visitor'а: посчитаем количество NumberLit
    class NumberCounter(NodeVisitor):
        def __init__(self):
            self.count = 0
        def visit_NumberLit(self, node):
            self.count += 1
            return node
    
    counter = NumberCounter()
    counter.visit(chunk)
    print(f"\nЧисел в AST: {counter.count}")
    
    # Тест transformer'а: удвоим все числа
    class DoubleNumbers(NodeTransformer):
        def visit_NumberLit(self, node):
            node.value *= 2
            return node
    
    print("\n" + "=" * 60)
    print("После удвоения всех чисел:")
    print("=" * 60)
    DoubleNumbers().visit(chunk)
    print(dump_ast(chunk))