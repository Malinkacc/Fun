"""
LuaSandbox — мини Lua-интерпретатор на Python.
Исполняет простые Lua-функции для расшифровки строк.
"""

from __future__ import annotations
import math
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

try:
    from obfuscator.parser import Parser
    from obfuscator.lexer import Lexer
    HAS_PARSER = True
except ImportError:
    HAS_PARSER = False


class LuaSandboxError(Exception): pass
class LuaBreak(Exception): pass
class LuaReturn(Exception):
    def __init__(self, values):
        self.values = values


class LuaTable:
    def __init__(self):
        self._hash = {}
        self._array = []
        self.metatable = None

    def rawget(self, key):
        if isinstance(key, bool):
            return self._hash.get(key)
        if isinstance(key, (int, float)):
            idx = int(key)
            if idx == key and 1 <= idx <= len(self._array):
                return self._array[idx - 1]
            return self._hash.get(key)
        return self._hash.get(key)

    def rawset(self, key, value):
        if isinstance(key, bool):
            self._hash[key] = value; return
        if isinstance(key, (int, float)):
            idx = int(key)
            if idx == key and idx >= 1:
                while len(self._array) < idx:
                    self._array.append(None)
                self._array[idx - 1] = value
                return
            self._hash[key] = value; return
        self._hash[key] = value

    def length(self):
        n = 0
        for v in self._array:
            if v is None: break
            n += 1
        return n

    def __repr__(self):
        return f"LuaTable(arr={self._array}, hash={self._hash})"


class _EnvTable(LuaTable):
    """Таблица-представление env-словаря (для _G / getfenv в VM-коде).

    Строковые ключи читаются/пишутся прямо в env-словарь, поэтому
    GETGLOBAL/SETGLOBAL внутри VM-диспетчера видят реальные глобалы.
    """

    def __init__(self, env: dict):
        super().__init__()
        self._env = env

    def rawget(self, key):
        v = super().rawget(key)
        if v is None and isinstance(key, str):
            return self._env.get(key)
        return v

    def rawset(self, key, value):
        if isinstance(key, str):
            self._env[key] = value
        else:
            super().rawset(key, value)


_MISS = object()


class _FuncEnv(dict):
    """Function env with an upvalue parent chain: locals live in this dict,
    reads fall back to enclosing envs, and assignments to names declared in
    an enclosing function write through to that env (real Lua upvalues)."""

    __slots__ = ('parent',)

    def __init__(self, parent):
        super().__init__()
        self.parent = parent

    def __contains__(self, k):
        if dict.__contains__(self, k):
            return True
        return self.parent is not None and k in self.parent

    def get(self, k, d=None):
        v = dict.get(self, k, _MISS)
        if v is not _MISS:
            return v
        return self.parent.get(k, d) if isinstance(self.parent, dict) else d

    def __getitem__(self, k):
        if dict.__contains__(self, k):
            return dict.__getitem__(self, k)
        return self.parent[k]

    def upvalue_set(self, name, value):
        p = self.parent
        while isinstance(p, _FuncEnv):
            if dict.__contains__(p, name):
                p[name] = value
                return True
            p = p.parent
        if isinstance(p, dict) and name in p:
            p[name] = value
            return True
        return False


class LuaFunction:
    def __init__(self, params, body, closure, sandbox, is_vararg=False):
        self.params = params
        self.body = body
        self.closure = closure
        self.sandbox = sandbox
        self.is_vararg = is_vararg

    def call(self, args):
        env = _FuncEnv(self.closure)
        for i, param in enumerate(self.params):
            env[param] = args[i] if i < len(args) else None
        if self.is_vararg:
            env['...'] = args[len(self.params):]
        return self.sandbox._exec_block(self.body, env)


class LuaSandbox:
    MAX_STEPS = 1_000_000
    MAX_DEPTH = 200

    def __init__(self):
        self._steps = 0
        self._depth = 0
        self._globals = self._make_globals()

    def _make_globals(self):
        string_lib = LuaTable()
        string_lib.rawset('byte', lambda args: self._str_byte(args))
        string_lib.rawset('char', lambda args: self._str_char(args))
        string_lib.rawset('len', lambda args: len(args[0]) if args else 0)
        string_lib.rawset('sub', lambda args: self._str_sub(args))
        string_lib.rawset('rep', lambda args: args[0] * int(args[1]) if len(args) >= 2 else '')
        string_lib.rawset('reverse', lambda args: args[0][::-1] if args else '')
        string_lib.rawset('lower', lambda args: args[0].lower() if args else '')
        string_lib.rawset('upper', lambda args: args[0].upper() if args else '')
        string_lib.rawset('format', lambda args: self._str_format(args))
        string_lib.rawset('find', lambda args: self._str_find(args))
        string_lib.rawset('gmatch', lambda args: self._str_gmatch(args))
        string_lib.rawset('gsub', lambda args: self._str_gsub(args))
        string_lib.rawset('match', lambda args: self._str_match(args))
        string_lib.rawset('pack', lambda args: self._str_pack(args))
        string_lib.rawset('unpack', lambda args: self._str_unpack(args))
        string_lib.rawset('packsize', lambda args: self._str_packsize(args))
        string_lib.rawset('split', lambda args: self._str_split(args))

        table_lib = LuaTable()
        table_lib.rawset('concat', lambda args: self._tbl_concat(args))
        table_lib.rawset('insert', lambda args: self._tbl_insert(args))
        table_lib.rawset('remove', lambda args: self._tbl_remove(args))
        table_lib.rawset('create', lambda args: self._tbl_create(args))
        table_lib.rawset('clear', lambda args: self._tbl_clear(args))
        table_lib.rawset('find', lambda args: self._tbl_find(args))
        table_lib.rawset('pack', lambda args: self._tbl_pack(args))
        table_lib.rawset('unpack', lambda args: self._unpack(args))
        table_lib.rawset('move', lambda args: self._tbl_move(args))
        table_lib.rawset('sort', lambda args: self._tbl_sort(args))

        math_lib = LuaTable()
        math_lib.rawset('floor', lambda args: math.floor(args[0]) if args else 0)
        math_lib.rawset('ceil', lambda args: math.ceil(args[0]) if args else 0)
        math_lib.rawset('abs', lambda args: abs(args[0]) if args else 0)
        math_lib.rawset('max', lambda args: max(args) if args else 0)
        math_lib.rawset('min', lambda args: min(args) if args else 0)
        math_lib.rawset('sqrt', lambda args: math.sqrt(args[0]) if args else 0)
        math_lib.rawset('huge', math.inf)
        math_lib.rawset('pi', math.pi)
        math_lib.rawset('fmod', lambda args: math.fmod(args[0], args[1]) if len(args)>=2 else 0)
        math_lib.rawset('pow', lambda args: args[0]**args[1] if len(args)>=2 else 0)

        return {
            'string': string_lib,
            'table': table_lib,
            'math': math_lib,
            'io': LuaTable(),
            'os': LuaTable(),
            'print': lambda args: None,
            'tostring': lambda args: self._tostring(args[0]) if args else 'nil',
            'tonumber': lambda args: self._tonumber(args),
            'type': lambda args: self._type(args[0]) if args else 'nil',
            'ipairs': lambda args: self._ipairs(args),
            'pairs': lambda args: self._pairs(args),
            'unpack': lambda args: self._unpack(args),
            'select': lambda args: self._select(args),
            'rawget': lambda args: args[0].rawget(args[1]) if len(args)>=2 and isinstance(args[0], LuaTable) else None,
            'rawset': lambda args: self._rawset(args),
            'setmetatable': lambda args: self._setmetatable(args),
            'getmetatable': lambda args: self._getmetatable(args),
            'rawlen': lambda args: (args[0].length() if isinstance(args[0], LuaTable) else (len(args[0]) if isinstance(args[0], str) else 0)) if args else 0,
            'error': lambda args: self._raise_error(args),
            'assert': lambda args: self._assert(args),
            'pcall': lambda args: self._pcall(args),
            'xpcall': lambda args: self._pcall([args[0]] + (args[2:] if len(args)>2 else [])),
            'next': lambda args: self._next(args),
            'rawequal': lambda args: args[0] is args[1] if len(args)>=2 else False,
            'rawlen': lambda args: args[0].length() if args and isinstance(args[0], LuaTable) else (len(args[0]) if args else 0),
            'load': lambda args: None,
            'loadstring': lambda args: None,
            'dofile': lambda args: None,
            'require': lambda args: None,
            'collectgarbage': lambda args: 0,
            'coroutine': self._make_coroutine(),
            'bit32': self._make_bit32(),
        }

    def _raise_error(self, args):
        raise LuaSandboxError(str(args[0]) if args else 'error')

    def _assert(self, args):
        if args and self._lua_truthy(args[0]):
            return args[0]
        raise LuaSandboxError('assertion failed')

    @staticmethod
    def _countlz(args) -> int:
        x = int(args[0]) & 0xFFFFFFFF if args and args[0] is not None else 0
        if x == 0:
            return 32
        n = 0
        while not (x & 0x80000000):
            x = (x << 1) & 0xFFFFFFFF
            n += 1
        return n

    @staticmethod
    def _countrz(args) -> int:
        x = int(args[0]) & 0xFFFFFFFF if args and args[0] is not None else 0
        if x == 0:
            return 32
        n = 0
        while not (x & 1):
            x >>= 1
            n += 1
        return n

    def _make_coroutine(self):
        """Минимальный coroutine-стаб: yield/create/wrap/status/resume.
        Достаточно для защит, которые только СОХРАНЯЮТ coroutine.yield
        или используют его как маркер среды."""
        co = LuaTable()
        state = {'cur': None}

        def _yield(args):
            return [None]

        def _create(args):
            fn = args[0] if args else None
            box = {'fn': fn, 'done': False}
            return box

        def _resume(args):
            box = args[0] if args else None
            if not isinstance(box, dict):
                return [False, 'bad coroutine']
            try:
                res = self._call_function(box['fn'], list(args[1:]),
                                          getattr(self, '_env', None) or {})
                box['done'] = True
                return [True, res]
            except Exception as e:  # noqa: BLE001
                return [False, str(e)]

        def _status(args):
            box = args[0] if args else None
            if isinstance(box, dict):
                return 'dead' if box.get('done') else 'suspended'
            return 'dead'

        def _wrap(args):
            fn = args[0] if args else None
            return lambda a: self._call_function(fn, list(a), {})

        co.rawset('yield', lambda args: _yield(args))
        co.rawset('create', lambda args: _create(args))
        co.rawset('resume', lambda args: _resume(args))
        co.rawset('status', lambda args: _status(args))
        co.rawset('wrap', lambda args: _wrap(args))
        co.rawset('running', lambda args: state['cur'])
        return co

    @staticmethod
    def b32(v) -> int:
        """Нормализация аргумента bit32 по семантике Luau: любое число
        приводится к unsigned 32-bit (отрицательные — как 2^32 + x)."""
        try:
            x = int(v)
        except (TypeError, ValueError):
            return 0
        return x & 0xFFFFFFFF

    def _make_bit32(self):
        b = LuaTable()
        b.rawset('band', lambda args: self._band(args))  # _band нормализует маской
        b.rawset('bor', lambda args: self._bor(args))  # _bor нормализует аргументы
        b.rawset('bxor', lambda args: self._bxor(args))  # _bxor нормализует аргументы
        b.rawset('bnot', lambda args: (~int(args[0])) & 0xFFFFFFFF if args else 0)
        b.rawset('lshift', lambda args: (self.b32(args[0]) << int(args[1])) & 0xFFFFFFFF if len(args) >= 2 and 0 <= int(args[1]) < 32 else 0)
        b.rawset('rshift', lambda args: self.b32(args[0]) >> int(args[1]) if len(args) >= 2 and 0 <= int(args[1]) < 32 else 0)
        b.rawset('arshift', lambda args: self._arshift(args[0], int(args[1])) if len(args) >= 2 else 0)
        b.rawset('rrotate', lambda args: self._rot32(self.b32(args[0]), -int(args[1])) if len(args) >= 2 else 0)
        b.rawset('lrotate', lambda args: self._rot32(self.b32(args[0]), int(args[1])) if len(args) >= 2 else 0)
        b.rawset('extract', lambda args: self._extract(args))
        b.rawset('countlz', lambda args: self._countlz(args))
        b.rawset('countrz', lambda args: self._countrz(args))
        return b

    def _arshift(self, x, n: int) -> int:
        """Luau bit32.arshift: сдвиг >= 32 даёт 0; иначе unsigned32
        трактуется как signed32, сдвигается арифметически и результат
        снова нормализуется в unsigned32."""
        u = self.b32(x)
        if n < 0:
            return 0
        if n >= 32:
            return 0
        s = u - 0x100000000 if u >= 0x80000000 else u
        return (s >> n) & 0xFFFFFFFF

    def _rot32(self, x, n):
        x &= 0xFFFFFFFF
        n %= 32
        return ((x << n) | (x >> (32 - n))) & 0xFFFFFFFF

    def _extract(self, args):
        if len(args) < 2: return 0
        x = int(args[0]) & 0xFFFFFFFF
        field = int(args[1])
        width = int(args[2]) if len(args) > 2 else 1
        field = max(0, min(31, field))
        width = max(1, min(32 - field, width))
        return (x >> field) & ((1 << width) - 1)

    def _band(self, args):
        r = 0xFFFFFFFF
        for a in args: r &= self.b32(a)
        return r
    def _bor(self, args):
        r = 0
        for a in args: r |= self.b32(a)
        return r
    def _bxor(self, args):
        r = 0
        for a in args: r ^= self.b32(a)
        return r

    # ─── String helpers ───────────────────────────────────────────────

    def _str_byte(self, args):
        if not args: return None
        s = args[0]
        if s is None: return None
        i = int(args[1]) if len(args) > 1 else 1
        j = int(args[2]) if len(args) > 2 else i
        i = max(1, i); j = min(len(s), j)
        if i > j: return None
        result = [ord(s[k-1]) for k in range(i, j+1)]
        return result[0] if len(result) == 1 else result

    def _str_char(self, args):
        try:
            return ''.join(chr(int(a)) for a in args if a is not None)
        except Exception:
            return ''

    def _str_sub(self, args):
        if not args: return ''
        s = args[0] or ''
        n = len(s)
        i = int(args[1]) if len(args) > 1 else 1
        j = int(args[2]) if len(args) > 2 else n
        if i < 0: i = max(n + i + 1, 1)
        if j < 0: j = n + j + 1
        i = max(1, i); j = min(n, j)
        if i > j: return ''
        return s[i-1:j]

    def _str_format(self, args):
        if not args: return ''
        fmt = args[0]; vals = args[1:]
        try:
            result = []
            vi = 0; i = 0
            while i < len(fmt):
                if fmt[i] == '%' and i+1 < len(fmt):
                    spec = fmt[i+1]
                    if spec in ('d', 'i'):
                        result.append(str(int(vals[vi])) if vi < len(vals) else '0'); vi += 1; i += 2
                    elif spec == 's':
                        result.append(str(vals[vi]) if vi < len(vals) else ''); vi += 1; i += 2
                    elif spec == 'f':
                        result.append(f"{float(vals[vi]):.6f}" if vi < len(vals) else '0.000000'); vi += 1; i += 2
                    elif spec == 'x':
                        result.append(hex(int(vals[vi]))[2:] if vi < len(vals) else '0'); vi += 1; i += 2
                    elif spec == '%':
                        result.append('%'); i += 2
                    else:
                        result.append(fmt[i]); i += 1
                else:
                    result.append(fmt[i]); i += 1
            return ''.join(result)
        except Exception:
            return fmt

    # ─── Lua patterns ─────────────────────────────────────────────────

    def _lp_charclass(self, c, d):
        o = ord(c) if c else 0
        ascii_c = o < 128
        if d == 'a': return ascii_c and c.isalpha()
        if d == 'A': return not (ascii_c and c.isalpha())
        if d == 'c': return o < 32 or o == 127
        if d == 'C': return not (o < 32 or o == 127)
        if d == 'd': return ascii_c and c.isdigit()
        if d == 'D': return not (ascii_c and c.isdigit())
        if d == 'l': return ascii_c and c.islower()
        if d == 'L': return not (ascii_c and c.islower())
        if d == 'p': return ascii_c and (not c.isalnum()) and c != ' '
        if d == 'P': return not (ascii_c and (not c.isalnum()) and c != ' ')
        if d == 's': return c in ' \t\n\r\f\v'
        if d == 'S': return c not in ' \t\n\r\f\v'
        if d == 'u': return ascii_c and c.isupper()
        if d == 'U': return not (ascii_c and c.isupper())
        if d == 'w': return ascii_c and c.isalnum()
        if d == 'W': return not (ascii_c and c.isalnum())
        if d == 'x': return c in '0123456789abcdefABCDEF'
        if d == 'X': return c not in '0123456789abcdefABCDEF'
        if d == 'g': return 33 <= o <= 126
        if d == 'G': return not (33 <= o <= 126)
        return c == d

    def _lp_setend(self, pat, pi):
        j = pi + 1
        if j < len(pat) and pat[j] == '^':
            j += 1
        if j < len(pat) and pat[j] == ']':
            j += 1
        while j < len(pat):
            if pat[j] == '%':
                j += 2
                continue
            if pat[j] == ']':
                return j
            j += 1
        return len(pat)

    def _lp_setmatch(self, c, pat, pi, endp):
        neg = False
        j = pi + 1
        if j < endp and pat[j] == '^':
            neg = True
            j += 1
        found = False
        first = True
        while j < endp:
            if first and pat[j] == ']':
                if c == ']':
                    found = True
                    break
                j += 1
                first = False
                continue
            first = False
            if pat[j] == '%' and j + 1 < endp:
                if self._lp_charclass(c, pat[j + 1]):
                    found = True
                    break
                j += 2
                continue
            lo = pat[j]
            j += 1
            if j + 1 <= endp - 1 and pat[j] == '-':
                if pat[j + 1] == '%' and j + 2 < endp:
                    hi = pat[j + 2]
                    j += 3
                else:
                    hi = pat[j + 1]
                    j += 2
                if lo <= c <= hi:
                    found = True
                    break
            else:
                if c == lo:
                    found = True
                    break
        return (not found) if neg else found

    def _lp_itemlen(self, pat, pi):
        ch = pat[pi]
        if ch == '%':
            return 2
        if ch == '[':
            return self._lp_setend(pat, pi) - pi + 1
        return 1

    def _lp_classmatch1(self, s, si, pat, pi):
        if si >= len(s):
            return False
        ch = pat[pi]
        if ch == '.':
            return True
        if ch == '%':
            if pi + 1 >= len(pat):
                return False
            d = pat[pi + 1]
            if d.isdigit():
                return False
            return self._lp_charclass(s[si], d)
        if ch == '[':
            return self._lp_setmatch(s[si], pat, pi, self._lp_setend(pat, pi))
        return s[si] == ch

    def _lp_match(self, s, si, pat, pi, caps):
        while True:
            if pi >= len(pat):
                return (si, caps)
            ch = pat[pi]
            if ch == '(':
                if pat[pi + 1:pi + 2] == ')':
                    return self._lp_match(s, si, pat, pi + 2, caps + [('pos', si)])
                return self._lp_match(s, si, pat, pi + 1, caps + [[si, None]])
            if ch == ')':
                idx = -1
                for k in range(len(caps) - 1, -1, -1):
                    cc = caps[k]
                    if isinstance(cc, list) and cc[1] is None:
                        idx = k
                        break
                if idx < 0:
                    raise LuaSandboxError('invalid pattern capture')
                caps = list(caps)
                caps[idx] = [caps[idx][0], si]
                pi += 1
                continue
            if ch == '$' and pi + 1 >= len(pat):
                return (si, caps) if si == len(s) else None
            if ch == '%' and pi + 1 < len(pat):
                d = pat[pi + 1]
                if d == 'b':
                    if pi + 3 >= len(pat):
                        return None
                    b1, b2 = pat[pi + 2], pat[pi + 3]
                    if si >= len(s) or s[si] != b1:
                        return None
                    depth = 0
                    k = si
                    while k < len(s):
                        if s[k] == b1:
                            depth += 1
                        elif s[k] == b2:
                            depth -= 1
                            if depth == 0:
                                return self._lp_match(s, k + 1, pat, pi + 4, caps)
                        k += 1
                    return None
                if d.isdigit():
                    n = int(d)
                    if n - 1 >= len(caps):
                        return None
                    cc = caps[n - 1]
                    if not isinstance(cc, list) or cc[1] is None:
                        return None
                    txt = s[cc[0]:cc[1]]
                    if txt and s.startswith(txt, si):
                        return self._lp_match(s, si + len(txt), pat, pi + 2, caps)
                    return None
            clen = self._lp_itemlen(pat, pi)
            q = pat[pi + clen] if pi + clen < len(pat) else ''
            if q == '*':
                k = si
                while k < len(s) and self._lp_classmatch1(s, k, pat, pi):
                    k += 1
                while k >= si:
                    r = self._lp_match(s, k, pat, pi + clen + 1, caps)
                    if r is not None:
                        return r
                    k -= 1
                return None
            if q == '+':
                if not self._lp_classmatch1(s, si, pat, pi):
                    return None
                k = si + 1
                while k < len(s) and self._lp_classmatch1(s, k, pat, pi):
                    k += 1
                while k >= si + 1:
                    r = self._lp_match(s, k, pat, pi + clen + 1, caps)
                    if r is not None:
                        return r
                    k -= 1
                return None
            if q == '-':
                k = si
                while True:
                    r = self._lp_match(s, k, pat, pi + clen + 1, caps)
                    if r is not None:
                        return r
                    if k < len(s) and self._lp_classmatch1(s, k, pat, pi):
                        k += 1
                    else:
                        return None
            if q == '?':
                if self._lp_classmatch1(s, si, pat, pi):
                    r = self._lp_match(s, si + 1, pat, pi + clen + 1, caps)
                    if r is not None:
                        return r
                return self._lp_match(s, si, pat, pi + clen + 1, caps)
            if self._lp_classmatch1(s, si, pat, pi):
                si += 1
                pi += clen
                continue
            return None

    def _lp_find(self, s, pat, init=1):
        if not isinstance(s, str):
            s = self._tostring(s)
        if not isinstance(pat, str):
            pat = self._tostring(pat)
        anchor = pat.startswith('^')
        p0 = 1 if anchor else 0
        si = max(0, int(init) - 1)
        while si <= len(s):
            r = self._lp_match(s, si, pat, p0, [])
            if r is not None:
                return (si, r[0], r[1])
            if anchor:
                return None
            si += 1
        return None

    def _lp_scan(self, s, pat, p0, si):
        """Ближайшее совпадение паттерна на позиции >= si (find-семантика)."""
        anchor = p0 > 0
        while si <= len(s):
            r = self._lp_match(s, si, pat, p0, [])
            if r is not None:
                return (si, r[0], r[1])
            if anchor:
                return None
            si += 1
        return None

    def _lp_capargs(self, s, caps, si, endi):
        if not caps:
            return [s[si:endi]]
        out = []
        for c in caps:
            if isinstance(c, tuple):
                out.append(c[1] + 1)
            else:
                e = c[1] if c[1] is not None else len(s)
                out.append(s[c[0]:e])
        return out

    def _lp_expand(self, repl, s, si, endi, caps):
        out = []
        i = 0
        while i < len(repl):
            c = repl[i]
            if c == '%' and i + 1 < len(repl):
                d = repl[i + 1]
                if d == '%':
                    out.append('%')
                    i += 2
                    continue
                if d.isdigit():
                    n = int(d)
                    if n == 0:
                        out.append(s[si:endi])
                    elif n - 1 < len(caps):
                        cc = caps[n - 1]
                        if isinstance(cc, tuple):
                            out.append(str(cc[1] + 1))
                        else:
                            e = cc[1] if cc[1] is not None else len(s)
                            out.append(s[cc[0]:e])
                    i += 2
                    continue
            out.append(c)
            i += 1
        return ''.join(out)

    def _str_find(self, args):
        if len(args) < 2: return None
        s = args[0]; pat = args[1]
        if not isinstance(s, str): s = self._tostring(s)
        if not isinstance(pat, str): pat = self._tostring(pat)
        init = args[2] if len(args) > 2 and args[2] is not None else 1
        plain = args[3] if len(args) > 3 else False
        if plain:
            idx = s.find(pat, max(0, int(init) - 1))
            if idx == -1: return None
            return [idx + 1, idx + len(pat)]
        r = self._lp_find(s, pat, init)
        if r is None: return None
        si, endi, caps = r
        out = [si + 1, endi]
        for c in caps:
            if isinstance(c, tuple):
                out.append(c[1] + 1)
            else:
                e = c[1] if c[1] is not None else len(s)
                out.append(s[c[0]:e])
        return out

    def _str_match(self, args):
        if len(args) < 2: return None
        s = args[0]; pat = args[1]
        init = args[2] if len(args) > 2 and args[2] is not None else 1
        r = self._lp_find(s, pat, init)
        if r is None: return None
        si, endi, caps = r
        if not isinstance(s, str): s = self._tostring(s)
        vals = self._lp_capargs(s, caps, si, endi)
        return vals[0] if len(vals) == 1 else vals

    def _str_gmatch(self, args):
        if len(args) < 2: return None
        s = args[0]; pat = args[1]
        if not isinstance(s, str): s = self._tostring(s)
        if not isinstance(pat, str): pat = self._tostring(pat)
        p0 = 1 if pat.startswith('^') else 0
        state = [0]
        def _nxt(_a):
            r = self._lp_scan(s, pat, p0, state[0])
            if r is None:
                return None
            si, endi, caps = r
            state[0] = endi if endi > si else si + 1
            return self._lp_capargs(s, caps, si, endi)
        return _nxt

    def _str_gsub(self, args):
        if len(args) < 3: return None
        s = args[0]
        if not isinstance(s, str): s = self._tostring(s)
        pat = args[1]
        if not isinstance(pat, str): pat = self._tostring(pat)
        repl = args[2]
        nmax = None
        if len(args) > 3 and args[3] is not None:
            try: nmax = int(args[3])
            except Exception: nmax = None
        anchor = pat.startswith('^')
        p0 = 1 if anchor else 0
        res = []
        last = 0
        si = 0
        count = 0
        while si <= len(s) and (nmax is None or count < nmax):
            r = self._lp_scan(s, pat, p0, si)
            if r is None:
                break
            msi, endi, caps = r
            if endi < msi:
                break
            si = msi
            key_vals = self._lp_capargs(s, caps, si, endi)
            key = key_vals[0]
            rep = None
            if isinstance(repl, str):
                rep = self._lp_expand(repl, s, si, endi, caps)
            elif isinstance(repl, LuaTable):
                v = self._tbl_meta_get(repl, key)
                if isinstance(v, list): v = v[0] if v else None
                if v is not None and v is not False:
                    rep = self._tostring(v)
            elif isinstance(repl, LuaFunction) or callable(repl):
                v = self._call_function(repl, key_vals)
                if isinstance(v, list): v = v[0] if v else None
                if v is not None and v is not False:
                    rep = self._tostring(v)
            if rep is None:
                rep = s[si:endi]
            res.append(s[last:si])
            res.append(rep)
            last = endi
            count += 1
            si = endi if endi > si else si + 1
            if anchor:
                break
        res.append(s[last:])
        return [''.join(res), count]

    # ─── string.pack / unpack ─────────────────────────────────────────

    def _tobytes(self, v):
        if v is None:
            return b''
        if isinstance(v, str):
            return bytes(ord(ch) & 0xFF for ch in v)
        if isinstance(v, bytes):
            return v
        return self._tostring(v).encode('latin-1', 'replace')

    def _pack_parse(self, fmt):
        ops = []
        endian = '<'
        maxalign = None
        i = 0
        n = len(fmt)
        while i < n:
            c = fmt[i]
            if c in ' \t':
                i += 1
                continue
            if c == '<':
                endian = '<'; i += 1; continue
            if c == '>':
                endian = '>'; i += 1; continue
            if c in ('=', '!'):
                if c == '=':
                    endian = '<'; i += 1; continue
                j = i + 1
                while j < n and fmt[j].isdigit():
                    j += 1
                maxalign = int(fmt[i + 1:j]) if j > i + 1 else 16
                i = j
                continue
            if c == 'x':
                ops.append(('pad', 1)); i += 1; continue
            if c == 'z':
                ops.append(('z',)); i += 1; continue
            if c == 's':
                j = i + 1
                while j < n and fmt[j].isdigit():
                    j += 1
                sz = int(fmt[i + 1:j]) if j > i + 1 else 8
                ops.append(('s', sz, endian)); i = j; continue
            if c == 'c':
                j = i + 1
                while j < n and fmt[j].isdigit():
                    j += 1
                if j == i + 1:
                    raise LuaSandboxError("string.pack: 'c' needs a size")
                ops.append(('c', int(fmt[i + 1:j]))); i = j; continue
            if c in 'bB':
                ops.append(('int', 1, c == 'b', endian, maxalign))
            elif c in 'hH':
                ops.append(('int', 2, c == 'h', endian, maxalign))
            elif c in 'lL':
                ops.append(('int', 4, c == 'l', endian, maxalign))
            elif c in 'jJ':
                ops.append(('int', 8, c == 'j', endian, maxalign))
            elif c == 'T':
                ops.append(('int', 8, False, endian, maxalign))
            elif c in 'iI':
                j = i + 1
                while j < n and fmt[j].isdigit():
                    j += 1
                sz = int(fmt[i + 1:j]) if j > i + 1 else 4
                ops.append(('int', sz, c == 'i', endian, maxalign))
                i = j - 1
            elif c == 'f':
                ops.append(('float', 4, endian, maxalign))
            elif c in 'dn':
                ops.append(('float', 8, endian, maxalign))
            else:
                raise LuaSandboxError('string.pack: unsupported format %r' % fmt)
            i += 1
        return ops

    def _str_pack(self, args):
        if not args: return ''
        fmt = args[0]
        if not isinstance(fmt, str): fmt = self._tostring(fmt)
        import struct as _st
        ops = self._pack_parse(fmt)
        out = bytearray()
        vi = 1
        for op in ops:
            t = op[0]
            if t == 'pad':
                out += b'\0' * op[1]
                continue
            if t in ('int', 'float'):
                ma = op[-1]
                if ma:
                    a = min(op[1], ma)
                    if a > 1:
                        out += b'\0' * ((-len(out)) % a)
            if t == 'int':
                size, signed, en = op[1], op[2], op[3]
                v = args[vi] if vi < len(args) else 0
                vi += 1
                iv = int(self._to_number(v)) & ((1 << (8 * size)) - 1)
                out += iv.to_bytes(size, 'little' if en == '<' else 'big')
            elif t == 'float':
                size, en = op[1], op[2]
                v = args[vi] if vi < len(args) else 0
                vi += 1
                fv = float(self._to_number(v))
                code = ('<' if en == '<' else '>') + ('f' if size == 4 else 'd')
                out += _st.pack(code, fv)
            elif t == 'z':
                v = args[vi] if vi < len(args) else ''
                vi += 1
                out += self._tobytes(v).replace(b'\0', b'') + b'\0'
            elif t == 's':
                size, en = op[1], op[2]
                v = args[vi] if vi < len(args) else ''
                vi += 1
                b = self._tobytes(v)
                out += len(b).to_bytes(size, 'little' if en == '<' else 'big')
                out += b
            elif t == 'c':
                sz = op[1]
                v = args[vi] if vi < len(args) else ''
                vi += 1
                b = self._tobytes(v)[:sz]
                out += b + b'\0' * (sz - len(b))
        return out.decode('latin-1')

    def _str_unpack(self, args):
        if len(args) < 2: return None
        fmt = args[0]; s = args[1]
        if not isinstance(fmt, str): fmt = self._tostring(fmt)
        pos = int(args[2]) if len(args) > 2 and args[2] is not None else 1
        import struct as _st
        ops = self._pack_parse(fmt)
        b = self._tobytes(s)
        p = max(0, pos - 1)
        vals = []
        for op in ops:
            t = op[0]
            if t == 'pad':
                p += op[1]
                continue
            if t in ('int', 'float'):
                ma = op[-1]
                if ma:
                    a = min(op[1], ma)
                    if a > 1:
                        p += (-p) % a
            if t == 'int':
                size, signed, en = op[1], op[2], op[3]
                if p + size > len(b):
                    raise LuaSandboxError('string.unpack: data too short')
                vals.append(int.from_bytes(b[p:p + size], 'little' if en == '<' else 'big', signed=signed))
                p += size
            elif t == 'float':
                size, en = op[1], op[2]
                if p + size > len(b):
                    raise LuaSandboxError('string.unpack: data too short')
                code = ('<' if en == '<' else '>') + ('f' if size == 4 else 'd')
                vals.append(_st.unpack(code, b[p:p + size])[0])
                p += size
            elif t == 'z':
                e = b.find(b'\0', p)
                if e < 0:
                    e = len(b)
                vals.append(b[p:e].decode('latin-1'))
                p = e + 1
            elif t == 's':
                size, en = op[1], op[2]
                if p + size > len(b):
                    raise LuaSandboxError('string.unpack: data too short')
                ln = int.from_bytes(b[p:p + size], 'little' if en == '<' else 'big')
                p += size
                vals.append(b[p:p + ln].decode('latin-1'))
                p += ln
            elif t == 'c':
                sz = op[1]
                vals.append(b[p:p + sz].decode('latin-1'))
                p += sz
        vals.append(p + 1)
        return vals

    def _str_packsize(self, args):
        if not args: return None
        fmt = args[0]
        if not isinstance(fmt, str): fmt = self._tostring(fmt)
        ops = self._pack_parse(fmt)
        p = 0
        for op in ops:
            t = op[0]
            if t in ('z', 's'):
                raise LuaSandboxError('string.packsize: variable-length format')
            if t == 'pad':
                p += op[1]
                continue
            if t == 'c':
                p += op[1]
                continue
            size = op[1]
            ma = op[-1]
            if ma:
                a = min(size, ma)
                if a > 1:
                    p += (-p) % a
            p += size
        return p

    def _str_split(self, args):
        if not args or args[0] is None: return None
        s = args[0]
        if not isinstance(s, str): s = self._tostring(s)
        sep = args[1] if len(args) > 1 and isinstance(args[1], str) else ','
        t = LuaTable()
        t._array.extend(s.split(sep))
        return t

    # ─── metatables ───────────────────────────────────────────────────

    def _setmetatable(self, args):
        if args and isinstance(args[0], LuaTable):
            mt = args[1] if len(args) > 1 else None
            args[0].metatable = mt if isinstance(mt, LuaTable) else None
            return args[0]
        return args[0] if args else None

    def _getmetatable(self, args):
        if args and isinstance(args[0], LuaTable):
            return getattr(args[0], 'metatable', None)
        return None

    def _tbl_meta_get(self, tbl, key, _depth=0):
        if not isinstance(tbl, LuaTable) or _depth > 8:
            return None
        v = tbl.rawget(key)
        if v is not None:
            return v
        mt = getattr(tbl, 'metatable', None)
        if not isinstance(mt, LuaTable):
            return None
        idx = mt.rawget('__index')
        if idx is None:
            return None
        if isinstance(idx, LuaTable):
            return self._tbl_meta_get(idx, key, _depth + 1)
        if isinstance(idx, LuaFunction) or callable(idx):
            r = self._call_function(idx, [tbl, key])
            if isinstance(r, list):
                r = r[0] if r else None
            return r
        return None


    # ─── Table helpers ────────────────────────────────────────────────

    def _tbl_create(self, args):
        n = int(args[0]) if args and args[0] is not None else 0
        val = args[1] if len(args) > 1 else None
        t = LuaTable()
        if n < 0:
            n = 0
        if n > 4_000_000:
            raise LuaSandboxError('table.create: size too large (%d)' % n)
        t._array = [val] * n if val is not None else [None] * n
        return t

    def _tbl_clear(self, args):
        if args and isinstance(args[0], LuaTable):
            args[0]._array = []
            args[0]._hash = {}
        return None

    def _tbl_find(self, args):
        if len(args) < 2 or not isinstance(args[0], LuaTable):
            return None
        tbl, val = args[0], args[1]
        init = int(args[2]) if len(args) > 2 and args[2] is not None else 1
        for k in range(init, len(tbl._array) + 1):
            if tbl.rawget(k) == val:
                return k
        return None

    def _tbl_pack(self, args):
        t = LuaTable()
        t._array = list(args)
        t.rawset('n', len(args))
        return t

    def _tbl_move(self, zargs):
        if len(zargs) < 4 or not isinstance(zargs[0], LuaTable):
            return zargs[4] if len(zargs) > 4 else None
        a1, f, e, t = zargs[0], int(zargs[1]), int(zargs[2]), int(zargs[3])
        a2 = zargs[4] if len(zargs) > 4 and isinstance(zargs[4], LuaTable) else a1
        if e >= f:
            if t > f and a1 is a2:
                for k in range(e, f - 1, -1):
                    a2.rawset(t + k - f, a1.rawget(k))
            else:
                for k in range(f, e + 1):
                    a2.rawset(t + k - f, a1.rawget(k))
        return a2

    def _tbl_sort(self, args):
        if not args or not isinstance(args[0], LuaTable):
            return None
        tbl = args[0]
        comp = args[1] if len(args) > 1 else None
        n = tbl.length()
        items = [tbl.rawget(k) for k in range(1, n + 1)]
        if comp is not None:
            import functools
            def _cmp(a, b):
                r = self._call_function(comp, [a, b])
                return -1 if self._lua_truthy(r) else 1
            try:
                items.sort(key=functools.cmp_to_key(_cmp))
            except Exception:
                raise LuaSandboxError('table.sort: invalid order function')
        else:
            try:
                items.sort(key=lambda x: (x is None, x))
            except Exception:
                raise LuaSandboxError('table.sort: attempt to compare values')
        tbl._array = items
        return None

    def _tbl_concat(self, args):
        if not args or not isinstance(args[0], LuaTable): return ''
        tbl = args[0]
        sep = args[1] if len(args) > 1 else ''
        i = int(args[2]) if len(args) > 2 else 1
        j = int(args[3]) if len(args) > 3 else tbl.length()
        parts = []
        for k in range(i, j+1):
            v = tbl.rawget(k)
            parts.append(self._tostring(v))
        return (sep or '').join(parts)

    def _tbl_insert(self, args):
        if not args or not isinstance(args[0], LuaTable): return
        tbl = args[0]
        if len(args) == 2:
            tbl._array.append(args[1])
        elif len(args) >= 3:
            idx = int(args[1]) - 1
            tbl._array.insert(idx, args[2])

    def _tbl_remove(self, args):
        if not args or not isinstance(args[0], LuaTable): return None
        tbl = args[0]
        idx = int(args[1]) - 1 if len(args) > 1 else len(tbl._array) - 1
        if 0 <= idx < len(tbl._array):
            return tbl._array.pop(idx)
        return None

    # ─── Misc helpers ─────────────────────────────────────────────────

    def _tostring(self, v):
        if v is None: return 'nil'
        if v is True: return 'true'
        if v is False: return 'false'
        if isinstance(v, float):
            if v == int(v): return str(int(v))
            return str(v)
        if isinstance(v, int): return str(v)
        if isinstance(v, str): return v
        if isinstance(v, LuaTable): return 'table'
        if isinstance(v, LuaFunction): return 'function'
        if callable(v): return 'function'
        return str(v)

    def _tonumber(self, args):
        if not args: return None
        v = args[0]
        base = int(args[1]) if len(args) > 1 else 10
        try:
            if isinstance(v, (int, float)): return v
            return int(str(v), base) if base != 10 else float(str(v))
        except Exception:
            return None

    def _type(self, v):
        if v is None: return 'nil'
        if isinstance(v, bool): return 'boolean'
        if isinstance(v, (int, float)): return 'number'
        if isinstance(v, str): return 'string'
        if isinstance(v, LuaTable): return 'table'
        if isinstance(v, LuaFunction) or callable(v): return 'function'
        return 'userdata'

    def _ipairs(self, args):
        if not args or not isinstance(args[0], LuaTable): return None
        tbl = args[0]
        idx = [0]
        def iterator(iargs):
            idx[0] += 1
            v = tbl.rawget(idx[0])
            if v is None: return [None]
            return [idx[0], v]
        return [iterator, tbl, 0]

    def _pairs(self, args):
        if not args or not isinstance(args[0], LuaTable): return None
        tbl = args[0]
        keys = list(range(1, len(tbl._array)+1)) + list(tbl._hash.keys())
        idx = [0]
        def iterator(iargs):
            while idx[0] < len(keys):
                k = keys[idx[0]]; idx[0] += 1
                v = tbl.rawget(k)
                if v is not None:
                    return [k, v]
            return [None]
        return [iterator, tbl, None]

    def _unpack(self, args):
        if not args or not isinstance(args[0], LuaTable): return []
        tbl = args[0]
        i = int(args[1]) if len(args) > 1 else 1
        j = int(args[2]) if len(args) > 2 else tbl.length()
        return [tbl.rawget(k) for k in range(i, j+1)]

    def _select(self, args):
        if not args: return None
        idx = args[0]; rest = args[1:]
        if isinstance(idx, str) and idx.lstrip('\\') == '#': return len(rest)
        try:
            i = int(idx)
            if i < 0: i = len(rest) + i + 1
            return rest[i-1:] if i <= len(rest) else []
        except Exception:
            return None

    def _rawset(self, args):
        if len(args) >= 3 and isinstance(args[0], LuaTable):
            args[0].rawset(args[1], args[2])
        return args[0] if args else None

    def _pcall(self, args):
        if not args: return [False, 'no function']
        fn = args[0]; fn_args = args[1:]
        try:
            result = self._call_function(fn, fn_args)
            if isinstance(result, list):
                return [True] + result
            return [True, result]
        except LuaSandboxError as e:
            return [False, str(e)]
        except Exception as e:
            return [False, str(e)]

    def _next(self, args):
        if not args or not isinstance(args[0], LuaTable): return [None, None]
        tbl = args[0]
        key = args[1] if len(args) > 1 else None
        all_keys = list(range(1, len(tbl._array)+1)) + list(tbl._hash.keys())
        if key is None:
            if all_keys:
                k = all_keys[0]
                return [k, tbl.rawget(k)]
            return [None, None]
        try:
            idx = all_keys.index(key)
            if idx + 1 < len(all_keys):
                k = all_keys[idx+1]
                return [k, tbl.rawget(k)]
        except ValueError:
            pass
        return [None, None]

    # ─── Core execution ───────────────────────────────────────────────

    def _step(self):
        self._steps += 1
        if self._steps > self.MAX_STEPS:
            raise LuaSandboxError(f'exceeded {self.MAX_STEPS} steps')

    def execute(self, lua_code: str, env: dict = None) -> dict:
        if not HAS_PARSER:
            raise LuaSandboxError('Parser not available')

        self._steps = 0
        self._depth = 0

        try:
            lexer = Lexer(lua_code)
            tokens = lexer.tokenize()
            parser = Parser(tokens)
            chunk = parser.parse()
        except Exception as e:
            raise LuaSandboxError(f'Parse error: {e}')

        exec_env = dict(self._globals)
        if env:
            exec_env.update(env)
        exec_env['_G'] = _EnvTable(exec_env)

        try:
            self._exec_chunk(chunk, exec_env)
        except LuaReturn as r:
            if len(r.values) == 1:
                exec_env['__return__'] = r.values[0]
            elif len(r.values) > 1:
                exec_env['__return__'] = r.values
        except LuaSandboxError:
            raise
        except Exception as e:
            import os as _os
            if _os.environ.get('NZL_SANDBOX_DEBUG'):
                raise  # внутренний traceback для отладки
            raise LuaSandboxError(f'Runtime error: {type(e).__name__}: {e}')

        return exec_env

    def call_function(self, lua_code: str, func_name: str, args: list):
        env = self.execute(lua_code)
        fn = env.get(func_name)
        if fn is None:
            raise LuaSandboxError(f'Function {func_name!r} not found')
        return self._call_function(fn, args, env)

    def eval_expr(self, lua_expr: str):
        result = self.execute(f'return {lua_expr}')
        return result.get('__return__')

    def _exec_chunk(self, chunk, env):
        block = getattr(chunk, 'body', None)
        if block is None:
            if isinstance(chunk, list):
                for stmt in chunk:
                    self._exec_stmt(stmt, env)
            return
        self._exec_block(block, env)

    def _exec_block(self, block, env):
        self._depth += 1
        if self._depth > self.MAX_DEPTH:
            raise LuaSandboxError('max recursion depth exceeded')

        try:
            stmts = getattr(block, 'statements', []) or []
            for stmt in stmts:
                self._step()
                self._exec_stmt(stmt, env)

            ret = getattr(block, 'return_stat', None)
            if ret is not None:
                values = self._exec_return(ret, env)
                raise LuaReturn(values)
            return []
        finally:
            self._depth -= 1

    def _exec_return(self, ret_node, env):
        values_nodes = getattr(ret_node, 'values', []) or []
        results = []
        for i, v in enumerate(values_nodes):
            val = self._eval(v, env)
            if isinstance(val, list) and i == len(values_nodes) - 1:
                results.extend(val)
            elif isinstance(val, list):
                results.append(val[0] if val else None)
            else:
                results.append(val)
        return results

    # ─── Statements ───────────────────────────────────────────────────

    def _exec_stmt(self, stmt, env):
        cls = type(stmt).__name__

        if cls == 'LocalAssignStat':
            self._exec_local_assign(stmt, env)
        elif cls == 'AssignStat':
            self._exec_assign(stmt, env)
        elif cls == 'CallStat':
            call = getattr(stmt, 'call', None)
            if call is not None:
                self._eval(call, env)
        elif cls == 'IfStat':
            self._exec_if(stmt, env)
        elif cls == 'WhileStat':
            self._exec_while(stmt, env)
        elif cls == 'RepeatStat':
            self._exec_repeat(stmt, env)
        elif cls == 'NumericForStat':
            self._exec_numeric_for(stmt, env)
        elif cls == 'GenericForStat':
            self._exec_generic_for(stmt, env)
        elif cls in ('DoStat', 'DoBlockStat'):
            body = getattr(stmt, 'body', None)
            if body:
                self._exec_block(body, env)
        elif cls == 'FunctionDeclStat':
            self._exec_function_decl(stmt, env)
        elif cls == 'LocalFunctionStat':
            self._exec_local_function(stmt, env)
        elif cls == 'ReturnStat':
            values = self._exec_return(stmt, env)
            raise LuaReturn(values)
        elif cls == 'BreakStat':
            raise LuaBreak()
        elif cls == 'CompoundAssignStat':
            self._exec_compound_assign(stmt, env)
        # прочее — молчком

    def _get_name_str(self, node):
        if isinstance(node, str):
            return node
        if node is None:
            return None
        return getattr(node, 'name', None)

    def _exec_local_assign(self, stmt, env):
        names = getattr(stmt, 'names', []) or []
        values_nodes = getattr(stmt, 'values', []) or []

        values = []
        for i, v in enumerate(values_nodes):
            val = self._eval(v, env)
            if isinstance(val, list) and i == len(values_nodes) - 1:
                values.extend(val)
            elif isinstance(val, list):
                values.append(val[0] if val else None)
            else:
                values.append(val)

        for i, name in enumerate(names):
            n = name if isinstance(name, str) else self._get_name_str(name)
            if n:
                v = values[i] if i < len(values) else None
                if isinstance(env, _FuncEnv) and not dict.__contains__(env, n) \
                        and env.upvalue_set(n, v):
                    continue
                env[n] = v

    def _exec_assign(self, stmt, env):
        targets = getattr(stmt, 'targets', []) or []
        values_nodes = getattr(stmt, 'values', []) or []

        values = []
        for i, v in enumerate(values_nodes):
            val = self._eval(v, env)
            if isinstance(val, list) and i == len(values_nodes) - 1:
                values.extend(val)
            elif isinstance(val, list):
                values.append(val[0] if val else None)
            else:
                values.append(val)

        for i, target in enumerate(targets):
            val = values[i] if i < len(values) else None
            self._assign_target(target, val, env)

    def _assign_target(self, target, value, env):
        cls = type(target).__name__
        if cls == 'NameExpr':
            n = getattr(target, 'name', None)
            if n:
                if isinstance(env, _FuncEnv) and not dict.__contains__(env, n) \
                        and env.upvalue_set(n, value):
                    return
                env[n] = value
        elif cls == 'IndexExpr':
            obj = self._eval(getattr(target, 'obj', None), env)
            if isinstance(obj, list): obj = obj[0] if obj else None
            is_dot = getattr(target, 'is_dot', False)
            idx_node = getattr(target, 'index', None)
            if is_dot:
                if isinstance(idx_node, str):
                    key = idx_node
                elif hasattr(idx_node, 'value'):
                    key = idx_node.value
                elif hasattr(idx_node, 'name'):
                    key = idx_node.name
                else:
                    key = None
            else:
                key = self._eval(idx_node, env)
                if isinstance(key, list): key = key[0] if key else None
            if isinstance(obj, LuaTable) and key is not None:
                obj.rawset(key, value)

    def _exec_compound_assign(self, stmt, env):
        target = getattr(stmt, 'target', None) or (getattr(stmt, 'targets', [None])[0])
        op = getattr(stmt, 'op', '+')
        val_node = getattr(stmt, 'value', None) or (getattr(stmt, 'values', [None])[0])
        current = self._eval(target, env)
        rhs = self._eval(val_node, env)
        result = self._apply_binop(op, current, rhs)
        self._assign_target(target, result, env)

    def _exec_if(self, stmt, env):
        branches = getattr(stmt, 'branches', []) or []
        else_block = getattr(stmt, 'else_block', None) or getattr(stmt, 'else_body', None)

        for pair in branches:
            if isinstance(pair, (tuple, list)) and len(pair) >= 2:
                condition, body = pair[0], pair[1]
            else:
                condition = getattr(pair, 'cond', None) or getattr(pair, 'condition', None)
                body = getattr(pair, 'body', None) or getattr(pair, 'block', None)
            if self._lua_truthy(self._eval(condition, env)):
                self._exec_block(body, env)
                return

        if else_block:
            self._exec_block(else_block, env)

    def _exec_while(self, stmt, env):
        condition = getattr(stmt, 'cond', None) or getattr(stmt, 'condition', None)
        body = getattr(stmt, 'body', None)
        while self._lua_truthy(self._eval(condition, env)):
            self._step()
            try:
                self._exec_block(body, env)
            except LuaBreak:
                break

    def _exec_repeat(self, stmt, env):
        condition = getattr(stmt, 'cond', None) or getattr(stmt, 'condition', None)
        body = getattr(stmt, 'body', None)
        while True:
            self._step()
            try:
                self._exec_block(body, env)
            except LuaBreak:
                break
            if self._lua_truthy(self._eval(condition, env)):
                break

    def _exec_numeric_for(self, stmt, env):
        var_name = getattr(stmt, 'var', None)
        if not isinstance(var_name, str):
            var_name = self._get_name_str(var_name)

        start_val = self._to_number(self._eval(getattr(stmt, 'start', None), env))
        stop_val = self._to_number(self._eval(getattr(stmt, 'stop', None), env))
        step_node = getattr(stmt, 'step', None)
        step_val = self._to_number(self._eval(step_node, env)) if step_node else 1.0
        body = getattr(stmt, 'body', None)

        if step_val == 0:
            raise LuaSandboxError("'for' step is zero")

        has_saved = var_name in env
        saved = env.get(var_name)

        i = start_val
        while (step_val > 0 and i <= stop_val) or (step_val < 0 and i >= stop_val):
            self._step()
            env[var_name] = i
            try:
                self._exec_block(body, env)
            except LuaBreak:
                break
            i += step_val

        if has_saved:
            env[var_name] = saved
        else:
            env.pop(var_name, None)

    def _exec_generic_for(self, stmt, env):
        names = getattr(stmt, 'names', None) or getattr(stmt, 'vars', []) or []
        exprs = getattr(stmt, 'exprs', None) or getattr(stmt, 'iterators', []) or []
        body = getattr(stmt, 'body', None)

        var_names = [n if isinstance(n, str) else self._get_name_str(n) for n in names]

        iter_vals = []
        for e in exprs:
            v = self._eval(e, env)
            if isinstance(v, list):
                iter_vals.extend(v)
            else:
                iter_vals.append(v)

        if len(iter_vals) >= 1 and (callable(iter_vals[0]) or isinstance(iter_vals[0], LuaFunction)):
            iter_fn = iter_vals[0]
            state = iter_vals[1] if len(iter_vals) > 1 else None
            control = iter_vals[2] if len(iter_vals) > 2 else None

            saved = {n: env.get(n) for n in var_names if n in env}
            had = {n: (n in env) for n in var_names}

            while True:
                self._step()
                results = self._call_function(iter_fn, [state, control], env)
                if not isinstance(results, list):
                    results = [results]
                if not results or results[0] is None:
                    break
                control = results[0]
                for i, vname in enumerate(var_names):
                    env[vname] = results[i] if i < len(results) else None
                try:
                    self._exec_block(body, env)
                except LuaBreak:
                    break

            for n in var_names:
                if had.get(n):
                    env[n] = saved[n]
                else:
                    env.pop(n, None)

    def _exec_function_decl(self, stmt, env):
        target = getattr(stmt, 'target', None) or getattr(stmt, 'name', None)
        method_name = getattr(stmt, 'method_name', None)
        func_node = getattr(stmt, 'func', None) or getattr(stmt, 'body', None)

        fn = self._make_lua_function(func_node, env, is_method=(method_name is not None))

        if target is None:
            return

        cls = type(target).__name__
        if cls == 'NameExpr':
            name = target.name
            if method_name:
                obj = env.get(name)
                if isinstance(obj, LuaTable):
                    obj.rawset(method_name, fn)
            else:
                env[name] = fn
        elif cls == 'IndexExpr':
            parent = self._eval(getattr(target, 'obj', None), env)
            is_dot = getattr(target, 'is_dot', True)
            idx_node = getattr(target, 'index', None)
            if is_dot:
                if isinstance(idx_node, str):
                    key = idx_node
                elif hasattr(idx_node, 'value'):
                    key = idx_node.value
                elif hasattr(idx_node, 'name'):
                    key = idx_node.name
                else:
                    key = None
            else:
                key = self._eval(idx_node, env)
            if isinstance(parent, LuaTable) and key is not None:
                if method_name:
                    sub = parent.rawget(key)
                    if isinstance(sub, LuaTable):
                        sub.rawset(method_name, fn)
                else:
                    parent.rawset(key, fn)

    def _exec_local_function(self, stmt, env):
        name = getattr(stmt, 'name', None)
        if not isinstance(name, str):
            name = self._get_name_str(name)
        func_node = getattr(stmt, 'func', None) or getattr(stmt, 'body', None)
        env[name] = None
        fn = self._make_lua_function(func_node, env)
        env[name] = fn
        if isinstance(fn, LuaFunction):
            fn.closure[name] = fn

    def _make_lua_function(self, func_node, env, is_method=False):
        if func_node is None:
            return None
        raw_params = getattr(func_node, 'params', []) or []
        is_vararg = getattr(func_node, 'is_vararg', False)
        params = []
        for p in raw_params:
            if isinstance(p, str):
                if p == '...':
                    is_vararg = True
                else:
                    params.append(p)
            else:
                n = self._get_name_str(p)
                if n == '...' or n is None:
                    is_vararg = True
                else:
                    params.append(n)
        if is_method:
            params = ['self'] + params
        body = getattr(func_node, 'body', None)
        return LuaFunction(params, body, env, self, is_vararg)

    # ─── Expressions ──────────────────────────────────────────────────

    def _eval(self, node, env):
        if node is None:
            return None

        cls = type(node).__name__

        if cls in ('NumberLit', 'Num'):
            return getattr(node, 'value', 0)
        elif cls in ('StringLit', 'Str'):
            return getattr(node, 'value', '')
        elif cls in ('BoolLit', 'Bool'):
            return getattr(node, 'value', False)
        elif cls in ('NilLit', 'Nil'):
            return None
        elif cls in ('VarArg', 'Vararg', 'VarargLit'):
            return env.get('...', [])
        elif cls == 'NameExpr':
            return env.get(getattr(node, 'name', ''))
        elif cls == 'BinaryOp':
            op = getattr(node, 'op', '')
            if op == 'and':
                left = self._eval(getattr(node, 'left', None), env)
                if isinstance(left, list): left = left[0] if left else None
                if not self._lua_truthy(left): return left
                right = self._eval(getattr(node, 'right', None), env)
                if isinstance(right, list): right = right[0] if right else None
                return right
            if op == 'or':
                left = self._eval(getattr(node, 'left', None), env)
                if isinstance(left, list): left = left[0] if left else None
                if self._lua_truthy(left): return left
                right = self._eval(getattr(node, 'right', None), env)
                if isinstance(right, list): right = right[0] if right else None
                return right
            left = self._eval(getattr(node, 'left', None), env)
            right = self._eval(getattr(node, 'right', None), env)
            if isinstance(left, list): left = left[0] if left else None
            if isinstance(right, list): right = right[0] if right else None
            return self._apply_binop(op, left, right)
        elif cls == 'UnaryOp':
            op = getattr(node, 'op', '')
            operand = self._eval(getattr(node, 'operand', None) or getattr(node, 'expr', None), env)
            if isinstance(operand, list): operand = operand[0] if operand else None
            return self._apply_unop(op, operand)
        elif cls == 'IndexExpr':
            obj = self._eval(getattr(node, 'obj', None), env)
            if isinstance(obj, list): obj = obj[0] if obj else None
            is_dot = getattr(node, 'is_dot', False)
            idx_node = getattr(node, 'index', None)
            if is_dot:
                if isinstance(idx_node, str):
                    key = idx_node
                elif hasattr(idx_node, 'value'):
                    key = idx_node.value
                elif hasattr(idx_node, 'name'):
                    key = idx_node.name
                else:
                    key = self._eval(idx_node, env)
            else:
                key = self._eval(idx_node, env)
                if isinstance(key, list): key = key[0] if key else None
            if obj is None:
                return None
            if isinstance(obj, LuaTable):
                return self._tbl_meta_get(obj, key)
            if isinstance(obj, dict):
                return obj.get(key)
            if isinstance(obj, str) and key is not None:
                str_lib = self._globals.get('string')
                if isinstance(str_lib, LuaTable):
                    return str_lib.rawget(key)
            return None
        elif cls == 'CallExpr':
            return self._exec_call(node, env)
        elif cls == 'MethodCallExpr':
            return self._exec_method_call(node, env)
        elif cls == 'TableExpr':
            return self._eval_table(node, env)
        elif cls == 'FunctionExpr':
            return self._make_lua_function(node, env)
        elif cls in ('ParenExpr', 'Paren'):
            inner_node = getattr(node, 'inner', None)
            if inner_node is None:
                inner_node = getattr(node, 'expr', None)
            inner = self._eval(inner_node, env)
            if isinstance(inner, list):
                return inner[0] if inner else None
            return inner
        elif isinstance(node, (int, float, str, bool)):
            return node

        return None

    def _exec_call(self, node, env):
        func_node = getattr(node, 'func', None)
        args_nodes = getattr(node, 'args', []) or []
        fn = self._eval(func_node, env)
        if isinstance(fn, list):
            fn = fn[0] if fn else None
        args = self._eval_args(args_nodes, env)
        return self._call_function(fn, args, env)

    def _exec_method_call(self, node, env):
        obj_node = getattr(node, 'obj', None)
        method = getattr(node, 'method', '')
        args_nodes = getattr(node, 'args', []) or []
        obj = self._eval(obj_node, env)
        if isinstance(obj, list):
            obj = obj[0] if obj else None
        args = self._eval_args(args_nodes, env)

        fn = None
        if isinstance(obj, LuaTable):
            fn = self._tbl_meta_get(obj, method)
        elif isinstance(obj, str):
            str_lib = self._globals.get('string')
            if isinstance(str_lib, LuaTable):
                fn = str_lib.rawget(method)

        if fn is None:
            return None
        return self._call_function(fn, [obj] + args, env)

    def _eval_args(self, args_nodes, env):
        args = []
        for i, a in enumerate(args_nodes):
            val = self._eval(a, env)
            if i == len(args_nodes) - 1 and isinstance(val, list):
                args.extend(val)
            else:
                if isinstance(val, list):
                    args.append(val[0] if val else None)
                else:
                    args.append(val)
        return args

    def _eval_table(self, node, env):
        tbl = LuaTable()
        fields = getattr(node, 'fields', []) or []
        array_idx = 1

        for i, field in enumerate(fields):
            key = getattr(field, 'key', None)
            value_node = getattr(field, 'value', field)
            is_name = getattr(field, 'is_name', False)

            val = self._eval(value_node, env)

            if key is None:
                if isinstance(val, list) and i == len(fields) - 1:
                    for v in val:
                        tbl.rawset(array_idx, v)
                        array_idx += 1
                else:
                    if isinstance(val, list):
                        val = val[0] if val else None
                    tbl.rawset(array_idx, val)
                    array_idx += 1
            else:
                if is_name:
                    if isinstance(key, str):
                        k = key
                    elif hasattr(key, 'value'):
                        k = key.value
                    elif hasattr(key, 'name'):
                        k = key.name
                    else:
                        k = self._eval(key, env)
                else:
                    k = self._eval(key, env)
                    if isinstance(k, list): k = k[0] if k else None
                if isinstance(val, list): val = val[0] if val else None
                tbl.rawset(k, val)

        return tbl

    def _call_function(self, fn, args, env=None):
        self._step()
        if fn is None:
            return None
        if isinstance(fn, LuaFunction):
            try:
                fn.call(args)
                return None
            except LuaReturn as r:
                if len(r.values) == 0: return None
                if len(r.values) == 1: return r.values[0]
                return r.values
            except LuaBreak:
                return None
        if isinstance(fn, LuaTable):
            cc = None
            mt = getattr(fn, 'metatable', None)
            while isinstance(mt, LuaTable):
                cc = mt.rawget('__call')
                if cc is not None:
                    break
                mt = getattr(mt, 'metatable', None)
            if cc is not None and cc is not fn:
                return self._call_function(cc, [fn] + list(args), env)
            return None
        if callable(fn):
            return fn(args)
        return None

    # ─── Operators ────────────────────────────────────────────────────

    def _apply_binop(self, op, left, right):
        if op == '..':
            return self._tostring(left) + self._tostring(right)
        if op == '==': return left == right
        if op == '~=': return left != right
        if op == '<':
            if isinstance(left, str) and isinstance(right, str): return left < right
            return self._to_number(left) < self._to_number(right)
        if op == '>':
            if isinstance(left, str) and isinstance(right, str): return left > right
            return self._to_number(left) > self._to_number(right)
        if op == '<=':
            if isinstance(left, str) and isinstance(right, str): return left <= right
            return self._to_number(left) <= self._to_number(right)
        if op == '>=':
            if isinstance(left, str) and isinstance(right, str): return left >= right
            return self._to_number(left) >= self._to_number(right)

        l, r = self._to_number(left), self._to_number(right)
        if op == '+': return l + r
        if op == '-': return l - r
        if op == '*': return l * r
        if op == '/': return l / r if r != 0 else math.inf
        if op == '//': return math.floor(l / r) if r != 0 else 0
        if op == '%':
            # Lua: a % b == a - floor(a/b)*b ; для int-ов результат int
            if r == 0: return 0
            v = l - math.floor(l / r) * r
            return int(v) if isinstance(l, int) and isinstance(r, int) else v
        if op == '^': return l ** r

        if op == '&': return int(l) & int(r)
        if op == '|': return int(l) | int(r)
        if op == '~': return int(l) ^ int(r)
        if op == '<<': return (int(l) << int(r)) & 0xFFFFFFFFFFFFFFFF
        if op == '>>': return (int(l) & 0xFFFFFFFFFFFFFFFF) >> int(r)

        return None

    def _apply_unop(self, op, operand):
        if op == '-':
            return -self._to_number(operand)
        if op == 'not':
            return not self._lua_truthy(operand)
        if op == '#':
            if isinstance(operand, str): return len(operand)
            if isinstance(operand, LuaTable): return operand.length()
            return 0
        if op == '~':
            return (~int(self._to_number(operand))) & 0xFFFFFFFFFFFFFFFF
        return None

    def _lua_truthy(self, v):
        return v is not None and v is not False

    def _to_number(self, v):
        if isinstance(v, bool):
            return 1 if v else 0
        if isinstance(v, (int, float)):
            return v
        if isinstance(v, str):
            try:
                return float(v)
            except Exception:
                return 0
        return 0


# ═══════════════════════════════════════════════════════════════════════════════
# ТЕСТЫ
# ═══════════════════════════════════════════════════════════════════════════════

def _run_tests():
    passed = 0
    failed = 0

    def test(name, code, expected, func=None, args=None):
        nonlocal passed, failed
        sb = LuaSandbox()
        try:
            if func:
                result = sb.call_function(code, func, args or [])
            else:
                env = sb.execute(code)
                result = env.get('__return__', env.get('result'))

            ok = result == expected
            if not ok and isinstance(expected, (int, float)) and isinstance(result, (int, float)):
                ok = abs(result - expected) < 1e-9

            if ok:
                print(f'  ✅ {name}')
                passed += 1
            else:
                print(f'  ❌ {name}: got {result!r}, expected {expected!r}')
                failed += 1
        except Exception as e:
            print(f'  ❌ {name}: EXCEPTION {type(e).__name__}: {e}')
            failed += 1

    print('\n🧪 LuaSandbox Tests\n')

    test('Arithmetic', 'result = 2 + 3 * 4', 14)
    test('string.char', 'result = string.char(72, 101, 108, 108, 111)', 'Hello')
    test('string.byte', 'result = string.byte("A")', 65)
    test('table.concat', '''
local t = {"H", "e", "l", "l", "o"}
result = table.concat(t)
''', 'Hello')
    test('XOR decrypt', r'''
local function decrypt(s, key)
    local result = ""
    for i = 1, #s do
        local b = string.byte(s, i)
        result = result .. string.char(bit32.bxor(b, key))
    end
    return result
end
result = decrypt("\42\7\14", 98)
''', 'Hel')
    test('Local vars', '''
local x = 10
local y = 20
result = x + y
''', 30)
    test('If/else', '''
local x = 5
if x > 3 then
    result = "big"
else
    result = "small"
end
''', 'big')
    test('Numeric for', '''
result = 0
for i = 1, 10 do
    result = result + i
end
''', 55)
    test('While loop', '''
result = 0
local i = 1
while i <= 5 do
    result = result + i
    i = i + 1
end
''', 15)
    test('Function return', '''
local function add(a, b)
    return a + b
end
result = add(3, 4)
''', 7)
    test('call_function API',
         'function decrypt(x) return x * 2 end',
         10,
         func='decrypt', args=[5])
    test('Table array', '''
local t = {10, 20, 30}
result = t[1] + t[2] + t[3]
''', 60)
    test('RC4 KSA style', '''
local function ksa(key)
    local s = {}
    for i = 0, 255 do
        s[i+1] = i
    end
    local j = 0
    for i = 0, 255 do
        j = (j + s[i+1] + string.byte(key, (i % #key) + 1)) % 256
        s[i+1], s[j+1] = s[j+1], s[i+1]
    end
    return s[1]
end
result = ksa("key")
''', 107)   # истинный Lua-результат KSA для key="key" (прежде 255 проходило лишь из-за битого ParenExpr)

    print(f'\n{"="*40}')
    print(f'✅ Passed: {passed}/13')
    print(f'❌ Failed: {failed}/13')
    if failed == 0:
        print('🎉 ВСЕ ТЕСТЫ ПРОШЛИ!')
    return failed == 0


if __name__ == '__main__':
    _run_tests()