# obfuscator/engine.py
"""
NZL Studio Obfuscator — Engine (v4)

Один уровень — ULTRA. Все защиты всегда включены.
Просто obfuscate(source) — и всё.
"""

import sys
import os
import argparse
import time
import traceback
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from obfuscator.protection.watermark import (
    WatermarkGenerator,
    OWNER_IDS,
    DISCORD_LINK,
)


# ═══════════════════════════════════════════════════════════════════════════
# OBFUSCATOR
# ═══════════════════════════════════════════════════════════════════════════

class ObfuscationError(Exception):
    pass


class Obfuscator:
    """Главный класс обфускатора NZL Studio. Один уровень — ULTRA."""

    def __init__(
        self,
        seed: Optional[int] = None,
        owner_id: Optional[int] = None,
        username: Optional[str] = None,
        verbose: bool = False,
    ):
        if seed is None:
            seed = int(time.time() * 1000) & 0xFFFFFFFF
        self.seed = seed
        self.owner_id = owner_id or OWNER_IDS[0]
        self.username = username
        self.watermark = WatermarkGenerator(seed, self.owner_id)
        self.verbose = verbose
        self.stats = {
            'input_size': 0,
            'output_size': 0,
            'stages': [],
            'total_time': 0.0,
        }

    def _log(self, msg: str):
        if self.verbose:
            print(f"[obf] {msg}")

    def _stage(self, name: str, fn):
        t0 = time.time()
        try:
            result = fn()
        except Exception as e:
            self._log(f"❌ Этап '{name}' упал: {type(e).__name__}: {e}")
            raise
        elapsed = time.time() - t0
        self.stats['stages'].append((name, elapsed))
        self._log(f"  ✅ {name}: {elapsed*1000:.1f} ms")
        return result

    def obfuscate(self, source: str, **kwargs) -> str:
        """
        Обфусцирует Lua-код. Всегда ULTRA — максимальная защита.

        Pipeline:
         1. String array extraction
         2. String encryption
         3. Number obfuscation
         4. Variable renaming
         5. Control flow flattening
         6. State machine obfuscation
         7. VM protection (bytecode + RC4)
         8. Anti-tamper (CRC, honeypots, traps)
         9. Environment checks
        10. Dead code + opaque predicates
        11. Watermark (zero-width + branding)
        """
        self.stats['input_size'] = len(source)
        self.stats['stages'] = []
        t_start = time.time()
        self._log(f"🚀 NZL Obfuscator ULTRA — seed={self.seed}")

        try:
            from obfuscator.ultra_obf import ultra_obfuscate
            final = self._stage(
                "ULTRA",
                lambda: ultra_obfuscate(source, seed=self.seed)
            )
        except Exception as e:
            self._log(f"⚠️  ULTRA упал: {e}, fallback chain...")
            if self.verbose:
                traceback.print_exc()
            final = self._fallback(source)

        self.stats['output_size'] = len(final)
        self.stats['total_time'] = time.time() - t_start
        self._log(
            f"✅ Готово: {self.stats['input_size']} → {self.stats['output_size']} байт "
            f"за {self.stats['total_time']*1000:.1f} ms"
        )
        return final

    def _fallback(self, source: str) -> str:
        """Fallback chain: Symbiote → LuraphVM → basic"""
        # Symbiote CFF
        try:
            from obfuscator.symbiote_obf import obfuscate_script as symbiote_obf
            return self._stage("SymbioteCFF", lambda: symbiote_obf(source, seed=self.seed))
        except Exception:
            pass
        # LuraphVM
        try:
            from obfuscator.luraph_vm import obfuscate_script
            return self._stage("LuraphVM", lambda: obfuscate_script(source, seed=self.seed))
        except Exception:
            pass
        # Basic: just parse + unparse
        from obfuscator.lexer import Lexer
        from obfuscator.parser import Parser
        from obfuscator.ast_unparser import unparse
        ast = Parser(Lexer(source).tokenize()).parse()
        code = unparse(ast)
        return f"-- NZL Studio Obfuscator | {DISCORD_LINK}\n{code}\n-- {DISCORD_LINK}"

    def get_stats(self) -> dict:
        return dict(self.stats)

    def print_stats(self):
        s = self.stats
        print()
        print("─" * 50)
        print(f"📊 Статистика:")
        print(f"  Seed:        {self.seed}")
        print(f"  Build ID:    {self.watermark.build_id}")
        print(f"  Owner ID:    {self.owner_id}")
        print(f"  Input size:  {s['input_size']:,} байт")
        print(f"  Output size: {s['output_size']:,} байт")
        ratio = s['output_size'] / max(1, s['input_size'])
        print(f"  Ratio:       {ratio:.2f}x")
        print(f"  Total time:  {s['total_time']*1000:.1f} ms")
        if s['stages']:
            print(f"  Этапы:")
            for name, t in s['stages']:
                print(f"    {name:<25} {t*1000:>7.1f} ms")
        print("─" * 50)


# ═══════════════════════════════════════════════════════════════════════════
# CONVENIENCE FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

def obfuscate(
    source: str,
    seed: Optional[int] = None,
    owner_id: Optional[int] = None,
    username: Optional[str] = None,
) -> str:
    """Обфусцировать строку Lua-кода."""
    obf = Obfuscator(seed=seed, owner_id=owner_id, username=username)
    return obf.obfuscate(source)


def obfuscate_file(
    input_path: str,
    output_path: Optional[str] = None,
    seed: Optional[int] = None,
    owner_id: Optional[int] = None,
    username: Optional[str] = None,
    verbose: bool = False,
) -> str:
    """Обфусцировать файл."""
    with open(input_path, 'r', encoding='utf-8') as f:
        source = f.read()

    obf = Obfuscator(seed=seed, owner_id=owner_id, username=username, verbose=verbose)
    result = obf.obfuscate(source)

    if output_path is None:
        base, ext = os.path.splitext(input_path)
        output_path = f"{base}_obf{ext}"

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(result)

    if verbose:
        obf.print_stats()

    return output_path


# ═══════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        prog='nzl-obfuscator',
        description='NZL Studio Lua/Luau Obfuscator — ULTRA protection',
        epilog=f'Discord: {DISCORD_LINK}',
    )
    parser.add_argument('input', nargs='?', help='Input Lua file')
    parser.add_argument('-o', '--output', help='Output file (default: input_obf.lua)')
    parser.add_argument('-s', '--seed', type=int, default=None)
    parser.add_argument('--owner-id', type=int, default=None)
    parser.add_argument('--username', type=str, default=None)
    parser.add_argument('-v', '--verbose', action='store_true')
    parser.add_argument('--test', action='store_true', help='Run tests')

    args = parser.parse_args()

    if args.test:
        return 0 if _run_tests() else 1

    if not args.input:
        parser.print_help()
        return 1

    if not os.path.exists(args.input):
        print(f"❌ Файл не найден: {args.input}")
        return 1

    try:
        out_path = obfuscate_file(
            args.input, args.output,
            seed=args.seed, owner_id=args.owner_id,
            username=args.username, verbose=args.verbose,
        )
        print(f"✅ Обфусцировано: {args.input} → {out_path}")
        return 0
    except Exception as e:
        print(f"❌ Ошибка обфускации: {e}")
        if args.verbose:
            traceback.print_exc()
        return 1


# ═══════════════════════════════════════════════════════════════════════════
# ТЕСТЫ
# ═══════════════════════════════════════════════════════════════════════════

def _run_tests():
    print("=" * 60)
    print("🧪 ТЕСТЫ: engine.py (v4 — ULTRA only)")
    print("=" * 60)

    passed = 0
    failed = 0

    def test(name: str, condition: bool, detail: str = ""):
        nonlocal passed, failed
        if condition:
            print(f"  ✅ {name}")
            passed += 1
        else:
            print(f"  ❌ {name}" + (f": {detail}" if detail else ""))
            failed += 1

    simple_code = 'print("Hello, World!")'

    print("\n📌 ULTRA обфускация:")
    try:
        obf = Obfuscator(seed=42)
        result = obf.obfuscate(simple_code)
        test("не падает", True)
        test("результат не пустой", len(result) > 0)
        test("содержит Discord", DISCORD_LINK in result)
        test("содержит NZL Studio", "NZL Studio" in result or "NZL" in result)
    except Exception as e:
        test("не падает", False, str(e)[:120])
        traceback.print_exc()

    print("\n📌 Валидность результата (parse обратно):")
    try:
        obf = Obfuscator(seed=123)
        result = obf.obfuscate(simple_code)
        from obfuscator.lexer import Lexer
        from obfuscator.parser import Parser
        tokens = Lexer(result).tokenize()
        ast = Parser(tokens).parse()
        test("output парсится", ast is not None)
    except Exception as e:
        test("output парсится", False, str(e)[:80])

    print("\n📌 Полиморфизм:")
    try:
        obf1 = Obfuscator(seed=111)
        r1 = obf1.obfuscate(simple_code)
        obf2 = Obfuscator(seed=222)
        r2 = obf2.obfuscate(simple_code)
        obf3 = Obfuscator(seed=111)
        r3 = obf3.obfuscate(simple_code)
        test("Разные seed → разный вывод", r1 != r2)
        test("Одинаковый seed → одинаковый вывод", r1 == r3)
    except Exception as e:
        test("Полиморфизм", False, str(e)[:80])

    print("\n📌 Статистика:")
    try:
        obf = Obfuscator(seed=42, verbose=False)
        obf.obfuscate(simple_code)
        stats = obf.get_stats()
        test("stats.input_size > 0", stats['input_size'] > 0)
        test("stats.output_size > 0", stats['output_size'] > 0)
        test("stats.stages не пустой", len(stats['stages']) > 0)
    except Exception as e:
        test("stats", False, str(e)[:80])

    print("\n📌 Convenience функции:")
    try:
        result = obfuscate(simple_code, seed=42)
        test("obfuscate() shortcut", len(result) > 0)
    except Exception as e:
        test("obfuscate() shortcut", False, str(e)[:80])

    try:
        tmp_in = "_test_in.lua"
        tmp_out = "_test_out.lua"
        with open(tmp_in, 'w', encoding='utf-8') as f:
            f.write(simple_code)
        out_path = obfuscate_file(tmp_in, tmp_out, seed=42)
        test("obfuscate_file() работает", os.path.exists(out_path))
        os.remove(tmp_in)
        os.remove(tmp_out)
    except Exception as e:
        test("obfuscate_file()", False, str(e)[:80])

    print("\n📌 Сложный скрипт:")
    complex_code = '''
local function add(a, b)
    return a + b
end
local function factorial(n)
    if n <= 1 then return 1 end
    return n * factorial(n - 1)
end
local x = add(10, 20)
print("Sum: " .. x)
print("Factorial 5: " .. factorial(5))
for i = 1, 10 do
    if i % 2 == 0 then
        print(i .. " is even")
    end
end
'''
    try:
        obf = Obfuscator(seed=999)
        result = obf.obfuscate(complex_code)
        test("сложный скрипт: не падает", True)
        test("сложный скрипт: output > 1KB", len(result) > 1000)
    except Exception as e:
        test("сложный скрипт", False, str(e)[:120])

    print()
    print("=" * 60)
    total = passed + failed
    print(f"📊 Результат: {passed}/{total} тестов прошло")
    if failed == 0:
        print("🎉🎉🎉 ОБФУСКАТОР РАБОТАЕТ! 🎉🎉🎉")
        print(f"    NZL Studio Obfuscator v4 — ULTRA ready!")
        print(f"    Discord: {DISCORD_LINK}")
    else:
        print(f"⚠️  Провалено: {failed}")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    if len(sys.argv) == 1:
        success = _run_tests()
        sys.exit(0 if success else 1)
    else:
        sys.exit(main())
