"""
NZL Deobfuscator - NZL Wrapper Stripper
========================================
Специализированный декодер для НАШЕГО собственного обфускатора.
Убирает всё, что мы сами добавили: watermark, anti-tamper, env-checks,
build-id, dead string_decryptor.

Что удаляем:
  1) `local _nzl = <big number>` — build ID
  2) `local _0xXXX_YYY = pcall(function() ... env-checks ... end)`
  3) `if not _0xXXX_YYY then while ... do end end` — anti-tamper crasher
  4) Мёртвые локальные функции с обфусцированными именами (I0001IOIo и т.п.),
     если они больше не используются после sandbox_decoder'а
  5) StringEncryptor helper (сигнатура: 3 параметра, if/elseif по типу шифра)

Работает как последний проход в pipeline — ПОСЛЕ sandbox_decoder,
чтобы decrypt-функция уже была без вызовов.
"""

import re
from obfuscator.deobfuscator.core.base import (
    NodeVisitor, Chunk, Block,
    LocalAssignStat, AssignStat, IfStat, WhileStat, RepeatStat, DoBlockStat,
    BinaryOp,
    LocalFunctionStat, FunctionDeclStat, CallStat, CallExpr,
    NameExpr, NumberLit, StringLit, BoolLit, NilLit, UnaryOp,
    FunctionExpr, IndexExpr,
)
from .base_decoder import BaseDecoder


class _NameUsageCounter(NodeVisitor):
    def __init__(self):
        self.counts: dict[str, int] = {}
    def visit_NameExpr(self, node):
        self.counts[node.name] = self.counts.get(node.name, 0) + 1
        return node


class NZLWrapperStripper(BaseDecoder):
    """
    Убирает NZL-специфичный boilerplate.
    Работает ТОЛЬКО на верхнем уровне chunk.body.statements.
    """
    
    NAME = "nzl wrapper strip"
    
    # Магическая константа watermark'а (совпадает с NZL:XXXXXXXX build hash)
    NZL_MAGIC_NAMES = {'_nzl'}
    
    # Регексы для распознавания обфусцированных имён
    OBF_NAME_PATTERNS = [
        re.compile(r'^_0x[0-9A-F]+_[a-zA-Z0-9]+$'),   # _0x4F2_IlII0l0
        re.compile(r'^[Il0O1o]{6,}$'),                # I0001IOIo, IOOllIl
    ]
    
    def is_obf_name(self, name: str) -> bool:
        return any(p.match(name) for p in self.OBF_NAME_PATTERNS)
    
    # ==================== ГЛАВНАЯ ЛОГИКА ====================
    
    def run(self, chunk: Chunk):
        from .base_decoder import DecoderStats
        self.stats = DecoderStats(name=self.NAME)
        
        # Считаем использования имён ДО удалений
        counter = _NameUsageCounter()
        counter.visit(chunk)
        # Имена anti-tamper переменных: те, что упомянуты в pcall+if not ... crasher
        antitamper_names = self._find_antitamper_names(chunk)
        
        new_stmts = []
        stmts = list(chunk.body.statements)
        i = 0
        while i < len(stmts):
            stat = stmts[i]
            self.stats.scanned += 1
            nxt = stmts[i + 1] if i + 1 < len(stmts) else None

            # 2.5) env-probe пара: local _0x = <probe> + if ... then hang end
            if self._is_env_probe_pair(stat, nxt):
                self.stats.replaced += 2
                self.stats.details.append(f"removed: env-probe pair ({stat.names[0]})")
                i += 2
                continue
            
            # 1) `local _nzl = <NUMBER>` — build ID
            if self._is_nzl_build_id(stat):
                self.stats.replaced += 1
                self.stats.details.append("removed: local _nzl = <build_id>")
                i += 1
                continue
            
            # 2) `local _0xXXX_YYY = pcall(function() env-checks end)` — anti-tamper init
            if self._is_antitamper_pcall(stat):
                self.stats.replaced += 1
                self.stats.details.append(f"removed: anti-tamper pcall ({stat.names[0]})")
                i += 1
                continue
            
            # 3) `if not _0xXXX_YYY then while true do end end` — anti-tamper crasher
            if self._is_antitamper_crasher(stat, antitamper_names):
                self.stats.replaced += 1
                self.stats.details.append("removed: anti-tamper crasher (if not ... while true)")
                i += 1
                continue
            
            # 4) Мёртвая обфусцированная local function (0 использований)
            if self._is_dead_obf_function(stat, counter.counts):
                self.stats.replaced += 1
                self.stats.details.append(f"removed dead function: {stat.name}")
                i += 1
                continue
            
            new_stmts.append(stat)
            i += 1

        # второй проход: висячие hang-if (их local уже снят) и мёртвые probe-local'и
        defined = set()
        for stat in new_stmts:
            if isinstance(stat, LocalAssignStat):
                defined.update(stat.names)
        counter2 = _NameUsageCounter()
        for stat in new_stmts:
            counter2.visit(stat)
        final = []
        for stat in new_stmts:
            if self._is_dangling_hang_if(stat, defined):
                self.stats.replaced += 1
                self.stats.details.append("removed: dangling hang-if")
                continue
            if self._is_literal_hang_if(stat):
                self.stats.replaced += 1
                self.stats.details.append("removed: opaque hang-if (literal cond)")
                continue
            final.append(stat)

        # pass 3: мёртвые probe-local'и (их hang-if уже снят -> использований 0)
        counter3 = _NameUsageCounter()
        for stat in final:
            counter3.visit(stat)
        final2 = []
        for stat in final:
            if (
                isinstance(stat, LocalAssignStat)
                and len(stat.names) == 1
                and self.is_obf_name(stat.names[0])
                and counter3.counts.get(stat.names[0], 0) == 0
                and stat.values
                and all(
                    self._value_is_literal_or_env(v) and self._value_has_no_call(v)
                    for v in stat.values
                )
            ):
                self.stats.replaced += 1
                self.stats.details.append(f"removed: dead probe local ({stat.names[0]})")
                continue
            final2.append(stat)

        chunk.body.statements = final2
        return chunk, self.stats
    
    # ==================== ДЕТЕКТОРЫ ====================
    
    def _is_nzl_build_id(self, stat) -> bool:
        """local _nzl = 2782434526"""
        if not isinstance(stat, LocalAssignStat):
            return False
        if len(stat.names) != 1 or stat.names[0] not in self.NZL_MAGIC_NAMES:
            return False
        if len(stat.values) != 1 or not isinstance(stat.values[0], NumberLit):
            return False
        return True
    
    def _is_antitamper_pcall(self, stat) -> bool:
        """
        local _0xNAME = pcall(function() ...env-checks with bit32/workspace/identifyexecutor... end)
        """
        if not isinstance(stat, LocalAssignStat):
            return False
        if len(stat.names) != 1 or not self.is_obf_name(stat.names[0]):
            return False
        if len(stat.values) != 1:
            return False
        val = stat.values[0]
        if not isinstance(val, CallExpr):
            return False
        # func должен быть NameExpr('pcall')
        if not isinstance(val.func, NameExpr) or val.func.name != 'pcall':
            return False
        # args[0] должен быть FunctionExpr, и тело должно содержать env-checks
        if not val.args or not isinstance(val.args[0], FunctionExpr):
            return False
        return self._looks_like_env_check_body(val.args[0].body)
    
    def _looks_like_env_check_body(self, body: Block) -> bool:
        """Тело содержит признаки env-check: bit32/workspace/identifyexecutor/type(...)=="function"."""
        keywords = {'bit32', 'workspace', 'identifyexecutor', 'gethui', 'game', 'script'}
        found = set()
        
        def walk(node):
            if isinstance(node, NameExpr) and node.name in keywords:
                found.add(node.name)
            for attr in ('body', 'statements', 'values', 'args', 'branches',
                         'left', 'right', 'operand', 'func', 'obj', 'index',
                         'target', 'cond', 'else_block', 'start', 'stop', 'step',
                         'value', 'inner', 'call'):
                v = getattr(node, attr, None)
                if v is None: continue
                if isinstance(v, list):
                    for it in v:
                        if isinstance(it, tuple):
                            for sub in it:
                                if hasattr(sub, '__dict__'): walk(sub)
                        elif hasattr(it, '__dict__'):
                            walk(it)
                elif hasattr(v, '__dict__'):
                    walk(v)
        
        walk(body)
        return len(found) >= 2
    
    # ==================== ENV-PROBE ПАРЫ (Sprint 3.5 fix) ====================
    # protection/environment генерирует не только pcall-блок, но и отдельные
    # пары верхнего уровня:
    #     local _0xAAA_BBB = task and task.wait
    #     if type(_0xAAA_BBB) ~= "function" then <hang: while/repeat> end
    # Формы hang рандомизированы по seed: while true / while 1 / repeat until
    # false — старые детекторы знали только pcall+crasher, из-за чего на
    # части seed'ов пары переживали pipeline и вешали LuaSandbox/Roblox-less
    # окружения. Снимаем их структурно.

    ENV_PROBE_ROOTS = {'task', 'game', 'Enum', 'workspace', 'identifyexecutor',
                       'gethui', 'script', 'string', 'table', 'bit32', 'os'}

    @staticmethod
    def _is_hang_loop(stat) -> bool:
        """while true/1 do end | repeat until false"""
        if isinstance(stat, WhileStat):
            c = stat.cond
            if isinstance(c, BoolLit) and c.value is True:
                return True
            if isinstance(c, NumberLit) and c.value == 1:
                return True
            if isinstance(c, BinaryOp) and isinstance(c.left, NumberLit) \
                    and isinstance(c.right, NumberLit) and c.left.value == c.right.value:
                return True
            return False
        if isinstance(stat, RepeatStat):
            c = stat.cond
            return isinstance(c, BoolLit) and c.value is False
        return False

    def _names_in(self, node, acc: set) -> None:
        if isinstance(node, NameExpr):
            acc.add(node.name)
            return
        if node is None or not hasattr(node, '__dataclass_fields__'):
            return
        from dataclasses import fields as dc_fields
        for f in dc_fields(node):
            v = getattr(node, f.name, None)
            if isinstance(v, (list, tuple)):
                for it in v:
                    if isinstance(it, tuple):
                        for sub in it:
                            self._names_in(sub, acc)
                    else:
                        self._names_in(it, acc)
            else:
                self._names_in(v, acc)

    def _block_is_hang(self, block) -> bool:
        """[hang] | [if true then <hang> end] (формы protection рандомизированы)"""
        stmts = getattr(block, 'statements', None) or []
        if len(stmts) != 1:
            return False
        st = stmts[0]
        if self._is_hang_loop(st):
            return True
        if isinstance(st, IfStat) and len(st.branches) == 1:
            cond, inner = st.branches[0]
            truthy = (isinstance(cond, BoolLit) and cond.value is True) or \
                     (isinstance(cond, NumberLit) and cond.value not in (0, 0.0))
            return bool(truthy) and self._block_is_hang(inner)
        return False

    def _is_hang_if_on(self, stat, name: str) -> bool:
        """if <cond с именем name> then <hang> end"""
        if not isinstance(stat, IfStat) or len(stat.branches) != 1:
            return False
        cond, block = stat.branches[0]
        acc: set = set()
        self._names_in(cond, acc)
        if name not in acc:
            return False
        return self._block_is_hang(block)

    def _is_env_probe_pair(self, stat, nxt) -> bool:
        if not isinstance(stat, LocalAssignStat) or len(stat.names) != 1:
            return False
        name = stat.names[0]
        if not self.is_obf_name(name):
            return False
        acc: set = set()
        for v in stat.values:
            self._names_in(v, acc)
        if not (acc & self.ENV_PROBE_ROOTS):
            return False
        return nxt is not None and self._is_hang_if_on(nxt, name)

    def _is_dangling_hang_if(self, stat, defined: set) -> bool:
        """if type(_0xMISSING) ~= ... then hang end — определение уже снято"""
        if not isinstance(stat, IfStat) or len(stat.branches) != 1:
            return False
        cond, block = stat.branches[0]
        if not self._block_is_hang(block):
            return False
        acc: set = set()
        self._names_in(cond, acc)
        obf_refs = [n for n in acc if self.is_obf_name(n)]
        return bool(obf_refs) and all(n not in defined for n in obf_refs)

    def _cond_meaningful_names(self, node, acc: set) -> None:
        """Имена в условии, КРОМЕ функций вызова (type/pcall/...) и env-корней."""
        if isinstance(node, NameExpr):
            if node.name not in self.ENV_PROBE_ROOTS and node.name not in ('type',):
                acc.add(node.name)
            return
        if isinstance(node, CallExpr):
            for a in node.args or []:
                self._cond_meaningful_names(a, acc)
            return
        if node is None or not hasattr(node, '__dataclass_fields__'):
            return
        from dataclasses import fields as dc_fields
        for f in dc_fields(node):
            v = getattr(node, f.name, None)
            if isinstance(v, (list, tuple)):
                for it in v:
                    if isinstance(it, tuple):
                        for sub in it:
                            self._cond_meaningful_names(sub, acc)
                    else:
                        self._cond_meaningful_names(it, acc)
            else:
                self._cond_meaningful_names(v, acc)

    def _is_literal_hang_if(self, stat) -> bool:
        """if <cond без значимых имён: type(773)=="number", false, ...> then hang end"""
        if not isinstance(stat, IfStat) or len(stat.branches) != 1:
            return False
        cond, block = stat.branches[0]
        acc: set = set()
        self._cond_meaningful_names(cond, acc)
        if acc:
            return False
        return self._block_is_hang(block)

    @staticmethod
    def _value_is_literal_or_env(node) -> bool:
        if isinstance(node, (NumberLit, StringLit, BoolLit, NilLit)):
            return True
        if isinstance(node, NameExpr):
            return node.name in NZLWrapperStripper.ENV_PROBE_ROOTS
        return False

    @staticmethod
    def _value_has_no_call(node) -> bool:
        if isinstance(node, CallExpr):
            return False
        if node is None or not hasattr(node, '__dataclass_fields__'):
            return True
        from dataclasses import fields as dc_fields
        for f in dc_fields(node):
            v = getattr(node, f.name, None)
            if isinstance(v, (list, tuple)):
                for it in v:
                    if isinstance(it, tuple):
                        if not all(NZLWrapperStripper._value_has_no_call(s) for s in it):
                            return False
                    elif not NZLWrapperStripper._value_has_no_call(it):
                        return False
            elif not NZLWrapperStripper._value_has_no_call(v):
                return False
        return True

    def _find_antitamper_names(self, chunk: Chunk) -> set[str]:
        """Собирает имена локалов, которые ЯВНО anti-tamper (по pcall+env-check)."""
        names = set()
        for stat in chunk.body.statements:
            if self._is_antitamper_pcall(stat):
                names.add(stat.names[0])
        return names
    
    def _is_antitamper_crasher(self, stat, at_names: set[str]) -> bool:
        """
        if not _0xXXX then while (true|1==1) do end end
        """
        if not isinstance(stat, IfStat):
            return False
        if len(stat.branches) != 1 or stat.else_block is not None:
            return False
        cond, block = stat.branches[0]
        # Условие: not NameExpr(anti-tamper)
        if not isinstance(cond, UnaryOp) or cond.op != 'not':
            return False
        if not isinstance(cond.operand, NameExpr):
            return False
        if cond.operand.name not in at_names:
            return False
        # Тело: одна инструкция WhileStat с бесконечным условием
        stmts = block.statements
        if len(stmts) != 1:
            return False
        w = stmts[0]
        if not isinstance(w, WhileStat):
            return False
        # Условие while — булев true или "1==1" и т.п. — просто убеждаемся что constant-truthy
        c = w.cond
        if isinstance(c, BoolLit) and c.value is True:
            return True
        # Уже свёрнутое (constant_fold превратил 1==1 в true)
        return isinstance(c, BoolLit) and c.value is True
    
    def _is_dead_obf_function(self, stat, usage_counts: dict[str, int]) -> bool:
        """local function ObfNaMe(...) end   при 0 использований в chunk"""
        if not isinstance(stat, LocalFunctionStat):
            return False
        if not self.is_obf_name(stat.name):
            return False
        # 0 использований в NameExpr'ах
        return usage_counts.get(stat.name, 0) == 0


# ============================================================
# TESTS
# ============================================================

if __name__ == "__main__":
    from obfuscator.deobfuscator.core.base import parse_code, ast_to_code
    
    print("=== Test NZLWrapperStripper ===\n")
    passed = failed = 0
    def test(name, cond, extra=""):
        global passed, failed
        if cond: print(f"  [OK] {name}"); passed += 1
        else:    print(f"  [XX] {name}  ({extra})"); failed += 1
    
    def run_strip(src):
        return NZLWrapperStripper().run(parse_code(src))
    
    # TEST 1: build_id removal
    src1 = 'local _nzl = 2782434526\nprint("hi")'
    new, s = run_strip(src1)
    out = ast_to_code(new)
    test("build_id removed", "_nzl" not in out, out[:200])
    test("print stays", 'print("hi")' in out, out[:200])
    
    # TEST 2: anti-tamper pcall + crasher
    src2 = '''
local _0x4F2_IlII0l0 = pcall(function()
    local _0x706_O0lo = bit32 and bit32.bxor
    local _0xDA8_IlOl = workspace
    local _0x73C_1oOIOO = identifyexecutor or function() return "unknown" end
end)
if not _0x4F2_IlII0l0 then while true do end end
print("payload")
'''
    new, s = run_strip(src2)
    out = ast_to_code(new)
    test("pcall antitamper removed", "pcall" not in out, out[:300])
    test("crasher removed", "while true" not in out, out[:300])
    test("payload stays", 'print("payload")' in out, out[:300])
    
    # TEST 3: dead obf function
    src3 = '''
local function I0001IOIo(a, b, c)
    return a
end
print("test")
'''
    new, s = run_strip(src3)
    out = ast_to_code(new)
    test("dead obf func removed", "I0001IOIo" not in out, out[:200])
    
    # TEST 4: живая функция НЕ трогаем
    src4 = '''
local function I0001IOIo(a, b, c)
    return a
end
local x = I0001IOIo(1, 2, 3)
'''
    new, s = run_strip(src4)
    out = ast_to_code(new)
    test("live obf func kept", "I0001IOIo" in out, out[:200])
    
    # TEST 5: обычный код (без обфускации) — ничего не тронуто
    src5 = '''
local function greet(name)
    return "hello " .. name
end
local msg = greet("world")
print(msg)
'''
    new, s = run_strip(src5)
    out = ast_to_code(new)
    test("normal code untouched",
         "function greet" in out and 'greet("world")' in out, out[:200])
    test("normal code: 0 replaced", s.replaced == 0)
    
    # TEST 6: полный NZL-обвес
    src6 = '''
local _nzl = 1234567890
local _0xAAA_bbb = pcall(function()
    local _c = bit32 and bit32.bxor
    local _d = workspace
end)
if not _0xAAA_bbb then while true do end end
local function IOOllIl(a, b, c)
    return a
end
print("actual code")
'''
    new, s = run_strip(src6)
    out = ast_to_code(new)
    test("full NZL wrap: build_id gone", "_nzl" not in out, out[:400])
    test("full NZL wrap: pcall gone", "pcall" not in out, out[:400])
    test("full NZL wrap: crasher gone", "while true" not in out, out[:400])
    test("full NZL wrap: dead func gone", "IOOllIl" not in out, out[:400])
    test("full NZL wrap: payload kept", 'print("actual code")' in out, out[:400])
    test("full NZL wrap: >= 4 replacements", s.replaced >= 4, f"replaced={s.replaced}")
    
    print(f"\n=== TOTAL: {passed}/{passed+failed} ===")
    if failed == 0: print("[!!] NZLWrapperStripper работает! [**]")
    
    # DEMO
    print("\n=== [**] DEMO: full NZL wrapper strip [**] ===")
    demo = '''
local _nzl = 2782434526
local _0x4F2_IlII0l0 = pcall(function()
    local _0x706_O0lo = bit32 and bit32.bxor
    local _0xDA8_IlOl = workspace
    local _0x73C_1oOIOO = identifyexecutor or function() return "unknown" end
end)
if not _0x4F2_IlII0l0 then while true do end end
local function I0001IOIo(a, b, c)
    return a
end
print("This is the ACTUAL script code!")
local x = 42
'''
    print("BEFORE:")
    print(demo)
    new_demo, ds = NZLWrapperStripper().run(parse_code(demo))
    print("AFTER:")
    print(ast_to_code(new_demo))
    print(f"\n{ds.summary()}")