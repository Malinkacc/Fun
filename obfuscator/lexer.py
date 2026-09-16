"""
NZL Studio Obfuscator - Lexer
Tokenizer for Lua 5.1 + Luau syntax

Supports:
    - All Lua 5.1 tokens
    - Luau extensions: continue, +=, -=, *=, /=, //=, ..=, //
    - Type annotations (parsed but ignored at token level)
    - String interpolation: `hello ${x}`
    - Long strings: [[...]], [=[...]=], [==[...]==]
    - All comment forms: --, --[[ ]], --[=[ ]=]
    - Hex numbers, floats, scientific notation
    - UTF-8 BOM auto-skip
"""

from enum import Enum, auto
from dataclasses import dataclass
from typing import List, Optional


# ==================== ТИПЫ ТОКЕНОВ ====================

class TokenType(Enum):
    # Литералы
    NUMBER = auto()
    STRING = auto()
    ISTRING = auto()
    NAME = auto()
    
    # Ключевые слова
    AND = auto()
    BREAK = auto()
    DO = auto()
    ELSE = auto()
    ELSEIF = auto()
    END = auto()
    FALSE = auto()
    FOR = auto()
    FUNCTION = auto()
    GOTO = auto()
    IF = auto()
    IN = auto()
    LOCAL = auto()
    NIL = auto()
    NOT = auto()
    OR = auto()
    REPEAT = auto()
    RETURN = auto()
    THEN = auto()
    TRUE = auto()
    UNTIL = auto()
    WHILE = auto()
    
    # Luau ключевые слова
    CONTINUE = auto()
    EXPORT = auto()
    TYPE = auto()
    TYPEOF = auto()
    
    # Операторы
    PLUS = auto()
    MINUS = auto()
    STAR = auto()
    SLASH = auto()
    DSLASH = auto()
    PERCENT = auto()
    CARET = auto()
    HASH = auto()
    
    # Compound assignment (Luau)
    PLUS_ASSIGN = auto()
    MINUS_ASSIGN = auto()
    STAR_ASSIGN = auto()
    SLASH_ASSIGN = auto()
    DSLASH_ASSIGN = auto()
    PERCENT_ASSIGN = auto()
    CARET_ASSIGN = auto()
    CONCAT_ASSIGN = auto()
    
    # Сравнения
    EQ = auto()
    NEQ = auto()
    LT = auto()
    GT = auto()
    LEQ = auto()
    GEQ = auto()
    
    # Присваивание и разделители
    ASSIGN = auto()
    LPAREN = auto()
    RPAREN = auto()
    LBRACE = auto()
    RBRACE = auto()
    LBRACKET = auto()
    RBRACKET = auto()
    SEMICOLON = auto()
    COLON = auto()
    DCOLON = auto()
    COMMA = auto()
    DOT = auto()
    CONCAT = auto()
    ELLIPSIS = auto()
    ARROW = auto()
    QUESTION = auto()
    PIPE = auto()
    AMPERSAND = auto()
    
    # Спец
    EOF = auto()


KEYWORDS = {
    'and': TokenType.AND,
    'break': TokenType.BREAK,
    'do': TokenType.DO,
    'else': TokenType.ELSE,
    'elseif': TokenType.ELSEIF,
    'end': TokenType.END,
    'false': TokenType.FALSE,
    'for': TokenType.FOR,
    'function': TokenType.FUNCTION,
    'goto': TokenType.GOTO,
    'if': TokenType.IF,
    'in': TokenType.IN,
    'local': TokenType.LOCAL,
    'nil': TokenType.NIL,
    'not': TokenType.NOT,
    'or': TokenType.OR,
    'repeat': TokenType.REPEAT,
    'return': TokenType.RETURN,
    'then': TokenType.THEN,
    'true': TokenType.TRUE,
    'until': TokenType.UNTIL,
    'while': TokenType.WHILE,
    'continue': TokenType.CONTINUE,
    'export': TokenType.EXPORT,
    'type': TokenType.TYPE,
    'typeof': TokenType.TYPEOF,
}


# ==================== ТОКЕН ====================

@dataclass
class Token:
    type: TokenType
    value: any
    raw: str
    line: int
    column: int
    
    def __repr__(self):
        if self.type in (TokenType.NUMBER, TokenType.STRING, TokenType.NAME, TokenType.ISTRING):
            return f"Token({self.type.name}, {self.value!r}, line={self.line})"
        return f"Token({self.type.name}, line={self.line})"


# ==================== ИСКЛЮЧЕНИЯ ====================

class LexerError(Exception):
    def __init__(self, message, line, column):
        self.message = message
        self.line = line
        self.column = column
        super().__init__(f"[Lexer] Line {line}:{column}: {message}")


# ==================== ЛЕКСЕР ====================

# Zero-width символы которые надо игнорировать в исходнике
# (обычно попадают из копипаста или BOM)
IGNORABLE_CHARS = {
    '\ufeff',  # BOM (Byte Order Mark)
    '\u200b',  # Zero Width Space
    '\u200c',  # Zero Width Non-Joiner
    '\u200d',  # Zero Width Joiner
    '\u2060',  # Word Joiner
}


class Lexer:
    """Токенизатор Luau"""
    
    def __init__(self, source: str):
        # ⭐ ФИКС: убираем BOM из самого начала файла
        if source.startswith('\ufeff'):
            source = source[1:]
        
        self.source = source
        self.pos = 0
        self.line = 1
        self.column = 1
        self.tokens: List[Token] = []
    
    # ---------- Утилиты ----------
    
    def _peek(self, offset: int = 0) -> str:
        p = self.pos + offset
        if p >= len(self.source):
            return '\0'
        return self.source[p]
    
    def _advance(self) -> str:
        if self.pos >= len(self.source):
            return '\0'
        c = self.source[self.pos]
        self.pos += 1
        if c == '\n':
            self.line += 1
            self.column = 1
        else:
            self.column += 1
        return c
    
    def _match(self, expected: str) -> bool:
        if self._peek() == expected:
            self._advance()
            return True
        return False
    
    def _is_at_end(self) -> bool:
        return self.pos >= len(self.source)
    
    def _is_digit(self, c: str) -> bool:
        return '0' <= c <= '9'
    
    def _is_hex_digit(self, c: str) -> bool:
        return self._is_digit(c) or ('a' <= c.lower() <= 'f')
    
    def _is_alpha(self, c: str) -> bool:
        return c.isalpha() or c == '_'
    
    def _is_alnum(self, c: str) -> bool:
        return self._is_alpha(c) or self._is_digit(c)
    
    def _error(self, msg: str):
        raise LexerError(msg, self.line, self.column)
    
    def _add_token(self, type: TokenType, value=None, raw=None, start_line=None, start_col=None):
        self.tokens.append(Token(
            type=type,
            value=value,
            raw=raw or '',
            line=start_line if start_line is not None else self.line,
            column=start_col if start_col is not None else self.column
        ))
    
    # ---------- Основной цикл ----------
    
    def tokenize(self) -> List[Token]:
        while not self._is_at_end():
            self._scan_token()
        self._add_token(TokenType.EOF, raw='', start_line=self.line, start_col=self.column)
        return self.tokens
    
    def _scan_token(self):
        c = self._peek()
        
        # Пропускаем пробелы и zero-width символы
        if c in ' \t\r\n':
            self._advance()
            return
        
        # ⭐ ФИКС: пропускаем любые ignorable Unicode символы (BOM, ZW и т.д.)
        if c in IGNORABLE_CHARS:
            self._advance()
            return
        
        start_line = self.line
        start_col = self.column
        
        # Комментарии
        if c == '-' and self._peek(1) == '-':
            self._skip_comment()
            return
        
        # Числа
        if self._is_digit(c):
            self._read_number(start_line, start_col)
            return
        
        # Числа начинающиеся с точки: .5
        if c == '.' and self._is_digit(self._peek(1)):
            self._read_number(start_line, start_col)
            return
        
        # Идентификаторы и ключевые слова
        if self._is_alpha(c):
            self._read_identifier(start_line, start_col)
            return
        
        # Строки
        if c == '"' or c == "'":
            self._read_string(c, start_line, start_col)
            return
        
        # Длинные строки [[ ]]
        if c == '[':
            if self._peek(1) == '[' or self._peek(1) == '=':
                level = self._check_long_bracket()
                if level >= 0:
                    self._read_long_string(level, start_line, start_col)
                    return
        
        # String interpolation
        if c == '`':
            self._read_interpolated_string(start_line, start_col)
            return
        
        # Операторы и пунктуация
        self._read_operator(start_line, start_col)
    
    # ---------- Комментарии ----------
    
    def _skip_comment(self):
        self._advance()  # -
        self._advance()  # -
        
        if self._peek() == '[':
            saved_pos = self.pos
            saved_line = self.line
            saved_col = self.column
            
            self._advance()  # [
            level = 0
            while self._peek() == '=':
                self._advance()
                level += 1
            
            if self._peek() == '[':
                self._advance()  # [
                closing = ']' + '=' * level + ']'
                while not self._is_at_end():
                    if self._peek() == ']':
                        matched = True
                        for i, ch in enumerate(closing):
                            if self._peek(i) != ch:
                                matched = False
                                break
                        if matched:
                            for _ in range(len(closing)):
                                self._advance()
                            return
                    self._advance()
                self._error("Unterminated long comment")
                return
            else:
                self.pos = saved_pos
                self.line = saved_line
                self.column = saved_col
        
        while not self._is_at_end() and self._peek() != '\n':
            self._advance()
    
    # ---------- Числа ----------
    
    def _read_number(self, start_line, start_col):
        start = self.pos
        
        if self._peek() == '0' and (self._peek(1) == 'x' or self._peek(1) == 'X'):
            self._advance()
            self._advance()
            if not (self._is_hex_digit(self._peek()) or self._peek() == '_'):
                self._error("Invalid hex number")
            while self._is_hex_digit(self._peek()) or self._peek() == '_':
                self._advance()
            if self._peek() == '.':
                self._advance()
                while self._is_hex_digit(self._peek()) or self._peek() == '_':
                    self._advance()
            if self._peek() in 'pP':
                self._advance()
                if self._peek() in '+-':
                    self._advance()
                while self._is_digit(self._peek()):
                    self._advance()
            raw = self.source[start:self.pos]
            try:
                if '.' in raw or 'p' in raw.lower():
                    value = float.fromhex(raw)
                else:
                    value = int(raw.replace('_', ''), 16)
            except ValueError:
                self._error(f"Invalid hex number: {raw}")
            self._add_token(TokenType.NUMBER, value=value, raw=raw, start_line=start_line, start_col=start_col)
            return
        
        # Бинарные литералы: 0b101 / 0B10_00 (Luraph v14 их эммитит!)
        if self._peek() == '0' and (self._peek(1) == 'b' or self._peek(1) == 'B'):
            self._advance()
            self._advance()
            if self._peek() not in '01_':
                self._error("Invalid binary number")
            while self._peek() in '01_':
                self._advance()
            raw = self.source[start:self.pos]
            digits = raw[2:].replace('_', '')
            if not digits:
                self._error(f"Invalid binary number: {raw}")
            try:
                value = int(digits, 2)
            except ValueError:
                self._error(f"Invalid binary number: {raw}")
            self._add_token(TokenType.NUMBER, value=value, raw=raw, start_line=start_line, start_col=start_col)
            return
        
        while self._is_digit(self._peek()):
            self._advance()
        
        if self._peek() == '.' and self._is_digit(self._peek(1)):
            self._advance()
            while self._is_digit(self._peek()):
                self._advance()
        elif self._peek() == '.' and not self._is_digit(self._peek(1)) and self._peek(1) != '.':
            self._advance()
        
        if self._peek() in 'eE':
            self._advance()
            if self._peek() in '+-':
                self._advance()
            if not self._is_digit(self._peek()):
                self._error("Invalid exponent in number")
            while self._is_digit(self._peek()):
                self._advance()
        
        raw = self.source[start:self.pos]
        try:
            if '.' in raw or 'e' in raw.lower():
                value = float(raw)
            else:
                value = int(raw)
        except ValueError:
            self._error(f"Invalid number: {raw}")
        
        self._add_token(TokenType.NUMBER, value=value, raw=raw, start_line=start_line, start_col=start_col)
    
    # ---------- Идентификаторы ----------
    
    def _read_identifier(self, start_line, start_col):
        start = self.pos
        while self._is_alnum(self._peek()):
            self._advance()
        
        raw = self.source[start:self.pos]
        
        if raw in KEYWORDS:
            self._add_token(KEYWORDS[raw], value=raw, raw=raw, start_line=start_line, start_col=start_col)
        else:
            self._add_token(TokenType.NAME, value=raw, raw=raw, start_line=start_line, start_col=start_col)
    
    # ---------- Обычные строки ----------
    
    def _read_string(self, quote: str, start_line, start_col):
        self._advance()
        result = []
        
        while not self._is_at_end() and self._peek() != quote:
            c = self._peek()
            
            if c == '\n':
                self._error("Unterminated string (newline in string)")
            
            if c == '\\':
                self._advance()
                escaped = self._peek()
                
                if escaped == 'a': result.append('\a'); self._advance()
                elif escaped == 'b': result.append('\b'); self._advance()
                elif escaped == 'f': result.append('\f'); self._advance()
                elif escaped == 'n': result.append('\n'); self._advance()
                elif escaped == 'r': result.append('\r'); self._advance()
                elif escaped == 't': result.append('\t'); self._advance()
                elif escaped == 'v': result.append('\v'); self._advance()
                elif escaped == '\\': result.append('\\'); self._advance()
                elif escaped == '"': result.append('"'); self._advance()
                elif escaped == "'": result.append("'"); self._advance()
                elif escaped == '\n': result.append('\n'); self._advance()
                elif escaped == 'x':
                    self._advance()
                    hex_str = ''
                    for _ in range(2):
                        if self._is_hex_digit(self._peek()):
                            hex_str += self._advance()
                        else:
                            break
                    if hex_str:
                        result.append(chr(int(hex_str, 16)))
                    else:
                        result.append('\\x')
                elif escaped == 'z':
                    self._advance()
                    while self._peek() in ' \t\n\r':
                        self._advance()
                elif self._is_digit(escaped):
                    num_str = ''
                    for _ in range(3):
                        if self._is_digit(self._peek()):
                            num_str += self._advance()
                        else:
                            break
                    if num_str:
                        n = int(num_str)
                        if n > 255:
                            self._error(f"Decimal escape too large: {n}")
                        result.append(chr(n))
                else:
                    result.append('\\' + escaped)
                    self._advance()
            else:
                result.append(c)
                self._advance()
        
        if self._is_at_end():
            self._error("Unterminated string")
        
        self._advance()
        
        value = ''.join(result)
        raw = self.source[self.pos - len(value) - 2:self.pos]
        self._add_token(TokenType.STRING, value=value, raw=raw, start_line=start_line, start_col=start_col)
    
    # ---------- Длинные строки ----------
    
    def _check_long_bracket(self) -> int:
        if self._peek() != '[':
            return -1
        offset = 1
        while self._peek(offset) == '=':
            offset += 1
        if self._peek(offset) == '[':
            return offset - 1
        return -1
    
    def _read_long_string(self, level: int, start_line, start_col):
        self._advance()  # [
        for _ in range(level):
            self._advance()
        self._advance()  # [
        
        if self._peek() == '\n':
            self._advance()
        
        closing = ']' + '=' * level + ']'
        start = self.pos
        
        while not self._is_at_end():
            if self._peek() == ']':
                matched = True
                for i, ch in enumerate(closing):
                    if self._peek(i) != ch:
                        matched = False
                        break
                if matched:
                    value = self.source[start:self.pos]
                    for _ in range(len(closing)):
                        self._advance()
                    self._add_token(TokenType.STRING, value=value, raw=value, start_line=start_line, start_col=start_col)
                    return
            self._advance()
        
        self._error("Unterminated long string")
    
    # ---------- String interpolation ----------
    
    def _read_interpolated_string(self, start_line, start_col):
        self._advance()  # `
        start = self.pos
        depth = 0
        
        while not self._is_at_end():
            c = self._peek()
            
            if c == '\\':
                self._advance()
                if not self._is_at_end():
                    self._advance()
                continue
            
            if c == '{':
                depth += 1
                self._advance()
                continue
            
            if c == '}':
                if depth > 0:
                    depth -= 1
                self._advance()
                continue
            
            if c == '`' and depth == 0:
                value = self.source[start:self.pos]
                self._advance()
                self._add_token(TokenType.ISTRING, value=value, raw=value, start_line=start_line, start_col=start_col)
                return
            
            self._advance()
        
        self._error("Unterminated interpolated string")
    
    # ---------- Операторы ----------
    
    def _read_operator(self, start_line, start_col):
        c = self._advance()
        
        if c == '+':
            if self._match('='):
                self._add_token(TokenType.PLUS_ASSIGN, raw='+=', start_line=start_line, start_col=start_col)
            else:
                self._add_token(TokenType.PLUS, raw='+', start_line=start_line, start_col=start_col)
        elif c == '-':
            if self._match('='):
                self._add_token(TokenType.MINUS_ASSIGN, raw='-=', start_line=start_line, start_col=start_col)
            elif self._match('>'):
                self._add_token(TokenType.ARROW, raw='->', start_line=start_line, start_col=start_col)
            else:
                self._add_token(TokenType.MINUS, raw='-', start_line=start_line, start_col=start_col)
        elif c == '*':
            if self._match('='):
                self._add_token(TokenType.STAR_ASSIGN, raw='*=', start_line=start_line, start_col=start_col)
            else:
                self._add_token(TokenType.STAR, raw='*', start_line=start_line, start_col=start_col)
        elif c == '/':
            if self._match('/'):
                if self._match('='):
                    self._add_token(TokenType.DSLASH_ASSIGN, raw='//=', start_line=start_line, start_col=start_col)
                else:
                    self._add_token(TokenType.DSLASH, raw='//', start_line=start_line, start_col=start_col)
            elif self._match('='):
                self._add_token(TokenType.SLASH_ASSIGN, raw='/=', start_line=start_line, start_col=start_col)
            else:
                self._add_token(TokenType.SLASH, raw='/', start_line=start_line, start_col=start_col)
        elif c == '%':
            if self._match('='):
                self._add_token(TokenType.PERCENT_ASSIGN, raw='%=', start_line=start_line, start_col=start_col)
            else:
                self._add_token(TokenType.PERCENT, raw='%', start_line=start_line, start_col=start_col)
        elif c == '^':
            if self._match('='):
                self._add_token(TokenType.CARET_ASSIGN, raw='^=', start_line=start_line, start_col=start_col)
            else:
                self._add_token(TokenType.CARET, raw='^', start_line=start_line, start_col=start_col)
        elif c == '#':
            self._add_token(TokenType.HASH, raw='#', start_line=start_line, start_col=start_col)
        elif c == '=':
            if self._match('='):
                self._add_token(TokenType.EQ, raw='==', start_line=start_line, start_col=start_col)
            else:
                self._add_token(TokenType.ASSIGN, raw='=', start_line=start_line, start_col=start_col)
        elif c == '~':
            if self._match('='):
                self._add_token(TokenType.NEQ, raw='~=', start_line=start_line, start_col=start_col)
            else:
                self._error(f"Unexpected character: '~'")
        elif c == '<':
            if self._match('='):
                self._add_token(TokenType.LEQ, raw='<=', start_line=start_line, start_col=start_col)
            else:
                self._add_token(TokenType.LT, raw='<', start_line=start_line, start_col=start_col)
        elif c == '>':
            if self._match('='):
                self._add_token(TokenType.GEQ, raw='>=', start_line=start_line, start_col=start_col)
            else:
                self._add_token(TokenType.GT, raw='>', start_line=start_line, start_col=start_col)
        elif c == '(':
            self._add_token(TokenType.LPAREN, raw='(', start_line=start_line, start_col=start_col)
        elif c == ')':
            self._add_token(TokenType.RPAREN, raw=')', start_line=start_line, start_col=start_col)
        elif c == '{':
            self._add_token(TokenType.LBRACE, raw='{', start_line=start_line, start_col=start_col)
        elif c == '}':
            self._add_token(TokenType.RBRACE, raw='}', start_line=start_line, start_col=start_col)
        elif c == '[':
            self._add_token(TokenType.LBRACKET, raw='[', start_line=start_line, start_col=start_col)
        elif c == ']':
            self._add_token(TokenType.RBRACKET, raw=']', start_line=start_line, start_col=start_col)
        elif c == ';':
            self._add_token(TokenType.SEMICOLON, raw=';', start_line=start_line, start_col=start_col)
        elif c == ':':
            if self._match(':'):
                self._add_token(TokenType.DCOLON, raw='::', start_line=start_line, start_col=start_col)
            else:
                self._add_token(TokenType.COLON, raw=':', start_line=start_line, start_col=start_col)
        elif c == ',':
            self._add_token(TokenType.COMMA, raw=',', start_line=start_line, start_col=start_col)
        elif c == '.':
            if self._match('.'):
                if self._match('.'):
                    self._add_token(TokenType.ELLIPSIS, raw='...', start_line=start_line, start_col=start_col)
                elif self._match('='):
                    self._add_token(TokenType.CONCAT_ASSIGN, raw='..=', start_line=start_line, start_col=start_col)
                else:
                    self._add_token(TokenType.CONCAT, raw='..', start_line=start_line, start_col=start_col)
            else:
                self._add_token(TokenType.DOT, raw='.', start_line=start_line, start_col=start_col)
        elif c == '?':
            self._add_token(TokenType.QUESTION, raw='?', start_line=start_line, start_col=start_col)
        elif c == '|':
            self._add_token(TokenType.PIPE, raw='|', start_line=start_line, start_col=start_col)
        elif c == '&':
            self._add_token(TokenType.AMPERSAND, raw='&', start_line=start_line, start_col=start_col)
        else:
            # Даём более информативное сообщение для не-ASCII символов
            code_point = ord(c) if c else 0
            if code_point > 127:
                self._error(f"Unexpected character: {c!r} (U+{code_point:04X})")
            else:
                self._error(f"Unexpected character: {c!r}")


# ==================== ХЕЛПЕР ====================

def tokenize(source: str) -> List[Token]:
    """Быстрый способ токенизировать код"""
    lexer = Lexer(source)
    return lexer.tokenize()


# ==================== ТЕСТ ====================

if __name__ == "__main__":
    # Тест 1: обычный код
    test_code = '''
-- Comment
local x = 100
local name = "Hello \\n world"
local hex = 0xFF
local float = 3.14e2
local long = [[
    multi
    line
]]
local interp = `hello ${x}`
if x >= 100 and x <= 200 then
    x += 1
    print(name .. " " .. tostring(x))
end
for i = 1, 10 do
    continue
end
--[[
    block comment
]]
'''
    
    # Тест 2: код с BOM в начале
    test_with_bom = '\ufefflocal x = 42\nprint(x)'
    
    # Тест 3: код с zero-width символами внутри
    test_with_zw = 'local x\u200b = 10\nprint(x)'
    
    print("=" * 60)
    print("🧪 Тест 1: обычный код")
    print("=" * 60)
    try:
        tokens = tokenize(test_code)
        print(f"✅ OK — {len(tokens)} токенов")
    except LexerError as e:
        print(f"❌ ERROR: {e}")
    
    print()
    print("=" * 60)
    print("🧪 Тест 2: код с BOM (\\ufeff в начале)")
    print("=" * 60)
    try:
        tokens = tokenize(test_with_bom)
        print(f"✅ OK — {len(tokens)} токенов (BOM пропущен)")
        for tok in tokens:
            print(f"    {tok}")
    except LexerError as e:
        print(f"❌ ERROR: {e}")
    
    print()
    print("=" * 60)
    print("🧪 Тест 3: код с zero-width внутри")
    print("=" * 60)
    try:
        tokens = tokenize(test_with_zw)
        print(f"✅ OK — {len(tokens)} токенов")
    except LexerError as e:
        print(f"❌ ERROR: {e}")
    
    print()
    print("=" * 60)
    print("✅ Все тесты прошли!")
    print("=" * 60)