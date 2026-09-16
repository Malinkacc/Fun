"""
NZL Deobfuscator - Name Normalizer (Sprint 3.5, deobf side)
===========================================================
Adversarial-пара к obf-фиче "короткие неоднозначные имена" (style='luraph'):
возвращает читаемые имена вместо обфусцированных.

Распознаёт семейства имён (и только их — обычный код не трогаем):
  SHORT  ^[lIO]{1,3}$            (l, Il, Oll  — стиль Luraph)
  HOMO   ^[Il1O0]{4,}$           (Il1O0-гомоглифы)
  HEX    ^_0x[0-9A-Fa-f]{3,5}_\\w+$   (_0x585_11oO)
  UND    ^_[Il1O0x0-9]{4,}$      (_0lIO1l — string array и т.п.)

Замена согласованная: одно обф-имя -> одно читаемое во всём чанке.
Роль определяется использованием: вызывается как функция -> func_N,
иначе var_N. Не трогаем: ключи таблиц {x = ...}, t.field (is_dot),
method/target у function a.b.c(), строки.

Позиция в pipeline: ПОСЛЕДНИМ (full/vm) — когда весь мусор уже снят
и оставшиеся имена — это именно имена переменных.
"""

import re
from dataclasses import fields, is_dataclass

from obfuscator.deobfuscator.core.base import (
    NameExpr, LocalAssignStat, LocalFunctionStat, FunctionExpr,
    IndexExpr, TableField, FunctionDeclStat, NumericForStat, GenericForStat,
)
from .base_decoder import BaseDecoder


_PATTERNS = (
    re.compile(r'^[lIO]{1,3}$'),
    re.compile(r'^[Il1O0]{4,}$'),
    re.compile(r'^_0x[0-9A-Fa-f]{3,5}_\w+$'),
    re.compile(r'^_[Il1O0x0-9]{4,}$'),
)


def is_obfuscated_name(name: str) -> bool:
    if not name or not isinstance(name, str):
        return False
    return any(p.match(name) for p in _PATTERNS)


class NameNormalizer(BaseDecoder):
    NAME = "name normalize"

    def run(self, chunk):
        from .base_decoder import DecoderStats
        self.stats = DecoderStats(name=self.NAME)

        # 1) роли: кто вызывается как функция
        called = set()
        self._collect_calls(chunk, called)

        # 2) согласованная карта imya -> читаемое
        mapping = {}

        def translate(name: str) -> str:
            if not is_obfuscated_name(name):
                return name
            if name not in mapping:
                idx = len(mapping) + 1
                mapping[name] = f"func_{idx}" if name in called else f"var_{idx}"
            return mapping[name]

        self._walk(chunk, translate)

        self.stats.scanned = len(mapping)
        self.stats.replaced = len(mapping)
        for old, new in list(mapping.items())[:10]:
            self.stats.details.append(f"{old} -> {new}")
        return chunk, self.stats

    # ------------------------------------------------------------
    def _collect_calls(self, node, called: set) -> None:
        from obfuscator.deobfuscator.core.base import CallExpr
        if isinstance(node, CallExpr):
            fn = getattr(node, 'func', None)
            if isinstance(fn, NameExpr):
                called.add(fn.name)
        if node is None or not is_dataclass(node):
            return
        for f in fields(node):
            v = getattr(node, f.name, None)
            if isinstance(v, (list, tuple)):
                for item in v:
                    if is_dataclass(item):
                        self._collect_calls(item, called)
            elif is_dataclass(v):
                self._collect_calls(v, called)

    # ------------------------------------------------------------
    def _walk(self, node, translate) -> None:
        if node is None or not is_dataclass(node):
            return
        if isinstance(node, NameExpr):
            node.name = translate(node.name)
            return
        if isinstance(node, LocalAssignStat):
            node.names = [translate(n) for n in node.names]
        elif isinstance(node, LocalFunctionStat):
            node.name = translate(node.name)
        elif isinstance(node, FunctionExpr):
            node.params = [translate(p) for p in node.params]
        elif isinstance(node, NumericForStat):
            node.var = translate(node.var)
        elif isinstance(node, GenericForStat):
            node.names = [translate(n) for n in node.names]
        elif isinstance(node, FunctionDeclStat):
            return  # внешние target/method не трогаем
        for f in fields(node):
            v = getattr(node, f.name, None)
            if isinstance(node, IndexExpr) and f.name == 'index' and node.is_dot:
                continue  # t.field — поле внешней таблицы
            if isinstance(node, TableField) and f.name == 'key':
                continue  # {x = ...} — ключ-строка
            if isinstance(v, (list, tuple)):
                for item in v:
                    if is_dataclass(item):
                        self._walk(item, translate)
            elif is_dataclass(v):
                self._walk(v, translate)


# ============================================================
# SELF-TEST
# ============================================================

if __name__ == '__main__':
    from obfuscator.deobfuscator.core.base import parse_code, ast_to_code

    passed = failed = 0

    def check(name, cond, extra=""):
        global passed, failed
        if cond:
            passed += 1
            print(f"[OK] {name}" + (f"  {extra}" if extra else ""))
        else:
            failed += 1
            print(f"[XX] {name}" + (f"  {extra}" if extra else ""))

    src = (
        'local Il = 5\n'
        'local lO = Il * 2\n'
        'local function Oll(x)\n'
        '  return x + Il\n'
        'end\n'
        'local _0xABC_12oO = Oll(lO)\n'
        'print(_0xABC_12oO)\n'
        'local t = { Il = 1 }\n'      # ключ таблицы НЕ переименовывать
        'print(t.Il)\n'               # is_dot НЕ переименовывать
    )
    import re as _re
    chunk = parse_code(src)
    _c, stats = NameNormalizer().run(chunk)
    out = ast_to_code(chunk)
    check("obfuscated declarations gone",
          _re.search(r'\blocal\s+(?:function\s+)?[lIO]{1,3}\b', out) is None
          and "_0x" not in out,
          out.replace("\n", " | ")[:80])
    check("func role detected", "func_" in out, "")
    check("consistent mapping", out.count("var_1") >= 3, f"var_1 uses={out.count('var_1')}")
    check("table key kept", "{ Il = 1 }" in out or "Il = 1" in out)
    check("dot field kept", "t.Il" in out)
    check("stats", stats.replaced == 4, f"replaced={stats.replaced}")

    # обычный код не трогаем
    src2 = 'local alpha = 1\nlocal beta = alpha + 1\nprint(beta)\n'
    chunk2 = parse_code(src2)
    _c2, stats2 = NameNormalizer().run(chunk2)
    out2 = ast_to_code(chunk2)
    check("plain code untouched", out2.strip() == src2.strip() and stats2.replaced == 0)

    print()
    print(f"NameNormalizer tests: {passed}/{passed + failed}")
    if failed:
        raise SystemExit(1)
    print("All name normalizer tests passed!")
