"""
NZL STUDIO - Sprint 2 Round-Trip Test (String Array Indexing)
=============================================================
Контракт спринта (adversarial-пара):

    obfuscate:  "Hello"          ->  local _X = {"Hello"} ... _X[1]
    deobfuscate: _X[1]            ->  "Hello", таблица удалена

Группы:
  T1  transformer: строки вынесены, dot/name-ключи целы, вывод парсится
  T2  decoder: инлайн + удаление таблицы; небезопасные кандидаты нетронуты
  T3  engine medium obf -> DeobfuscatorEngine full: строки восстановлены,
      ссылок на массив не осталось
  T4  compare-фича string_array_indexing детектится на medium-выводе
  T5  Luraph v14.6 sample: decoder не ломает чужой код (safe-skip)

Запуск:  py -m obfuscator.deobfuscator.tests.test_string_array_roundtrip
"""

import re
import sys

PASSED = 0
FAILED = 0


def report(ok: bool, name: str, extra: str = "") -> None:
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f"[OK] {name}" + (f"  {extra}" if extra else ""))
    else:
        FAILED += 1
        print(f"[XX] {name}" + (f"  {extra}" if extra else ""))


SAMPLE_STRINGS = ["Hello", "World", "Players", "LocalPlayer", "warn me"]

SRC = (
    'local msg = "Hello"\n'
    'print(msg)\n'
    'print("Hello")\n'
    'warn("World")\n'
    'local svc = game:GetService("Players")\n'
    'local lp = svc.LocalPlayer\n'
    'print("LocalPlayer", lp)\n'
    'for i = 1, 3 do warn("warn me") end\n'
)


def original_strings_present(cleaned: str):
    return [s for s in SAMPLE_STRINGS if f'"{s}"' not in cleaned]


# ============================================================
# T1 - obf side
# ============================================================

def t1_transformer():
    from obfuscator.lexer import Lexer
    from obfuscator.parser import Parser
    from obfuscator.ast_unparser import unparse
    from obfuscator.utils.random_gen import make_rng
    from obfuscator.transformers.string_array import (
        StringArrayConfig, obfuscate_string_array,
    )

    chunk = Parser(Lexer(SRC).tokenize()).parse()
    new_chunk, stats = obfuscate_string_array(
        chunk, make_rng(seed=11), StringArrayConfig(probability=1.0))
    out = unparse(new_chunk)

    report(out.splitlines()[0].startswith("local _"), "T1 array is first statement",
           out.splitlines()[0][:36])
    uses = len(re.findall(r'_\w+\[\d+\]', out))
    report(uses >= 6, "T1 indexing uses present", f"uses={uses}")
    report(out.count('"Hello"') == 1, "T1 duplicates share one entry",
           f"inline count={out.count('Hello')}")
    ok_reparse = True
    try:
        Parser(Lexer(out).tokenize()).parse()
    except Exception as e:  # noqa: BLE001
        ok_reparse = False
        print(f"     reparse: {e}")
    report(ok_reparse, "T1 output reparseable")
    report(stats.hoisted == 5 and stats.replaced_uses >= 6, "T1 stats",
           f"hoisted={stats.hoisted}, uses={stats.replaced_uses}")


# ============================================================
# T2 - deobf side (unit)
# ============================================================

def t2_decoder():
    from obfuscator.deobfuscator.core.base import parse_code, ast_to_code
    from obfuscator.deobfuscator.decoders.string_array_decoder import StringArrayDecoder

    src = (
        'local _Il1I0O = {"Hello", "World"}\n'
        'print(_Il1I0O[1])\n'
        'warn(_Il1I0O[2])\n'
    )
    chunk = parse_code(src)
    _c, stats = StringArrayDecoder().run(chunk)
    out = ast_to_code(chunk)
    report('"Hello"' in out and '"World"' in out and "_Il1I0O" not in out,
           "T2 inline + table removed", out.replace("\n", " | ")[:70])
    report(stats.replaced == 2, "T2 stats replaced=2", f"got={stats.replaced}")


# ============================================================
# T3 - engine round-trip
# ============================================================

def t3_engine():
    from obfuscator.engine import obfuscate
    from obfuscator.deobfuscator.engine import DeobfuscatorEngine

    for seed in (1, 2, 3):
        obf = obfuscate(SRC, level='medium', seed=seed)
        has_array = bool(re.search(r'local\s+\w+\s*=\s*\{', obf)) and \
            bool(re.search(r'\w+\s*\[\s*[\d(]', obf))
        cleaned, _logs = DeobfuscatorEngine(level="full", verbose=False).deobfuscate(obf)
        missing = original_strings_present(cleaned)
        leftover = bool(re.search(r'local\s+\w+\s*=\s*\{\s*["\']', cleaned))
        ok = has_array and not missing and not leftover
        report(ok, f"T3 seed={seed}: medium obf -> full deob restores strings",
               f"array={has_array}, missing={missing}, leftover_table={leftover}")


# ============================================================
# T4 - compare detector sees the feature
# ============================================================

def t4_compare_feature():
    import importlib
    from obfuscator.engine import obfuscate
    mod = importlib.import_module("obfuscator.deobfuscator.tools.compare_obfuscators")
    hits = 0
    for seed in (42, 1, 7):
        out = obfuscate(SRC, level='medium', seed=seed)
        if mod.analyze_source(out, f"s{seed}")["features"]["string_array_indexing"]:
            hits += 1
    report(hits >= 1, "T4 compare detector: string_array_indexing [OK]", f"seeds hit={hits}/3")


# ============================================================
# T5 - Luraph sample safety
# ============================================================

def t5_luraph_safe():
    import os
    from obfuscator.deobfuscator.core.base import parse_code, ast_to_code
    from obfuscator.deobfuscator.decoders.string_array_decoder import StringArrayDecoder

    path = os.path.normpath(os.path.join(
        os.path.dirname(__file__), "..", "samples", "luraph", "v14.6_sample1.lua"))
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        sample = fh.read()
    chunk = parse_code(sample)
    before = ast_to_code(chunk)
    _c, stats = StringArrayDecoder().run(chunk)
    after = ast_to_code(chunk)
    report(before == after, "T5 Luraph sample untouched by decoder",
           f"scanned={stats.scanned}, replaced={stats.replaced}")


def main() -> int:
    print("=" * 70)
    print("NZL Sprint 2 - string array indexing ROUND-TRIP test")
    print("=" * 70)
    t1_transformer()
    t2_decoder()
    t3_engine()
    t4_compare_feature()
    t5_luraph_safe()
    print("-" * 70)
    print(f"Round-trip tests: {PASSED}/{PASSED + FAILED}")
    if FAILED:
        print("FAILURES PRESENT")
        return 1
    print("All string array round-trip tests passed!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
