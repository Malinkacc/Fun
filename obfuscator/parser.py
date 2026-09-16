"""
NZL Studio Obfuscator - Parser
Recursive descent parser for Lua 5.1 + Luau

Turns a token stream (from lexer.py) into an AST (ast_nodes.py).

Features:
    - Full Lua 5.1 grammar
    - Luau extensions:
        * compound assignments (+=, -=, *=, /=, //=, %=, ^=, ..=)
        * continue statement
        * string interpolation `hello ${x}`
        * type annotations (parsed but stored as raw strings)
        * type aliases (type X = ...)
        * generic function types <T>
        * integer division //
    - Operator precedence table
    - Meaningful error messages with line/column
"""

from typing import List, Optional, Tuple
from .lexer import Token, TokenType, Lexer, LexerError
from .ast_nodes import *


# ==================== ПРИОРИТЕТЫ ОПЕРАТОРОВ ====================
BINARY_PRECEDENCE = {
    TokenType.OR:        (1, 1),
    TokenType.AND:       (2, 2),
    TokenType.LT:        (3, 3),
    TokenType.GT:        (3, 3),
    TokenType.LEQ:       (3, 3),
    TokenType.GEQ:       (3, 3),
    TokenType.EQ:        (3, 3),
    TokenType.NEQ:       (3, 3),
    TokenType.CONCAT:    (9, 8),
    TokenType.PLUS:      (10, 10),
    TokenType.MINUS:     (10, 10),
    TokenType.STAR:      (11, 11),
    TokenType.SLASH:     (11, 11),
    TokenType.DSLASH:    (11, 11),
    TokenType.PERCENT:   (11, 11),
    TokenType.CARET:     (14, 13),
}

UNARY_PRECEDENCE = 12

BIN_OP_STRINGS = {
    TokenType.OR: 'or',
    TokenType.AND: 'and',
    TokenType.LT: '<',
    TokenType.GT: '>',
    TokenType.LEQ: '<=',
    TokenType.GEQ: '>=',
    TokenType.EQ: '==',
    TokenType.NEQ: '~=',
    TokenType.CONCAT: '..',
    TokenType.PLUS: '+',
    TokenType.MINUS: '-',
    TokenType.STAR: '*',
    TokenType.SLASH: '/',
    TokenType.DSLASH: '//',
    TokenType.PERCENT: '%',
    TokenType.CARET: '^',
}

UNARY_OP_STRINGS = {
    TokenType.MINUS: '-',
    TokenType.NOT: 'not',
    TokenType.HASH: '#',
}

COMPOUND_ASSIGN_OPS = {
    TokenType.PLUS_ASSIGN: '+',
    TokenType.MINUS_ASSIGN: '-',
    TokenType.STAR_ASSIGN: '*',
    TokenType.SLASH_ASSIGN: '/',
    TokenType.DSLASH_ASSIGN: '//',
    TokenType.PERCENT_ASSIGN: '%',
    TokenType.CARET_ASSIGN: '^',
    TokenType.CONCAT_ASSIGN: '..',
}

# ==================== CONTEXTUAL KEYWORDS ====================
# Эти токены могут использоваться как обычные имена в expression-контексте.
# В Luau: type, continue, export — не жёсткие зарезервированные слова.
CONTEXTUAL_KEYWORDS = {
    TokenType.TYPE,
    TokenType.EXPORT,
    TokenType.CONTINUE,  # в expr-контексте (хотя как стейтмент — особый)
}


# ==================== ИСКЛЮЧЕНИЯ ====================

class ParserError(Exception):
    def __init__(self, message, line, column):
        self.message = message
        self.line = line
        self.column = column
        super().__init__(f"[Parser] Line {line}:{column}: {message}")


# ==================== ПАРСЕР ====================

class Parser:
    """Recursive descent parser для Lua/Luau"""

    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.pos = 0

    # ---------- Утилиты ----------

    def _peek(self, offset: int = 0) -> Token:
        p = self.pos + offset
        if p >= len(self.tokens):
            return self.tokens[-1]
        return self.tokens[p]

    def _current(self) -> Token:
        return self._peek(0)

    def _advance(self) -> Token:
        tok = self._current()
        if tok.type != TokenType.EOF:
            self.pos += 1
        return tok

    def _check(self, *types: TokenType) -> bool:
        return self._current().type in types

    def _match(self, *types: TokenType) -> Optional[Token]:
        if self._check(*types):
            return self._advance()
        return None

    def _expect(self, type: TokenType, message: str = None) -> Token:
        if self._check(type):
            return self._advance()
        tok = self._current()
        msg = message or f"Expected {type.name}, got {tok.type.name}"
        self._error(msg)

    def _error(self, message: str):
        tok = self._current()
        raise ParserError(message, tok.line, tok.column)

    def _is_block_end(self) -> bool:
        return self._check(
            TokenType.END, TokenType.ELSE, TokenType.ELSEIF,
            TokenType.UNTIL, TokenType.EOF
        )

    def _is_contextual_keyword(self) -> bool:
        """Текущий токен — contextual keyword (может быть именем в expr)"""
        return self._current().type in CONTEXTUAL_KEYWORDS

    def _try_consume_as_name(self) -> Optional[Token]:
        """
        Пытается съесть текущий токен как имя.
        Работает для NAME и contextual keywords (type, export, continue).
        Возвращает токен с type=NAME (мутирует копию) или None.
        """
        tok = self._current()
        if tok.type == TokenType.NAME:
            return self._advance()
        if tok.type in CONTEXTUAL_KEYWORDS:
            self._advance()
            # Возвращаем «как будто NAME» — value уже содержит строку
            return tok
        return None

    # ==================== ГЛАВНЫЙ МЕТОД ====================

    def parse(self) -> Chunk:
        line = self._current().line
        body = self._parse_block()
        self._expect(TokenType.EOF, "Expected end of file")
        return Chunk(line=line, body=body)

    # ==================== БЛОК И СТЕЙТМЕНТЫ ====================

    def _parse_block(self) -> Block:
        line = self._current().line
        statements = []
        return_stat = None

        while not self._is_block_end():
            if self._check(TokenType.RETURN):
                return_stat = self._parse_return()
                self._match(TokenType.SEMICOLON)
                break

            stat = self._parse_statement()
            if stat is not None:
                statements.append(stat)

        return Block(line=line, statements=statements, return_stat=return_stat)

    def _parse_statement(self) -> Optional[Stat]:
        tok = self._current()

        if self._match(TokenType.SEMICOLON):
            return None

        if tok.type == TokenType.LOCAL:
            return self._parse_local()
        if tok.type == TokenType.IF:
            return self._parse_if()
        if tok.type == TokenType.WHILE:
            return self._parse_while()
        if tok.type == TokenType.FOR:
            return self._parse_for()
        if tok.type == TokenType.REPEAT:
            return self._parse_repeat()
        if tok.type == TokenType.FUNCTION:
            return self._parse_function_decl()
        if tok.type == TokenType.DO:
            return self._parse_do_block()
        if tok.type == TokenType.BREAK:
            self._advance()
            return BreakStat(line=tok.line)
        if tok.type == TokenType.GOTO:
            self._advance()
            name = self._expect(TokenType.NAME, "Expected label name after 'goto'")
            return GotoStat(line=tok.line, label=name.value)
        if tok.type == TokenType.DCOLON:
            return self._parse_label()

        # CONTINUE: в statement-контексте — ContinueStat
        # НО только если это одиночный continue (не continue(...) вызов)
        if tok.type == TokenType.CONTINUE:
            # Если следующий токен — '(' значит это вызов функции continue(...)
            # Иначе — оператор continue
            if self._peek(1).type != TokenType.LPAREN:
                self._advance()
                return ContinueStat(line=tok.line)
            # Иначе падаем в _parse_expr_statement ниже

        # Luau: export type Name = ...
        if tok.type == TokenType.EXPORT and self._peek(1).type == TokenType.TYPE:
            return self._parse_type_alias(is_export=True)

        # Luau: type Name = ... (только если это реально type alias, не вызов type())
        if tok.type == TokenType.TYPE:
            return self._try_parse_type_alias_or_expr()

        # Иначе — присваивание или вызов функции
        return self._parse_expr_statement()

    def _try_parse_type_alias_or_expr(self) -> Stat:
        """
        Токен TYPE в начале стейтмента.
        Если паттерн: type <NAME> = ...  или  type <NAME> < ...
        → это type alias.
        Иначе → это вызов функции type(...), парсим как expr statement.
        """
        # type <NAME> (= | <)  → type alias
        next1 = self._peek(1)
        next2 = self._peek(2)

        if (next1.type == TokenType.NAME and
                next2.type in (TokenType.ASSIGN, TokenType.LT)):
            return self._parse_type_alias(is_export=False)

        # Иначе: type используется как имя функции → expr statement
        return self._parse_expr_statement()

    # ---------- local ----------

    def _parse_local(self) -> Stat:
        line = self._current().line
        self._advance()  # local

        if self._match(TokenType.FUNCTION):
            name = self._expect(TokenType.NAME, "Expected function name")
            func = self._parse_function_body()
            return LocalFunctionStat(line=line, name=name.value, func=func)

        names = []
        attribs = []

        while True:
            name = self._expect(TokenType.NAME, "Expected variable name")
            names.append(name.value)

            attrib = None
            if self._match(TokenType.LT):
                attr_name = self._expect(TokenType.NAME, "Expected attribute name")
                self._expect(TokenType.GT, "Expected '>' after attribute")
                attrib = attr_name.value
            attribs.append(attrib)

            if self._match(TokenType.COLON):
                self._skip_type()

            if not self._match(TokenType.COMMA):
                break

        values = []
        if self._match(TokenType.ASSIGN):
            values = self._parse_expr_list()

        return LocalAssignStat(line=line, names=names, values=values, attribs=attribs)

    # ---------- if ----------

    def _parse_if(self) -> IfStat:
        line = self._current().line
        self._advance()  # if

        branches = []

        cond = self._parse_expression()
        self._expect(TokenType.THEN, "Expected 'then' after if condition")
        body = self._parse_block()
        branches.append((cond, body))

        while self._match(TokenType.ELSEIF):
            cond = self._parse_expression()
            self._expect(TokenType.THEN, "Expected 'then' after elseif condition")
            body = self._parse_block()
            branches.append((cond, body))

        else_block = None
        if self._match(TokenType.ELSE):
            else_block = self._parse_block()

        self._expect(TokenType.END, "Expected 'end' to close if")
        return IfStat(line=line, branches=branches, else_block=else_block)

    # ---------- while ----------

    def _parse_while(self) -> WhileStat:
        line = self._current().line
        self._advance()  # while
        cond = self._parse_expression()
        self._expect(TokenType.DO, "Expected 'do' after while condition")
        body = self._parse_block()
        self._expect(TokenType.END, "Expected 'end' to close while")
        return WhileStat(line=line, cond=cond, body=body)

    # ---------- repeat ----------

    def _parse_repeat(self) -> RepeatStat:
        line = self._current().line
        self._advance()  # repeat
        body = self._parse_block()
        self._expect(TokenType.UNTIL, "Expected 'until' after repeat body")
        cond = self._parse_expression()
        return RepeatStat(line=line, body=body, cond=cond)

    # ---------- for ----------

    def _parse_for(self) -> Stat:
        line = self._current().line
        self._advance()  # for

        first_name = self._expect(TokenType.NAME, "Expected variable name after 'for'")

        if self._match(TokenType.ASSIGN):
            start = self._parse_expression()
            self._expect(TokenType.COMMA, "Expected ',' in numeric for")
            stop = self._parse_expression()
            step = None
            if self._match(TokenType.COMMA):
                step = self._parse_expression()
            self._expect(TokenType.DO, "Expected 'do' in for")
            body = self._parse_block()
            self._expect(TokenType.END, "Expected 'end' to close for")
            return NumericForStat(
                line=line, var=first_name.value,
                start=start, stop=stop, step=step, body=body
            )

        names = [first_name.value]
        while self._match(TokenType.COMMA):
            n = self._expect(TokenType.NAME, "Expected variable name")
            names.append(n.value)
            if self._match(TokenType.COLON):
                self._skip_type()

        self._expect(TokenType.IN, "Expected 'in' in generic for")
        exprs = self._parse_expr_list()
        self._expect(TokenType.DO, "Expected 'do' in for")
        body = self._parse_block()
        self._expect(TokenType.END, "Expected 'end' to close for")
        return GenericForStat(line=line, names=names, exprs=exprs, body=body)

    # ---------- function declaration ----------

    def _parse_function_decl(self) -> FunctionDeclStat:
        line = self._current().line
        self._advance()  # function

        name_tok = self._expect(TokenType.NAME, "Expected function name")
        target = NameExpr(line=name_tok.line, name=name_tok.value)

        while self._match(TokenType.DOT):
            field = self._expect(TokenType.NAME, "Expected field name after '.'")
            target = IndexExpr(
                line=field.line, obj=target,
                index=StringLit(line=field.line, value=field.value),
                is_dot=True
            )

        method_name = None
        if self._match(TokenType.COLON):
            method_tok = self._expect(TokenType.NAME, "Expected method name after ':'")
            method_name = method_tok.value

        func = self._parse_function_body(is_method=(method_name is not None))
        return FunctionDeclStat(
            line=line, target=target, method_name=method_name, func=func
        )

    # ---------- do block ----------

    def _parse_do_block(self) -> DoBlockStat:
        line = self._current().line
        self._advance()  # do
        body = self._parse_block()
        self._expect(TokenType.END, "Expected 'end' to close do")
        return DoBlockStat(line=line, body=body)

    # ---------- label ----------

    def _parse_label(self) -> LabelStat:
        line = self._current().line
        self._advance()  # ::
        name = self._expect(TokenType.NAME, "Expected label name")
        self._expect(TokenType.DCOLON, "Expected '::' to close label")
        return LabelStat(line=line, name=name.value)

    # ---------- return ----------

    def _parse_return(self) -> ReturnStat:
        line = self._current().line
        self._advance()  # return
        values = []
        if not self._is_block_end() and not self._check(TokenType.SEMICOLON):
            values = self._parse_expr_list()
        return ReturnStat(line=line, values=values)

    # ---------- type alias (Luau) ----------

    def _parse_type_alias(self, is_export: bool) -> TypeAliasStat:
        line = self._current().line
        if is_export:
            self._advance()  # export
        self._advance()  # type
        name = self._expect(TokenType.NAME, "Expected type name")

        if self._match(TokenType.LT):
            self._skip_until_gt()

        self._expect(TokenType.ASSIGN, "Expected '=' in type alias")
        self._skip_type()
        return TypeAliasStat(line=line, name=name.value, type_expr="", is_export=is_export)

    def _skip_type(self):
        """Пропускает type expression (упрощённо)."""
        depth = 0

        while True:
            tok = self._current()

            if tok.type == TokenType.EOF:
                break

            if tok.type in (TokenType.LT, TokenType.LPAREN, TokenType.LBRACE, TokenType.LBRACKET):
                depth += 1
                self._advance()
                continue

            if tok.type in (TokenType.GT, TokenType.RPAREN, TokenType.RBRACE, TokenType.RBRACKET):
                if depth > 0:
                    depth -= 1
                    self._advance()
                    continue
                else:
                    break

            if depth == 0:
                if tok.type in (
                    TokenType.ASSIGN, TokenType.COMMA, TokenType.SEMICOLON,
                    TokenType.DO, TokenType.THEN, TokenType.END, TokenType.LOCAL,
                    TokenType.RETURN, TokenType.IF, TokenType.FOR, TokenType.WHILE,
                    TokenType.FUNCTION, TokenType.ELSE, TokenType.ELSEIF, TokenType.UNTIL,
                    TokenType.IN
                ):
                    break

            self._advance()

    def _skip_until_gt(self):
        depth = 1
        while depth > 0 and not self._check(TokenType.EOF):
            if self._match(TokenType.LT):
                depth += 1
            elif self._match(TokenType.GT):
                depth -= 1
            else:
                self._advance()

    # ---------- expression statement ----------

    def _parse_expr_statement(self) -> Stat:
        line = self._current().line
        first = self._parse_suffixed_expression()

        # Составное присваивание (Luau)
        for tok_type, op_str in COMPOUND_ASSIGN_OPS.items():
            if self._check(tok_type):
                self._advance()
                value = self._parse_expression()
                return CompoundAssignStat(line=line, target=first, op=op_str, value=value)

        # Обычное присваивание
        if self._check(TokenType.ASSIGN) or self._check(TokenType.COMMA):
            targets = [first]
            while self._match(TokenType.COMMA):
                t = self._parse_suffixed_expression()
                targets.append(t)
            self._expect(TokenType.ASSIGN, "Expected '=' in assignment")
            values = self._parse_expr_list()
            return AssignStat(line=line, targets=targets, values=values)

        # Вызов функции
        if isinstance(first, (CallExpr, MethodCallExpr)):
            return CallStat(line=line, call=first)

        self._error("Expected statement (assignment or function call)")

    # ==================== ВЫРАЖЕНИЯ ====================

    def _parse_expr_list(self) -> List[Expr]:
        exprs = [self._parse_expression()]
        while self._match(TokenType.COMMA):
            exprs.append(self._parse_expression())
        return exprs

    def _parse_expression(self) -> Expr:
        return self._parse_subexpr(0)

    def _parse_subexpr(self, min_precedence: int) -> Expr:
        line = self._current().line

        # Унарные операторы
        if self._check(TokenType.MINUS, TokenType.NOT, TokenType.HASH):
            op_tok = self._advance()
            op = UNARY_OP_STRINGS[op_tok.type]
            operand = self._parse_subexpr(UNARY_PRECEDENCE)
            left = UnaryOp(line=line, op=op, operand=operand)
        else:
            left = self._parse_simple_expression()

        # Бинарные операторы
        while True:
            tok = self._current()
            if tok.type not in BINARY_PRECEDENCE:
                break
            left_prec, right_prec = BINARY_PRECEDENCE[tok.type]
            if left_prec < min_precedence:
                break

            self._advance()
            op = BIN_OP_STRINGS[tok.type]
            right = self._parse_subexpr(right_prec + 1)
            left = BinaryOp(line=tok.line, op=op, left=left, right=right)

        return left

    def _parse_simple_expression(self) -> Expr:
        tok = self._current()
        line = tok.line

        if tok.type == TokenType.NUMBER:
            self._advance()
            return NumberLit(line=line, value=tok.value)

        if tok.type == TokenType.STRING:
            self._advance()
            return StringLit(line=line, value=tok.value)

        if tok.type == TokenType.ISTRING:
            self._advance()
            return self._parse_interp_string(tok.value, line)

        if tok.type == TokenType.NIL:
            self._advance()
            return NilLit(line=line)

        if tok.type == TokenType.TRUE:
            self._advance()
            return BoolLit(line=line, value=True)

        if tok.type == TokenType.FALSE:
            self._advance()
            return BoolLit(line=line, value=False)

        if tok.type == TokenType.ELLIPSIS:
            self._advance()
            return VarargLit(line=line)

        if tok.type == TokenType.FUNCTION:
            self._advance()
            return self._parse_function_body(is_method=False)

        if tok.type == TokenType.LBRACE:
            return self._parse_table()

        # Suffixed expression (включая contextual keywords как имена)
        return self._parse_suffixed_expression()

    def _parse_suffixed_expression(self) -> Expr:
        """
        primary_expr (. NAME | [ expr ] | : NAME args | args)*
        primary_expr: NAME / contextual_keyword / ( expr )
        """
        line = self._current().line

        # Primary
        if self._match(TokenType.LPAREN):
            inner = self._parse_expression()
            self._expect(TokenType.RPAREN, "Expected ')'")
            expr = ParenExpr(line=line, inner=inner)
        else:
            # ⭐ ФИКС: принимаем NAME и contextual keywords как имена
            name_tok = self._try_consume_as_name()
            if name_tok is not None:
                expr = NameExpr(line=name_tok.line, name=name_tok.value)
            else:
                self._error(f"Unexpected token: {self._current().type.name}")

        # Суффиксы
        while True:
            tok = self._current()

            if tok.type == TokenType.DOT:
                self._advance()
                # После точки тоже могут быть contextual keywords как поля
                field_tok = self._try_consume_as_name()
                if field_tok is None:
                    self._error("Expected field name after '.'")
                expr = IndexExpr(
                    line=field_tok.line, obj=expr,
                    index=StringLit(line=field_tok.line, value=field_tok.value),
                    is_dot=True
                )
            elif tok.type == TokenType.LBRACKET:
                self._advance()
                index = self._parse_expression()
                self._expect(TokenType.RBRACKET, "Expected ']'")
                expr = IndexExpr(line=tok.line, obj=expr, index=index, is_dot=False)
            elif tok.type == TokenType.COLON:
                self._advance()
                method_tok = self._try_consume_as_name()
                if method_tok is None:
                    self._error("Expected method name after ':'")
                args = self._parse_call_args()
                expr = MethodCallExpr(
                    line=method_tok.line, obj=expr,
                    method=method_tok.value, args=args
                )
            elif tok.type in (TokenType.LPAREN, TokenType.STRING, TokenType.LBRACE):
                args = self._parse_call_args()
                expr = CallExpr(line=tok.line, func=expr, args=args)
            elif tok.type == TokenType.ISTRING:
                # f`interpolated` — вызов с интерп. строкой
                self._advance()
                interp = self._parse_interp_string(tok.value, tok.line)
                expr = CallExpr(line=tok.line, func=expr, args=[interp])
            else:
                break

        return expr

    def _parse_call_args(self) -> List[Expr]:
        tok = self._current()

        if tok.type == TokenType.LPAREN:
            self._advance()
            args = []
            if not self._check(TokenType.RPAREN):
                args = self._parse_expr_list()
            self._expect(TokenType.RPAREN, "Expected ')' in function call")
            return args

        if tok.type == TokenType.STRING:
            self._advance()
            return [StringLit(line=tok.line, value=tok.value)]

        if tok.type == TokenType.LBRACE:
            return [self._parse_table()]

        self._error("Expected function arguments")

    # ---------- function body ----------

    def _parse_function_body(self, is_method: bool = False) -> FunctionExpr:
        line = self._current().line

        if self._match(TokenType.LT):
            self._skip_until_gt()

        self._expect(TokenType.LPAREN, "Expected '(' in function definition")

        params = []
        is_vararg = False

        if is_method:
            params.append("self")

        if not self._check(TokenType.RPAREN):
            while True:
                if self._match(TokenType.ELLIPSIS):
                    is_vararg = True
                    if self._match(TokenType.COLON):
                        self._skip_type()
                    break

                name = self._expect(TokenType.NAME, "Expected parameter name")
                params.append(name.value)

                if self._match(TokenType.COLON):
                    self._skip_type()

                if not self._match(TokenType.COMMA):
                    break

        self._expect(TokenType.RPAREN, "Expected ')' after parameters")

        if self._match(TokenType.COLON):
            self._skip_type()

        body = self._parse_block()
        self._expect(TokenType.END, "Expected 'end' to close function")

        return FunctionExpr(line=line, params=params, is_vararg=is_vararg, body=body)

    # ---------- table constructor ----------

    def _parse_table(self) -> TableExpr:
        line = self._current().line
        self._expect(TokenType.LBRACE, "Expected '{'")

        fields = []

        while not self._check(TokenType.RBRACE):
            field = self._parse_table_field()
            fields.append(field)

            if not (self._match(TokenType.COMMA) or self._match(TokenType.SEMICOLON)):
                break

        self._expect(TokenType.RBRACE, "Expected '}' to close table")
        return TableExpr(line=line, fields=fields)

    def _parse_table_field(self) -> TableField:
        line = self._current().line

        # [expr] = value
        if self._match(TokenType.LBRACKET):
            key = self._parse_expression()
            self._expect(TokenType.RBRACKET, "Expected ']' in table key")
            self._expect(TokenType.ASSIGN, "Expected '=' in table field")
            value = self._parse_expression()
            return TableField(line=line, key=key, value=value, is_name=False)

        # name = value  (NAME и contextual keywords)
        # Проверяем: текущий — имя/keyword, следующий — '='
        cur = self._current()
        if (cur.type in (TokenType.NAME,) or cur.type in CONTEXTUAL_KEYWORDS) \
                and self._peek(1).type == TokenType.ASSIGN:
            name_tok = self._advance()
            self._advance()  # =
            value = self._parse_expression()
            return TableField(
                line=line,
                key=StringLit(line=name_tok.line, value=name_tok.value),
                value=value,
                is_name=True
            )

        # Просто value
        value = self._parse_expression()
        return TableField(line=line, key=None, value=value, is_name=False)

    # ---------- interpolated string ----------

    def _parse_interp_string(self, raw: str, line: int) -> InterpStringLit:
        parts = []
        buf = []
        i = 0
        n = len(raw)

        while i < n:
            c = raw[i]

            if c == '\\' and i + 1 < n:
                nxt = raw[i + 1]
                if nxt == '`':  buf.append('`');  i += 2; continue
                if nxt == '$':  buf.append('$');  i += 2; continue
                if nxt == '\\': buf.append('\\'); i += 2; continue
                if nxt == 'n':  buf.append('\n'); i += 2; continue
                if nxt == 't':  buf.append('\t'); i += 2; continue
                if nxt == 'r':  buf.append('\r'); i += 2; continue
                buf.append(c)
                i += 1
                continue

            if c == '$' and i + 1 < n and raw[i + 1] == '{':
                if buf:
                    parts.append(''.join(buf))
                    buf = []

                j = i + 2
                depth = 1
                while j < n and depth > 0:
                    if raw[j] == '{':
                        depth += 1
                    elif raw[j] == '}':
                        depth -= 1
                        if depth == 0:
                            break
                    j += 1

                if depth != 0:
                    raise ParserError("Unterminated ${...} in interpolated string", line, 0)

                expr_str = raw[i+2:j]

                try:
                    sub_lexer = Lexer(expr_str)
                    sub_tokens = sub_lexer.tokenize()
                    sub_parser = Parser(sub_tokens)
                    expr = sub_parser._parse_expression()
                except (LexerError, ParserError) as e:
                    raise ParserError(f"Error in string interpolation: {e}", line, 0)

                parts.append(expr)
                i = j + 1
                continue

            buf.append(c)
            i += 1

        if buf:
            parts.append(''.join(buf))

        return InterpStringLit(line=line, parts=parts)


# ==================== ХЕЛПЕР ====================

def parse(source: str) -> Chunk:
    """Быстрый способ распарсить исходник в AST"""
    lexer = Lexer(source)
    tokens = lexer.tokenize()
    parser = Parser(tokens)
    return parser.parse()


# ==================== ТЕСТ ====================

if __name__ == "__main__":
    test_cases = [
        # (название, код, должен_пройти)
        ("basic expressions", '''
local x = 1 + 2 * 3
local name = "World"
local t = {1, 2, x = 100, [name] = true}
''', True),

        ("if/elseif/else", '''
if x > 5 then
    print("big")
elseif x == 5 then
    print("five")
else
    print("small")
end
''', True),

        ("numeric for + continue", '''
for i = 1, 10, 2 do
    if i == 6 then
        continue
    end
    x = x + 1
end
''', True),

        ("generic for", '''
for k, v in pairs(t) do
    print(k, v)
end
''', True),

        ("functions + type annotations", '''
local function fact(n: number): number
    if n <= 1 then return 1 end
    return n * fact(n - 1)
end
''', True),

        ("interpolated string", '''
local function greet(who: string): string
    return `Hello, ${who}!`
end
''', True),

        ("method decl + call chain", '''
local obj = {}
function obj:method(a, b)
    self.value = a + b
    return self
end
obj:method(1, 2):method(3, 4)
''', True),

        ("repeat/until", '''
repeat
    x = x - 1
until x == 0
''', True),

        ("do block", '''
do
    local scoped = 42
end
''', True),

        ("goto/label", '''
::mylabel::
goto mylabel
''', True),

        ("type alias", '''
type Vector = { x: number, y: number }
''', True),

        ("export type", '''
export type MyType = string | number
''', True),

        # ⭐ ГЛАВНЫЙ ТЕСТ — type() как вызов функции
        ("type() as function call", '''
local x = 1
if type(x) ~= "number" then
    while true do end
end
''', True),

        # type в разных позициях
        ("type in various positions", '''
local t = type(x)
local ok = type(obj) == "table"
if type(callback) ~= "function" then
    repeat until false
end
''', True),

        # Переменная с именем type
        ("type as variable name", '''
local type = "hello"
print(type)
''', True),

        # export как имя
        ("export as variable name", '''
local export = {}
export.value = 42
''', True),

        # compound assignments
        ("compound assignments", '''
x += 1
x -= 2
x *= 3
x /= 4
x //= 5
x %= 6
x ^= 2
x ..= "!"
''', True),

        # Сложный кейс из environment.py
        ("environment checks pattern", '''
local _0x706_O0lo = game
if type(_0x706_O0lo) ~= "function" then
    repeat until false
end
if type(game.Players) ~= "table" then
    while 1 do end
end
''', True),

        # type alias рядом с type()
        ("type alias + type() call", '''
type MyStr = string
local x = type(42)
if type(x) == "string" then
    print(x)
end
''', True),
    ]

    passed = 0
    failed = 0

    for name, code, should_pass in test_cases:
        try:
            chunk = parse(code)
            if should_pass:
                print(f"  ✅ {name}")
                passed += 1
            else:
                print(f"  ❌ {name} (expected failure but passed)")
                failed += 1
        except (LexerError, ParserError) as e:
            if not should_pass:
                print(f"  ✅ {name} (expected failure: {e})")
                passed += 1
            else:
                print(f"  ❌ {name}")
                print(f"      {e}")
                failed += 1

    print()
    print(f"{'=' * 50}")
    print(f"Parser tests: {passed}/{passed+failed}")
    if failed == 0:
        print("All tests passed! 🎉")
    else:
        print(f"{failed} test(s) failed ❌")