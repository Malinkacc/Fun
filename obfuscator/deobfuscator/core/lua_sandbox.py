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


class LuaFunction:
    def __init__(self, params, body, closure, sandbox, is_vararg=False):
        self.params = params
        self.body = body
        self.closure = closure
        self.sandbox = sandbox
        self.is_vararg = is_vararg

    def call(self, args):
        env = dict(self.closure)
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
        string_lib.rawset('gmatch', lambda args: None)
        string_lib.rawset('gsub', lambda args: None)

        table_lib = LuaTable()
        table_lib.rawset('concat', lambda args: self._tbl_concat(args))
        table_lib.rawset('insert', lambda args: self._tbl_insert(args))
        table_lib.rawset('remove', lambda args: self._tbl_remove(args))

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
            'setmetatable': lambda args: args[0] if args else None,
            'getmetatable': lambda args: None,
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
            'bit32': self._make_bit32(),
        }

    def _raise_error(self, args):
        raise LuaSandboxError(str(args[0]) if args else 'error')

    def _assert(self, args):
        if args and self._lua_truthy(args[0]):
            return args[0]
        raise LuaSandboxError('assertion failed')

    def _make_bit32(self):
        b = LuaTable()
        b.rawset('band', lambda args: self._band(args))
        b.rawset('bor', lambda args: self._bor(args))
        b.rawset('bxor', lambda args: self._bxor(args))
        b.rawset('bnot', lambda args: (~int(args[0])) & 0xFFFFFFFF if args else 0)
        b.rawset('lshift', lambda args: (int(args[0]) << int(args[1])) & 0xFFFFFFFF if len(args)>=2 else 0)
        b.rawset('rshift', lambda args: (int(args[0]) & 0xFFFFFFFF) >> int(args[1]) if len(args)>=2 else 0)
        b.rawset('arshift', lambda args: int(args[0]) >> int(args[1]) if len(args)>=2 else 0)
        b.rawset('rrotate', lambda args: self._rot32(int(args[0]), -int(args[1])) if len(args)>=2 else 0)
        b.rawset('lrotate', lambda args: self._rot32(int(args[0]), int(args[1])) if len(args)>=2 else 0)
        b.rawset('extract', lambda args: self._extract(args))
        return b

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
        for a in args: r &= int(a)
        return r
    def _bor(self, args):
        r = 0
        for a in args: r |= int(a)
        return r
    def _bxor(self, args):
        r = 0
        for a in args: r ^= int(a)
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

    def _str_find(self, args):
        if len(args) < 2: return None
        s, pat = args[0], args[1]
        plain = args[3] if len(args) > 3 else False
        if plain:
            idx = s.find(pat)
            if idx == -1: return None
            return [idx+1, idx+len(pat)]
        return None

    # ─── Table helpers ────────────────────────────────────────────────

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
        if idx == '#': return len(rest)
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
        elif cls == 'DoStat':
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
                env[n] = values[i] if i < len(values) else None

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
        return LuaFunction(params, body, dict(env), self, is_vararg)

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
        elif cls in ('VarArg', 'Vararg'):
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
                return obj.rawget(key)
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
            fn = obj.rawget(method)
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