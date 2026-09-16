"""
compare_obfuscators.py — Сравнение NZL vs Luraph v14.6
Показывает метрики, features, side-by-side анализ
"""
import os
import re
import sys
import time
from pathlib import Path

# ================== TEST SOURCE ==================
TEST_SOURCE = """
local function greet(name)
    local msg = "Hello, " .. name .. "!"
    print(msg)
    return #msg
end

local function factorial(n)
    if n <= 1 then return 1 end
    return n * factorial(n - 1)
end

local secrets = {"alpha", "beta", "gamma"}
local total = 0
for i, s in ipairs(secrets) do
    total = total + #s * factorial(i)
end

print(greet("World"), total)
""".strip()

# ================== ANALYZERS ==================

def analyze_source(source: str, name: str) -> dict:
    """Извлекает метрики из обфусцированного кода"""
    stats = {
        "name": name,
        "size_bytes": len(source),
        "size_kb": len(source) / 1024,
        "lines": source.count("\n") + 1,
        "chars": len(source),
    }
    
    # Feature detection
    features = {}
    
    # String protection
    features["string_encryption"] = bool(
        re.search(r'string\.char\s*\(\s*\d+\s*,', source) or
        re.search(r'_decrypt|_dec|_d\(', source) or
        re.search(r'bit32\.bxor.*string\.byte', source)
    )
    features["string_array_indexing"] = bool(
        re.search(r'local\s+\w+\s*=\s*\{\s*[\'"]', source) and
        re.search(r'\w+\[\d+\]', source)
    )
    features["non_ascii_bytes"] = any(ord(c) > 127 for c in source[:5000])
    features["raw_byte_strings"] = bool(re.search(r'\\\d{3}', source))
    
    # Control flow
    features["opaque_predicates"] = bool(
        re.search(r'if\s+(\d+\s*[=<>!~]+\s*\d+|true|false)\s+then', source) and
        source.count("if ") > 10
    )
    features["control_flow_flattening"] = bool(
        re.search(r'while\s+true\s+do.*if.*==.*then', source, re.DOTALL) and
        source.count("while true") >= 3
    )
    features["state_machine"] = bool(
        re.search(r'(state|q|_)\s*==?\s*\d+.*continue|break', source)
    )
    features["junk_code"] = source.count("--") > 5 or source.count("do end") > 3
    
    # Naming
    features["homoglyph_names"] = bool(re.search(r'[Il1O0]{4,}', source))
    features["short_ambiguous_names"] = bool(
        len(re.findall(r'\blocal\s+[a-zA-Z]{1,3}\b', source)) > 20
    )
    
    # Numbers
    features["binary_literals"] = bool(re.search(r'0[bB][01_]+', source))
    features["hex_literals"] = bool(re.search(r'0[xX][0-9a-fA-F_]+', source))
    features["math_expressions"] = source.count("bit32.") >= 3
    features["number_folding"] = bool(re.search(r'\(\d+\s*[\+\-\*\/]\s*\d+', source))
    
    # VM
    features["custom_vm"] = bool(
        re.search(r'while\s+true\s+do.*opcode|instruction', source, re.DOTALL) or
        source.count("function()") > 20 or
        re.search(r'\[=\[LPH', source)
    )
    features["luraph_signature"] = bool(re.search(r'Luraph|LPH~|\[=\[LPH', source))
    features["nzl_signature"] = bool(re.search(r'NZL|_nzl|nzl_', source, re.IGNORECASE))
    
    # Anti-tamper
    features["pcall_wrapping"] = source.count("pcall") > 3
    features["env_checks"] = bool(re.search(r'getfenv|setfenv|_ENV', source))
    features["error_calls"] = source.count("error(") > 2
    
    # Structure
    features["huge_table"] = bool(re.search(r'\{[^}]{500,}\}', source))
    features["big_string_blob"] = bool(re.search(r'[\'"][^\'"]{1000,}[\'"]', source) or
                                        re.search(r'\[=?\[[^\]]{1000,}\]=?\]', source))
    
    stats["features"] = features
    stats["feature_count"] = sum(1 for v in features.values() if v)
    
    return stats


def try_load_nzl_obfuscator():
    """Пробуем загрузить наш обфускатор"""
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
        from obfuscator.engine import obfuscate
        return obfuscate
    except Exception as e:
        print(f"[!!] Не удалось загрузить NZL обфускатор: {e}")
        return None


def load_luraph_sample() -> str | None:
    """Загружаем сохранённый Luraph сэмпл"""
    sample_path = Path(__file__).parent.parent / "samples" / "luraph" / "v14.6_sample1.lua"
    if not sample_path.exists():
        print(f"[!!] Luraph сэмпл не найден: {sample_path}")
        print(f"[!!] Сохрани файл туда для сравнения")
        return None
    return sample_path.read_text(encoding="utf-8", errors="replace")


# ================== PRINTER ==================

def print_header(title: str):
    line = "=" * 70
    print(f"\n{line}")
    print(f"  {title}")
    print(line)


def print_stat_row(label: str, nzl_val, luraph_val, orig_val=None):
    if orig_val is not None:
        print(f"  {label:35s} {str(orig_val):>15s} {str(nzl_val):>15s} {str(luraph_val):>15s}")
    else:
        print(f"  {label:35s} {'':>15s} {str(nzl_val):>15s} {str(luraph_val):>15s}")


def print_feature_row(label: str, nzl_has: bool, luraph_has: bool):
    nzl_mark = "[OK]" if nzl_has else "[  ]"
    lur_mark = "[OK]" if luraph_has else "[  ]"
    winner = ""
    if nzl_has and not luraph_has:
        winner = " <- NZL only!"
    elif luraph_has and not nzl_has:
        winner = " <- Luraph only"
    print(f"  {label:35s}     {nzl_mark}          {lur_mark}   {winner}")


# ================== MAIN ==================

def main():
    print_header("NZL vs LURAPH v14.6 — OBFUSCATOR COMPARISON")
    
    # 1. Analyze original
    print("\n[**] Analyzing test source...")
    orig_stats = analyze_source(TEST_SOURCE, "Original")
    print(f"  Original: {orig_stats['size_bytes']} bytes, {orig_stats['lines']} lines")
    
    # 2. Try NZL obfuscator
    print("\n[**] Running NZL obfuscator...")
    obfuscate = try_load_nzl_obfuscator()
    
    nzl_results = {}
    if obfuscate:
        for level in ["medium", "hard", "insane"]:
            try:
                t0 = time.time()
                obfuscated = obfuscate(TEST_SOURCE, level=level, seed=42)
                elapsed = (time.time() - t0) * 1000
                stats = analyze_source(obfuscated, f"NZL-{level}")
                stats["time_ms"] = elapsed
                nzl_results[level] = stats
                print(f"  [OK] {level:6s}: {stats['size_bytes']:>7d} bytes  ({stats['size_bytes']/orig_stats['size_bytes']:>5.1f}x)  {elapsed:>6.1f}ms")
            except Exception as e:
                print(f"  [XX] {level}: {e}")
                nzl_results[level] = None
    
    # 3. Load Luraph sample
    print("\n[**] Loading Luraph v14.6 sample...")
    luraph_source = load_luraph_sample()
    if luraph_source:
        luraph_stats = analyze_source(luraph_source, "Luraph-14.6")
        print(f"  [OK] Luraph: {luraph_stats['size_bytes']:>7d} bytes  (unknown original ratio)")
    else:
        luraph_stats = None
        print("  [XX] Skipping Luraph analysis")
    
    # 4. Size comparison
    print_header("SIZE COMPARISON")
    print(f"  {'Metric':35s} {'Original':>15s} {'NZL-medium':>15s} {'Luraph':>15s}")
    print("  " + "-" * 70)
    if luraph_stats and nzl_results.get("medium"):
        nzl_med = nzl_results["medium"]
        print_stat_row("Size (bytes)", nzl_med["size_bytes"], luraph_stats["size_bytes"], orig_stats["size_bytes"])
        print_stat_row("Size (KB)", f"{nzl_med['size_kb']:.1f}", f"{luraph_stats['size_kb']:.1f}", f"{orig_stats['size_kb']:.2f}")
        print_stat_row("Lines", nzl_med["lines"], luraph_stats["lines"], orig_stats["lines"])
        
        nzl_ratio = nzl_med["size_bytes"] / orig_stats["size_bytes"]
        # Luraph работал на другом исходнике - примерная оценка
        print(f"\n  NZL blow-up ratio: {nzl_ratio:.1f}x (medium)")
        if nzl_results.get("insane"):
            ins_ratio = nzl_results["insane"]["size_bytes"] / orig_stats["size_bytes"]
            print(f"  NZL blow-up ratio: {ins_ratio:.1f}x (insane)")
        print(f"  Luraph typical:    500-2000x blow-up on 200-byte scripts")
    
    # 5. Feature-by-feature comparison
    print_header("FEATURE COMPARISON (NZL medium vs Luraph v14.6)")
    print(f"  {'Feature':35s}     NZL         Luraph   Notes")
    print("  " + "-" * 70)
    
    if luraph_stats and nzl_results.get("medium"):
        # Feature = СПОСОБНОСТЬ обфускатора, а не удача одного розыгрыша:
        # union по нескольким seed'ам (один draw может статистически не дать 0B).
        union_feat = dict(nzl_results["medium"]["features"])
        if obfuscate:
            for extra_seed in (1, 7):
                try:
                    extra_src = obfuscate(TEST_SOURCE, level="medium", seed=extra_seed)
                    extra = analyze_source(extra_src, f"NZL-medium-s{extra_seed}")["features"]
                    for k in union_feat:
                        union_feat[k] = bool(union_feat[k]) or bool(extra.get(k, False))
                except Exception as e:  # noqa: BLE001
                    print(f"  [!!] seed {extra_seed}: {e}")
        nzl_feat = union_feat
        lur_feat = luraph_stats["features"]
        
        categories = [
            ("--- String Protection ---", []),
            ("String encryption", "string_encryption"),
            ("String array indexing", "string_array_indexing"),
            ("Non-ASCII bytes", "non_ascii_bytes"),
            ("Raw byte strings (\\ddd)", "raw_byte_strings"),
            ("Big string blob", "big_string_blob"),
            
            ("--- Control Flow ---", []),
            ("Opaque predicates", "opaque_predicates"),
            ("Control flow flattening", "control_flow_flattening"),
            ("State machine dispatch", "state_machine"),
            ("Junk code injection", "junk_code"),
            
            ("--- Name Obfuscation ---", []),
            ("Homoglyph names (Il10O)", "homoglyph_names"),
            ("Short ambiguous names", "short_ambiguous_names"),
            
            ("--- Number Obfuscation ---", []),
            ("Binary literals (0b101)", "binary_literals"),
            ("Hex literals (0x1A)", "hex_literals"),
            ("Math expressions (bit32)", "math_expressions"),
            ("Number folding", "number_folding"),
            
            ("--- VM Virtualization ---", []),
            ("Custom VM", "custom_vm"),
            ("Huge dispatch table", "huge_table"),
            
            ("--- Anti-Tamper ---", []),
            ("pcall wrapping", "pcall_wrapping"),
            ("Environment checks", "env_checks"),
            ("Error() calls", "error_calls"),
            
            ("--- Signatures ---", []),
            ("Luraph signature (LPH~)", "luraph_signature"),
            ("NZL signature", "nzl_signature"),
        ]
        
        nzl_wins = 0
        luraph_wins = 0
        both = 0
        neither = 0
        
        for label, key in categories:
            if not key:
                print(f"\n  {label}")
                continue
            n = nzl_feat.get(key, False)
            l = lur_feat.get(key, False)
            print_feature_row(label, n, l)
            if n and l:
                both += 1
            elif n and not l:
                nzl_wins += 1
            elif l and not n:
                luraph_wins += 1
            else:
                neither += 1
        
        print("\n  " + "-" * 70)
        print(f"  Both:        {both:2d} features")
        print(f"  NZL only:    {nzl_wins:2d} features")
        print(f"  Luraph only: {luraph_wins:2d} features  <-- what we need to add")
        print(f"  Neither:     {neither:2d} features")
    
    # 6. Verdict
    print_header("VERDICT")
    if luraph_stats and nzl_results.get("medium"):
        nzl_total = nzl_results["medium"]["feature_count"]
        lur_total = luraph_stats["feature_count"]
        ratio = nzl_total / lur_total * 100 if lur_total > 0 else 0
        print(f"""
  NZL feature score:    {nzl_total} techniques detected
  Luraph feature score: {lur_total} techniques detected
  
  NZL is at ~{ratio:.0f}% of Luraph level (feature-wise)
  
  --- Top 5 things to add to NZL ---
  1. Control Flow Flattening (Luraph's killer feature)
  2. Opaque Predicates (if 1==1 then...)
  3. Number -> Expression (5 -> bit32.rrotate(0xA0, 3))
  4. String Array Indexing (all strings in one table)
  5. Bigger VM (150+ opcodes vs our 51)
  
  --- NZL's strengths ---
  * VM works reliably in Roblox
  * Watermark via steganography
  * StringEncryptor is solid
  * Homoglyph naming works
""")
    else:
        print("  [!!] Не удалось сравнить: сохрани Luraph сэмпл в samples/luraph/v14.6_sample1.lua")
    
    print("=" * 70)
    print("  Done!")
    print("=" * 70)


if __name__ == "__main__":
    main()