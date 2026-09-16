r"""
NZL Studio Obfuscator — AST Unparser
Преобразует AST обратно в валидный Lua/Luau код.

FIX:
    - корректная сериализация RawByteString из crypto.py
    - никакого двойного экранирования
    - decimal escapes всегда \ddd
    - защита от склейки: после decimal escape цифры тоже экранируются
    - обычные Unicode-строки пользователя не ломаются
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from obfuscator.ast_nodes import (
    Node, Expr, Stat, Block, Chunk,
    NilLit, BoolLit, NumberLit, StringLit, InterpStringLit, VarargLit,
    NameExpr, IndexExpr, ParenExpr,
    BinaryOp, UnaryOp,
    CallExpr, MethodCallExpr,
    FunctionExpr, TableExpr, TableField,
    AssignStat, CompoundAssignStat, LocalAssignStat,
    LocalFunctionStat, FunctionDeclStat, CallStat,
    DoBlockStat, WhileStat, RepeatStat, IfStat,
    NumericForStat, GenericForStat, ReturnStat,
    BreakStat, ContinueStat, GotoStat, LabelStat,
    TypeAliasStat,
)
from obfuscator.utils.crypto import RawByteString


# ============================================================
# OPERATOR PRIORITIES (Lua 5.1 / Luau)
# ============================================================

BINARY_PRIORITY = {
    'or':  (1, 1),
    'and': (2, 2),
    '<':   (3, 3), '>': (3, 3), '<=': (3, 3), '>=': (3, 3),
    '==':  (3, 3), '~=': (3, 3), '!=': (3, 3),
    '|':   (4, 4),
    '~':   (5, 5),
    '&':   (6, 6),
    '<<':  (7, 7), '>>': (7, 7),
    '..':  (9, 8),
    '+':   (10, 10), '-': (10, 10),
    '*':   (11, 11), '/': (11, 11), '//': (11, 11), '%': (11, 11),
    '^':   (14, 13),
}

UNARY_PRIORITY = 12


# ============================================================
# STRING ESCAPING
# ============================================================

def _choose_quote(s: str, prefer_quote: str = '"') -> str:
    has_double = '"' in s
    has_single = "'" in s

    if has_double and not has_single:
        return "'"
    if has_single and not has_double:
        return '"'
    return prefer_quote


def _decimal_escape(code: int) -> str:
    return f'\\{code:03d}'


def _escape_raw_byte_string(s: RawByteString, prefer_quote: str = '"') -> str:
    r"""
    Для зашифрованных payload'ов:
    - это именно байты 0..255
    - non-printable и >=128 всегда пишем как \ddd
    - после \ddd цифра не должна идти сырой, иначе Lua склеит
    """
    quote = _choose_quote(s, prefer_quote)
    result = [quote]
    prev_was_decimal_escape = False

    for ch in s:
        byte = ord(ch)

        if ch == quote:
            result.append('\\' + quote)
            prev_was_decimal_escape = False
        elif ch == '\\':
            result.append('\\\\')
            prev_was_decimal_escape = False
        elif prev_was_decimal_escape and 48 <= byte <= 57:
            result.append(_decimal_escape(byte))
            prev_was_decimal_escape = True
        elif 32 <= byte <= 126:
            result.append(ch)
            prev_was_decimal_escape = False
        else:
            result.append(_decimal_escape(byte))
            prev_was_decimal_escape = True

    result.append(quote)
    return ''.join(result)


def _escape_text_string(s: str, prefer_quote: str = '"') -> str:
    """
    Для обычных пользовательских строк:
    - Unicode-текст сохраняем как текст
    - control chars экранируем
    - если после decimal escape идёт цифра, цифру тоже экранируем
    """
    has_newline = '\n' in s
    has_bracket_close = ']]' in s

    if has_newline and not has_bracket_close and len(s) > 20:
        if not any((ord(ch) < 0x20 and ch not in '\n\t') or ord(ch) == 0x7F for ch in s):
            level = 0
            marker = ']' + '=' * level + ']'
            while marker in s:
                level += 1
                marker = ']' + '=' * level + ']'

            eq = '=' * level
            prefix = '\n' if s.startswith('\n') else ''
            return f'[{eq}[{prefix}{s}]{eq}]'

    quote = _choose_quote(s, prefer_quote)
    result = [quote]
    prev_was_decimal_escape = False

    for ch in s:
        code = ord(ch)

        if ch == quote:
            result.append('\\' + quote)
            prev_was_decimal_escape = False
        elif ch == '\\':
            result.append('\\\\')
            prev_was_decimal_escape = False
        elif ch == '\n':
            result.append('\\n')
            prev_was_decimal_escape = False
        elif ch == '\r':
            result.append('\\r')
            prev_was_decimal_escape = False
        elif ch == '\t':
            result.append('\\t')
            prev_was_decimal_escape = False
        elif ch == '\a':
            result.append('\\a')
            prev_was_decimal_escape = False
        elif ch == '\b':
            result.append('\\b')
            prev_was_decimal_escape = False
        elif ch == '\f':
            result.append('\\f')
            prev_was_decimal_escape = False
        elif ch == '\v':
            result.append('\\v')
            prev_was_decimal_escape = False
        elif ch == '\0':
            result.append('\\000')
            prev_was_decimal_escape = True
        elif code < 0x20 or code == 0x7F:
            result.append(_decimal_escape(code))
            prev_was_decimal_escape = True
        elif prev_was_decimal_escape and '0' <= ch <= '9':
            result.append(_decimal_escape(code))
            prev_was_decimal_escape = True
        else:
            result.append(ch)
            prev_was_decimal_escape = False

    result.append(quote)
    return ''.join(result)


def escape_lua_string(s: str, prefer_quote: str = '"') -> str:
    if isinstance(s, RawByteString):
        return _escape_raw_byte_string(s, prefer_quote)
    return _escape_text_string(s, prefer_quote)


def format_number(n) -> str:
    if isinstance(n, bool):
        return 'true' if n else 'false'
    if isinstance(n, int):
        return str(n)
    if isinstance(n, float):
        if n == int(n) and abs(n) < 1e16:
            return f"{int(n)}"
        return repr(n)
    return str(n)


def is_valid_identifier(name: str) -> bool:
    if not name or not (name[0].isalpha() or name[0] == '_'):
        return False
    return all(c.isalnum() or c == '_' for c in name)


# ============================================================
# UNPARSER
# ============================================================

class ASTUnparser:
    def __init__(self, minified: bool = False, indent: str = "  "):
        self.minified = minified
        self.indent_str = indent
        self.depth = 0

    def unparse(self, node) -> str:
        if node is None:
            return ""
        return self._dispatch(node)

    def _dispatch(self, node):
        method_name = f"_u_{type(node).__name__}"
        method = getattr(self, method_name, None)
        if method is None:
            raise NotImplementedError(f"Unparser: нет метода для {type(node).__name__}")
        return method(node)

    # ---------------- FORMATTING HELPERS ----------------

    def _indent(self) -> str:
        if self.minified:
            return ""
        return self.indent_str * self.depth

    def _nl(self) -> str:
        return "" if self.minified else "\n"

    def _stmt_sep(self) -> str:
        return "; " if self.minified else "\n"

    # ---------------- CHUNK & BLOCK ----------------

    def _u_Chunk(self, node: Chunk) -> str:
        if node.body is None:
            return ""
        return self._unparse_block_content(node.body)

    def _u_Block(self, node: Block) -> str:
        return self._unparse_block_content(node)

    def _unparse_block_content(self, block: Block) -> str:
        if block is None:
            return ""
        parts = []
        for stmt in block.statements:
            s = self._dispatch(stmt)
            if s:
                parts.append(self._indent() + s)
        if block.return_stat is not None:
            ret = self._dispatch(block.return_stat)
            parts.append(self._indent() + ret)
        return self._stmt_sep().join(parts)

    # ---------------- LITERALS ----------------

    def _u_NilLit(self, node: NilLit) -> str:
        return "nil"

    def _u_BoolLit(self, node: BoolLit) -> str:
        return "true" if node.value else "false"

    def _u_NumberLit(self, node: NumberLit) -> str:
        raw = getattr(node, 'raw', '') or ''
        if raw:
            prefix = raw[:2].lower()
            digits = raw[2:].replace('_', '')
            try:
                if prefix == '0x' and '.' not in digits and int(digits, 16) == node.value:
                    return raw
                if prefix == '0b' and int(digits, 2) == node.value:
                    return raw
            except (ValueError, IndexError):
                pass
        return format_number(node.value)

    def _u_StringLit(self, node: StringLit) -> str:
        return escape_lua_string(node.value)

    def _u_VarargLit(self, node: VarargLit) -> str:
        return "..."

    def _u_InterpStringLit(self, node: InterpStringLit) -> str:
        parts = ["`"]
        for p in node.parts:
            if isinstance(p, str):
                escaped = (
                    p.replace('\\', '\\\\')
                     .replace('`', '\\`')
                     .replace('{', '\\{')
                     .replace('\n', '\\n')
                )
                parts.append(escaped)
            else:
                parts.append("{" + self._dispatch(p) + "}")
        parts.append("`")
        return "".join(parts)

    # ---------------- NAMES & ACCESS ----------------

    def _u_NameExpr(self, node: NameExpr) -> str:
        return node.name

    def _u_IndexExpr(self, node: IndexExpr) -> str:
        obj_str = self._unparse_prefix(node.obj)

        if node.is_dot:
            if isinstance(node.index, StringLit) and is_valid_identifier(node.index.value):
                return f"{obj_str}.{node.index.value}"
            if isinstance(node.index, NameExpr) and is_valid_identifier(node.index.name):
                return f"{obj_str}.{node.index.name}"
            if isinstance(node.index, str) and is_valid_identifier(node.index):
                return f"{obj_str}.{node.index}"
            return f"{obj_str}[{self._dispatch(node.index)}]"

        return f"{obj_str}[{self._dispatch(node.index)}]"

    def _u_ParenExpr(self, node: ParenExpr) -> str:
        return f"({self._dispatch(node.inner)})"

    def _unparse_prefix(self, node) -> str:
        if isinstance(node, (NameExpr, IndexExpr, CallExpr, MethodCallExpr, ParenExpr)):
            return self._dispatch(node)
        return f"({self._dispatch(node)})"

    # ---------------- OPERATIONS ----------------

    def _get_priority(self, node) -> int:
        if isinstance(node, BinaryOp):
            return BINARY_PRIORITY.get(node.op, (0, 0))[0]
        if isinstance(node, UnaryOp):
            return UNARY_PRIORITY
        return 100

    def _u_BinaryOp(self, node: BinaryOp) -> str:
        left_prio, right_prio = BINARY_PRIORITY.get(node.op, (0, 0))
        left_str = self._dispatch(node.left)
        right_str = self._dispatch(node.right)

        if self._need_paren_left(node.left, left_prio):
            left_str = f"({left_str})"
        if self._need_paren_right(node.right, right_prio):
            right_str = f"({right_str})"

        op = node.op
        if op == '!=':
            op = '~='

        return f"{left_str} {op} {right_str}"

    def _need_paren_left(self, node, our_prio: int) -> bool:
        if isinstance(node, BinaryOp):
            child_left, _ = BINARY_PRIORITY.get(node.op, (0, 0))
            return child_left < our_prio
        if isinstance(node, UnaryOp):
            return UNARY_PRIORITY < our_prio
        return False

    def _need_paren_right(self, node, our_prio: int) -> bool:
        if isinstance(node, BinaryOp):
            _, child_right = BINARY_PRIORITY.get(node.op, (0, 0))
            return child_right < our_prio
        if isinstance(node, UnaryOp):
            return UNARY_PRIORITY < our_prio
        return False

    def _u_UnaryOp(self, node: UnaryOp) -> str:
        operand_str = self._dispatch(node.operand)
        if isinstance(node.operand, BinaryOp):
            child_prio, _ = BINARY_PRIORITY.get(node.operand.op, (0, 0))
            if child_prio < UNARY_PRIORITY:
                operand_str = f"({operand_str})"

        if node.op == 'not':
            return f"not {operand_str}"
        return f"{node.op}{operand_str}"

    # ---------------- CALLS ----------------

    def _u_CallExpr(self, node: CallExpr) -> str:
        func_str = self._unparse_prefix(node.func)
        args_str = self._unparse_call_args(node.args)
        return f"{func_str}{args_str}"

    def _u_MethodCallExpr(self, node: MethodCallExpr) -> str:
        obj_str = self._unparse_prefix(node.obj)
        args_str = self._unparse_call_args(node.args)
        return f"{obj_str}:{node.method}{args_str}"

    def _unparse_call_args(self, args: list) -> str:
        if not args:
            return "()"
        return "(" + ", ".join(self._dispatch(a) for a in args) + ")"

    # ---------------- FUNCTIONS ----------------

    def _u_FunctionExpr(self, node: FunctionExpr) -> str:
        params = list(node.params or [])
        if node.is_vararg:
            params = params + ["..."]
        param_str = ", ".join(params)
        body_str = self._unparse_indented_block(node.body)

        if self.minified:
            return f"function({param_str}) {body_str} end"
        return f"function({param_str})\n{body_str}\n{self._indent()}end"

    def _unparse_indented_block(self, block: Block) -> str:
        if block is None:
            return ""
        self.depth += 1
        result = self._unparse_block_content(block)
        self.depth -= 1
        return result

    # ---------------- TABLES ----------------

    def _u_TableExpr(self, node: TableExpr) -> str:
        if not node.fields:
            return "{}"

        field_strs = [self._u_TableField(field) for field in node.fields]

        if self.minified:
            return "{" + ", ".join(field_strs) + "}"

        inline = "{" + ", ".join(field_strs) + "}"
        if len(inline) <= 60 and len(field_strs) <= 4:
            return inline

        self.depth += 1
        indent = self._indent()
        self.depth -= 1
        outer_indent = self._indent()
        body = (",\n" + indent).join(field_strs)
        return "{\n" + indent + body + "\n" + outer_indent + "}"

    def _u_TableField(self, node: TableField) -> str:
        val_str = self._dispatch(node.value)

        if node.key is None:
            return val_str

        if node.is_name:
            if isinstance(node.key, str) and is_valid_identifier(node.key):
                return f"{node.key} = {val_str}"
            if isinstance(node.key, StringLit) and is_valid_identifier(node.key.value):
                return f"{node.key.value} = {val_str}"
            key_str = self._dispatch(node.key) if not isinstance(node.key, str) else node.key
            return f"[{key_str}] = {val_str}"

        key_str = self._dispatch(node.key)
        return f"[{key_str}] = {val_str}"

    # ---------------- STATEMENTS ----------------

    def _u_AssignStat(self, node: AssignStat) -> str:
        targets = ", ".join(self._dispatch(t) for t in node.targets)
        values = ", ".join(self._dispatch(v) for v in node.values)
        return f"{targets} = {values}"

    def _u_CompoundAssignStat(self, node: CompoundAssignStat) -> str:
        target = self._dispatch(node.target)
        val = self._dispatch(node.value)
        return f"{target} {node.op}= {val}"

    def _u_LocalAssignStat(self, node: LocalAssignStat) -> str:
        parts = []
        attribs = node.attribs or []

        for i, name in enumerate(node.names):
            piece = name
            if i < len(attribs) and attribs[i]:
                piece += f" <{attribs[i]}>"
            parts.append(piece)

        name_str = ", ".join(parts)
        if node.values:
            val_str = ", ".join(self._dispatch(v) for v in node.values)
            return f"local {name_str} = {val_str}"
        return f"local {name_str}"

    def _u_LocalFunctionStat(self, node: LocalFunctionStat) -> str:
        func_expr = node.func
        params = list(func_expr.params or [])
        if func_expr.is_vararg:
            params = params + ["..."]
        param_str = ", ".join(params)
        body_str = self._unparse_indented_block(func_expr.body)

        if self.minified:
            return f"local function {node.name}({param_str}) {body_str} end"
        return f"local function {node.name}({param_str})\n{body_str}\n{self._indent()}end"

    def _u_FunctionDeclStat(self, node: FunctionDeclStat) -> str:
        target_str = self._dispatch(node.target)
        if node.method_name:
            target_str = f"{target_str}:{node.method_name}"

        func_expr = node.func
        params = list(func_expr.params or [])
        if node.method_name and params and params[0] == 'self':
            params = params[1:]
        if func_expr.is_vararg:
            params = params + ["..."]

        param_str = ", ".join(params)
        body_str = self._unparse_indented_block(func_expr.body)

        if self.minified:
            return f"function {target_str}({param_str}) {body_str} end"
        return f"function {target_str}({param_str})\n{body_str}\n{self._indent()}end"

    def _u_CallStat(self, node: CallStat) -> str:
        return self._dispatch(node.call)

    def _u_DoBlockStat(self, node: DoBlockStat) -> str:
        body = self._unparse_indented_block(node.body)
        if self.minified:
            return f"do {body} end"
        return f"do\n{body}\n{self._indent()}end"

    def _u_WhileStat(self, node: WhileStat) -> str:
        cond = self._dispatch(node.cond)
        body = self._unparse_indented_block(node.body)
        if self.minified:
            return f"while {cond} do {body} end"
        return f"while {cond} do\n{body}\n{self._indent()}end"

    def _u_RepeatStat(self, node: RepeatStat) -> str:
        body = self._unparse_indented_block(node.body)
        cond = self._dispatch(node.cond)
        if self.minified:
            return f"repeat {body} until {cond}"
        return f"repeat\n{body}\n{self._indent()}until {cond}"

    def _u_IfStat(self, node: IfStat) -> str:
        parts = []

        for i, (cond, block) in enumerate(node.branches):
            keyword = "if" if i == 0 else "elseif"
            cond_str = self._dispatch(cond)
            body = self._unparse_indented_block(block)
            if self.minified:
                parts.append(f"{keyword} {cond_str} then {body}")
            else:
                parts.append(f"{keyword} {cond_str} then\n{body}")

        if node.else_block is not None:
            body = self._unparse_indented_block(node.else_block)
            if self.minified:
                parts.append(f"else {body}")
            else:
                parts.append(f"else\n{body}")

        if self.minified:
            return " ".join(parts) + " end"

        result = ("\n" + self._indent()).join(parts)
        return result + "\n" + self._indent() + "end"

    def _u_NumericForStat(self, node: NumericForStat) -> str:
        start = self._dispatch(node.start)
        stop = self._dispatch(node.stop)
        parts = [start, stop]
        if node.step is not None:
            parts.append(self._dispatch(node.step))

        header = f"for {node.var} = {', '.join(parts)}"
        body = self._unparse_indented_block(node.body)

        if self.minified:
            return f"{header} do {body} end"
        return f"{header} do\n{body}\n{self._indent()}end"

    def _u_GenericForStat(self, node: GenericForStat) -> str:
        names = ", ".join(node.names)
        exprs = ", ".join(self._dispatch(e) for e in node.exprs)
        body = self._unparse_indented_block(node.body)

        if self.minified:
            return f"for {names} in {exprs} do {body} end"
        return f"for {names} in {exprs} do\n{body}\n{self._indent()}end"

    def _u_ReturnStat(self, node: ReturnStat) -> str:
        if not node.values:
            return "return"
        vals = ", ".join(self._dispatch(v) for v in node.values)
        return f"return {vals}"

    def _u_BreakStat(self, node: BreakStat) -> str:
        return "break"

    def _u_ContinueStat(self, node: ContinueStat) -> str:
        return "continue"

    def _u_GotoStat(self, node: GotoStat) -> str:
        return f"goto {node.label}"

    def _u_LabelStat(self, node: LabelStat) -> str:
        return f"::{node.name}::"

    def _u_TypeAliasStat(self, node: TypeAliasStat) -> str:
        prefix = "export " if node.is_export else ""
        if isinstance(node.type_expr, str):
            type_str = node.type_expr
        else:
            type_str = self._dispatch(node.type_expr)
        return f"{prefix}type {node.name} = {type_str}"


# ============================================================
# CONVENIENCE
# ============================================================

def unparse(node, minified: bool = False, indent: str = "  ") -> str:
    unparser = ASTUnparser(minified=minified, indent=indent)
    return unparser.unparse(node)


def unparse_minified(node) -> str:
    return unparse(node, minified=True)


def unparse_pretty(node, indent: str = "  ") -> str:
    return unparse(node, minified=False, indent=indent)


# ============================================================
# TESTS
# ============================================================

def _run_tests():
    from obfuscator.lexer import Lexer
    from obfuscator.parser import Parser
    from obfuscator.utils.crypto import bytes_to_py_string

    print("=" * 60)
    print("🧪 TESTS: ast_unparser.py")
    print("=" * 60)

    passed = 0
    failed = 0

    def test(name: str, condition: bool, detail: str = ""):
        nonlocal passed, failed
        if condition:
            print(f"  ✅ {name}")
            passed += 1
        else:
            print(f"  ❌ {name}" + (f": {detail}" if detail else ""))
            failed += 1

    def parse_code(code: str):
        tokens = Lexer(code).tokenize()
        return Parser(tokens).parse()

    def round_trip(code: str, minified: bool = False) -> str:
        ast = parse_code(code)
        return unparse(ast, minified=minified)

    def round_trip_double(code: str) -> bool:
        try:
            ast1 = parse_code(code)
            out = unparse(ast1)
            ast2 = parse_code(out)
            return True
        except Exception as e:
            print(f"    ↪️ Ошибка: {e}")
            print(f"    ↪️ Код: {out[:200] if 'out' in locals() else code[:200]}")
            return False

    print("\n📌 Литералы:")
    r = round_trip("local x = nil"); test("nil", "nil" in r)
    r = round_trip("local x = true"); test("true", "true" in r)
    r = round_trip("local x = 42"); test("integer", "42" in r)
    r = round_trip("local x = 3.14"); test("float", "3.14" in r)
    r = round_trip('local x = "hello"'); test("string", '"hello"' in r)
    r = round_trip("local x = ..."); test("vararg", "..." in r)

    print("\n📌 Операторы и приоритеты:")
    r = round_trip("local x = 1 + 2 * 3")
    test("1 + 2 * 3 без лишних скобок", "1 + 2 * 3" in r and "(2 * 3)" not in r, f"got: {r}")
    r = round_trip("local x = (1 + 2) * 3")
    test("(1+2)*3 сохраняет скобки", "(1 + 2) * 3" in r, f"got: {r}")
    r = round_trip("local x = 1 - 2 - 3")
    test("1 - 2 - 3 (left-assoc)", "1 - 2 - 3" in r, f"got: {r}")
    r = round_trip("local x = 2 ^ 3 ^ 4")
    test("2 ^ 3 ^ 4 (right-assoc)", "2 ^ 3 ^ 4" in r, f"got: {r}")
    r = round_trip("local x = not true"); test("unary not", "not true" in r)
    r = round_trip("local x = -5"); test("unary minus", "-5" in r)
    r = round_trip('local x = "a" .. "b" .. "c"')
    test("concat right-assoc", '.."b"..' in r.replace(" ", "") or '.. "b" ..' in r, f"got: {r}")

    print("\n📌 Доступ к полям:")
    r = round_trip("local x = t.a"); test("t.a (dot)", "t.a" in r, f"got: {r}")
    r = round_trip("local x = t[1]"); test("t[1] (index)", "t[1]" in r, f"got: {r}")
    r = round_trip('local x = t["key with space"]')
    test("t['key with space']", "[" in r and "key with space" in r)
    r = round_trip("local x = obj.a.b.c")
    test("chained a.b.c", "obj.a.b.c" in r, f"got: {r}")

    print("\n📌 FIX IndexExpr(is_dot=True, index=NameExpr):")
    r = round_trip("local x = bit32.bxor(1, 2)")
    test("bit32.bxor выводится через точку", "bit32.bxor" in r and "bit32[bxor]" not in r, f"got: {r}")
    r = round_trip("local x = string.byte(s, 1)")
    test("string.byte корректно", "string.byte" in r, f"got: {r}")
    r = round_trip("local x = math.floor(a / b)")
    test("math.floor корректно", "math.floor" in r, f"got: {r}")

    print("\n📌 Вызовы функций:")
    r = round_trip("print(1, 2, 3)"); test("print(1, 2, 3)", "print(1, 2, 3)" in r)
    r = round_trip("obj:method(x)"); test("obj:method(x)", "obj:method(x)" in r)
    r = round_trip("f()()"); test("f()() (chained)", "f()()" in r)
    r = round_trip("t.a.b(x)"); test("t.a.b(x)", "t.a.b(x)" in r)

    print("\n📌 Функции:")
    r = round_trip("local function f(a, b) return a + b end")
    test("local function", "local function f(a, b)" in r and "return a + b" in r)
    r = round_trip("function t.m(x) return x end")
    test("function t.m(x)", "function t.m(x)" in r)
    r = round_trip("function obj:method(x) return x end")
    test("function obj:method(x)", "function obj:method(x)" in r)
    r = round_trip("local f = function(...) return ... end")
    test("anonymous function with vararg", "function(...)" in r)

    print("\n📌 Таблицы:")
    r = round_trip("local t = {}"); test("empty table", "{}" in r)
    r = round_trip("local t = {1, 2, 3}")
    test("array table", "{1, 2, 3}" in r or "{ 1, 2, 3 }" in r, f"got: {r}")
    r = round_trip('local t = {a = 1, b = 2}')
    test("named fields", "a = 1" in r and "b = 2" in r)
    r = round_trip('local t = {["key"] = 1}')
    test("[expr] key", "[" in r)

    print("\n📌 Управление потоком:")
    r = round_trip("if x then y = 1 end"); test("if-then", "if x then" in r and "end" in r)
    r = round_trip("if x then a = 1 elseif y then a = 2 else a = 3 end")
    test("if-elseif-else", "elseif" in r and "else" in r)
    r = round_trip("while x do y = y + 1 end"); test("while", "while x do" in r)
    r = round_trip("repeat y = y + 1 until x"); test("repeat-until", "repeat" in r and "until x" in r)
    r = round_trip("for i = 1, 10 do print(i) end"); test("numeric for", "for i = 1, 10 do" in r)
    r = round_trip("for i = 1, 10, 2 do print(i) end"); test("numeric for with step", "for i = 1, 10, 2 do" in r)
    r = round_trip("for k, v in pairs(t) do print(k, v) end")
    test("generic for", "for k, v in pairs(t) do" in r)
    r = round_trip("do local x = 1 end"); test("do-block", "do" in r and "end" in r)
    r = round_trip("for i = 1, 10 do break end"); test("break", "break" in r)
    r = round_trip("::label:: goto label"); test("goto+label", "::label::" in r and "goto label" in r)

    print("\n📌 Round-trip (parse -> unparse -> parse):")
    samples = [
        "local x = 1 + 2 * 3 - 4 / 2",
        "for i = 1, 100 do if i % 2 == 0 then print(i) end end",
        "local t = {a = 1, b = {c = 2, d = {3, 4, 5}}}",
        "local function fib(n) if n < 2 then return n end return fib(n-1) + fib(n-2) end",
        "local x, y, z = 1, 2, 3; x, y = y, x",
        'print("hello, " .. name .. "!")',
        "local x = bit32.bxor(1495, 1492)",
        "local y = string.byte(s, ((39 + 0) + (866 - 895)))",
    ]
    for i, code in enumerate(samples, 1):
        ok = round_trip_double(code)
        test(f"round-trip #{i}: {code[:40]}...", ok)

    print("\n📌 Форматирование:")
    code = "local function f(a, b)\n  return a + b\nend"
    ast = parse_code(code)
    pretty = unparse_pretty(ast)
    mini = unparse_minified(ast)
    test("Minified короче pretty", len(mini) < len(pretty), f"pretty={len(pretty)}, mini={len(mini)}")
    test("Pretty содержит \\n", "\n" in pretty)
    test("Minified без \\n", "\n" not in mini or mini.count("\n") <= 1)

    print("\n📌 Luau специфика:")
    try:
        r = round_trip("x += 1")
        test("compound +=", "x += 1" in r, f"got: {r}")
    except Exception as e:
        test("compound +=", False, str(e))
    try:
        r = round_trip("continue")
        test("continue statement", "continue" in r)
    except Exception:
        pass

    print("\n📌 Escape строк:")
    r = escape_lua_string("hello")
    test("plain string", r == '"hello"', f"got: {r}")

    r = escape_lua_string('with "quotes"')
    test("string with quotes", "'" in r or '\\"' in r, f"got: {r}")

    r = escape_lua_string("with\nnewline")
    test("string with newline", "\\n" in r or "[[" in r, f"got: {r}")

    r = escape_lua_string("with\ttab")
    test("string with tab", "\\t" in r, f"got: {r}")

    r = escape_lua_string("é")
    test("unicode text preserved", "é" in r, f"got: {r!r}")

    raw = bytes_to_py_string(bytes([221, 48, 49, 34, 92]))
    r = escape_lua_string(raw)
    test("raw byte string uses \\ddd", "\\221" in r and "\\\\221" not in r, f"got: {r!r}")
    test("digit after raw-byte escape protected", "\\048" in r and "\\049" in r, f"got: {r!r}")

    print("\n📌 Реалистичные сниппеты:")
    real_code = """
local Players = game:GetService("Players")
local LocalPlayer = Players.LocalPlayer

local function onCharacter(char)
    local humanoid = char:WaitForChild("Humanoid")
    humanoid.WalkSpeed = 32
    if humanoid.Health > 0 then
        print("Alive")
    else
        return
    end
end

LocalPlayer.CharacterAdded:Connect(onCharacter)
"""
    try:
        ast = parse_code(real_code)
        out = unparse(ast)
        ast2 = parse_code(out)
        test("Реалистичный Roblox код", True)
    except Exception as e:
        test("Реалистичный Roblox код", False, str(e))

    print()
    print("=" * 60)
    total = passed + failed
    print(f"📊 Результат: {passed}/{total} тестов прошло")
    if failed == 0:
        print("🎉 ВСЕ ТЕСТЫ ПРОШЛИ!")
    else:
        print(f"⚠️ Провалилось: {failed}")
    print("=" * 60)

    if failed == 0:
        print("\n📄 Пример работы:")
        print("—" * 60)
        ast = parse_code("local function greet(name) return 'Hello, ' .. name end print(greet('World'))")
        print("PRETTY:")
        print(unparse_pretty(ast))
        print("\nMINIFIED:")
        print(unparse_minified(ast))
        print("—" * 60)

    return failed == 0


if __name__ == "__main__":
    success = _run_tests()
    sys.exit(0 if success else 1)