# obfuscator/engine.py
"""
NZL Studio Obfuscator — Engine (v3)
Часть 13: главный оркестратор всех модулей

⚡ v3 фиксы:
- Добавлен level='insane' с VM pipeline
- vm_protection инжектится в _extra_prelude
- Правильный порядок stages: Variables ДО ControlFlow ДО VM
"""

import sys
import os
import argparse
import time
import traceback
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from obfuscator.lexer import Lexer
from obfuscator.parser import Parser
from obfuscator.ast_unparser import unparse

from obfuscator.utils.random_gen import make_rng, NameGenerator

from obfuscator.transformers.string_encryptor import encrypt_strings_in_chunk
from obfuscator.transformers.number_obfuscator import (
    obfuscate_numbers_in_chunk,
    NumberObfuscatorConfig,
)
from obfuscator.transformers.variable_renamer import VariableRenamer
from obfuscator.transformers.control_flow import ControlFlowFlattener

from obfuscator.protection.environment import generate_environment_checks
from obfuscator.protection.anti_tamper import generate_anti_tamper
from obfuscator.protection.watermark import (
    WatermarkGenerator,
    OWNER_IDS,
    DISCORD_LINK,
)

# VM Protection (опционально — не ломаем если нет файла)
try:
    from obfuscator.transformers.vm_protection import VMProtectionTransformer
    _VM_PROTECTION_AVAILABLE = True
except ImportError:
    _VM_PROTECTION_AVAILABLE = False


# ═══════════════════════════════════════════════════════════════════════════
# КОНСТАНТЫ
# ═══════════════════════════════════════════════════════════════════════════

LEVELS = ('medium', 'hard', 'insane')

DEFAULT_MEDIUM_CONFIG = {
    'string_array': True,
    'state_machine': True,
    'name_style': 'luraph',
    'strings': True,
    'numbers': True,
    'variables': True,
    'control_flow': False,
    'vm_protection': False,
    'anti_tamper': False,
    'environment_checks': True,
    'watermark': True,
    'minified': False,
}

DEFAULT_HARD_CONFIG = {
    'string_array': True,
    'state_machine': True,
    'name_style': 'luraph',
    'strings': True,
    'numbers': True,
    'variables': True,
    'control_flow': True,
    'vm_protection': False,
    'anti_tamper': True,
    'environment_checks': True,
    'watermark': True,
    'minified': True,
}

# 🔥 INSANE: полный pipeline с VM
DEFAULT_INSANE_CONFIG = {
    'string_array': True,
    'state_machine': True,
    'name_style': 'luraph',
    'strings': True,
    'numbers': True,
    'variables': True,
    'control_flow': True,
    'vm_protection': True,   # ← VM защита функций с маркером @vm
    'anti_tamper': True,
    'environment_checks': True,
    'watermark': True,
    'minified': True,
}


# ═══════════════════════════════════════════════════════════════════════════
# OBFUSCATOR
# ═══════════════════════════════════════════════════════════════════════════

class ObfuscationError(Exception):
    pass


class Obfuscator:
    """Главный класс обфускатора NZL Studio."""

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
        self.rng = make_rng(seed)

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

        self._extra_prelude = []

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

    def obfuscate(
        self,
        source: str,
        level: str = 'medium',
        config_override: Optional[dict] = None,
    ) -> str:
        """Обфусцирует Lua-код."""
        if level not in LEVELS:
            raise ObfuscationError(
                f"Неизвестный уровень: {level}. Доступно: {LEVELS}"
            )

        if level == 'insane':
            base_config = DEFAULT_INSANE_CONFIG
        elif level == 'hard':
            base_config = DEFAULT_HARD_CONFIG
        else:
            base_config = DEFAULT_MEDIUM_CONFIG

        config = dict(base_config)
        if config_override:
            config.update(config_override)

        # VM protection требует наличия модуля
        if config.get('vm_protection') and not _VM_PROTECTION_AVAILABLE:
            self._log("⚠️  vm_protection недоступен — пропускаем")
            config['vm_protection'] = False

        self._extra_prelude = []

        self.stats['input_size'] = len(source)
        self.stats['stages'] = []
        t_start = time.time()
        self._log(f"🚀 NZL Obfuscator — level={level}, seed={self.seed}")

        # ── STAGE 1: LEX ──
                # ⚡ VM Preprocessing — ищем -- @vm маркеры в исходнике
        if config.get('vm_protection'):
            try:
                from obfuscator.transformers.vm_protection import preprocess_source
                source = self._stage(
                    "VMPreprocess",
                    lambda: preprocess_source(source)
                )
            except Exception as e:
                self._log(f"⚠️  VMPreprocess пропущен: {e}")

        # ── STAGE 1: LEX ──
        tokens = self._stage("Lex", lambda: Lexer(source).tokenize())

        # ── STAGE 2: PARSE ──
        ast = self._stage("Parse", lambda: Parser(tokens).parse())

        # ── STAGE 3: TRANSFORMERS ──
        # ⚡ ПОРЯДОК:
        # 1. VM Protection  — ДО всего (ищем маркеры в исходном коде)
        # 2. Strings        — шифруем строки
        # 3. Numbers        — обфусцируем числа
        # 4. Variables      — переименовываем ДО control_flow (scope цел)
        # 5. ControlFlow    — flatten уже с новыми именами

        # ⚡ VM Protection — ПЕРВЫМ (до rename, чтобы маркеры не потерялись)
        if config.get('vm_protection'):
            try:
                ast = self._stage(
                    "VMProtection",
                    lambda: self._apply_vm_protection(ast)
                )
            except Exception as e:
                self._log(f"⚠️  VMProtection пропущен: {e}")
                if self.verbose:
                    traceback.print_exc()

        if config.get('string_array'):
            try:
                ast = self._stage(
                    "StringArray",
                    lambda: self._apply_string_array(ast)
                )
            except Exception as e:
                self._log(f"⚠️  StringArray пропущен: {e}")

        if config['strings']:
            try:
                ast = self._stage(
                    "StringEncryptor",
                    lambda: self._apply_strings(ast)
                )
            except Exception as e:
                self._log(f"⚠️  StringEncryptor пропущен: {e}")

        if config.get('state_machine'):
            try:
                ast = self._stage(
                    "StateMachine",
                    lambda: self._apply_state_machine(ast)
                )
            except Exception as e:
                self._log(f"⚠️  StateMachine пропущен: {e}")

        if config['numbers']:
            try:
                ast = self._stage(
                    "NumberObfuscator",
                    lambda: self._apply_numbers(ast, level)
                )
            except Exception as e:
                self._log(f"⚠️  NumberObfuscator пропущен: {e}")

        # ⚡ Variables ДО ControlFlow!
        self._name_style = config.get('name_style', 'confusing')
        if config['variables']:
            try:
                ast = self._stage(
                    "VariableRenamer",
                    lambda: self._apply_vars(ast)
                )
            except Exception as e:
                self._log(f"⚠️  VariableRenamer пропущен: {e}")

        if config['control_flow']:
            try:
                ast = self._stage(
                    "ControlFlowFlattener",
                    lambda: self._apply_control_flow(ast)
                )
            except Exception as e:
                self._log(f"⚠️  ControlFlow пропущен: {e}")

        # ── STAGE 4: UNPARSE ──
        lua_code = self._stage(
            "Unparse",
            lambda: unparse(ast, minified=config['minified'])
        )

        # ── STAGE 5: PROTECTION LAYER ──
        protection_prefix = self._stage(
            "Protection",
            lambda: self._build_protection_layer(config)
        )

        # ── STAGE 6: ASSEMBLE ──
        assembled = self._stage(
            "Assemble",
            lambda: self._assemble(protection_prefix, lua_code, config)
        )

        # ── STAGE 7: WATERMARK ──
        if config['watermark']:
            final = self._stage(
                "Watermark",
                lambda: self.watermark.apply_watermarks(
                    assembled, username=self.username, num_inline=3
                )
            )
        else:
            final = assembled

        self.stats['output_size'] = len(final)
        self.stats['total_time'] = time.time() - t_start
        self._log(
            f"✅ Готово: {self.stats['input_size']} → {self.stats['output_size']} байт "
            f"за {self.stats['total_time']*1000:.1f} ms"
        )

        return final

    # ═══════════════════════════════════════════════════════════════
    # TRANSFORMER APPLIERS
    # ═══════════════════════════════════════════════════════════════

    def _apply_vm_protection(self, ast):
        """Применяет VM защиту — ищет @vm маркеры и компилирует функции."""
        transformer = VMProtectionTransformer(seed=self.seed ^ 0xF00DBEEF)
        prelude_code, new_ast = transformer.transform(ast)

        vm_stats = transformer.stats
        self._log(
            f"    VM: protected={vm_stats['functions_protected']}, "
            f"failed={vm_stats['functions_failed']}, "
            f"skipped={vm_stats['functions_skipped']}"
        )

        if prelude_code:
            self._extra_prelude.append(("vm_protection", prelude_code))

        return new_ast

    def _apply_strings(self, ast):
        rng = make_rng(self.seed ^ 0xDEADBEEF)
        name_gen = NameGenerator(rng, style='confusing')

        result = encrypt_strings_in_chunk(
            ast,
            rng=rng,
            name_gen=name_gen,
            enable_chunking=True,
        )

        new_ast = result[0]
        decryptor_code = result[1] if len(result) > 1 else None

        if decryptor_code:
            self._extra_prelude.append(("string_decryptor", decryptor_code))

        return new_ast

    def _apply_string_array(self, ast):
        from obfuscator.transformers.string_array import (
            StringArrayConfig, obfuscate_string_array,
        )
        rng = make_rng(self.seed ^ 0x5A17A7)
        result = obfuscate_string_array(ast, rng=rng, config=StringArrayConfig.balanced())
        new_ast = result[0] if isinstance(result, tuple) else result
        return new_ast

    def _apply_state_machine(self, ast):
        from obfuscator.transformers.state_machine import (
            StateMachineConfig, obfuscate_state_machine,
        )
        rng = make_rng(self.seed ^ 0x57A7E)
        result = obfuscate_state_machine(ast, rng=rng, config=StateMachineConfig.balanced())
        new_ast = result[0] if isinstance(result, tuple) else result
        return new_ast

    def _apply_numbers(self, ast, level: str = 'medium'):
        # РАНЬШЕ: config не передавался вовсе -> всегда дефолт 0.35,
        # пресеты balanced()/aggressive() не использовались НИКОГДА.
        if level == 'insane':
            cfg = NumberObfuscatorConfig.aggressive()
        else:
            cfg = NumberObfuscatorConfig.balanced()
        rng = make_rng(self.seed ^ 0xCAFEBABE)
        result = obfuscate_numbers_in_chunk(ast, rng=rng, config=cfg)
        new_ast = result[0] if isinstance(result, tuple) else result
        return new_ast

    def _apply_control_flow(self, ast):
        try:
            transformer = ControlFlowFlattener(seed=self.seed)
        except TypeError:
            try:
                rng = make_rng(self.seed ^ 0xBADF00D)
                transformer = ControlFlowFlattener(rng=rng)
            except TypeError:
                transformer = ControlFlowFlattener()

        result = transformer.transform(ast)
        return result if result is not None else ast

    def _apply_vars(self, ast):
        style = getattr(self, '_name_style', 'confusing')
        try:
            transformer = VariableRenamer(seed=self.seed, style=style)
        except TypeError:
            try:
                rng = make_rng(self.seed ^ 0xFEEDFACE)
                transformer = VariableRenamer(rng=rng, style=style)
            except TypeError:
                try:
                    transformer = VariableRenamer(seed=self.seed)
                except TypeError:
                    transformer = VariableRenamer()

        result = transformer.transform(ast)
        return result if result is not None else ast

    # ═══════════════════════════════════════════════════════════════
    # PROTECTION LAYER
    # ═══════════════════════════════════════════════════════════════

    def _build_protection_layer(self, config: dict) -> str:
        parts = []

        if config['environment_checks']:
            try:
                env_code = generate_environment_checks(self.seed)
                if env_code:
                    parts.append("-- [env]")
                    parts.append(env_code)
            except Exception as e:
                self._log(f"⚠️  environment_checks: {e}")

        if config['anti_tamper']:
            try:
                tamper_code = generate_anti_tamper(self.seed)
                if tamper_code:
                    parts.append("-- [at]")
                    parts.append(tamper_code)
            except Exception as e:
                self._log(f"⚠️  anti_tamper: {e}")

        return "\n".join(parts)

    def _assemble(self, protection: str, code: str, config: dict) -> str:
        parts = []

        if protection:
            parts.append(protection)

        for name, prelude_code in self._extra_prelude:
            parts.append(f"-- [{name}]")
            parts.append(prelude_code)

        parts.append(code)
        parts.append(f"-- {DISCORD_LINK}")

        sep = "\n"
        return sep.join(p for p in parts if p)

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
    level: str = 'medium',
    seed: Optional[int] = None,
    owner_id: Optional[int] = None,
    username: Optional[str] = None,
) -> str:
    obf = Obfuscator(seed=seed, owner_id=owner_id, username=username)
    return obf.obfuscate(source, level=level)


def obfuscate_file(
    input_path: str,
    output_path: Optional[str] = None,
    level: str = 'medium',
    seed: Optional[int] = None,
    owner_id: Optional[int] = None,
    username: Optional[str] = None,
    verbose: bool = False,
) -> str:
    with open(input_path, 'r', encoding='utf-8') as f:
        source = f.read()

    obf = Obfuscator(seed=seed, owner_id=owner_id, username=username, verbose=verbose)
    result = obf.obfuscate(source, level=level)

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
        description='NZL Studio Lua/Luau Obfuscator',
        epilog=f'Discord: {DISCORD_LINK}',
    )
    parser.add_argument('input', nargs='?', help='Input Lua file')
    parser.add_argument('-o', '--output', help='Output file (default: input_obf.lua)')
    parser.add_argument('-l', '--level', choices=LEVELS, default='medium')
    parser.add_argument('-s', '--seed', type=int, default=None)
    parser.add_argument('--owner-id', type=int, default=None)
    parser.add_argument('--username', type=str, default=None)
    parser.add_argument('--minified', action='store_true')
    parser.add_argument('--pretty', action='store_true')
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

    override = None
    if args.minified:
        override = {'minified': True}
    elif args.pretty:
        override = {'minified': False}

    try:
        with open(args.input, 'r', encoding='utf-8') as f:
            source = f.read()

        obf = Obfuscator(
            seed=args.seed,
            owner_id=args.owner_id,
            username=args.username,
            verbose=args.verbose,
        )
        result = obf.obfuscate(source, level=args.level, config_override=override)

        output_path = args.output
        if output_path is None:
            base, ext = os.path.splitext(args.input)
            output_path = f"{base}_obf{ext}"

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(result)

        print(f"✅ Обфусцировано: {args.input} → {output_path}")
        if args.verbose:
            obf.print_stats()

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
    print("🧪 ТЕСТЫ: engine.py (v3)")
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

    print("\n📌 Базовая обфускация:")

    simple_code = 'print("Hello, World!")'

    for lvl in ('medium', 'hard', 'insane'):
        try:
            obf = Obfuscator(seed=42)
            result = obf.obfuscate(simple_code, level=lvl)
            test(f"{lvl}: не падает", True)
            test(f"{lvl}: результат не пустой", len(result) > 0)
            test(f"{lvl}: содержит Discord", DISCORD_LINK in result)
        except Exception as e:
            test(f"{lvl}: не падает", False, str(e)[:120])
            traceback.print_exc()

    print("\n📌 Валидность результата (parse обратно):")

    for lvl in ('medium', 'hard', 'insane'):
        try:
            obf = Obfuscator(seed=123)
            result = obf.obfuscate(simple_code, level=lvl)
            tokens = Lexer(result).tokenize()
            ast = Parser(tokens).parse()
            test(f"{lvl} output парсится", ast is not None)
        except Exception as e:
            test(f"{lvl} output парсится", False, str(e)[:80])

    print("\n📌 INSANE уровень:")

    test("insane в LEVELS", 'insane' in LEVELS)
    test("vm_protection в insane config", DEFAULT_INSANE_CONFIG.get('vm_protection') is True)
    test("control_flow в insane config", DEFAULT_INSANE_CONFIG.get('control_flow') is True)
    test("vm_protection доступен", _VM_PROTECTION_AVAILABLE,
         "vm_protection.py не найден" if not _VM_PROTECTION_AVAILABLE else "")

    print("\n📌 VM Protection с маркером @vm:")

    vm_code = '''local function add(a, b) -- @vm
    return a + b
end
local result = add(2, 3)
'''
    if _VM_PROTECTION_AVAILABLE:
        try:
            obf = Obfuscator(seed=42, verbose=False)
            result = obf.obfuscate(vm_code, level='insane')
            test("insane + @vm: не падает", True)
            test("insane + @vm: результат не пустой", len(result) > 0)
            # Проверяем что vm_protection этап был
            stage_names = [s[0] for s in obf.stats['stages']]
            test("VMProtection этап выполнился", 'VMProtection' in stage_names,
                 f"stages={stage_names}")
        except Exception as e:
            test("insane + @vm: не падает", False, str(e)[:120])
            traceback.print_exc()
    else:
        test("vm_protection: модуль недоступен", False,
             "создай vm_protection.py")

    print("\n📌 Полиморфизм:")

    try:
        obf1 = Obfuscator(seed=111)
        r1 = obf1.obfuscate(simple_code, level='medium')
        obf2 = Obfuscator(seed=222)
        r2 = obf2.obfuscate(simple_code, level='medium')
        obf3 = Obfuscator(seed=111)
        r3 = obf3.obfuscate(simple_code, level='medium')
        test("Разные seed → разный вывод", r1 != r2)
        test("Одинаковый seed → одинаковый вывод", r1 == r3)
    except Exception as e:
        test("Полиморфизм", False, str(e)[:80])

    print("\n📌 Статистика:")

    try:
        obf = Obfuscator(seed=42, verbose=False)
        obf.obfuscate(simple_code, level='medium')
        stats = obf.get_stats()
        test("stats.input_size > 0", stats['input_size'] > 0)
        test("stats.output_size > 0", stats['output_size'] > 0)
        test("stats.stages не пустой", len(stats['stages']) > 0)
    except Exception as e:
        test("stats", False, str(e)[:80])

    print("\n📌 Convenience функции:")

    try:
        result = obfuscate(simple_code, level='medium', seed=42)
        test("obfuscate() shortcut", len(result) > 0)
    except Exception as e:
        test("obfuscate() shortcut", False, str(e)[:80])

    try:
        tmp_in = "_test_in.lua"
        tmp_out = "_test_out.lua"
        with open(tmp_in, 'w', encoding='utf-8') as f:
            f.write(simple_code)
        out_path = obfuscate_file(tmp_in, tmp_out, level='medium', seed=42)
        test("obfuscate_file() работает", os.path.exists(out_path))
        os.remove(tmp_in)
        os.remove(tmp_out)
    except Exception as e:
        test("obfuscate_file()", False, str(e)[:80])

    print()
    print("=" * 60)
    total = passed + failed
    print(f"📊 Результат: {passed}/{total} тестов прошло")
    if failed == 0:
        print("🎉🎉🎉 ОБФУСКАТОР РАБОТАЕТ! 🎉🎉🎉")
        print(f"    NZL Studio Obfuscator v1.0 — level insane готов!")
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