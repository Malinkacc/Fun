"""
NZL Deobfuscator - Sandbox Decoder
===================================
[**] KILLER FEATURE [**]

Находит функции расшифровки строк и прогоняет их через LuaSandbox,
заменяя все вызовы на готовые литералы.

API sandbox: call_function(lua_code, func_name, args) — 3 аргумента!
"""

from obfuscator.deobfuscator.core.base import (
    NodeTransformer, NodeVisitor,
    Chunk, Block,
    LocalFunctionStat, FunctionDeclStat, LocalAssignStat, AssignStat,
    CallExpr, NameExpr, IndexExpr,
    NumberLit, StringLit, BoolLit, NilLit,
    FunctionExpr,
    is_literal, get_literal_value, make_literal,
    ast_to_code,
)
from obfuscator.deobfuscator.core.lua_sandbox import (
    LuaSandbox, LuaSandboxError, LuaTable,
)
from obfuscator.ast_unparser import RawByteString
from .base_decoder import BaseDecoder


DECRYPT_HINTS = {
    'string.byte', 'string.char', 'string.sub', 'string.len',
    'bit32.bxor', 'bit32.band', 'bit32.bor', 'bit32.bnot',
    'bit32.lshift', 'bit32.rshift',
    'table.concat', 'table.insert',
}


class _HintScanner(NodeVisitor):
    def __init__(self):
        self.hints = set()
        self.has_string_ops = False
        self.has_loops = False
    
    def visit_IndexExpr(self, node):
        path = self._extract_path(node)
        if path in DECRYPT_HINTS:
            self.hints.add(path)
            if path.startswith('string.') or path.startswith('bit32.'):
                self.has_string_ops = True
        return self.generic_visit(node)
    
    def visit_NumericForStat(self, node):
        self.has_loops = True
        return self.generic_visit(node)
    
    def visit_WhileStat(self, node):
        self.has_loops = True
        return self.generic_visit(node)
    
    def visit_GenericForStat(self, node):
        self.has_loops = True
        return self.generic_visit(node)
    
    def _extract_path(self, node) -> str:
        if isinstance(node, NameExpr):
            return node.name
        if isinstance(node, IndexExpr) and node.is_dot and isinstance(node.index, StringLit):
            base = self._extract_path(node.obj)
            return f"{base}.{node.index.value}"
        return ""


class _NameUsageCounter(NodeVisitor):
    def __init__(self):
        self.counts: dict[str, int] = {}
    
    def visit_NameExpr(self, node):
        self.counts[node.name] = self.counts.get(node.name, 0) + 1
        return node


def _lua_value_to_python(v):
    """Конвертирует Lua-значение в Python.
    ВАЖНО: строки с байтами >127 или control chars оборачиваются в RawByteString,
    чтобы unparser сгенерил \\ddd escape'ы, а не сырой UTF-8 (крокозябры)."""
    if isinstance(v, LuaTable):
        return None
    if isinstance(v, str):
        for ch in v:
            code = ord(ch)
            if code > 126 or (code < 32 and ch not in '\n\r\t'):
                return RawByteString(v)
        return v
    if isinstance(v, (int, float, bool)) or v is None:
        return v
    return None


def _is_folding_candidate(v):
    """True если значение можно превратить в AST-литерал."""
    if v is None: return True
    if isinstance(v, bool): return True
    if isinstance(v, (int, float)):
        if isinstance(v, float):
            import math
            if math.isnan(v) or math.isinf(v):
                return False
        return True
    if isinstance(v, str):
        return True
    return False


class SandboxDecoder(BaseDecoder):
    NAME = "sandbox decoder"
    MIN_STRING_HINTS = 2
    MAX_PARAMS = 3
    
    def __init__(self, verbose: bool = False):
        super().__init__()
        self.verbose = verbose
    
    def run(self, chunk: Chunk):
        from .base_decoder import DecoderStats
        self.stats = DecoderStats(name=self.NAME)
        
        candidates = self._find_candidates(chunk)
        if self.verbose:
            print(f"[sandbox] candidates: {list(candidates.keys())}")
        if not candidates:
            return chunk, self.stats
        
        try:
            preload_code = self._build_preload_code(chunk, candidates)
        except Exception as e:
            self.stats.errors += 1
            self.stats.details.append(f"preload build failed: {type(e).__name__}: {e}")
            return chunk, self.stats
        
        # Smoke-test preload
        try:
            test_sandbox = LuaSandbox()
            test_sandbox.execute(preload_code)
        except Exception as e:
            self.stats.errors += 1
            self.stats.details.append(f"preload smoke-test failed: {type(e).__name__}: {e}")
            if self.verbose:
                import traceback; traceback.print_exc()
            return chunk, self.stats
        
        folder = _CallFolder(preload_code, candidates, self.stats, self.verbose)
        new_chunk = folder.visit(chunk)
        new_chunk = self._prune_unused_decls(new_chunk, candidates)
        return new_chunk, self.stats
    
    def _find_candidates(self, chunk: Chunk) -> dict[str, LocalFunctionStat]:
        result = {}
        for stat in chunk.body.statements:
            if isinstance(stat, LocalFunctionStat):
                if self._looks_like_decrypt(stat.func):
                    result[stat.name] = stat
                    if self.verbose:
                        print(f"[sandbox] candidate: {stat.name}")
        return result
    
    def _looks_like_decrypt(self, func: FunctionExpr) -> bool:
        if len(func.params) > self.MAX_PARAMS or len(func.params) == 0:
            return False
        if func.is_vararg:
            return False
        scanner = _HintScanner()
        scanner.visit(func.body)
        if not scanner.has_string_ops:
            return False
        if len(scanner.hints) < self.MIN_STRING_HINTS:
            return False
        return True
    
    def _build_preload_code(self, chunk: Chunk, candidates: dict) -> str:
        decl_stmts = []
        for stat in chunk.body.statements:
            if isinstance(stat, (LocalFunctionStat, FunctionDeclStat)):
                decl_stmts.append(stat)
            elif isinstance(stat, LocalAssignStat):
                if all(is_literal(v) for v in stat.values):
                    decl_stmts.append(stat)
        if not decl_stmts:
            return ""
        mini_block = Block(line=0, statements=decl_stmts, return_stat=None)
        mini_chunk = Chunk(line=0, body=mini_block)
        return ast_to_code(mini_chunk)
    
    def _prune_unused_decls(self, chunk: Chunk, candidates: dict) -> Chunk:
        counter = _NameUsageCounter()
        counter.visit(chunk)
        new_stmts = []
        for stat in chunk.body.statements:
            if isinstance(stat, LocalFunctionStat) and stat.name in candidates:
                usage = counter.counts.get(stat.name, 0)
                if usage == 0:
                    self.stats.details.append(f"removed unused function '{stat.name}'")
                    continue
            new_stmts.append(stat)
        chunk.body.statements = new_stmts
        return chunk


class _CallFolder(NodeTransformer):
    def __init__(self, preload_code: str, candidates: dict, stats, verbose: bool):
        super().__init__()
        self.preload_code = preload_code
        self.candidates = candidates
        self.stats = stats
        self.verbose = verbose
    
    def visit_CallExpr(self, node):
        node = self.generic_visit(node)
        if not isinstance(node.func, NameExpr):
            return node
        fname = node.func.name
        if fname not in self.candidates:
            return node
        
        self.stats.scanned += 1
        args_py = []
        for arg in node.args:
            if not is_literal(arg):
                return node
            args_py.append(get_literal_value(arg))
        
        sandbox = LuaSandbox()
        try:
            result = sandbox.call_function(self.preload_code, fname, args_py)
        except LuaSandboxError as e:
            self.stats.errors += 1
            self.stats.details.append(f"{fname}(...) sandbox error: {e}")
            return node
        except Exception as e:
            self.stats.errors += 1
            self.stats.details.append(f"{fname}(...) crash: {type(e).__name__}: {e}")
            if self.verbose:
                import traceback; traceback.print_exc()
            return node
        
        if isinstance(result, list):
            if len(result) == 0:
                return node
            result = result[0]
        
        py_val = _lua_value_to_python(result)
        if not _is_folding_candidate(py_val):
            return node
        
        try:
            new_lit = make_literal(py_val, line=node.line)
        except Exception as e:
            self.stats.errors += 1
            self.stats.details.append(f"make_literal fail: {e}")
            return node
        
        self.stats.replaced += 1
        preview = repr(py_val)[:40]
        self.stats.details.append(f"{fname}(...) -> {preview}")
        if self.verbose:
            print(f"[sandbox] {fname}(...) -> {preview}")
        return new_lit


# ============================================================
# TESTS
# ============================================================

if __name__ == "__main__":
    from obfuscator.deobfuscator.core.base import parse_code, ast_to_code
    
    print("=== Test SandboxDecoder ===\n")
    passed = failed = 0
    def test(name, cond, extra=""):
        global passed, failed
        if cond: print(f"  [OK] {name}"); passed += 1
        else:    print(f"  [XX] {name}  ({extra})"); failed += 1
    
    def run_sb(src, verbose=False):
        ast = parse_code(src)
        return SandboxDecoder(verbose=verbose).run(ast)
    
    # TEST 1: XOR 42 -> aeiou
    src1 = '''
local function _d(s)
    local r = ""
    for i = 1, #s do
        r = r .. string.char(bit32.bxor(string.byte(s, i), 42))
    end
    return r
end
local x = _d("\\75\\79\\67\\69\\95")
'''
    new_ast, s1 = run_sb(src1)
    out1 = ast_to_code(new_ast)
    test("XOR 42: replaced==1", s1.replaced == 1, f"stats={s1}")
    test("XOR 42: result = 'aeiou'", "aeiou" in out1, out1[:150])
    test("XOR 42: _d removed", "function _d" not in out1, out1[:150])
    
    # TEST 2: table.concat style
    src2 = '''
local function _dc(s)
    local t = {}
    for i = 1, #s do
        t[i] = string.char(bit32.bxor(string.byte(s, i), 13))
    end
    return table.concat(t)
end
print(_dc("mibbi"))
'''
    new_ast, s2 = run_sb(src2)
    out2 = ast_to_code(new_ast)
    test("table.concat: replaced==1", s2.replaced == 1, f"stats={s2}")
    test("table.concat: folded", 'print("' in out2 or "print('" in out2, out2[:150])
    
    # TEST 3: multiple calls
    src3 = '''
local function _x(s)
    local r = ""
    for i = 1, #s do
        r = r .. string.char(bit32.bxor(string.byte(s, i), 1))
    end
    return r
end
local a = _x("Ic")
local b = _x("Ne")
local c = _x("Nf")
'''
    new_ast, s3 = run_sb(src3)
    out3 = ast_to_code(new_ast)
    test("3 calls: replaced==3", s3.replaced == 3, f"stats={s3}")
    test("3 calls: 'Hb' in output", '"Hb"' in out3 or "'Hb'" in out3, out3[:150])
    test("3 calls: _x removed", "function _x" not in out3, out3[:150])
    
    # TEST 4: shift -1
    src4 = '''
local function _s(s)
    local r = ""
    for i = 1, #s do
        r = r .. string.char(string.byte(s, i) - 1)
    end
    return r
end
local x = _s("Ifmmp")
'''
    new_ast, s4 = run_sb(src4)
    out4 = ast_to_code(new_ast)
    test("shift -1: replaced==1", s4.replaced == 1, f"stats={s4}")
    test("shift -1: -> 'Hello'", "Hello" in out4, out4[:150])
    
    # TEST 5: variable arg
    src5 = '''
local function _d(s)
    local r = ""
    for i = 1, #s do
        r = r .. string.char(bit32.bxor(string.byte(s, i), 42))
    end
    return r
end
local user_input = "hi"
local x = _d(user_input)
'''
    new_ast, s5 = run_sb(src5)
    test("skip call with variable arg", s5.replaced == 0, f"stats={s5}")
    
    # TEST 6: two decrypt functions
    src6 = '''
local function _a(s)
    local r = ""
    for i = 1, #s do
        r = r .. string.char(bit32.bxor(string.byte(s, i), 5))
    end
    return r
end
local function _b(s)
    local r = ""
    for i = 1, #s do
        r = r .. string.char(bit32.bxor(string.byte(s, i), 10))
    end
    return r
end
local x = _a("MMM")
local y = _b("BBB")
'''
    new_ast, s6 = run_sb(src6)
    out6 = ast_to_code(new_ast)
    test("2 functions: replaced==2", s6.replaced == 2, f"stats={s6}")
    test("2 functions: both removed",
         "function _a" not in out6 and "function _b" not in out6, out6[:150])
    
    # TEST 7: keep-if-runtime
    src7 = '''
local function _d(s)
    local r = ""
    for i = 1, #s do
        r = r .. string.char(bit32.bxor(string.byte(s, i), 7))
    end
    return r
end
local static = _d("abc")
some_global(function(v) return _d(v) end)
'''
    new_ast, s7 = run_sb(src7)
    out7 = ast_to_code(new_ast)
    test("keep-if-runtime: static folded", s7.replaced == 1, f"stats={s7}")
    test("keep-if-runtime: _d NOT removed", "function _d" in out7, out7[:150])
    
    # TEST 8: RawByteString wrap для non-ASCII результата
    src8 = '''
local function _bin(s)
    local r = ""
    for i = 1, #s do
        r = r .. string.char(bit32.bxor(string.byte(s, i), 200))
    end
    return r
end
local x = _bin("A")
'''
    new_ast, s8 = run_sb(src8)
    out8 = ast_to_code(new_ast)
    test("high byte -> escaped", "\\" in out8, out8[:150])
    test("high byte NOT raw utf8", "├" not in out8 and "┬" not in out8, out8[:150])
    
    print(f"\n=== TOTAL: {passed}/{passed+failed} ===")
    if failed == 0: print("[!!] SandboxDecoder работает! [**]")
    
    # DEMO
    print("\n=== [**] DEMO: real-world decrypt [**] ===")
    demo = '''
local function _decrypt(s)
    local out = {}
    for i = 1, #s do
        out[i] = string.char(bit32.bxor(string.byte(s, i), 0x2A))
    end
    return table.concat(out)
end
local msg   = _decrypt("\\104\\79\\70\\70\\69")
local url   = _decrypt("\\120\\120\\120\\1\\30\\11\\11\\79\\79\\4\\30\\79\\13\\77\\79\\6")
local flag  = _decrypt("\\126\\79\\70\\70\\79")
print(msg, url, flag)
'''
    print("BEFORE:")
    print(demo)
    new_demo, ds = SandboxDecoder(verbose=False).run(parse_code(demo))
    print("AFTER:")
    print(ast_to_code(new_demo))
    print(f"\n{ds.summary()}")