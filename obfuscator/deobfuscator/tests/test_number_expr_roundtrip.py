"""
NZL STUDIO - Sprint 1 Round-Trip Test
=====================================
Adversarial-пара: обфускатор чисел (NumberExprGen v2.1) против
деобфускатора (NumberExprDecoder). Контракт спринта:

    obfuscate(value) -> deobfuscate -> value

Группы тестов:
  T1  lexer/unparser: 0B/0X литералы парсятся и сохраняют стиль
  T2  LuaSandbox.eval_expr соглашается с NumberExprGen (математика верна)
  T3  transformer(prob=1.0) -> unparse -> NumberExprDecoder -> значения восстановлены
  T4  engine obfuscate(medium) -> DeobfuscatorEngine(full) -> оригиналы восстановлены
  T5  живой Luraph v14.6 sample: парсится (0B!) и number-выражения сворачиваются

Запуск:  py -m obfuscator.deobfuscator.tests.test_number_expr_roundtrip
"""

import os
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


def collect_numbers(chunk):
    """Все NumberLit.value в AST (рекурсивно, безопасно к str/float)."""
    from dataclasses import fields, is_dataclass
    from obfuscator.deobfuscator.core.base import NumberLit

    out = []

    def walk(n):
        if n is None or isinstance(n, (str, bytes, bool)):
            return
        if isinstance(n, (int, float)):
            return
        if isinstance(n, NumberLit):
            out.append(n.value)
        if not is_dataclass(n):
            return
        for f in fields(n):
            v = getattr(n, f.name, None)
            if isinstance(v, (list, tuple)):
                for it in v:
                    walk(it)
            else:
                walk(v)

    walk(chunk)
    return out


# ============================================================
# T1 - lexer/unparser: binary & hex literals
# ============================================================

def t1_literal_roundtrip() -> None:
    from obfuscator.lexer import Lexer
    from obfuscator.parser import Parser
    from obfuscator.ast_unparser import unparse

    src = "local a = 0B101010\nlocal b = 0X2A\nlocal c = 0B10_00\nlocal d = 0xFF_FF\n"
    try:
        chunk = Parser(Lexer(src).tokenize()).parse()
    except Exception as e:  # noqa: BLE001
        report(False, "T1 parse 0B/0X literals", f"crashed: {e}")
        return
    vals = collect_numbers(chunk)
    report(vals == [42, 42, 8, 65535], "T1 parse values [42,42,8,65535]", f"got {vals}")
    out = unparse(chunk)
    report("0B101010" in out and "0X2A" in out and "0B10_00" in out,
           "T1 unparse keeps literal style", out.replace("\n", " | ")[:90])


# ============================================================
# T2 - sandbox agrees with NumberExprGen
# ============================================================

def t2_sandbox_math() -> None:
    from obfuscator.utils.random_gen import NumberExprGen, make_rng
    from obfuscator.deobfuscator.core.lua_sandbox import LuaSandbox

    sandbox = LuaSandbox()
    values = [2, 7, 42, 100, 255, 1024, 1337, 4096, 65535, 999999, 123456789]
    bad = []
    checked = 0
    for seed in (1, 2, 3):
        gen = NumberExprGen(make_rng(seed=seed))
        for v in values:
            expr = gen.gen(v, depth=1)
            got = sandbox.eval_expr(str(expr))
            checked += 1
            if not isinstance(got, (int, float)) or int(got) != v:
                bad.append((v, str(expr), got))
    report(not bad, f"T2 sandbox verifies NumberExprGen ({checked} exprs)",
           f"wrong: {bad[:3]}" if bad else "all equal")


# ============================================================
# T3 - transformer -> decoder round-trip (probability = 1.0)
# ============================================================

def t3_transformer_roundtrip() -> None:
    from obfuscator.lexer import Lexer
    from obfuscator.parser import Parser
    from obfuscator.ast_unparser import unparse
    from obfuscator.utils.random_gen import make_rng
    from obfuscator.transformers.number_obfuscator import (
        NumberObfuscatorConfig, obfuscate_numbers_in_chunk,
    )
    from obfuscator.deobfuscator.decoders.number_expr_decoder import NumberExprDecoder

    values = [2, 5, 42, 77, 100, 255, 512, 1024, 1337, 2048, 65535, 999999]
    src = "\n".join(f"local v{i:02d} = {v}" for i, v in enumerate(values))
    src += "\nprint(v00 + v11)\n"

    chunk = Parser(Lexer(src).tokenize()).parse()
    cfg = NumberObfuscatorConfig(probability=1.0, depth=1, skip_values=set())
    new_chunk, stats = obfuscate_numbers_in_chunk(chunk, make_rng(seed=7), cfg)
    obf_src = unparse(new_chunk)

    report(stats.parse_failures == 0,
           "T3 transformer: zero parse failures (0B/0X now survive)",
           f"obfuscated={stats.obfuscated}, parse_failures={stats.parse_failures}")
    has_feat = ("bit32." in obf_src) or ("0B" in obf_src) or ("0X" in obf_src)
    report(has_feat, "T3 obfuscated source shows bit32/0B/0X features",
           f"bit32={obf_src.count('bit32.')}, 0B={len(re.findall(r'0B', obf_src))}, 0X={len(re.findall(r'0X', obf_src))}")

    dec_chunk = Parser(Lexer(obf_src).tokenize()).parse()
    dec = NumberExprDecoder()
    clean_chunk, dstats = dec.run(dec_chunk)
    clean_src = unparse(clean_chunk)

    got = set(collect_numbers(clean_chunk))
    missing = [v for v in values if v not in got]
    report(not missing, "T3 decoder restores ALL original values", f"missing={missing}")
    report("bit32." not in clean_src, "T3 no bit32 left after decode",
           f"replaced={dstats.replaced}")


# ============================================================
# T4 - full engine round-trip: obfuscate(medium) -> deobfuscate(full)
# ============================================================

def t4_engine_roundtrip() -> None:
    from obfuscator.engine import obfuscate
    from obfuscator.deobfuscator.engine import DeobfuscatorEngine
    from obfuscator.deobfuscator.core.base import parse_code

    values = [42, 100, 1337, 7, 255, 1024, 999999]
    src = "\n".join(f"local n{i} = {v}" for i, v in enumerate(values))
    src += "\nprint(n0 + n1 + n2)\nwarn(n3, n4, n5, n6)\n"

    all_ok = True
    for seed in (1, 2, 3):
        obf = obfuscate(src, level='medium', seed=seed)
        bit32_before = obf.count("bit32.")
        cleaned, _logs = DeobfuscatorEngine(level="full", verbose=False).deobfuscate(obf)
        bit32_after = cleaned.count("bit32.")
        try:
            got = set(collect_numbers(parse_code(cleaned)))
        except Exception as e:  # noqa: BLE001
            report(False, f"T4 seed={seed} cleaned source re-parse", f"crashed: {e}")
            all_ok = False
            continue
        missing = [v for v in values if v not in got]
        ok = (not missing) and (bit32_after < bit32_before or bit32_before == 0)
        all_ok = all_ok and ok
        report(ok, f"T4 seed={seed}: medium obf -> full deob restores values",
               f"bit32 {bit32_before}->{bit32_after}, missing={missing}")
    return all_ok


# ============================================================
# T5 - real Luraph v14.6 sample
# ============================================================

def t5_luraph_sample() -> None:
    from obfuscator.deobfuscator.core.base import parse_code
    from obfuscator.deobfuscator.decoders.number_expr_decoder import NumberExprDecoder

    path = os.path.join(os.path.dirname(__file__), "..", "samples", "luraph", "v14.6_sample1.lua")
    path = os.path.normpath(path)
    if not os.path.exists(path):
        report(False, "T5 luraph sample exists", path)
        return
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        sample = fh.read()
    try:
        chunk = parse_code(sample)
    except Exception as e:  # noqa: BLE001
        report(False, "T5 luraph sample parses (0B literals!)", f"crashed: {e}")
        return
    report(True, "T5 luraph sample parses (0B literals!)", f"{len(sample)} bytes")
    dec = NumberExprDecoder()
    _new_chunk, stats = dec.run(chunk)
    report(stats.replaced > 0, "T5 decoder folds Luraph number expressions",
           f"replaced={stats.replaced}")


def main() -> int:
    print("=" * 70)
    print("NZL Sprint 1 - number obfuscation ROUND-TRIP test")
    print("=" * 70)
    t1_literal_roundtrip()
    t2_sandbox_math()
    t3_transformer_roundtrip()
    t4_engine_roundtrip()
    t5_luraph_sample()
    print("-" * 70)
    print(f"Round-trip tests: {PASSED}/{PASSED + FAILED}")
    if FAILED:
        print("FAILURES PRESENT")
        return 1
    print("All round-trip tests passed!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
