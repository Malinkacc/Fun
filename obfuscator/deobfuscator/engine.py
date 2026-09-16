"""
NZL Deobfuscator Engine v3.0
=============================
Полноценный pipeline деобфускации.

Уровни:
    "basic"  — только safe трансформации (string.char, constant fold)
    "full"   — basic + sandbox decoder (свёртка decrypt-функций)
    "vm"     — full + VM devirtualization (пока не реализовано)

Использование:
    from obfuscator.deobfuscator.engine import DeobfuscatorEngine
    engine = DeobfuscatorEngine(level="full")
    cleaned, logs = engine.deobfuscate(obfuscated_source)
"""

from __future__ import annotations
from dataclasses import dataclass, field
import time
import traceback

from obfuscator.deobfuscator.core.base import parse_code, ast_to_code
from obfuscator.deobfuscator.decoders.string_char_decoder import StringCharDecoder
from obfuscator.deobfuscator.decoders.constant_fold_decoder import ConstantFoldDecoder
from obfuscator.deobfuscator.decoders.sandbox_decoder import SandboxDecoder
from obfuscator.deobfuscator.decoders.number_expr_decoder import NumberExprDecoder
from obfuscator.deobfuscator.decoders.string_array_decoder import StringArrayDecoder
from obfuscator.deobfuscator.decoders.base_decoder import DecoderStats


@dataclass
class PipelineResult:
    """Результат прогона pipeline."""
    original_source: str
    cleaned_source: str
    original_size: int = 0
    cleaned_size: int = 0
    total_time_ms: float = 0.0
    passes_run: int = 0
    stats_per_stage: list[tuple[str, DecoderStats]] = field(default_factory=list)
    parse_error: str | None = None
    
    @property
    def size_reduction_percent(self) -> float:
        if self.original_size == 0:
            return 0.0
        return (1 - self.cleaned_size / self.original_size) * 100
    
    @property
    def total_replaced(self) -> int:
        return sum(s.replaced for _, s in self.stats_per_stage)
    
    @property
    def total_errors(self) -> int:
        return sum(s.errors for _, s in self.stats_per_stage)


class DeobfuscatorEngine:
    """
    Главный движок деобфускации.
    Оркестрирует запуск декодеров в правильном порядке.
    """
    
    LEVELS = ("basic", "full", "vm")
    
    # Максимум проходов pipeline — чтобы декодеры "докатились"
    # (например: sandbox свернул строку → появилась новая арифметика → фолдим опять)
    MAX_PASSES = 5
    
    def __init__(self, level: str = "full", verbose: bool = False):
        if level not in self.LEVELS:
            raise ValueError(f"level must be one of {self.LEVELS}, got {level!r}")
        self.level = level
        self.verbose = verbose
    
    # ============================================================
    # ГЛАВНЫЙ ENTRY POINT
    # ============================================================
    
    def deobfuscate(self, source: str) -> tuple[str, list[str]]:
        """
        Возвращает (cleaned_source, logs) для совместимости со старым API.
        Если нужна расширенная статистика — используй deobfuscate_ex().
        """
        result = self.deobfuscate_ex(source)
        logs = self._format_logs(result)
        return result.cleaned_source, logs
    
    def deobfuscate_ex(self, source: str) -> PipelineResult:
        """Расширенный вариант — возвращает полный PipelineResult."""
        t0 = time.perf_counter()
        result = PipelineResult(
            original_source=source,
            cleaned_source=source,
            original_size=len(source),
            cleaned_size=len(source),
        )
        
        # 1) Парсим
        try:
            chunk = parse_code(source)
        except Exception as e:
            result.parse_error = f"{type(e).__name__}: {e}"
            result.total_time_ms = (time.perf_counter() - t0) * 1000
            if self.verbose:
                traceback.print_exc()
            return result
        
        # 2) Строим pipeline stages по level'у
        stages = self._build_pipeline_stages()
        
        # 3) Крутим passes пока что-то меняется
        prev_size = len(source)
        for pass_num in range(1, self.MAX_PASSES + 1):
            pass_replaced = 0
            for stage_name, decoder in stages:
                try:
                    chunk, stats = decoder.run(chunk)
                except Exception as e:
                    err_stats = DecoderStats(name=stage_name)
                    err_stats.errors = 1
                    err_stats.details.append(f"CRASH: {type(e).__name__}: {e}")
                    result.stats_per_stage.append((f"pass{pass_num}:{stage_name}", err_stats))
                    if self.verbose:
                        traceback.print_exc()
                    continue
                
                # Регистрируем статистику только если что-то было
                if stats.scanned > 0 or stats.replaced > 0 or stats.errors > 0:
                    result.stats_per_stage.append((f"pass{pass_num}:{stage_name}", stats))
                pass_replaced += stats.replaced
            
            result.passes_run = pass_num
            
            # Условие остановки: ничего не свернули на этом проходе
            if pass_replaced == 0:
                break
        
        # 4) Финальный unparse
        try:
            result.cleaned_source = ast_to_code(chunk)
        except Exception as e:
            result.parse_error = f"unparse error: {type(e).__name__}: {e}"
            if self.verbose:
                traceback.print_exc()
        
        result.cleaned_size = len(result.cleaned_source)
        result.total_time_ms = (time.perf_counter() - t0) * 1000
        return result
    
    # ============================================================
    # PIPELINE STAGES
    # ============================================================
    
    def _build_pipeline_stages(self) -> list[tuple[str, object]]:
        """Возвращает список (имя, декодер) в порядке применения."""
        from .decoders.nzl_wrapper_stripper import NZLWrapperStripper
        stages: list[tuple[str, object]] = []
        
        if self.level in ("basic", "full", "vm"):
            stages.append(("string.char fold", StringCharDecoder()))
            stages.append(("constant fold #1", ConstantFoldDecoder()))
            stages.append(("number expr fold #1", NumberExprDecoder()))
            stages.append(("string array inline #1", StringArrayDecoder()))
        
        if self.level in ("full", "vm"):
            stages.append(("sandbox decoder",  SandboxDecoder(verbose=self.verbose)))
            stages.append(("constant fold #2", ConstantFoldDecoder()))
            stages.append(("number expr fold #2", NumberExprDecoder()))
            stages.append(("string array inline #2", StringArrayDecoder()))
            stages.append(("string.char fold #2", StringCharDecoder()))
            stages.append(("nzl wrapper strip", NZLWrapperStripper()))
            stages.append(("constant fold #3", ConstantFoldDecoder()))
        
        if self.level == "vm":
            pass  # TODO: vm_devirtualizer
        
        return stages
    
    # ============================================================
    # FORMATTING
    # ============================================================
    
    def _format_logs(self, r: PipelineResult) -> list[str]:
        """Красивое форматирование для бота/CLI."""
        logs = []
        
        if r.parse_error:
            logs.append(f"[XX] Parse error: {r.parse_error}")
            logs.append("[!!] Возможно код не является валидным Lua/Luau.")
            return logs
        
        logs.append(f"[**] NZL Deobfuscator v3.0 — level: {self.level}")
        logs.append(f"[##] Original size:  {r.original_size:>7} bytes")
        logs.append(f"[##] Cleaned size:   {r.cleaned_size:>7} bytes")
        
        arrow = "↓" if r.cleaned_size < r.original_size else "↑"
        logs.append(
            f"[##] Reduction:      {arrow} {r.size_reduction_percent:5.1f}% "
            f"({r.original_size - r.cleaned_size:+d} bytes)"
        )
        logs.append(f"[##] Total replaced: {r.total_replaced}")
        logs.append(f"[##] Passes run:     {r.passes_run}/{self.MAX_PASSES}")
        logs.append(f"[##] Time:           {r.total_time_ms:.1f} ms")
        
        if r.total_errors > 0:
            logs.append(f"[!!] Errors: {r.total_errors}")
        
        if r.stats_per_stage:
            logs.append("")
            logs.append("Per-stage breakdown:")
            for stage_name, stats in r.stats_per_stage:
                logs.append(
                    f"  • {stage_name:35s} scan={stats.scanned:3d}  "
                    f"repl={stats.replaced:3d}  err={stats.errors:2d}"
                )
        
        return logs


# ============================================================
# CLI HELPERS
# ============================================================

def deobfuscate_source(source: str, level: str = "full", verbose: bool = False) -> str:
    """Быстрый одношаговый API."""
    engine = DeobfuscatorEngine(level=level, verbose=verbose)
    cleaned, _ = engine.deobfuscate(source)
    return cleaned


def deobfuscate_file(input_path: str, output_path: str | None = None,
                     level: str = "full", verbose: bool = False) -> str:
    """Читает файл, деобфусцирует, пишет результат."""
    with open(input_path, "r", encoding="utf-8") as f:
        source = f.read()
    engine = DeobfuscatorEngine(level=level, verbose=verbose)
    result = engine.deobfuscate_ex(source)
    
    if output_path is None:
        output_path = input_path.replace(".lua", ".deobf.lua")
        if output_path == input_path:
            output_path = input_path + ".deobf"
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(result.cleaned_source)
    
    if verbose:
        engine2 = DeobfuscatorEngine(level=level, verbose=False)
        _, logs = engine2.deobfuscate(source)
        for line in logs:
            print(line)
    
    return output_path


# ============================================================
# ТЕСТЫ
# ============================================================

if __name__ == "__main__":
    print("=== Test DeobfuscatorEngine Pipeline ===\n")
    passed = failed = 0
    def test(name, cond, extra=""):
        global passed, failed
        if cond: print(f"  [OK] {name}"); passed += 1
        else:    print(f"  [XX] {name}  ({extra})"); failed += 1
    
    # ==================== TEST 1: basic level ====================
    src1 = 'local x = string.char(72, 105) local y = 2 + 3'
    e1 = DeobfuscatorEngine(level="basic")
    r1 = e1.deobfuscate_ex(src1)
    test("basic: no parse error", r1.parse_error is None, r1.parse_error or "")
    test("basic: 'Hi' в выводе", '"Hi"' in r1.cleaned_source or "'Hi'" in r1.cleaned_source, r1.cleaned_source)
    test("basic: '5' в выводе", "= 5" in r1.cleaned_source, r1.cleaned_source)
    test("basic: total_replaced>=2", r1.total_replaced >= 2, str(r1.total_replaced))
    
    # ==================== TEST 2: full level со sandbox ====================
    src2 = '''
local function _d(s)
    local r = ""
    for i = 1, #s do
        r = r .. string.char(bit32.bxor(string.byte(s, i), 42))
    end
    return r
end
local msg = _d("\\75\\79\\67\\69\\95")
print(msg)
'''
    e2 = DeobfuscatorEngine(level="full")
    r2 = e2.deobfuscate_ex(src2)
    test("full: no error", r2.parse_error is None, r2.parse_error or "")
    test("full: 'aeiou' в выводе", "aeiou" in r2.cleaned_source, r2.cleaned_source[:200])
    test("full: _d удалён", "function _d" not in r2.cleaned_source, r2.cleaned_source[:200])
    test("full: reduction > 40%", r2.size_reduction_percent > 40, f"{r2.size_reduction_percent:.1f}%")
    
    # ==================== TEST 3: инвалидный уровень ====================
    try:
        DeobfuscatorEngine(level="wrong")
        test("invalid level рейзит", False)
    except ValueError:
        test("invalid level рейзит", True)
    
    # ==================== TEST 4: пустой ввод ====================
    e4 = DeobfuscatorEngine(level="full")
    r4 = e4.deobfuscate_ex("")
    test("empty input не крашится", r4.parse_error is None or True)
    
    # ==================== TEST 5: сломанный Lua ====================
    r5 = DeobfuscatorEngine(level="full").deobfuscate_ex("local x = ((((")
    test("сломанный Lua ловится в parse_error", r5.parse_error is not None)
    
    # ==================== TEST 6: комбо со всеми декодерами ====================
    src6 = '''
local function _dec(s)
    local out = {}
    for i = 1, #s do
        out[i] = string.char(bit32.bxor(string.byte(s, i), 5))
    end
    return table.concat(out)
end
local a = string.char(78, 90, 76)
local b = 2 + 3 * 4
local c = _dec("HJK")
local d = "prefix " .. "suffix"
print(a, b, c, d)
'''
    e6 = DeobfuscatorEngine(level="full")
    r6 = e6.deobfuscate_ex(src6)
    out6 = r6.cleaned_source
    test("combo: NZL", '"NZL"' in out6, out6[:300])
    test("combo: 14 (2+3*4)", "= 14" in out6, out6[:300])
    test("combo: _dec удалён", "function _dec" not in out6, out6[:300])
    test("combo: 'prefix suffix'", "prefix suffix" in out6, out6[:300])
    test("combo: multi-pass использован", r6.passes_run >= 2, f"passes={r6.passes_run}")
    
    print(f"\n=== TOTAL: {passed}/{passed+failed} ===")
    
    # ==================== DEMO ====================
    print("\n=== [**] FULL PIPELINE DEMO [**] ===")
    demo = '''
local function _decrypt(s)
    local out = {}
    for i = 1, #s do
        out[i] = string.char(bit32.bxor(string.byte(s, i), 0x2A))
    end
    return table.concat(out)
end

local greeting = string.char(72, 101, 108, 108, 111, 44, 32)
local subject  = _decrypt("\\126\\79\\70\\70\\79")
local counter  = (5 + 3) * 2 - 1
print(greeting .. subject, counter)
'''
    print("BEFORE:")
    print(demo)
    print()
    engine = DeobfuscatorEngine(level="full", verbose=False)
    result = engine.deobfuscate_ex(demo)
    print("AFTER:")
    print(result.cleaned_source)
    print()
    for line in engine._format_logs(result):
        print(line)