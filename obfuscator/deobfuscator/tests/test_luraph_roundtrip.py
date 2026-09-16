"""
NZL STUDIO - Sprint 5: round-trip тесты Luraph-пары
===================================================
T1  mimic round-trip: исходник -> LuraphStyleTransformer ->
    деобфускатор (luraph decoder, unwrap) -> семантика == оригинал
T2  mimic детектится парсером как Luraph-форма
T3  живой Luraph v14.6: alias-inline срабатывает (>=50 замен),
    результат парсится, VM-диспетч не тронут (честно)
T4  medium через full-пайплайн с новой стадией: no-op, семантика цела

Запуск: python -m obfuscator.deobfuscator.tests.test_luraph_roundtrip
"""

import os
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


def same(a, b) -> bool:
    if a == b:
        return True
    return (isinstance(a, (int, float)) and isinstance(b, (int, float))
            and not isinstance(a, bool) and not isinstance(b, bool)
            and float(a) == float(b))


MIMIC_CASES = [
    "local function f(a, b) local x = a + b * 2 return x - 1 end\n"
    "result = f(6, 3)",
    "local t = {1, 2, 3}\nlocal s = 0\nfor i = 1, #t do s = s + t[i] * 2 end\n"
    "result = s",
    "local function w(n) local s = 0 while n > 0 do s = s + n % 10 "
    "n = n // 10 end return s end\nresult = w(4096)",
]


# ============================================================
# T1 + T2 - mimic
# ============================================================

def t1_mimic_roundtrip():
    from obfuscator.lexer import Lexer
    from obfuscator.parser import Parser
    from obfuscator.ast_unparser import unparse
    from obfuscator.transformers.luraph_style import LuraphStyleTransformer
    from obfuscator.deobfuscator.core.lua_sandbox import LuaSandbox
    from obfuscator.deobfuscator.engine import DeobfuscatorEngine
    from obfuscator.deobfuscator.luraph.parser import parse_chunk

    ok_sem = 0
    ok_det = 0
    fails = []
    for src in MIMIC_CASES:
        try:
            orig = LuaSandbox().execute(src).get("result")
            chunk = Parser(Lexer(src).tokenize()).parse()
            mim = LuraphStyleTransformer(seed=7).transform(chunk)
            mim_src = unparse(mim)

            rep = parse_chunk(mim)
            if rep.detected and rep.dispatcher == 'S':
                ok_det += 1
            else:
                fails.append(f"detect={rep.summary()}")

            res = DeobfuscatorEngine(level='full').deobfuscate_ex(mim_src)
            got = LuaSandbox().execute(res.cleaned_source).get("result")
            if same(got, orig) and res.parse_error is None:
                ok_sem += 1
            else:
                fails.append(f"orig={orig!r} got={got!r} "
                             f"err={res.parse_error}")
        except Exception as e:  # noqa: BLE001
            fails.append(f"EXC {type(e).__name__}: {str(e)[:90]}")
    n = len(MIMIC_CASES)
    report(ok_sem == n, "T1 mimic -> devirt(unwrap) semantics == original",
           f"{ok_sem}/{n}" + (f"  {'; '.join(fails[:2])}" if fails else ""))
    report(ok_det == n, "T2 mimic detected as Luraph shape",
           f"{ok_det}/{n}")


# ============================================================
# T3 - живой Luraph v14.6: alias inline
# ============================================================

def t3_real_sample_alias_inline():
    from obfuscator.deobfuscator.core.base import parse_code
    from obfuscator.deobfuscator.decoders.luraph_decoder import LuraphDecoder
    from obfuscator.ast_unparser import unparse

    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(here, "..", "samples", "luraph",
                        "v14.6_sample1.lua")
    if not os.path.exists(path):
        report(False, "T3 real sample exists", path)
        return
    src = open(path, encoding="utf-8", errors="replace").read()
    try:
        chunk = parse_code(src)
        before = unparse(chunk)
        dec = LuraphDecoder()
        out, stats = dec.run(chunk)
        after = unparse(out)
        ok_n = stats.replaced >= 50
        # VM-диспетч честно остался: repeat/until-диспетч на месте
        still_vm = 'until false' in after or 'while true do' in after
        report(ok_n and still_vm and stats.errors == 0,
               "T3 real v14.6: alias calls inlined, VM left in place",
               f"replaced={stats.replaced} size {len(before)}->{len(after)}"
               f" still_vm={still_vm}")
    except Exception as e:  # noqa: BLE001
        report(False, "T3 real v14.6: alias calls inlined, VM left in place",
               f"EXC {type(e).__name__}: {str(e)[:90]}")


# ============================================================
# T4 - medium no-op
# ============================================================

def t4_medium_noop():
    from obfuscator.engine import obfuscate
    from obfuscator.deobfuscator.core.lua_sandbox import LuaSandbox
    from obfuscator.deobfuscator.engine import DeobfuscatorEngine

    src = ("local total = 0\nfor i = 1, 5 do total = total + i * 2 end\n"
           "local function dbl(x) return x * 2 end\n"
           "result = dbl(total)\n")
    orig = LuaSandbox().execute(src).get("result")
    obf = obfuscate(src, level='medium', seed=7)
    res = DeobfuscatorEngine(level='full').deobfuscate_ex(obf)
    got = LuaSandbox().execute(res.cleaned_source).get("result")
    errs = [s for nm, s in res.stats_per_stage
            if 'luraph' in nm and s.errors > 0]
    report(same(got, orig) and res.parse_error is None and not errs,
           "T4 medium unaffected by luraph stage",
           f"orig={orig!r} got={got!r}")


def main() -> int:
    print("=" * 60)
    print("  test_luraph_roundtrip — Sprint 5")
    print("=" * 60)
    t1_mimic_roundtrip()
    t3_real_sample_alias_inline()
    t4_medium_noop()
    print("=" * 60)
    print(f"  Result: {PASSED}/{PASSED + FAILED}")
    if FAILED:
        print("  [XX] SOME TESTS FAILED")
        return 1
    print("  [OK] ALL PASSED")
    return 0


if __name__ == '__main__':
    sys.exit(main())
