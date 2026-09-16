"""
NZL Deobfuscator - Real-World Round-Trip Test
==============================================
Берёт простой Lua-код → обфусцирует через наш /obfuscate → 
прогоняет через деобфускатор → показывает результат side-by-side.

Это ГЛАВНОЕ ДЕМО деобфускатора v3.0.
"""

import time
from obfuscator.engine import obfuscate
from obfuscator.deobfuscator.engine import DeobfuscatorEngine


# ============================================================
# SAMPLES — что обфусцируем
# ============================================================

SAMPLES = [
    ("simple_hello",
     '''
print("Hello, World!")
local x = 42
local y = "some string"
'''),

    ("with_functions",
     '''
local function greet(name)
    return "Hello, " .. name .. "!"
end
local msg = greet("NZL")
print(msg)
'''),

    ("with_loops",
     '''
local total = 0
for i = 1, 10 do
    total = total + i
end
print("Sum:", total)
'''),

    ("with_table",
     '''
local player = {
    name = "Alice",
    hp = 100,
    level = 5
}
print(player.name, player.hp)
'''),

    ("complex",
     '''
local function factorial(n)
    if n <= 1 then return 1 end
    return n * factorial(n - 1)
end

local secrets = {"password123", "api_key_xyz", "token_abc"}
for i, s in ipairs(secrets) do
    print(i, s, factorial(i))
end
'''),
]


def print_side_by_side(title: str, before: str, after: str, max_lines: int = 25):
    """Красивый вывод двух блоков рядом."""
    bef_lines = before.splitlines() or [""]
    aft_lines = after.splitlines() or [""]
    if len(bef_lines) > max_lines:
        bef_lines = bef_lines[:max_lines] + [f"... (+{len(before.splitlines()) - max_lines} more)"]
    if len(aft_lines) > max_lines:
        aft_lines = aft_lines[:max_lines] + [f"... (+{len(after.splitlines()) - max_lines} more)"]
    
    print(f"\n{'='*80}")
    print(f"  {title}")
    print("="*80)
    print(f"BEFORE ({len(before)} bytes):")
    print("-" * 80)
    print(before)
    print("-" * 80)
    print(f"AFTER  ({len(after)} bytes):")
    print("-" * 80)
    print(after)
    print("-" * 80)


def run_round_trip(name: str, source: str, obf_level: str = "medium", deobf_level: str = "full"):
    """Обфускация → деобфускация → сравнение."""
    print(f"\n\n{'#'*80}")
    print(f"# ROUND-TRIP: {name}   (obf={obf_level}, deobf={deobf_level})")
    print(f"{'#'*80}")
    
    # 1) Обфускация
    print(f"\n[step 1/3] Obfuscating with level={obf_level!r}...")
    t0 = time.perf_counter()
    try:
        obfuscated = obfuscate(source, level=obf_level, seed=42)
    except Exception as e:
        print(f"  [XX] obfuscate FAILED: {type(e).__name__}: {e}")
        return
    obf_time = (time.perf_counter() - t0) * 1000
    print(f"  [OK] {len(source)} bytes -> {len(obfuscated)} bytes  ({obf_time:.1f} ms)")
    
    # 2) Деобфускация
    print(f"\n[step 2/3] Deobfuscating with level={deobf_level!r}...")
    engine = DeobfuscatorEngine(level=deobf_level, verbose=False)
    result = engine.deobfuscate_ex(obfuscated)
    print(f"  [OK] {result.original_size} bytes -> {result.cleaned_size} bytes")
    print(f"       replaced={result.total_replaced}, passes={result.passes_run}, "
          f"time={result.total_time_ms:.1f}ms, errors={result.total_errors}")
    
    if result.parse_error:
        print(f"  [XX] parse_error: {result.parse_error}")
    
    # 3) Показ
    print(f"\n[step 3/3] Side-by-side comparison:")
    print_side_by_side(f"{name}: ORIGINAL vs OBFUSCATED", source, obfuscated, max_lines=20)
    print_side_by_side(f"{name}: OBFUSCATED vs DEOBFUSCATED", obfuscated, result.cleaned_source, max_lines=20)
    
    # Метрика "восстановления"
    orig_size = len(source)
    obf_size  = len(obfuscated)
    clean_size = len(result.cleaned_source)
    growth = obf_size / max(orig_size, 1)
    recovery = 1 - (clean_size - orig_size) / max(obf_size - orig_size, 1)
    print(f"\n[metrics]")
    print(f"  Original:  {orig_size:>7} bytes  (baseline)")
    print(f"  Obf x{growth:.1f}: {obf_size:>7} bytes  (+{obf_size-orig_size} vs orig)")
    print(f"  Cleaned:   {clean_size:>7} bytes  (recovery: {recovery*100:.1f}% from obf back to orig)")


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    print("=" * 80)
    print("  NZL DEOBFUSCATOR v3.0 — REAL-WORLD ROUND-TRIP TEST")
    print("=" * 80)
    print(f"Testing {len(SAMPLES)} samples through obfuscate -> deobfuscate pipeline\n")
    
    # Разные комбинации level'ов
    for name, src in SAMPLES:
        run_round_trip(name, src, obf_level="medium", deobf_level="full")
    
    print("\n\n" + "=" * 80)
    print("  DONE — real-world round-trip completed!")
    print("=" * 80)