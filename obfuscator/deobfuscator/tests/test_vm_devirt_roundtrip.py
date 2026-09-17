"""
NZL STUDIO - Sprint 4b: round-trip тесты VM-devirtualizer
=========================================================
T1  battery: VMProtectionTransformer(insane VM) -> engine(level='vm')
    -> create_vm/блоб/dispatch исчезли, семантика == оригинал (LuaSandbox)
T2  end-to-end: obfuscate(level='insane') -> deobfuscate(level='vm')
    -> семантика == оригинал
T3  medium (без VM) через level='vm' -> no-op, без поломок
T4  структурная подделка (два string-литерала, чужой runtime)
    -> честный bail: ошибки в stats, чанк не сломан

Запуск:  python -m obfuscator.deobfuscator.tests.test_vm_devirt_roundtrip
"""

import os
import re
import sys

# прямой запуск файла (без -m): sys.path[0] = каталог tests/, поэтому
# явно добавляем корень репозитория
_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

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


def vm_markers(text: str) -> int:
    """Признаки живого VM-dispatch в тексте."""
    n = 0
    if len(re.findall(r'== \d+ then', text)) > 60:
        n += 1
    if text.count('while true do') > 3:
        n += 1
    if re.search(r'"(?:[^"\\]|\\.){500,}"', text):
        n += 1
    if re.search(r"'(?:[^'\\]|\\.){500,}'", text):
        n += 1
    return n


# ============================================================
# T1 - battery through VMProtectionTransformer + engine(vm)
# ============================================================

def t1_battery_devirt():
    from obfuscator.lexer import Lexer
    from obfuscator.parser import Parser
    from obfuscator.ast_unparser import unparse
    from obfuscator.transformers.vm_protection import VMProtectionTransformer
    from obfuscator.deobfuscator.core.lua_sandbox import LuaSandbox
    from obfuscator.deobfuscator.engine import DeobfuscatorEngine
    from obfuscator.deobfuscator.tests.test_vm_roundtrip import VM_BATTERY

    originals = [LuaSandbox().execute(src).get("result")
                 for src, _want in VM_BATTERY]

    for seed in (7, 42):
        ok_sem = 0
        ok_clean = 0
        fails = []
        for (src, _want), orig in zip(VM_BATTERY, originals):
            try:
                chunk = Parser(Lexer(src).tokenize()).parse()
                t = VMProtectionTransformer(seed=seed, all_functions=True)
                prelude, new_ast = t.transform(chunk)
                obf = prelude + "\n" + unparse(new_ast)
                had_vm = vm_markers(obf) > 0

                res = DeobfuscatorEngine(level='vm').deobfuscate_ex(obf)
                cleaned = res.cleaned_source

                sem = same(LuaSandbox().execute(cleaned).get("result"),
                           orig)
                clean = (res.parse_error is None
                         and (not had_vm or vm_markers(cleaned) == 0)
                         and (not had_vm or len(cleaned) * 3 < len(obf)))
                if sem:
                    ok_sem += 1
                if clean:
                    ok_clean += 1
                if not (sem and clean):
                    fails.append(
                        f"sem={sem} clean={clean} had_vm={had_vm} "
                        f"err={res.parse_error} "
                        f"size={len(obf)}->{len(cleaned)}")
            except Exception as e:  # noqa: BLE001
                fails.append(f"EXC {type(e).__name__}: {str(e)[:90]}")
        n = len(VM_BATTERY)
        report(ok_sem == n and ok_clean == n,
               f"T1 seed={seed}: devirt semantics + VM removed",
               f"sem={ok_sem}/{n} clean={ok_clean}/{n}"
               + (f"  {'; '.join(fails[:2])}" if fails else ""))


# ============================================================
# T2 - end-to-end insane -> vm-level deobfuscation
# ============================================================

T2_CASES = [
    "local function f(a, b) local x = a + b * 2 return x - 1 end\n"
    "result = f(6, 3)",
    "local function g(n) if n <= 1 then return 1 end "
    "return n * g(n - 1) end\nresult = g(5)",
    "local function w(n) local s = 0 while n > 0 do s = s + n % 10 "
    "n = n // 10 end return s end\nresult = w(98765)",
]


def t2_end_to_end_insane():
    from obfuscator.engine import obfuscate
    from obfuscator.deobfuscator.core.lua_sandbox import LuaSandbox
    from obfuscator.deobfuscator.engine import DeobfuscatorEngine

    ok = 0
    fails = []
    for src in T2_CASES:
        try:
            orig = LuaSandbox().execute(src).get("result")
            obf = obfuscate(src, level='insane', seed=7)
            res = DeobfuscatorEngine(level='vm').deobfuscate_ex(obf)
            got = LuaSandbox().execute(res.cleaned_source).get("result")
            if same(got, orig) and res.parse_error is None:
                ok += 1
            else:
                fails.append(f"orig={orig!r} got={got!r} "
                             f"err={res.parse_error}")
        except Exception as e:  # noqa: BLE001
            fails.append(f"EXC {type(e).__name__}: {str(e)[:90]}")
    report(ok == len(T2_CASES), "T2 insane -> devirt end-to-end",
           f"{ok}/{len(T2_CASES)}" + (f"  {'; '.join(fails[:2])}"
                                      if fails else ""))


# ============================================================
# T3 - medium (VM-free) через level 'vm' — no-op
# ============================================================

MEDIUM_SRC = (
    "local total = 0\n"
    "for i = 1, 5 do\n"
    "  total = total + i * 2\n"
    "end\n"
    "local function double(x)\n"
    "  return x * 2\n"
    "end\n"
    "result = double(total)\n"
)


def t3_medium_noop():
    from obfuscator.engine import obfuscate
    from obfuscator.deobfuscator.core.lua_sandbox import LuaSandbox
    from obfuscator.deobfuscator.engine import DeobfuscatorEngine

    orig = LuaSandbox().execute(MEDIUM_SRC).get("result")
    obf = obfuscate(MEDIUM_SRC, level='medium', seed=7)
    res = DeobfuscatorEngine(level='vm').deobfuscate_ex(obf)
    got = LuaSandbox().execute(res.cleaned_source).get("result")
    devirt_errs = [s for nm, s in res.stats_per_stage
                   if 'devirtualizer' in nm and s.errors > 0]
    report(same(got, orig) and res.parse_error is None
           and not devirt_errs,
           "T3 medium stays VM-free, devirt no-op",
           f"orig={orig!r} got={got!r}")


# ============================================================
# T4 - чужой код с похожим вызовом: честный bail
# ============================================================

def t4_foreign_blob_bail():
    from obfuscator.deobfuscator.engine import DeobfuscatorEngine

    fake = (
        'local function create_vm(a, b) return function() return 1 end end\n'
        'local f = create_vm("ZZZZ' + 'A' * 400 + '", "0123456789abcdef")\n'
        'result = f()\n'
    )
    try:
        res = DeobfuscatorEngine(level='vm').deobfuscate_ex(fake)
        devirt = [(nm, s) for nm, s in res.stats_per_stage
                  if 'devirtualizer' in nm]
        bailed = res.parse_error is None and (
            not devirt or devirt[0][1].replaced == 0)
        report(bailed, "T4 foreign blob -> honest bail, no crash",
               f"stages={[(nm, s.errors) for nm, s in devirt]}")
    except Exception as e:  # noqa: BLE001
        report(False, "T4 foreign blob -> honest bail, no crash",
               f"EXC {type(e).__name__}: {str(e)[:90]}")


def main() -> int:
    print("=" * 60)
    print("  test_vm_devirt_roundtrip — Sprint 4b")
    print("=" * 60)
    t1_battery_devirt()
    t2_end_to_end_insane()
    t3_medium_noop()
    t4_foreign_blob_bail()
    print("=" * 60)
    print(f"  Result: {PASSED}/{PASSED + FAILED}")
    if FAILED:
        print("  [XX] SOME TESTS FAILED")
        return 1
    print("  [OK] ALL PASSED")
    return 0


if __name__ == '__main__':
    sys.exit(main())
