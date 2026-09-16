"""
NZL STUDIO - Sprint 1 diagnostic (adaptive, no hard-coded API assumptions).

Goal: find out WHY `obfuscate(src, level='medium')` does not emit
bit32.* / 0X.. / 0B.. even though NumberExprGen v2.1 works standalone.

Run from the project root:
    python diag_sprint1.py
    python diag_sprint1.py --level hard --seed 1 --dump 60

Every section is independent and guarded: a crash in one does not stop the rest.
ASCII markers only ([OK]/[XX]/[!!]/[--]) so cp1251 consoles do not break.
"""

from __future__ import annotations

import argparse
import dataclasses
import importlib
import importlib.util
import inspect
import os
import re
import sys
import time

HR = "-" * 78


def head(title: str) -> None:
    print()
    print(HR)
    print(title)
    print(HR)


def ok(msg: str) -> None:
    print("[OK] " + msg)


def bad(msg: str) -> None:
    print("[XX] " + msg)


def warn(msg: str) -> None:
    print("[!!] " + msg)


def info(msg: str) -> None:
    print("[--] " + msg)


def try_import(*names):
    """Import the first module that exists. Returns (module, name) or (None, None)."""
    for n in names:
        try:
            return importlib.import_module(n), n
        except Exception as exc:  # noqa: BLE001
            info(f"import {n} failed: {type(exc).__name__}: {exc}")
    return None, None


def pick(obj, *names, default=None):
    """Return the first existing attribute from names."""
    for n in names:
        if hasattr(obj, n):
            return getattr(obj, n)
    return default


def call_any(obj, names, *args, **kwargs):
    """Call the first existing callable from names."""
    for n in names:
        fn = getattr(obj, n, None)
        if callable(fn):
            try:
                return fn(*args, **kwargs), n
            except Exception as exc:  # noqa: BLE001
                warn(f"{n}() raised {type(exc).__name__}: {exc}")
    return None, None


# --------------------------------------------------------------------------- #
# patterns we care about
# --------------------------------------------------------------------------- #
PATTERNS = {
    "bit32_calls": r"bit32\s*\.",
    "hex_literals": r"0[xX][0-9a-fA-F]",
    "bin_literals": r"0[bB][01]",
    "string_char": r"string\s*\.\s*char",
    "raw_bytes": r"\\\d{1,3}",
    "math_calls": r"math\s*\.\s*(floor|abs|sqrt|ceil|pow|max|min)",
    "concat": r"\.\.",
}

SAMPLE = (
    'local a = 42\n'
    'local b = 100\n'
    'local c = 1337\n'
    'local d = 7\n'
    'local e = 255\n'
    'local f = 1024\n'
    'local g = 3.5\n'
    'local h = 0\n'
    'local i = 1\n'
    'local j = 999999\n'
    'print(a + b + c)\n'
    'warn(d, e, f, g, h, i, j)\n'
    'for k = 1, 10 do print(k * 3) end\n'
    'if a > 40 then print("big") else print("small") end\n'
)


def count_patterns(text: str) -> dict:
    return {k: len(re.findall(v, text or "")) for k, v in PATTERNS.items()}


def report_counts(text: str, label: str) -> dict:
    counts = count_patterns(text)
    size = len((text or "").encode("utf-8", "replace"))
    print(f"  {label:<14} size={size:<8} " + "  ".join(f"{k}={v}" for k, v in counts.items()))
    return counts


# --------------------------------------------------------------------------- #
# [1] environment / file shadowing
# --------------------------------------------------------------------------- #
def section_env() -> None:
    head("[1] ENVIRONMENT + FILE SHADOWING")
    info(f"python      : {sys.version.split()[0]}  ({sys.executable})")
    info(f"cwd         : {os.getcwd()}")
    info(f"sys.path[0] : {sys.path[0] if sys.path else '(none)'}")

    spec = importlib.util.find_spec("obfuscator")
    if spec is None:
        bad("package 'obfuscator' NOT importable from this cwd - run from project root")
        return
    origin = spec.origin or "?"
    ok(f"obfuscator  : {origin}")
    pkg_dir = os.path.dirname(origin)

    # duplicate / stale copies of the two files in question
    targets = ("random_gen.py", "number_obfuscator.py", "engine.py", "compare_obfuscators.py")
    found = []
    for root, dirs, files in os.walk(pkg_dir):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for f in files:
            if f in targets:
                p = os.path.join(root, f)
                st = os.stat(p)
                found.append((p, st.st_size, st.st_mtime))
    for p, size, mtime in sorted(found):
        rel = os.path.relpath(p, os.path.dirname(pkg_dir))
        info(f"{rel:<58} {size:>7} B  {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(mtime))}")

    # stale bytecode check
    pyc = []
    for root, dirs, files in os.walk(pkg_dir):
        if os.path.basename(root) == "__pycache__":
            for f in files:
                if f.endswith((".pyc",)):
                    p = os.path.join(root, f)
                    pyc.append((p, os.stat(p).st_mtime))
    if pyc:
        warn(f"{len(pyc)} __pycache__ .pyc files present - newest: "
             f"{time.strftime('%H:%M:%S', time.localtime(max(m for _, m in pyc)))}")
    else:
        ok("no __pycache__ .pyc found (clean)")


# --------------------------------------------------------------------------- #
# [2] NumberExprGen standalone + math correctness via LuaSandbox
# --------------------------------------------------------------------------- #
def section_exprgen():
    head("[2] NumberExprGen STANDALONE (obfuscator/utils/random_gen.py)")
    rg, rg_name = try_import("obfuscator.utils.random_gen", "obfuscator.random_gen")
    if rg is None:
        bad("random_gen module not found - nothing else will work")
        return None, None

    info(f"module file : {getattr(rg, '__file__', '?')}")
    src = ""
    try:
        src = inspect.getsource(rg)
    except Exception as exc:  # noqa: BLE001
        warn(f"getsource failed: {exc}")

    bit32_methods = sorted(set(re.findall(r"bit32\.(\w+)", src)))
    info(f"bit32 ops in source ({len(bit32_methods)}): {', '.join(bit32_methods) or '(none)'}")
    info(f"0X in source: {len(re.findall(r'0X', src))}   0B in source: {len(re.findall(r'0B', src))}")

    gen_cls = getattr(rg, "NumberExprGen", None)
    if gen_cls is None:
        bad("class NumberExprGen NOT defined in random_gen.py")
        return None, None

    methods = [m for m in dir(gen_cls) if not m.startswith("__") and callable(getattr(gen_cls, m, None))]
    ok(f"NumberExprGen found, public methods ({len(methods)}): {', '.join(methods)}")

    make_rng = getattr(rg, "make_rng", None)
    rng = None
    if callable(make_rng):
        for kwargs in ({"seed": 42}, {"seed": 42}, {}):
            try:
                rng = make_rng(**kwargs)
                break
            except Exception:  # noqa: BLE001
                try:
                    rng = make_rng(42)
                    break
                except Exception:  # noqa: BLE001
                    rng = None
    if rng is None:
        import random
        rng = random.Random(42)
        warn("make_rng unusable, falling back to random.Random(42)")

    gen = None
    for args in ((rng,), (rng, None), ()):
        try:
            gen = gen_cls(*[a for a in args if a is not None])
            break
        except Exception as exc:  # noqa: BLE001
            info(f"NumberExprGen{args} -> {type(exc).__name__}: {exc}")
    if gen is None:
        bad("cannot instantiate NumberExprGen")
        return gen_cls, None

    gen_fn = None
    for name in ("gen", "generate", "expr", "make", "obfuscate", "gen_expr"):
        if callable(getattr(gen, name, None)):
            gen_fn = name
            break
    if gen_fn is None:
        bad("no gen()/generate() method on NumberExprGen instance")
        return gen_cls, gen

    # optional sandbox for real math verification
    sb_mod, sb_name = try_import(
        "obfuscator.deobfuscator.core.lua_sandbox",
        "obfuscator.deobfuscator.lua_sandbox",
    )
    sandbox = None
    if sb_mod is not None:
        cls = getattr(sb_mod, "LuaSandbox", None)
        if cls is not None:
            try:
                sandbox = cls()
                ok(f"LuaSandbox available ({sb_name}) - will verify math for real")
            except Exception as exc:  # noqa: BLE001
                warn(f"LuaSandbox() failed: {exc}")
    else:
        warn("LuaSandbox not importable - math verification skipped (decoder will need it!)")

    values = [0, 1, 7, 42, 100, 255, 1024, 1337, 65535, 999999]
    good = fail = unver = 0
    print()
    for v in values:
        try:
            expr = getattr(gen, gen_fn)(v)
        except TypeError:
            try:
                expr = getattr(gen, gen_fn)(value=v)
            except Exception as exc:  # noqa: BLE001
                bad(f"gen({v}) raised {type(exc).__name__}: {exc}")
                fail += 1
                continue
        except Exception as exc:  # noqa: BLE001
            bad(f"gen({v}) raised {type(exc).__name__}: {exc}")
            fail += 1
            continue

        verdict = "?"
        if sandbox is not None:
            got, used = call_any(sandbox, ("eval_expr", "eval", "evaluate"), str(expr))
            if used is None:
                verdict = "no-eval-api"
                unver += 1
            elif isinstance(got, (int, float)) and int(got) == int(v):
                verdict = "OK"
                good += 1
            elif got is None:
                verdict = "sandbox-None"
                unver += 1
            else:
                verdict = f"MISMATCH got={got!r}"
                fail += 1
        else:
            unver += 1
        print(f"  {v:>7} -> {str(expr):<44} [{verdict}]")

    print()
    if fail:
        bad(f"exprgen: {fail} WRONG / {good} verified / {unver} unverified")
    elif good:
        ok(f"exprgen: {good}/{good} mathematically correct")
    else:
        warn(f"exprgen: {unver} generated but NOT verified (no sandbox)")
    return gen_cls, gen


# --------------------------------------------------------------------------- #
# [3] number_obfuscator: does it use the SAME NumberExprGen?
# --------------------------------------------------------------------------- #
def section_transformer(gen_cls, gen) -> None:
    head("[3] transformers/number_obfuscator.py - WHICH GENERATOR DOES IT CALL?")
    no, no_name = try_import(
        "obfuscator.transformers.number_obfuscator",
        "obfuscator.number_obfuscator",
    )
    if no is None:
        bad("number_obfuscator module not found")
        return
    info(f"module file : {getattr(no, '__file__', '?')}")
    try:
        src = inspect.getsource(no)
    except Exception:  # noqa: BLE001
        src = ""

    imported_ref = getattr(no, "NumberExprGen", None)
    if imported_ref is None:
        warn("number_obfuscator does NOT expose NumberExprGen at module level")
    elif gen_cls is not None and imported_ref is gen_cls:
        ok("number_obfuscator.NumberExprGen IS random_gen.NumberExprGen (same class object)")
    else:
        bad("number_obfuscator uses a DIFFERENT NumberExprGen class - shadow/local copy!")
        info(f"   transformer's class: {imported_ref!r} from {getattr(imported_ref, '__module__', '?')}")

    local_defs = re.findall(r"^\s*(?:class|def)\s+(_?\w*(?:gen|expr|obf)\w*)", src, re.M | re.I)
    if local_defs:
        warn(f"local generator-ish definitions inside number_obfuscator: {', '.join(sorted(set(local_defs)))}")

    info(f"bit32 mentions in number_obfuscator source: {len(re.findall(r'bit32', src))}")
    gen_call_re = re.compile(r"\.(?:gen|generate)\s*\(")
    info(f"calls to .gen(/generate(: {len(gen_call_re.findall(src))}")

    # config presets
    cfg_cls = pick(no, "NumberObfuscatorConfig", "NumberObfConfig", "Config")
    if cfg_cls is None:
        warn("no NumberObfuscatorConfig class found in this module")
    else:
        print()
        for preset in ("conservative", "balanced", "aggressive", "default", "light", "max", "heavy"):
            fn = getattr(cfg_cls, preset, None)
            if not callable(fn):
                continue
            try:
                inst = fn()
            except Exception as exc:  # noqa: BLE001
                warn(f"{preset}() raised {exc}")
                continue
            if dataclasses.is_dataclass(inst):
                fields = {f.name: getattr(inst, f.name) for f in dataclasses.fields(inst)}
            elif isinstance(inst, dict):
                fields = inst
            else:
                fields = {k: v for k, v in vars(inst).items() if not k.startswith("_")}
            prob = fields.get("probability", fields.get("prob", fields.get("chance", "?")))
            print(f"  {preset:<14} probability={prob!s:<8} {fields}")
        print()


# --------------------------------------------------------------------------- #
# [4] engine: what does 'medium' actually enable?
# --------------------------------------------------------------------------- #
def section_engine() -> None:
    head("[4] engine.py - LEVEL PIPELINES (is number obfuscation even on for medium?)")
    eng, eng_name = try_import("obfuscator.engine")
    if eng is None:
        bad("obfuscator.engine not importable")
        return
    info(f"module file : {getattr(eng, '__file__', '?')}")

    # dump every module-level mapping / config that mentions levels
    for name in dir(eng):
        if name.startswith("__"):
            continue
        val = getattr(eng, name)
        if isinstance(val, dict) and any(isinstance(k, str) and k.lower() in
                                        ("medium", "hard", "insane", "light", "basic", "max")
                                        for k in val):
            print(f"\n  dict {name}:")
            for k, v in val.items():
                if dataclasses.is_dataclass(v):
                    v = {f.name: getattr(v, f.name) for f in dataclasses.fields(v)}
                print(f"    {k:<10} {v}")
        elif dataclasses.is_dataclass(val) and not inspect.isclass(val):
            print(f"\n  dataclass instance {name}: {val}")

    for fn_name in ("get_level_config", "level_config", "config_for", "build_pipeline", "make_pipeline"):
        fn = getattr(eng, fn_name, None)
        if callable(fn):
            for lvl in ("medium", "hard", "insane"):
                try:
                    cfg = fn(lvl)
                except Exception as exc:  # noqa: BLE001
                    warn(f"{fn_name}({lvl!r}) raised {exc}")
                    continue
                if dataclasses.is_dataclass(cfg):
                    cfg = {f.name: getattr(cfg, f.name) for f in dataclasses.fields(cfg)}
                print(f"\n  {fn_name}({lvl!r}) -> {cfg}")

    # order of transformers in the source
    try:
        esrc = inspect.getsource(eng)
    except Exception:  # noqa: BLE001
        esrc = ""
    order = re.findall(r"(string_encrypt\w*|number_obfusc\w*|variable_renam\w*|control_flow\w*|"
                       r"vm_protect\w*|watermark\w*|anti_tamper\w*|environment\w*|junk\w*)", esrc)
    if order:
        seen = []
        for o in order:
            if o not in seen:
                seen.append(o)
        info("transformer mentions (source order, deduped): " + " -> ".join(seen))


# --------------------------------------------------------------------------- #
# [5] end-to-end: obfuscate() output per level
# --------------------------------------------------------------------------- #
def section_end_to_end(levels, seed) -> dict:
    head(f"[5] END-TO-END obfuscate(SAMPLE, level=..., seed={seed})")
    eng, _ = try_import("obfuscator.engine")
    results = {}
    if eng is None:
        bad("engine missing")
        return results

    obf_fn = pick(eng, "obfuscate", "obfuscate_source", "run")
    if not callable(obf_fn):
        bad("no obfuscate() callable in engine")
        return results

    num_lit_re = re.compile(r"(?<![\w.])\d+(?:\.\d+)?")
    print(f"  sample: {len(SAMPLE)} bytes, {len(num_lit_re.findall(SAMPLE))} numeric literals")
    print()
    for lvl in levels:
        text = None
        for kwargs in ({"level": lvl, "seed": seed}, {"level": lvl}, {}):
            try:
                out = obf_fn(SAMPLE, **kwargs)
                text = out if isinstance(out, str) else pick(out, "code", "source", "output", "result")
                if text:
                    break
            except Exception as exc:  # noqa: BLE001
                info(f"obfuscate(level={lvl!r}, {kwargs}) -> {type(exc).__name__}: {exc}")
        if not text:
            bad(f"level={lvl}: no output")
            continue
        results[lvl] = text
        report_counts(text, f"level={lvl}")
    return results


# --------------------------------------------------------------------------- #
# [6] transformer in isolation (pipeline vs transformer)
# --------------------------------------------------------------------------- #
def section_isolated(seed) -> None:
    head("[6] NUMBER TRANSFORMER IN ISOLATION (bypasses engine pipeline)")
    lex_mod, _ = try_import("obfuscator.lexer")
    par_mod, _ = try_import("obfuscator.parser")
    unp_mod, _ = try_import("obfuscator.ast_unparser", "obfuscator.unparser")
    no_mod, _ = try_import("obfuscator.transformers.number_obfuscator", "obfuscator.number_obfuscator")
    if not (par_mod and unp_mod and no_mod):
        warn("parser/unparser/number_obfuscator not all importable - skipping")
        return

    chunk = None
    for name in ("parse", "parse_source", "parse_chunk"):
        fn = getattr(par_mod, name, None)
        if callable(fn):
            try:
                if lex_mod is not None:
                    lex_fn = pick(lex_mod, "lex", "tokenize", "Lexer")
                    try:
                        chunk = fn(SAMPLE, lex_fn(SAMPLE) if callable(lex_fn) else None)
                    except Exception:  # noqa: BLE001
                        chunk = fn(SAMPLE)
                else:
                    chunk = fn(SAMPLE)
                ok(f"parsed via {name}() -> {type(chunk).__name__}")
                break
            except Exception as exc:  # noqa: BLE001
                info(f"{name}() raised {type(exc).__name__}: {exc}")
    if chunk is None:
        bad("could not parse the sample")
        return

    def count_numbers(node, depth=0):
        if node is None or depth > 60:
            return 0
        if type(node).__name__ in ("NumberLit", "Num", "Number"):
            return 1
        total = 0
        for attr in ("body", "left", "right", "operand", "obj", "index", "func",
                     "value", "key", "cond", "start", "stop", "step", "call", "target"):
            total += count_numbers(getattr(node, attr, None), depth + 1)
        for attr in ("statements", "values", "args", "fields", "names", "exprs", "branches", "body_"):
            v = getattr(node, attr, None)
            if isinstance(v, (list, tuple)):
                for item in v:
                    if isinstance(item, tuple):
                        for sub in item:
                            total += count_numbers(sub, depth + 1)
                    else:
                        total += count_numbers(item, depth + 1)
        rs = getattr(node, "return_stat", None)
        total += count_numbers(rs, depth + 1)
        return total

    before = count_numbers(chunk)
    info(f"NumberLit nodes in AST before: {before}")

    unparse = pick(unp_mod, "unparse", "to_source", "unparse_chunk", "render")
    if callable(unparse):
        try:
            info(f"source round-trip OK, {len(unparse(chunk))} bytes")
        except Exception as exc:  # noqa: BLE001
            warn(f"unparse failed: {exc}")

    # find the transformer entry point
    candidates = []
    for name in dir(no_mod):
        if name.startswith("_"):
            continue
        obj = getattr(no_mod, name)
        if inspect.isclass(obj):
            candidates.append(("class", name, obj))
        elif callable(obj):
            candidates.append(("func", name, obj))
    info("public symbols in number_obfuscator: " + ", ".join(f"{k}:{n}" for k, n, _ in candidates))

    applied = False
    for kind, name, obj in candidates:
        try:
            if kind == "class":
                inst = obj()
                for m in ("transform", "apply", "run", "process", "obfuscate"):
                    fn = getattr(inst, m, None)
                    if callable(fn):
                        try:
                            fn(chunk)
                            ok(f"applied {name}().{m}() to the AST")
                            applied = True
                            break
                        except TypeError:
                            try:
                                fn(chunk, None)
                                ok(f"applied {name}().{m}(chunk, None)")
                                applied = True
                                break
                            except Exception:  # noqa: BLE001
                                continue
                        except Exception as exc:  # noqa: BLE001
                            info(f"{name}().{m}() raised {type(exc).__name__}: {exc}")
            else:
                try:
                    obj(chunk)
                    ok(f"applied function {name}()")
                    applied = True
                    break
                except TypeError:
                    continue
        except Exception as exc:  # noqa: BLE001
            info(f"{name} instantiation raised {type(exc).__name__}: {exc}")

    if not applied:
        warn("could not auto-apply the transformer - inspect number_obfuscator API manually")
        return

    after = count_numbers(chunk)
    info(f"NumberLit nodes in AST after : {after}")
    if callable(unparse):
        try:
            text = unparse(chunk)
            counts = report_counts(text, "isolated")
            if counts["bit32_calls"] or counts["bin_literals"]:
                ok("ISOLATED transformer DOES emit bit32/0B => bug is in the ENGINE pipeline or level config")
            else:
                bad("ISOLATED transformer emits NO bit32/0B => bug is in number_obfuscator/probability/config")
            print()
            print("  --- first 900 chars of isolated output ---")
            print("  " + text[:900].replace("\n", "\n  "))
        except Exception as exc:  # noqa: BLE001
            warn(f"unparse after transform failed: {exc}")


# --------------------------------------------------------------------------- #
# [7] compare_obfuscators detector regexes vs real output
# --------------------------------------------------------------------------- #
def section_compare(results: dict) -> None:
    head("[7] tools/compare_obfuscators.py - DETECTOR REGEXES vs REAL OUTPUT")
    cmp_mod, _ = try_import(
        "obfuscator.deobfuscator.tools.compare_obfuscators",
        "obfuscator.tools.compare_obfuscators",
    )
    if cmp_mod is None:
        warn("compare_obfuscators not importable - skipping")
        return
    info(f"module file : {getattr(cmp_mod, '__file__', '?')}")
    try:
        csrc = inspect.getsource(cmp_mod)
    except Exception:  # noqa: BLE001
        csrc = ""

    feats = re.findall(r"[\"']([\w \.\(\)]{3,40})[\"']\s*:\s*r?[\"'](.*?)[\"']\s*,?\s*$", csrc, re.M)
    regexes = re.findall(r"r[\"'](.{2,60}?)[\"']", csrc)
    interesting = [r for r in regexes if re.search(r"0\[?[bBxX]|bit32|binary|math", r, re.I)]
    info("detector-ish regexes in source:")
    for r in interesting or regexes[:25]:
        print(f"      {r}")

    sample_text = results.get("medium") or (next(iter(results.values())) if results else "")
    if not sample_text:
        warn("no obfuscated output available to test the detectors against")
        return
    print()
    for r in interesting:
        try:
            n = len(re.findall(r, sample_text))
        except re.error as exc:
            warn(f"bad regex {r!r}: {exc}")
            continue
        mark = "HIT " if n else "MISS"
        print(f"  [{mark}] {r:<40} matches={n}")

    if feats:
        print()
        info("feature-name -> regex pairs parsed from source:")
        for name, rx in feats[:25]:
            print(f"      {name:<34} {rx}")


# --------------------------------------------------------------------------- #
# [8] verdict
# --------------------------------------------------------------------------- #
def section_verdict(results: dict) -> None:
    head("[8] VERDICT / MOST LIKELY ROOT CAUSE")
    med = results.get("medium", "")
    c = count_patterns(med)
    if not med:
        bad("no medium-level output produced - the pipeline itself is broken")
        return
    if c["bit32_calls"] == 0 and c["bin_literals"] == 0 and c["hex_literals"] == 0:
        bad("medium output has ZERO bit32/0B/0X => NumberExprGen v2.1 is never reached")
        info("check in order:")
        info("  a) section [4]: does the 'medium' config enable number obfuscation at all?")
        info("  b) section [3]: probability of the preset used by medium (0.35 default?)")
        info("  c) section [6]: isolated run - if it emits bit32, the engine pipeline drops it")
        info("  d) section [3]: is number_obfuscator bound to a DIFFERENT (old) NumberExprGen?")
    elif c["bit32_calls"] > 0:
        ok(f"medium DOES emit bit32 ({c['bit32_calls']}x) => problem is the DETECTOR in compare tool")
    else:
        warn("partial: some number obfuscation present, but not the v2.1 bit32 family")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--level", action="append", default=None)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--dump", type=int, default=0, help="dump N chars of medium output")
    args = ap.parse_args()
    levels = args.level or ["medium", "hard"]

    print("=" * 78)
    print("NZL STUDIO - SPRINT 1 DIAGNOSTIC (number obfuscation pipeline)")
    print("=" * 78)

    try:
        section_env()
    except Exception as exc:  # noqa: BLE001
        bad(f"section [1] crashed: {exc}")
    gen_cls = gen = None
    try:
        gen_cls, gen = section_exprgen()
    except Exception as exc:  # noqa: BLE001
        bad(f"section [2] crashed: {exc}")
    try:
        section_transformer(gen_cls, gen)
    except Exception as exc:  # noqa: BLE001
        bad(f"section [3] crashed: {exc}")
    try:
        section_engine()
    except Exception as exc:  # noqa: BLE001
        bad(f"section [4] crashed: {exc}")
    results = {}
    try:
        results = section_end_to_end(levels, args.seed)
    except Exception as exc:  # noqa: BLE001
        bad(f"section [5] crashed: {exc}")
    try:
        section_isolated(args.seed)
    except Exception as exc:  # noqa: BLE001
        bad(f"section [6] crashed: {exc}")
    try:
        section_compare(results)
    except Exception as exc:  # noqa: BLE001
        bad(f"section [7] crashed: {exc}")

    if args.dump and results.get("medium"):
        head(f"[DUMP] medium output, first {args.dump} chars")
        print(results["medium"][:args.dump])

    try:
        section_verdict(results)
    except Exception as exc:  # noqa: BLE001
        bad(f"section [8] crashed: {exc}")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
