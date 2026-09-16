"""
NZL Studio Obfuscator — Part 11a: Environment Checks
Проверки окружения выполнения (Roblox / executor / Luau).

При обнаружении неправильной среды скрипт "молча" уходит
в бесконечный цикл (никаких ошибок с трассировкой).
"""

from __future__ import annotations
import random
from typing import Dict, List, Optional, Any

from ..utils.random_gen import NameGenerator, make_rng, shuffle_list


# ══════════════════════════════════════════════════════════════════
#  ТИПЫ ПРОВЕРОК
# ══════════════════════════════════════════════════════════════════

CHECK_TYPES = [
    'roblox_game',       # game существует
    'roblox_workspace',  # workspace существует
    'roblox_script',     # script существует
    'roblox_enum',       # Enum.KeyCode существует
    'roblox_services',   # GetService работает
    'executor_getgenv',  # getgenv функция есть
    'executor_ident',    # identifyexecutor есть
    'luau_continue',     # continue statement работает (только Luau)
    'luau_bit32',        # bit32 библиотека
    'luau_task',         # task библиотека
    'lua_string',        # string библиотека
    'lua_math',          # math библиотека
    'lua_table',         # table библиотека
]


# ══════════════════════════════════════════════════════════════════
#  ГЕНЕРАТОР ПРОВЕРОК
# ══════════════════════════════════════════════════════════════════

class EnvironmentChecker:
    """
    Генерирует Lua-код с проверками окружения.
    
    Все проверки строятся так, чтобы при провале:
      - НЕ бросать error() (трассировка палит обфускацию)
      - НЕ печатать warn() (видно в консоли)
      - Просто уйти в while true do end
    
    Полиморфизм:
      - Разный набор проверок каждый билд
      - Разные имена локальных переменных
      - Разный порядок
      - Обфускация через opaque predicates
    """

    def __init__(
        self,
        seed: Optional[int] = None,
        num_checks: Optional[int] = None,      # сколько проверок (None = случайно 4-8)
        include_checks: Optional[List[str]] = None,   # белый список
        exclude_checks: Optional[List[str]] = None,   # чёрный список
        silent_fail: bool = True,              # тихий фейл (while true do end)
        obfuscate_names: bool = True,
    ):
        if seed is None:
            seed = random.randint(0, 2**32 - 1)
        self.seed = seed
        self.rng = make_rng(seed)
        self.name_gen = NameGenerator(rng=self.rng, style='hex')

        self.silent_fail = silent_fail
        self.obfuscate_names = obfuscate_names

        # Определяем какие проверки использовать
        available = list(CHECK_TYPES)
        if include_checks:
            available = [c for c in available if c in include_checks]
        if exclude_checks:
            available = [c for c in available if c not in exclude_checks]

        if num_checks is None:
            num_checks = self.rng.randint(4, 8)
        num_checks = min(num_checks, len(available))

        self.rng.shuffle(available)
        self.chosen_checks = available[:num_checks]

    # ══════════════════════════════════════════════════════════════
    #  ГЛАВНАЯ ФУНКЦИЯ — СГЕНЕРИРОВАТЬ БЛОК ПРОВЕРОК
    # ══════════════════════════════════════════════════════════════

    def generate(self) -> str:
        """
        Возвращает Lua-код с проверками.
        Обычно вставляется в начало обфусцированного скрипта.
        """
        lines: List[str] = []

        # Иногда — обёртываем всё в pcall (тихий отказ)
        # Иногда — прямые проверки

        use_pcall = self.rng.random() < 0.7

        checks_code: List[str] = []
        for check_name in self.chosen_checks:
            code = self._generate_check(check_name)
            if code:
                checks_code.append(code)

        # Добавим "мусорные" проверки (всегда истинные)
        for _ in range(self.rng.randint(2, 5)):
            checks_code.append(self._generate_junk_check())

        # Перемешаем финальный порядок
        self.rng.shuffle(checks_code)

        if use_pcall:
            lines.append(self._wrap_in_pcall(checks_code))
        else:
            lines.extend(checks_code)

        return '\n'.join(lines)

    # ══════════════════════════════════════════════════════════════
    #  ОДНА ПРОВЕРКА
    # ══════════════════════════════════════════════════════════════

    def _generate_check(self, check_name: str) -> str:
        """Генерирует Lua-код для одной проверки."""
        method = getattr(self, f'_check_{check_name}', None)
        if method is None:
            return ''
        return method()

    # ── Roblox globals ────────────────────────────────────────────

    def _check_roblox_game(self) -> str:
        v = self._local_name()
        return self._make_check(
            f'local {v} = game',
            f'not {v} or type({v}) ~= "userdata"',
        )

    def _check_roblox_workspace(self) -> str:
        v = self._local_name()
        return self._make_check(
            f'local {v} = workspace',
            f'not {v}',
        )

    def _check_roblox_script(self) -> str:
        v = self._local_name()
        # script может быть nil в некоторых executor'ах, поэтому не строгая проверка
        return self._make_check(
            f'local {v} = script or getfenv().script',
            f'not {v} and false',  # Всегда false → не срабатывает (soft check)
        )

    def _check_roblox_enum(self) -> str:
        v = self._local_name()
        return self._make_check(
            f'local {v} = Enum and Enum.KeyCode',
            f'not {v}',
        )

    def _check_roblox_services(self) -> str:
        v = self._local_name()
        return self._make_check(
            f'local {v} = game:GetService("Players")',
            f'not {v}',
        )

    # ── Executor ─────────────────────────────────────────────────

    def _check_executor_getgenv(self) -> str:
        v = self._local_name()
        return self._make_check(
            f'local {v} = getgenv and getgenv()',
            f'not {v}',
        )

    def _check_executor_ident(self) -> str:
        v = self._local_name()
        # Не всегда есть — soft check
        return self._make_check(
            f'local {v} = identifyexecutor or function() return "unknown" end',
            f'type({v}) ~= "function"',
        )

    # ── Luau specifics ───────────────────────────────────────────

    def _check_luau_continue(self) -> str:
        # continue statement — только в Luau
        # Проверяем через попытку выполнить (в safe pcall)
        v = self._local_name()
        return f'''local {v} = pcall(function()
    for _ = 1, 1 do
        if false then continue end
    end
end)
{self._trap_if(f'not {v}')}'''

    def _check_luau_bit32(self) -> str:
        v = self._local_name()
        return self._make_check(
            f'local {v} = bit32 and bit32.bxor',
            f'type({v}) ~= "function"',
        )

    def _check_luau_task(self) -> str:
        v = self._local_name()
        return self._make_check(
            f'local {v} = task and task.wait',
            f'type({v}) ~= "function"',
        )

    # ── Standard Lua ─────────────────────────────────────────────

    def _check_lua_string(self) -> str:
        v = self._local_name()
        return self._make_check(
            f'local {v} = string and string.byte',
            f'type({v}) ~= "function"',
        )

    def _check_lua_math(self) -> str:
        v = self._local_name()
        return self._make_check(
            f'local {v} = math and math.floor',
            f'type({v}) ~= "function"',
        )

    def _check_lua_table(self) -> str:
        v = self._local_name()
        return self._make_check(
            f'local {v} = table and table.insert',
            f'type({v}) ~= "function"',
        )

    # ══════════════════════════════════════════════════════════════
    #  ХЕЛПЕРЫ
    # ══════════════════════════════════════════════════════════════

    def _local_name(self) -> str:
        """Полиморфное имя локальной переменной."""
        if self.obfuscate_names:
            return self.name_gen.generate()
        return '_check_' + str(self.rng.randint(1000, 9999))

    def _make_check(self, setup: str, fail_cond: str) -> str:
        """
        Стандартная проверка:
          <setup>
          if <fail_cond> then <trap> end
        """
        return f'{setup}\n{self._trap_if(fail_cond)}'

    def _trap_if(self, condition: str) -> str:
        """Если condition истинно → уходим в trap."""
        # Разные варианты trap'ов для полиморфизма
        traps = [
            'while true do end',
            'while 1 do end',
            'repeat until false',
            'while (1==1) do end',
        ]
        trap = self.rng.choice(traps)

        # Иногда прячем trap за opaque predicate
        if self.rng.random() < 0.4:
            a = self.rng.randint(1, 100)
            b = self.rng.randint(1, 100)
            fake = f'({a} + {b}) == {a + b}'
            return f'if {condition} then if {fake} then {trap} end end'

        return f'if {condition} then {trap} end'

    def _wrap_in_pcall(self, checks: List[str]) -> str:
        """
        Оборачиваем все проверки в pcall.
        Если внутри что-то упало (например, game nil в non-Roblox) — trap.
        """
        v = self._local_name()
        indent = '    '
        body = '\n'.join(indent + line for line in '\n'.join(checks).split('\n'))
        return f'''local {v} = pcall(function()
{body}
end)
{self._trap_if(f'not {v}')}'''

    def _generate_junk_check(self) -> str:
        """
        Мусорная проверка — всегда проходит, но выглядит как настоящая.
        Добавляется для запутывания reverse-engineer.
        """
        v = self._local_name()
        # Всегда-истинные выражения
        a = self.rng.randint(1, 1000)
        b = self.rng.randint(1, 1000)
        c = self.rng.randint(1, 1000)

        expressions = [
            f'({a} + {b}) == {a + b}',
            f'({a} * 1) == {a}',
            f'math.floor({a}) == {a}',
            f'type("string") == "string"',
            f'type({a}) == "number"',
            f'#"abc" == 3',
            f'"" == ""',
            f'not (not true)',
            f'(true and true) == true',
        ]
        expr = self.rng.choice(expressions)

        # Полезная нагрузка — обычно ничего, иногда nop
        payload_options = [
            f'local {v} = {a}',
            f'local {v} = {expr}',
            '',
        ]
        payload = self.rng.choice(payload_options)

        # if !expression then trap — но expression всегда true → trap не сработает
        return f'{payload}\nif not ({expr}) then while true do end end'

    # ══════════════════════════════════════════════════════════════
    #  СТАТИСТИКА
    # ══════════════════════════════════════════════════════════════

    def stats(self) -> Dict[str, Any]:
        return {
            'seed': self.seed,
            'checks_used': self.chosen_checks,
            'num_checks': len(self.chosen_checks),
        }


# ══════════════════════════════════════════════════════════════════
#  ПУБЛИЧНЫЙ API
# ══════════════════════════════════════════════════════════════════

def generate_environment_checks(
    seed: Optional[int] = None,
    num_checks: Optional[int] = None,
    **kwargs,
) -> str:
    """Быстрая генерация блока проверок."""
    checker = EnvironmentChecker(seed=seed, num_checks=num_checks, **kwargs)
    return checker.generate()


# ══════════════════════════════════════════════════════════════════
#  SELF-TEST
# ══════════════════════════════════════════════════════════════════

def _test():
    passed = 0
    failed = 0

    def ok(l):
        nonlocal passed
        passed += 1
        print(f'  ✅ {l}')

    def fail(l, d=''):
        nonlocal failed
        failed += 1
        print(f'  ❌ {l}' + (f' — {d}' if d else ''))

    def check(l, c, d=''):
        if c:
            ok(l)
        else:
            fail(l, d)

    print('\n' + '═' * 56)
    print('  NZL Environment Checker — Tests')
    print('═' * 56)

    # ── Test 1: базовая генерация ────────────────────────────────
    print('\n[1] Базовая генерация')
    chk = EnvironmentChecker(seed=1)
    code = chk.generate()
    check('код сгенерирован', isinstance(code, str) and len(code) > 50,
          f'len={len(code)}')
    check('содержит while true do end или repeat',
          'while true do end' in code or 'repeat until' in code or
          'while 1 do' in code or 'while (1==1)' in code)

    # ── Test 2: полиморфизм ───────────────────────────────────────
    print('\n[2] Полиморфизм (разные seeds → разный код)')
    c1 = EnvironmentChecker(seed=100).generate()
    c2 = EnvironmentChecker(seed=200).generate()
    c3 = EnvironmentChecker(seed=100).generate()  # тот же seed
    check('разные seeds → разный код', c1 != c2)
    check('одинаковые seeds → одинаковый код', c1 == c3)

    # ── Test 3: выбор конкретных проверок ────────────────────────
    print('\n[3] include_checks')
    chk = EnvironmentChecker(
        seed=5,
        include_checks=['roblox_game', 'executor_getgenv'],
        num_checks=2,
    )
    code = chk.generate()
    check('game упоминается', 'game' in code)
    check('getgenv упоминается', 'getgenv' in code)
    check('выбрано ровно 2 проверки (плюс junk)',
          len(chk.chosen_checks) == 2)

    # ── Test 4: exclude_checks ────────────────────────────────────
    print('\n[4] exclude_checks')
    chk = EnvironmentChecker(
        seed=5,
        exclude_checks=['roblox_game', 'roblox_workspace'],
        num_checks=5,
    )
    check('roblox_game не в списке',
          'roblox_game' not in chk.chosen_checks)
    check('roblox_workspace не в списке',
          'roblox_workspace' not in chk.chosen_checks)

    # ── Test 5: junk checks добавляются ──────────────────────────
    print('\n[5] Junk checks (всегда-истинные)')
    chk = EnvironmentChecker(seed=42, num_checks=1)
    code = chk.generate()
    # Junk checks обычно содержат числовые тавтологии
    has_junk_pattern = any(op in code for op in ['== ', '+ ', '* 1', 'type('])
    check('обнаружены junk patterns', has_junk_pattern)

    # ── Test 6: stats ─────────────────────────────────────────────
    print('\n[6] Stats')
    chk = EnvironmentChecker(seed=777, num_checks=6)
    chk.generate()
    s = chk.stats()
    check('stats содержит seed', s.get('seed') == 777)
    check('stats содержит checks_used', 'checks_used' in s)
    check('num_checks корректный', s.get('num_checks') == 6)

    # ── Test 7: obfuscate_names включает hex-имена ───────────────
    print('\n[7] Обфусцированные имена переменных')
    chk = EnvironmentChecker(seed=1, obfuscate_names=True)
    code = chk.generate()
    # Полиморфные hex-имена начинаются с _0x или содержат hex
    has_hex_name = '_0x' in code or any(
        f'_{c}' in code for c in '0123456789abcdef'
    )
    check('содержит hex-имена', has_hex_name)

    # ── Test 8: silent_fail — только while true, никаких error() ──
    print('\n[8] Silent fail (нет error/warn/print)')
    for seed in range(1, 20):
        chk = EnvironmentChecker(seed=seed, silent_fail=True)
        code = chk.generate()
        assert 'error(' not in code, f'seed={seed}: содержит error()!'
        assert 'warn(' not in code, f'seed={seed}: содержит warn()!'
    check('никаких error() и warn() в 20 разных билдах', True)

    # ── Test 9: pcall wrapping ────────────────────────────────────
    print('\n[9] pcall wrapping')
    # Форсим несколько билдов, проверяем что иногда есть pcall
    has_pcall_count = 0
    for seed in range(50):
        code = EnvironmentChecker(seed=seed).generate()
        if 'pcall' in code:
            has_pcall_count += 1
    check(f'pcall используется в {has_pcall_count}/50 билдах',
          has_pcall_count > 20)

    # ── Test 10: количество проверок ─────────────────────────────
    print('\n[10] num_checks = None → случайное 4-8')
    for seed in range(1, 30):
        chk = EnvironmentChecker(seed=seed, num_checks=None)
        n = len(chk.chosen_checks)
        assert 4 <= n <= 8, f'seed={seed}: got {n} checks'
    check('количество в диапазоне 4-8', True)

    # ── Test 11: все проверки работают без ошибок ────────────────
    print('\n[11] Все типы проверок генерируются без ошибок')
    for check_name in CHECK_TYPES:
        try:
            chk = EnvironmentChecker(
                seed=1,
                include_checks=[check_name],
                num_checks=1,
            )
            code = chk.generate()
            assert isinstance(code, str) and len(code) > 5
        except Exception as e:
            fail(f'проверка {check_name} упала', str(e))
            break
    else:
        ok(f'все {len(CHECK_TYPES)} типов проверок работают')

    # ── Test 12: publik API ──────────────────────────────────────
    print('\n[12] Публичный API generate_environment_checks')
    code = generate_environment_checks(seed=1)
    check('public API возвращает строку', isinstance(code, str))
    check('код не пустой', len(code) > 100)

    # ── Test 13: разнообразие trap'ов ────────────────────────────
    print('\n[13] Trap варианты (полиморфизм)')
    trap_variants: set = set()
    for seed in range(200):
        code = EnvironmentChecker(seed=seed, num_checks=2).generate()
        if 'while true do end' in code:
            trap_variants.add('while true')
        if 'while 1 do end' in code:
            trap_variants.add('while 1')
        if 'repeat until false' in code:
            trap_variants.add('repeat until')
        if 'while (1==1)' in code:
            trap_variants.add('while 1==1')
    check(f'найдено {len(trap_variants)} вариантов trap',
          len(trap_variants) >= 3, f'variants={trap_variants}')

    # ── итог ─────────────────────────────────────────────────────
    total = passed + failed
    print('\n' + '═' * 56)
    print(f'  Результат: {passed}/{total} тестов прошло', end='')
    if failed == 0:
        print(' 🎉')
    else:
        print(f' ({failed} провалено) ❌')
    print('═' * 56)

    # ── демонстрация ─────────────────────────────────────────────
    print('\n📄 Пример сгенерированных проверок (seed=42):')
    demo = EnvironmentChecker(seed=42, num_checks=5)
    demo_code = demo.generate()
    for line in demo_code.split('\n'):
        print('  ' + line)
    print(f'\n📊 Использованные проверки: {demo.chosen_checks}')
    print()

    return failed == 0


if __name__ == '__main__':
    import sys
    success = _test()
    sys.exit(0 if success else 1)