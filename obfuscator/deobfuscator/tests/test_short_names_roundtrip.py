"""
NZL STUDIO - Sprint 3.5 Round-Trip Test (Short Ambiguous Names)
===============================================================
Контракт спринта (adversarial-пара):

    obfuscate:  name_style='luraph' -> имена l / Il / Oll / _0x..._...
    deobfuscate: NameNormalizer    -> читаемые var_N / func_N

Группы:
  T1  NameGenerator: стиль luraph даёт смесь short+confusing, уникально
  T2  NameNormalizer: роли func/var, согласованность, reparse
  T3  engine medium obf -> full deob: обф-имён в cleaned НЕТ,
      семантика через LuaSandbox совпадает с оригиналом
  T4  compare-фичи на medium: short_ambiguous_names И homoglyph_names [OK]
  T5  Luraph v14.6: нормализатор переименовывает короткие имена,
      вывод парсится (деобфускатор стал понимать Luraph-имена)

Запуск:  py -m obfuscator.deobfuscator.tests.test_short_names_roundtrip
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


SEM_SRC = (
    "local total = 0\n"
    "for i = 1, 5 do\n"
    "  total = total + i * 2\n"
    "end\n"
    "local function double(x)\n"
    "  return x * 2\n"
    "end\n"
    "local tag = \"sum\"\n"
    "result = double(total)\n"
)

OBF_DECL = re.compile(r'\blocal\s+(?:function\s+)?[lIO]{1,3}\b')
HOMO = re.compile(r'[Il1O0]{4,}')

# детектор compare плотностной (как у Luraph) — нужен источник
# сопоставимого с compare-овским размера
T4_SRC = (
    "local width = 120\n"
    "local height = 40\n"
    "local depth = width * height\n"
    "local counter = 0\n"
    "local limit = 1000\n"
    "local label = \"grid\"\n"
    "local function area(w, h)\n"
    "  return w * h\n"
    "end\n"
    "local function perimeter(w, h)\n"
    "  return 2 * (w + h)\n"
    "end\n"
    "local function scale(v, k)\n"
    "  return v * k\n"
    "end\n"
    "local total = area(width, height)\n"
    "local edge = perimeter(width, height)\n"
    "local scaled = scale(total, 3)\n"
    "for step = 1, 10 do\n"
    "  counter = counter + step\n"
    "end\n"
    "local report = label .. \":\" .. counter\n"
    "print(report, total, edge, scaled, depth, limit)\n"
    "warn(report)\n"
)


# ============================================================
# T1 - generator
# ============================================================

def t1_generator():
    from obfuscator.utils.random_gen import NameGenerator, make_rng

    gen = NameGenerator(rng=make_rng(seed=11), style='luraph')
    names = [gen.generate() for _ in range(16)]
    short = [n for n in names if len(n) <= 3 and set(n) <= set('lIO')]
    long_conf = [n for n in names if len(n) >= 8]
    report(len(names) == len(set(names)), "T1 names unique", f"n={len(names)}")
    report(len(short) >= 12, "T1 mostly short ambiguous", f"short={len(short)}/16")
    report(len(long_conf) >= 1, "T1 confusing long present (homoglyph feature)",
           f"long={len(long_conf)}")


# ============================================================
# T2 - normalizer unit
# ============================================================

def t2_normalizer():
    from obfuscator.deobfuscator.core.base import parse_code, ast_to_code
    from obfuscator.deobfuscator.decoders.name_normalizer import NameNormalizer

    src = (
        "local O = 2\n"
        "local function lI(v)\n"
        "  return v * O\n"
        "end\n"
        "local OO = lI(O)\n"
        "print(OO)\n"
    )
    chunk = parse_code(src)
    _c, stats = NameNormalizer().run(chunk)
    out = ast_to_code(chunk)
    ok_parse = True
    try:
        parse_code(out)
    except Exception as e:  # noqa: BLE001
        ok_parse = False
        print("     reparse:", e)
    report(OBF_DECL.search(out) is None, "T2 obfuscated declarations gone",
           out.replace("\n", " | ")[:70])
    report("func_1" in out or "func_2" in out, "T2 function role", "")
    report(ok_parse, "T2 cleaned reparseable")
    report(stats.replaced == 3, "T2 stats", f"replaced={stats.replaced}")


# ============================================================
# T3 - engine round-trip + semantics
# ============================================================

def t3_engine():
    from obfuscator.engine import obfuscate
    from obfuscator.deobfuscator.engine import DeobfuscatorEngine
    from obfuscator.deobfuscator.core.lua_sandbox import LuaSandbox

    sandbox = LuaSandbox()
    expected = sandbox.execute(SEM_SRC).get("result")

    for seed in (1, 2):
        obf = obfuscate(SEM_SRC, level="medium", seed=seed)
        n_obf_short = len(OBF_DECL.findall(obf))
        has_homo = HOMO.search(obf) is not None
        cleaned, _logs = DeobfuscatorEngine(level="full", verbose=False).deobfuscate(obf)
        n_clean_short = len(OBF_DECL.findall(cleaned))
        got = sandbox.execute(cleaned).get("result")
        report(n_obf_short >= 2 and has_homo,
               f"T3 seed={seed}: medium emits short+homoglyph names",
               f"short_decls={n_obf_short}, homo={has_homo}")
        report(n_clean_short == 0,
               f"T3 seed={seed}: cleaned has no obfuscated declarations",
               f"left={n_clean_short}")
        report(got == expected,
               f"T3 seed={seed}: sandbox semantics survive normalize",
               f"orig={expected}, cleaned={got}")


# ============================================================
# T4 - compare detectors
# ============================================================

def t4_compare():
    import importlib
    from obfuscator.engine import obfuscate
    mod = importlib.import_module("obfuscator.deobfuscator.tools.compare_obfuscators")
    short_hits = homo_hits = 0
    for seed in (42, 1, 7):
        feats = mod.analyze_source(obfuscate(T4_SRC, level="medium", seed=seed),
                                   f"s{seed}")["features"]
        short_hits += bool(feats["short_ambiguous_names"])
        homo_hits += bool(feats["homoglyph_names"])
    report(short_hits >= 1, "T4 compare: short_ambiguous_names [OK]",
           f"seeds hit={short_hits}/3")
    report(homo_hits >= 1, "T4 compare: homoglyph_names still [OK]",
           f"seeds hit={homo_hits}/3")


# ============================================================
# T5 - Luraph names become readable
# ============================================================

def t5_luraph():
    import os
    from obfuscator.deobfuscator.core.base import parse_code, ast_to_code
    from obfuscator.deobfuscator.decoders.name_normalizer import NameNormalizer

    path = os.path.normpath(os.path.join(
        os.path.dirname(__file__), "..", "samples", "luraph", "v14.6_sample1.lua"))
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        sample = fh.read()
    chunk = parse_code(sample)
    _c, stats = NameNormalizer().run(chunk)
    out = ast_to_code(chunk)
    ok_parse = True
    try:
        parse_code(out)
    except Exception as e:  # noqa: BLE001
        ok_parse = False
        print("     reparse:", e)
    report(stats.replaced > 0 and ok_parse,
           "T5 Luraph short names normalized, output parses",
           f"renamed={stats.replaced}")


def main() -> int:
    print("=" * 70)
    print("NZL Sprint 3.5 - short ambiguous names ROUND-TRIP test")
    print("=" * 70)
    t1_generator()
    t2_normalizer()
    t3_engine()
    t4_compare()
    t5_luraph()
    print("-" * 70)
    print(f"Round-trip tests: {PASSED}/{PASSED + FAILED}")
    if FAILED:
        print("FAILURES PRESENT")
        return 1
    print("All short names round-trip tests passed!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
