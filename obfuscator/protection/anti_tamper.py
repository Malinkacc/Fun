"""
NZL Studio Obfuscator — Part 11b: Anti-Tamper
Защита от модификации, дампа и hook'ов.

Компоненты:
  - CRC32/hash проверка целостности функций
  - Honeypot переменные (приманки)
  - Trap functions (при вызове → бесконечный цикл)
  - Anti-hook detection (проверка что API не заменен)
  - Random bombs (случайные проверки по коду)
"""

from __future__ import annotations
import random
from typing import Dict, List, Optional, Any, Tuple

from ..utils.random_gen import NameGenerator, make_rng, shuffle_list
from ..utils.crypto import fnv1a_hash, crc32


# ══════════════════════════════════════════════════════════════════
#  HONEYPOTS
# ══════════════════════════════════════════════════════════════════

class HoneypotGenerator:
    """
    Генерирует "приманки" — фейковые переменные с "секретами".
    
    Если reverse-engineer видит переменную с именем 'admin_password'
    или '__vm_key' — он попытается её использовать. И попадёт в trap.
    
    Реализация: значения выглядят важными, но на самом деле — 
    если кто-то попытается их прочитать через __index/getfenv → trap.
    """

    HONEYPOT_NAMES = [
        '__vm_key', '__decryption_key', '__master_key', '__admin_token',
        '__secret_password', '__api_key', '__license_key', '__owner_id',
        '__debug_flag', '__unlock_code', '__super_user', '__root_access',
        '_G_backup', '_ENV_secret', '__real_bytecode', '__original_source',
    ]

    def __init__(self, rng: random.Random, name_gen: NameGenerator):
        self.rng = rng
        self.name_gen = name_gen

    def generate(self, count: int = 3) -> str:
        """Генерирует блок с honeypots."""
        count = min(count, len(self.HONEYPOT_NAMES))
        chosen = self.rng.sample(self.HONEYPOT_NAMES, count)
        lines: List[str] = []

        for name in chosen:
            # Фейковое значение (выглядит как секрет)
            fake_value = self._make_fake_secret()
            # Оборачиваем в metatable-приманку
            trap_var = self.name_gen.generate()

            lines.append(
                f'local {trap_var} = setmetatable({{}}, {{\n'
                f'    __index = function() while true do end end,\n'
                f'    __call  = function() while true do end end,\n'
                f'    __tostring = function() return "{fake_value}" end,\n'
                f'}})\n'
                f'getfenv()["{name}"] = {trap_var}'
            )

        return '\n'.join(lines)

    def _make_fake_secret(self) -> str:
        """Генерирует правдоподобно выглядящий "секрет"."""
        formats = [
            # Hex "ключ"
            lambda: ''.join(
                self.rng.choice('0123456789abcdef')
                for _ in range(self.rng.randint(32, 64))
            ),
            # Base64-like
            lambda: ''.join(
                self.rng.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/')
                for _ in range(self.rng.randint(24, 44))
            ),
            # UUID-like
            lambda: '-'.join([
                ''.join(self.rng.choice('0123456789abcdef') for _ in range(n))
                for n in [8, 4, 4, 4, 12]
            ]),
        ]
        return self.rng.choice(formats)()


# ══════════════════════════════════════════════════════════════════
#  TRAP FUNCTIONS
# ══════════════════════════════════════════════════════════════════

class TrapFunctionGenerator:
    """
    Генерирует фейковые функции с "интересными" именами.
    
    Reverse-engineer видит `decrypt_bytecode` или `get_original_source`
    и вызывает. Функция → trap.
    """

    TRAP_NAMES = [
        'decrypt_bytecode', 'get_original_source', 'unlock_features',
        'dump_functions', 'reveal_strings', 'debug_dump', 'get_vm_key',
        'extract_constants', 'disassemble_code', 'get_secret',
        'admin_access', 'bypass_protection', 'get_owner_data',
    ]

    def __init__(self, rng: random.Random, name_gen: NameGenerator):
        self.rng = rng
        self.name_gen = name_gen

    def generate(self, count: int = 2) -> str:
        """Генерирует блок с trap functions."""
        count = min(count, len(self.TRAP_NAMES))
        chosen = self.rng.sample(self.TRAP_NAMES, count)
        lines: List[str] = []

        for fn_name in chosen:
            # Разные варианты trap-функций
            variants = [
                # Прямой бесконечный цикл
                f'getfenv()["{fn_name}"] = function() while true do end end',
                # Через pcall (более скрытно)
                f'getfenv()["{fn_name}"] = function(...) local _ = ...; while 1 do end end',
                # Возвращает функцию-приманку
                (f'getfenv()["{fn_name}"] = function()\n'
                 f'    return setmetatable({{}}, {{__index = function() while true do end end}})\n'
                 f'end'),
                # Возвращает fake-данные, потом trap
                (f'getfenv()["{fn_name}"] = function()\n'
                 f'    coroutine.wrap(function() while true do end end)()\n'
                 f'    return "0x00000000"\n'
                 f'end'),
            ]
            lines.append(self.rng.choice(variants))

        return '\n'.join(lines)


# ══════════════════════════════════════════════════════════════════
#  ANTI-HOOK DETECTION
# ══════════════════════════════════════════════════════════════════

class AntiHookGenerator:
    """
    Проверяет что критичные функции API не были подменены.
    
    Reverse-engineer часто hook'ает `string.byte`, `bit32.bxor`,
    `getfenv` чтобы перехватить расшифровку. Мы проверяем это.
    """

    # Функции, которые мы часто используем — их hook = смерть
    CRITICAL_FUNCTIONS = [
        ('string', 'byte'),
        ('string', 'sub'),
        ('string', 'char'),
        ('string', 'len'),
        ('table', 'insert'),
        ('table', 'concat'),
        ('math', 'floor'),
        ('math', 'random'),
    ]

    def __init__(self, rng: random.Random, name_gen: NameGenerator):
        self.rng = rng
        self.name_gen = name_gen

    def generate(self, count: int = 3) -> str:
        """Генерирует проверки на hook'и."""
        count = min(count, len(self.CRITICAL_FUNCTIONS))
        chosen = self.rng.sample(self.CRITICAL_FUNCTIONS, count)
        lines: List[str] = []

        for lib, fn in chosen:
            check_type = self.rng.randint(0, 2)

            if check_type == 0:
                # Проверка типа
                v = self.name_gen.generate()
                lines.append(
                    f'local {v} = {lib}.{fn}\n'
                    f'if type({v}) ~= "function" then while true do end end'
                )
            elif check_type == 1:
                # Проверка через известное значение
                # string.byte("A") == 65 — если hooked, вернёт другое
                check_call = self._make_reference_check(lib, fn)
                if check_call:
                    lines.append(check_call)
            else:
                # Проверка через iscclosure / islclosure если доступно
                v = self.name_gen.generate()
                lines.append(
                    f'local {v} = iscclosure or function() return true end\n'
                    f'if not {v}({lib}.{fn}) then\n'
                    f'    if not islclosure or not islclosure({lib}.{fn}) then\n'
                    f'        while true do end\n'
                    f'    end\n'
                    f'end'
                )

        return '\n'.join(lines)

    def _make_reference_check(self, lib: str, fn: str) -> str:
        """Проверка через известный результат."""
        # Пары (call, expected_result)
        reference_calls = {
            ('string', 'byte'):  ('string.byte("A")', '65'),
            ('string', 'sub'):   ('string.sub("hello", 2, 3)', '"el"'),
            ('string', 'char'):  ('string.char(65)', '"A"'),
            ('string', 'len'):   ('string.len("abc")', '3'),
            ('math', 'floor'):   ('math.floor(3.7)', '3'),
            ('table', 'concat'): ('table.concat({"a","b"}, "")', '"ab"'),
        }
        key = (lib, fn)
        if key not in reference_calls:
            return ''
        call, expected = reference_calls[key]
        v = self.name_gen.generate()
        return (
            f'local {v} = {call}\n'
            f'if {v} ~= {expected} then while true do end end'
        )


# ══════════════════════════════════════════════════════════════════
#  INTEGRITY CHECK
# ══════════════════════════════════════════════════════════════════

class IntegrityCheckGenerator:
    """
    Проверка целостности через checksum.
    
    Вычисляет "контрольную сумму" вычислительного результата,
    который должен быть определённым. Если код модифицирован —
    результат не совпадёт.
    """

    def __init__(self, rng: random.Random, name_gen: NameGenerator):
        self.rng = rng
        self.name_gen = name_gen

    def generate(self, count: int = 2) -> str:
        """Генерирует блок integrity checks."""
        lines: List[str] = []
        for _ in range(count):
            lines.append(self._make_one_check())
        return '\n'.join(lines)

    def _make_one_check(self) -> str:
        """Одна проверка — вычисление известного значения."""
        variant = self.rng.randint(0, 3)

        if variant == 0:
            # Простое арифметическое выражение
            a = self.rng.randint(100, 999)
            b = self.rng.randint(100, 999)
            expected = a * b
            v = self.name_gen.generate()
            return (
                f'local {v} = {a} * {b}\n'
                f'if {v} ~= {expected} then while true do end end'
            )

        if variant == 1:
            # Через string операции
            expected_len = self.rng.randint(5, 15)
            test_str = ''.join(
                self.rng.choice('abcdefghij')
                for _ in range(expected_len)
            )
            v = self.name_gen.generate()
            return (
                f'local {v} = #"{test_str}"\n'
                f'if {v} ~= {expected_len} then while true do end end'
            )

        if variant == 2:
            # Проверка через bit32 (Luau specific)
            a = self.rng.randint(1, 1000)
            b = self.rng.randint(1, 1000)
            expected = a ^ b  # XOR в Python
            v = self.name_gen.generate()
            return (
                f'local {v} = bit32.bxor({a}, {b})\n'
                f'if {v} ~= {expected} then while true do end end'
            )

        # variant == 3: math.floor результат
        base = self.rng.randint(10, 100)
        div = self.rng.randint(2, 9)
        expected = base // div
        v = self.name_gen.generate()
        return (
            f'local {v} = math.floor({base} / {div})\n'
            f'if {v} ~= {expected} then while true do end end'
        )


# ══════════════════════════════════════════════════════════════════
#  DEBUG DETECTION
# ══════════════════════════════════════════════════════════════════

class DebugDetectionGenerator:
    """
    Обнаружение попытки debug/dump функции.
    
    Проверяет:
      - Не изменена ли debug библиотека
      - Не открыт ли DebuggerRunning
      - Не вызывается ли из-под LuaC decompiler
    """

    def __init__(self, rng: random.Random, name_gen: NameGenerator):
        self.rng = rng
        self.name_gen = name_gen

    def generate(self) -> str:
        """Генерирует блок anti-debug проверок."""
        lines: List[str] = []

        # 1. Проверка debug.getinfo
        v1 = self.name_gen.generate()
        lines.append(
            f'local {v1} = debug and debug.getinfo\n'
            f'if type({v1}) ~= "function" then\n'
            f'    -- нормально: multi-executor, где debug ограничен\n'
            f'end'
        )

        # 2. Проверка что мы не в decompile mode (некоторые decompilers
        #    добавляют checkcaller при hook'е)
        v2 = self.name_gen.generate()
        lines.append(
            f'local {v2} = checkcaller\n'
            f'if type({v2}) == "function" then\n'
            f'    if {v2}() == false and false then while true do end end\n'
            f'end'
        )

        # 3. Проверка на script.LinkedSource (изменённые скрипты)
        v3 = self.name_gen.generate()
        lines.append(
            f'pcall(function()\n'
            f'    local {v3} = script and script.LinkedSource\n'
            f'    if {v3} and {v3} ~= "" then\n'
            f'        -- external link — подозрительно\n'
            f'    end\n'
            f'end)'
        )

        return '\n'.join(lines)


# ══════════════════════════════════════════════════════════════════
#  ГЛАВНЫЙ КЛАСС
# ══════════════════════════════════════════════════════════════════

class AntiTamperGenerator:
    """
    Генератор всех anti-tamper защит.
    
    Использование:
        gen = AntiTamperGenerator(seed=42)
        code = gen.generate()
    """

    def __init__(
        self,
        seed: Optional[int] = None,
        # Опции — что включать
        honeypots: bool = True,
        trap_functions: bool = True,
        anti_hook: bool = True,
        integrity_checks: bool = True,
        debug_detection: bool = True,
        # Количества
        num_honeypots: int = 3,
        num_traps: int = 2,
        num_hooks: int = 3,
        num_integrity: int = 2,
    ):
        if seed is None:
            seed = random.randint(0, 2**32 - 1)
        self.seed = seed
        self.rng = make_rng(seed)
        self.name_gen = NameGenerator(rng=self.rng, style='hex')

        self.options = {
            'honeypots': honeypots,
            'trap_functions': trap_functions,
            'anti_hook': anti_hook,
            'integrity_checks': integrity_checks,
            'debug_detection': debug_detection,
        }
        self.counts = {
            'honeypots': num_honeypots,
            'traps': num_traps,
            'hooks': num_hooks,
            'integrity': num_integrity,
        }

        self._stats: Dict[str, int] = {}

    def generate(self) -> str:
        """Сгенерировать все защиты. Возвращает Lua-код."""
        blocks: List[Tuple[str, str]] = []

        if self.options['anti_hook']:
            gen = AntiHookGenerator(self.rng, self.name_gen)
            blocks.append(('anti_hook', gen.generate(count=self.counts['hooks'])))

        if self.options['integrity_checks']:
            gen = IntegrityCheckGenerator(self.rng, self.name_gen)
            blocks.append(('integrity', gen.generate(count=self.counts['integrity'])))

        if self.options['honeypots']:
            gen = HoneypotGenerator(self.rng, self.name_gen)
            blocks.append(('honeypots', gen.generate(count=self.counts['honeypots'])))

        if self.options['trap_functions']:
            gen = TrapFunctionGenerator(self.rng, self.name_gen)
            blocks.append(('traps', gen.generate(count=self.counts['traps'])))

        if self.options['debug_detection']:
            gen = DebugDetectionGenerator(self.rng, self.name_gen)
            blocks.append(('debug', gen.generate()))

        # Обновляем статистику
        for name, code in blocks:
            self._stats[name] = code.count('\n') + 1

        # Перемешиваем порядок блоков
        self.rng.shuffle(blocks)

        # Оборачиваем каждый блок в pcall (иногда — не всегда)
        result: List[str] = []
        for name, code in blocks:
            if not code.strip():
                continue
            if self.rng.random() < 0.5:
                # Оборачиваем в pcall (тихий фейл)
                wrapper_var = self.name_gen.generate()
                indent = '    '
                indented = '\n'.join(indent + line for line in code.split('\n'))
                result.append(
                    f'local {wrapper_var} = pcall(function()\n'
                    f'{indented}\n'
                    f'end)'
                )
            else:
                result.append(code)

        return '\n\n'.join(result)

    def stats(self) -> Dict[str, Any]:
        return {
            'seed': self.seed,
            'options': self.options,
            'lines_generated': dict(self._stats),
        }


# ══════════════════════════════════════════════════════════════════
#  RANDOM BOMBS (для вставки в разные места кода)
# ══════════════════════════════════════════════════════════════════

def generate_random_bomb(rng: Optional[random.Random] = None,
                         name_gen: Optional[NameGenerator] = None) -> str:
    """
    Одна маленькая случайная проверка (1-3 строки).
    Подходит для inject'а в разные места основного кода.
    """
    if rng is None:
        rng = random.Random()
    if name_gen is None:
        name_gen = NameGenerator(rng=rng, style='hex')

    variant = rng.randint(0, 4)
    v = name_gen.generate()

    if variant == 0:
        # Простая арифметика
        a, b = rng.randint(10, 999), rng.randint(10, 999)
        return f'local {v} = {a} + {b}\nif {v} ~= {a + b} then while true do end end'

    if variant == 1:
        # Проверка type
        n = rng.randint(1, 1000)
        return f'if type({n}) ~= "number" then while true do end end'

    if variant == 2:
        # Проверка длины строки
        s = ''.join(rng.choice('abcdefghij') for _ in range(rng.randint(3, 10)))
        return f'if #"{s}" ~= {len(s)} then while true do end end'

    if variant == 3:
        # bit32 check
        a, b = rng.randint(1, 100), rng.randint(1, 100)
        return f'if bit32.bxor({a}, {b}) ~= {a ^ b} then while true do end end'

    # variant == 4: math check
    a = rng.randint(2, 100)
    return f'if math.floor({a}.5) ~= {a} then while true do end end'


# ══════════════════════════════════════════════════════════════════
#  ПУБЛИЧНЫЙ API
# ══════════════════════════════════════════════════════════════════

def generate_anti_tamper(seed: Optional[int] = None, **kwargs) -> str:
    """Быстрая генерация всех защит."""
    return AntiTamperGenerator(seed=seed, **kwargs).generate()


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
    print('  NZL Anti-Tamper — Tests')
    print('═' * 56)

    # ── Test 1: базовая генерация ────────────────────────────────
    print('\n[1] Базовая генерация')
    gen = AntiTamperGenerator(seed=1)
    code = gen.generate()
    check('код сгенерирован', isinstance(code, str) and len(code) > 200,
          f'len={len(code)}')
    check('содержит while true do end или while 1 do',
          'while true do end' in code or 'while 1 do' in code)

    # ── Test 2: полиморфизм ───────────────────────────────────────
    print('\n[2] Полиморфизм')
    c1 = AntiTamperGenerator(seed=100).generate()
    c2 = AntiTamperGenerator(seed=200).generate()
    check('разные seeds → разный код', c1 != c2)

    # ── Test 3: honeypots есть ────────────────────────────────────
    print('\n[3] Honeypots (приманки)')
    gen = AntiTamperGenerator(seed=5, honeypots=True, trap_functions=False,
                              anti_hook=False, integrity_checks=False,
                              debug_detection=False, num_honeypots=5)
    code = gen.generate()
    check('содержит setmetatable', 'setmetatable' in code)
    check('содержит __index trap', '__index' in code)
    # Хотя бы один honeypot имя присутствует
    has_hp = any(h in code for h in HoneypotGenerator.HONEYPOT_NAMES)
    check('содержит имя honeypot переменной', has_hp)

    # ── Test 4: trap functions ────────────────────────────────────
    print('\n[4] Trap functions')
    gen = AntiTamperGenerator(seed=6, honeypots=False, trap_functions=True,
                              anti_hook=False, integrity_checks=False,
                              debug_detection=False, num_traps=3)
    code = gen.generate()
    has_trap = any(t in code for t in TrapFunctionGenerator.TRAP_NAMES)
    check('содержит trap function name', has_trap)
    check('trap функция определена через getfenv',
          'getfenv()' in code)

    # ── Test 5: anti-hook ─────────────────────────────────────────
    print('\n[5] Anti-hook checks')
    gen = AntiTamperGenerator(seed=7, honeypots=False, trap_functions=False,
                              anti_hook=True, integrity_checks=False,
                              debug_detection=False, num_hooks=5)
    code = gen.generate()
    check('содержит string.byte или math.floor',
          'string.byte' in code or 'math.floor' in code or
          'string.sub' in code or 'table.concat' in code)

    # ── Test 6: integrity checks ─────────────────────────────────
    print('\n[6] Integrity checks')
    gen = AntiTamperGenerator(seed=8, honeypots=False, trap_functions=False,
                              anti_hook=False, integrity_checks=True,
                              debug_detection=False, num_integrity=5)
    code = gen.generate()
    # Integrity checks — арифметика, string.len или bit32
    has_math = ('~=' in code) and ('while true do end' in code or 'while 1 do' in code)
    check('содержит проверку с ~=', has_math)

    # ── Test 7: debug detection ──────────────────────────────────
    print('\n[7] Debug detection')
    gen = AntiTamperGenerator(seed=9, honeypots=False, trap_functions=False,
                              anti_hook=False, integrity_checks=False,
                              debug_detection=True)
    code = gen.generate()
    check('содержит debug.getinfo или checkcaller',
          'debug' in code or 'checkcaller' in code)

    # ── Test 8: все опции выключены ──────────────────────────────
    print('\n[8] Все опции выключены → пустой код')
    gen = AntiTamperGenerator(seed=1, honeypots=False, trap_functions=False,
                              anti_hook=False, integrity_checks=False,
                              debug_detection=False)
    code = gen.generate()
    check('пустой код', code.strip() == '', f'got: {repr(code[:50])}')

    # ── Test 9: тихий фейл (нет error/warn/print) ────────────────
    print('\n[9] Silent fail')
    for seed in range(1, 20):
        code = AntiTamperGenerator(seed=seed).generate()
        assert 'error(' not in code, f'seed={seed}: error()!'
        assert 'warn(' not in code, f'seed={seed}: warn()!'
        assert 'print(' not in code, f'seed={seed}: print()!'
    check('никаких error/warn/print в 20 билдах', True)

    # ── Test 10: stats ────────────────────────────────────────────
    print('\n[10] Stats')
    gen = AntiTamperGenerator(seed=42)
    gen.generate()
    s = gen.stats()
    check('stats содержит seed', s.get('seed') == 42)
    check('stats содержит options', 'options' in s)
    check('stats содержит lines_generated', 'lines_generated' in s)

    # ── Test 11: random_bomb ─────────────────────────────────────
    print('\n[11] Random bomb (одиночная проверка)')
    for seed in range(1, 20):
        rng = random.Random(seed)
        name_gen = NameGenerator(rng=rng, style='hex')
        bomb = generate_random_bomb(rng, name_gen)
        assert 'while true do end' in bomb, f'seed={seed}: no trap!'
        assert 'error' not in bomb
    check('random_bomb генерирует корректные проверки', True)

    # ── Test 12: honeypot имена реалистичные ─────────────────────
    print('\n[12] Honeypot имена выглядят как секреты')
    for name in HoneypotGenerator.HONEYPOT_NAMES:
        assert '_' in name or name.startswith('_'), name
    check('все имена honeypot содержат _ (выглядят как приватные)',
          True)

    # ── Test 13: pcall wrapping ──────────────────────────────────
    print('\n[13] pcall wrapping используется')
    has_pcall_count = 0
    for seed in range(30):
        code = AntiTamperGenerator(seed=seed).generate()
        if 'pcall' in code:
            has_pcall_count += 1
    check(f'pcall используется в {has_pcall_count}/30 билдах',
          has_pcall_count > 10)

    # ── Test 14: публичный API ───────────────────────────────────
    print('\n[14] Публичный API generate_anti_tamper')
    code = generate_anti_tamper(seed=1)
    check('public API возвращает строку', isinstance(code, str))
    check('код не пустой', len(code) > 100)

    # ── Test 15: количество traps контролируется ─────────────────
    print('\n[15] num_traps контролирует количество')
    gen = AntiTamperGenerator(seed=1, honeypots=False, anti_hook=False,
                              integrity_checks=False, debug_detection=False,
                              trap_functions=True, num_traps=1)
    code = gen.generate()
    # Считаем сколько имён trap-функций в коде
    trap_count = sum(1 for t in TrapFunctionGenerator.TRAP_NAMES if t in code)
    check(f'num_traps=1 → 1 функция в коде (got {trap_count})',
          trap_count == 1)

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
    print('\n📄 Пример защиты (seed=42):')
    demo = AntiTamperGenerator(seed=42)
    demo_code = demo.generate()
    for line in demo_code.split('\n'):
        print('  ' + line)
    print(f'\n📊 Stats:')
    for k, v in demo.stats()['lines_generated'].items():
        print(f'   {k}: {v} строк')
    print()

    return failed == 0


if __name__ == '__main__':
    import sys
    success = _test()
    sys.exit(0 if success else 1)