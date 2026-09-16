"""
NZL STUDIO - Sprint 3 Round-Trip Test (State Machine Dispatch)
==============================================================
Контракт спринта (adversarial-пара):

    obfuscate:  линейный блок      ->  local state = N / while true / if-chain
    deobfuscate: dispatch-автомат  ->  линейный блок в исходном порядке

Группы:
  T1  transformer: dispatch построен, вывод парсится
  T2  unflattener: цепочка восстановлена в исходном порядке
  T3  СЕМАНТИКА: LuaSandbox исполняет оригинал и obf(config_override)
      с одинаковым результатом (не только синтаксис!)
  T4  engine medium obf -> DeobfuscatorEngine full: маркеры исходника
      на месте, dispatch-обёртки не осталось
  T5  compare-фича state_machine детектится на medium
  T6  Luraph v14.6: unflattener не трогает чужой dispatch (safe-skip)

Запуск:  py -m obfuscator.deobfuscator.tests.test_state_machine_roundtrip
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
    "local tag = \"sum\"\n"
    "result = total\n"
)

LIN_SRC = (
    "local a = 1\n"
    "local b = a + 1\n"
    "local c = b * 3\n"
    "print(c)\n"
    "warn(\"done\")\n"
)


# ============================================================
# T1 - obf side
# ============================================================

def t1_transformer():
    from obfuscator.lexer import Lexer
    from obfuscator.parser import Parser
    from obfuscator.ast_unparser import unparse
    from obfuscator.utils.random_gen import make_rng
    from obfuscator.transformers.state_machine import (
        StateMachineConfig, obfuscate_state_machine,
    )

    chunk = Parser(Lexer(LIN_SRC).tokenize()).parse()
    new_chunk, stats = obfuscate_state_machine(chunk, make_rng(seed=9))
    out = unparse(new_chunk)

    report("while true do" in out, "T1 while true dispatch present")
    report(out.count("== ") >= 4, "T1 if-chain arms", f"arms={out.count('== ')}")
    ok_reparse = True
    try:
        Parser(Lexer(out).tokenize()).parse()
    except Exception as e:  # noqa: BLE001
        ok_reparse = False
        print("     reparse:", e)
    report(ok_reparse, "T1 output reparseable")
    report(stats.blocks_flattened == 1 and stats.statements_dispatched == 5,
           "T1 stats", f"flat={stats.blocks_flattened}, disp={stats.statements_dispatched}")


# ============================================================
# T2 - deobf side
# ============================================================

def t2_unflattener():
    from obfuscator.deobfuscator.core.base import parse_code, ast_to_code
    from obfuscator.deobfuscator.decoders.state_machine_unflattener import (
        StateMachineUnflattener,
    )

    src = (
        "local q = 777\n"
        "while true do\n"
        "  if q == 777 then\n"
        "    local x = 5\n"
        "    q = 888\n"
        "  elseif q == 888 then\n"
        "    local y = x * 2\n"
        "    q = 999\n"
        "  elseif q == 999 then\n"
        "    print(y)\n"
        "    q = 0\n"
        "  else\n"
        "    break\n"
        "  end\n"
        "end\n"
    )
    chunk = parse_code(src)
    _c, stats = StateMachineUnflattener().run(chunk)
    out = ast_to_code(chunk)
    order_ok = ("local x = 5" in out and "local y = x * 2" in out and "print(y)" in out
                and out.index("local x = 5") < out.index("local y = x * 2") < out.index("print(y)"))
    report(order_ok, "T2 linear order restored", out.replace("\n", " | ")[:70])
    report("while true" not in out, "T2 dispatch removed")
    report(stats.replaced == 1, "T2 stats", f"replaced={stats.replaced}")


# ============================================================
# T3 - semantics via LuaSandbox
# ============================================================

def t3_semantics():
    from obfuscator.engine import Obfuscator
    from obfuscator.deobfuscator.core.lua_sandbox import LuaSandbox

    sandbox = LuaSandbox()
    base_env = sandbox.execute(SEM_SRC)
    expected = base_env.get("result")

    only_sm = {
        "string_array": False,
        "strings": False,
        "numbers": False,
        "variables": False,
        "control_flow": False,
        "vm_protection": False,
        "anti_tamper": False,
        "environment_checks": False,
        "watermark": False,
        "minified": False,
        "state_machine": True,
    }
    for seed in (1, 2, 3):
        obf = Obfuscator(seed=seed).obfuscate(SEM_SRC, level="medium", config_override=only_sm)
        got_env = sandbox.execute(obf)
        got = got_env.get("result")
        report(got == expected, f"T3 seed={seed}: sandbox semantics equal",
               f"orig={expected}, obf={got}")


# ============================================================
# T4 - engine round-trip
# ============================================================

def t4_engine():
    """
    medium обфусцирует ИМЕНА (variables=True) — 'local a = 1' искать нельзя.
    Проверяем структуру: исходный линейный порядок восстановлен,
    dispatch-сравнений не осталось, маркеры print/warn на месте.
    """
    from obfuscator.engine import obfuscate
    from obfuscator.deobfuscator.engine import DeobfuscatorEngine

    src = LIN_SRC
    for seed in (1, 2):
        obf = obfuscate(src, level="medium", seed=seed)
        had_dispatch = bool(re.search(r'while\s+true\s+do', obf))
        cleaned, _logs = DeobfuscatorEngine(level="full", verbose=False).deobfuscate(obf)
        no_dispatch = not re.search(r'==\s*\d{3,}\s+then', cleaned)
        markers_ok = (
            re.search(r'local\s+\w+\s*=\s*1\b', cleaned) is not None
            and "print(" in cleaned
            and "done" in cleaned
            and cleaned.index("print(") < cleaned.index('done')
        )
        report(had_dispatch and markers_ok and no_dispatch,
               f"T4 seed={seed}: medium obf -> full deob linear again",
               f"dispatch_in_obf={had_dispatch}, markers={markers_ok}, clean={no_dispatch}")


# ============================================================
# T5 - compare detector
# ============================================================

def t5_compare_feature():
    import importlib
    from obfuscator.engine import obfuscate
    mod = importlib.import_module("obfuscator.deobfuscator.tools.compare_obfuscators")
    hits = 0
    for seed in (42, 1, 7):
        out = obfuscate(LIN_SRC, level="medium", seed=seed)
        if mod.analyze_source(out, f"s{seed}")["features"]["state_machine"]:
            hits += 1
    report(hits >= 1, "T5 compare detector: state_machine [OK]", f"seeds hit={hits}/3")


# ============================================================
# T6 - Luraph safety
# ============================================================

def t6_luraph_safe():
    import os
    from obfuscator.deobfuscator.core.base import parse_code, ast_to_code
    from obfuscator.deobfuscator.decoders.state_machine_unflattener import (
        StateMachineUnflattener,
    )

    path = os.path.normpath(os.path.join(
        os.path.dirname(__file__), "..", "samples", "luraph", "v14.6_sample1.lua"))
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        sample = fh.read()
    chunk = parse_code(sample)
    before = ast_to_code(chunk)
    _c, stats = StateMachineUnflattener().run(chunk)
    after = ast_to_code(chunk)
    report(before == after and stats.replaced == 0,
           "T6 Luraph dispatch untouched (strict pattern)",
           f"scanned={stats.scanned}, replaced={stats.replaced}")


def main() -> int:
    print("=" * 70)
    print("NZL Sprint 3 - state machine dispatch ROUND-TRIP test")
    print("=" * 70)
    t1_transformer()
    t2_unflattener()
    t3_semantics()
    t4_engine()
    t5_compare_feature()
    t6_luraph_safe()
    print("-" * 70)
    print(f"Round-trip tests: {PASSED}/{PASSED + FAILED}")
    if FAILED:
        print("FAILURES PRESENT")
        return 1
    print("All state machine round-trip tests passed!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
