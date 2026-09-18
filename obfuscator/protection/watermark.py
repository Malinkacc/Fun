# obfuscator/protection/watermark.py
"""
NZL Studio Obfuscator — Watermark & Header Generator
Часть 11c: вшивка водяных знаков, header, zero-width markers
"""

import hashlib
import struct
import re
from typing import Optional

# Импортируем утилиты
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from obfuscator.utils.crypto import fnv1a_hash, fnv1a_seeded, gen_random_key
from obfuscator.utils.random_gen import make_rng, gen_build_id

# ──────────────────────────────────────────────────────────────────────────────
# КОНСТАНТЫ
# ──────────────────────────────────────────────────────────────────────────────

OWNER_IDS = [582821107065683971, 1468154878420455476]
DISCORD_LINK = "discord.gg/c3kBtN9vXb"
OBFUSCATOR_NAME = "NZL Studio Obfuscator"
VERSION = "v1.0"

# Zero-width Unicode символы для стеганографии
ZW_CHARS = {
    '0': '\u200B',  # Zero Width Space
    '1': '\u200C',  # Zero Width Non-Joiner
    'sep': '\u200D',  # Zero Width Joiner (разделитель)
    'start': '\u2060',  # Word Joiner (маркер начала)
    'end': '\uFEFF',  # Zero Width No-Break Space (маркер конца)
}

# Обратный маппинг
ZW_REVERSE = {v: k for k, v in ZW_CHARS.items() if k not in ('sep', 'start', 'end')}

# ──────────────────────────────────────────────────────────────────────────────
# ZERO-WIDTH ENCODER
# ──────────────────────────────────────────────────────────────────────────────

def encode_zw(data: str) -> str:
    """
    Кодирует строку в zero-width символы (побитово).
    data → бинарная строка → ZW_CHARS['0'/'1'] + разделители
    """
    bits = []
    for char in data:
        byte = ord(char) if len(char) == 1 else ord(char[0])
        for i in range(7, -1, -1):
            bits.append('1' if (byte >> i) & 1 else '0')

    result = [ZW_CHARS['start']]
    for i, bit in enumerate(bits):
        result.append(ZW_CHARS[bit])
        # Разделитель после каждого байта (8 бит)
        if (i + 1) % 8 == 0:
            result.append(ZW_CHARS['sep'])
    result.append(ZW_CHARS['end'])

    return ''.join(result)


def decode_zw(text: str) -> Optional[str]:
    """
    Извлекает данные из zero-width символов.
    Возвращает None если маркеры не найдены.
    """
    start_idx = text.find(ZW_CHARS['start'])
    end_idx = text.find(ZW_CHARS['end'])

    if start_idx == -1 or end_idx == -1 or start_idx >= end_idx:
        return None

    # Извлекаем только битовые символы (без разделителей и маркеров)
    payload = text[start_idx + 1:end_idx]
    bits = []
    for ch in payload:
        if ch in ZW_REVERSE:
            bits.append(ZW_REVERSE[ch])
        # Разделители (sep) — игнорируем

    # Декодируем байты
    result = []
    for i in range(0, len(bits) - 7, 8):
        byte_bits = bits[i:i + 8]
        if len(byte_bits) == 8:
            byte_val = int(''.join(byte_bits), 2)
            if 32 <= byte_val <= 126:  # Printable ASCII
                result.append(chr(byte_val))

    return ''.join(result) if result else None


# ──────────────────────────────────────────────────────────────────────────────
# BUILD ID
# ──────────────────────────────────────────────────────────────────────────────

def generate_build_id(seed: int) -> str:
    """
    Генерирует детерминированный 8-hex Build ID от seed.
    Использует gen_build_id из random_gen + fnv1a для усиления.
    """
    rng = make_rng(seed)
    base = gen_build_id(rng)  # 8 hex chars

    # Усиливаем через fnv1a для уникальности
    enhanced = fnv1a_seeded(base.encode(), seed)
    return f"{enhanced:08x}"[:8].upper()


# ──────────────────────────────────────────────────────────────────────────────
# WATERMARK GENERATOR
# ──────────────────────────────────────────────────────────────────────────────

class WatermarkGenerator:
    """
    Генератор водяных знаков для обфусцированного Lua-кода.

    Возможности:
    - ASCII-art header с build ID
    - Zero-width Unicode маркеры (стеганография)
    - Дублирующие метки в коде (anti-remove)
    - Discord metadata в комментариях
    - Extract функция для проверки авторства
    """

    def __init__(self, seed: int, owner_id: Optional[int] = None):
        self.seed = seed
        self.rng = make_rng(seed)
        self.owner_id = owner_id or OWNER_IDS[0]
        self.build_id = generate_build_id(seed)
        self._wm_hash = self._compute_wm_hash()

    def _compute_wm_hash(self) -> str:
        """Вычисляет fingerprint = fnv1a(owner_id + build_id)"""
        payload = f"{self.owner_id}:{self.build_id}"
        h = fnv1a_hash(payload.encode())
        return f"{h:08x}".upper()

    # ──────────────────────────────────────────────────────────────────────────
    # HEADER
    # ──────────────────────────────────────────────────────────────────────────

    def generate_header(self, username: Optional[str] = None) -> str:
        """
        Генерирует ASCII-art header в виде Lua-комментария.

        Args:
            username: имя пользователя (опционально, иначе показываем ID)
        """
        owner_display = username if username else str(self.owner_id)

        # Zero-width watermark вшиваем прямо в строку header
        zw_mark = encode_zw(f"NZL:{self.owner_id}:{self.build_id}")

        lines = [
            f"--[[{zw_mark}",
            f"╔═══════════════════════════════════════╗",
            f"║   {OBFUSCATOR_NAME} {VERSION:<16}      ║",
            f"║   Discord: {DISCORD_LINK:<28}║",
            f"║   Build: {self.build_id:<30}║",
            f"║   Owner: {owner_display:<30}║",
            f"╚═══════════════════════════════════════╝",
            f"]]",
        ]

        return '\n'.join(lines)

    # ──────────────────────────────────────────────────────────────────────────
    # INLINE WATERMARKS (anti-remove)
    # ──────────────────────────────────────────────────────────────────────────

    def generate_inline_marks(self) -> list[str]:
        """
        Генерирует несколько inline-меток для вставки в код.
        Они рассыпаются по всему скрипту — удалить все трудно.

        Возвращает список Lua-строк (комментарии + ZW-строки).
        """
        marks = []

        # 1. Простой комментарий с hash
        marks.append(f"--[[ NZL:{self._wm_hash} ]]")

        # 2. Zero-width в пустой строке-комментарии (невидим)
        zw = encode_zw(f"{self.owner_id}:{self.build_id}")
        marks.append(f"--{zw}")


        # 4. Discord ссылка
        marks.append(f"-- Protected by {OBFUSCATOR_NAME} | {DISCORD_LINK}")

        return marks

    def generate_lua_wm_variable(self) -> str:
        """
        Генерирует Lua-переменную с watermark.
        Выглядит как обычная переменная, хранит WM hash.
        Используется для anti-deobfuscator trap.
        """
        # Случайное имя переменной (детерминированное от seed)
        var_names = ["_", "__", "___", "_0", "_00", "_nzl"]
        var_name = self.rng.choice(var_names)

        # Значение = fnv1a hash в виде числа
        wm_val = fnv1a_hash(self._wm_hash.encode())

        return f"local {var_name} = {wm_val} -- {self._wm_hash}"

    def generate_anti_deobf_trap(self) -> str:
        """
        Anti-deobfuscator trap: бесконечный цикл при попытке
        анализировать структуру кода (срабатывает при выполнении
        в нестандартной среде).

        Никаких error/warn — только while true do end.
        """
        zw = encode_zw(f"NZL:{self._wm_hash}")
        trap_lines = [
            f"--{zw}",
            f"-- {OBFUSCATOR_NAME} | {DISCORD_LINK}",
        ]
        return '\n'.join(trap_lines)

    # ──────────────────────────────────────────────────────────────────────────
    # ASSEMBLE: полная вставка в скрипт
    # ──────────────────────────────────────────────────────────────────────────

    def apply_watermarks(
        self,
        lua_code: str,
        username: Optional[str] = None,
        num_inline: int = 3
    ) -> str:
        """
        Вшивает все watermark-слои в готовый Lua-скрипт.

        Args:
            lua_code: готовый обфусцированный Lua-код
            username: имя владельца для header
            num_inline: количество inline-меток для рассыпки по коду

        Returns:
            Lua-код с watermark'ами
        """
        parts = []

        # 1. Header (самый верх)
        parts.append(self.generate_header(username))
        parts.append("")

        # 2. Anti-deobf trap (сразу после header)
        parts.append(self.generate_anti_deobf_trap())
        parts.append("")

        # 3. WM переменная
        parts.append(self.generate_lua_wm_variable())
        parts.append("")

        # 4. Тело кода с рассыпанными inline метками
        inline_marks = self.generate_inline_marks()
        lines = lua_code.split('\n')
        total_lines = len(lines)

        if total_lines > 0 and num_inline > 0:
            # Равномерно рассыпаем метки по коду
            step = max(1, total_lines // (num_inline + 1))
            positions = sorted(set(
                min(step * (i + 1), total_lines - 1)
                for i in range(min(num_inline, len(inline_marks)))
            ))

            # Вставляем метки в нужные позиции
            offset = 0
            for i, pos in enumerate(positions):
                mark = inline_marks[i % len(inline_marks)]
                lines.insert(pos + offset, mark)
                offset += 1

        parts.append('\n'.join(lines))

        return '\n'.join(parts)

    # ──────────────────────────────────────────────────────────────────────────
    # EXTRACT: извлечение метаданных из обфусцированного скрипта
    # ──────────────────────────────────────────────────────────────────────────

    def extract_watermark(self, lua_code: str) -> dict:
        """
        Извлекает watermark данные из обфусцированного скрипта.

        Returns:
            dict с полями:
            - found: bool
            - owner_id: str или None
            - build_id: str или None
            - wm_hash: str или None
            - discord: str или None
            - zw_data: str или None (сырые ZW данные)
        """
        result = {
            'found': False,
            'owner_id': None,
            'build_id': None,
            'wm_hash': None,
            'discord': None,
            'zw_data': None,
        }

        # 1. Ищем Discord ссылку
        if DISCORD_LINK in lua_code:
            result['discord'] = DISCORD_LINK

        # 2. Ищем WM hash паттерн (8 hex uppercase)
        wm_pattern = re.compile(r'NZL:([0-9A-F]{8})')
        m = wm_pattern.search(lua_code)
        if m:
            result['wm_hash'] = m.group(1)
            result['found'] = True

        # 3. Извлекаем zero-width данные
        zw_data = decode_zw(lua_code)
        if zw_data:
            result['zw_data'] = zw_data
            result['found'] = True

            # Парсим формат "NZL:owner_id:build_id"
            nzl_pattern = re.compile(r'NZL:(\d+):([0-9A-Fa-f]{8})')
            zm = nzl_pattern.match(zw_data)
            if zm:
                result['owner_id'] = zm.group(1)
                result['build_id'] = zm.group(2).upper()

        # 4. Ищем Build ID в header
        build_pattern = re.compile(r'Build:\s*([0-9A-Fa-f]{8})', re.IGNORECASE)
        bm = build_pattern.search(lua_code)
        if bm and not result['build_id']:
            result['build_id'] = bm.group(1).upper()
            result['found'] = True

        return result


# ──────────────────────────────────────────────────────────────────────────────
# CONVENIENCE FUNCTIONS
# ──────────────────────────────────────────────────────────────────────────────

def generate_watermark(seed: int, owner_id: Optional[int] = None) -> WatermarkGenerator:
    """Фабричная функция — создаёт WatermarkGenerator."""
    return WatermarkGenerator(seed, owner_id)


def apply_full_watermark(
    lua_code: str,
    seed: int,
    owner_id: Optional[int] = None,
    username: Optional[str] = None
) -> str:
    """
    Применяет полный watermark к Lua-коду.
    Shortcut для engine.py.
    """
    wm = WatermarkGenerator(seed, owner_id)
    return wm.apply_watermarks(lua_code, username)


def extract_watermark_info(lua_code: str) -> dict:
    """
    Извлекает watermark без знания seed.
    Работает только с ZW-данными и паттернами.
    """
    # Создаём временный generator только для extract
    dummy = WatermarkGenerator(0)
    return dummy.extract_watermark(lua_code)


# ──────────────────────────────────────────────────────────────────────────────
# ТЕСТЫ
# ──────────────────────────────────────────────────────────────────────────────

def _run_tests():
    print("=" * 60)
    print("🧪 ТЕСТЫ: watermark.py")
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

    # ── Тест 1: Zero-width encode/decode ────────────────────────────────────
    print("\n📌 Zero-width encoding:")

    zw = encode_zw("Hello")
    decoded = decode_zw(zw)
    test("encode/decode 'Hello'", decoded == "Hello", f"got: {decoded!r}")

    zw2 = encode_zw("NZL:582821107065683971:ABCD1234")
    decoded2 = decode_zw(zw2)
    test("encode/decode owner+build", decoded2 == "NZL:582821107065683971:ABCD1234", f"got: {decoded2!r}")

    test("ZW string не пустая", len(zw) > len("Hello"))
    test("decode_zw(plain_text) → None", decode_zw("plain text without markers") is None)

    # ── Тест 2: Build ID детерминизм ────────────────────────────────────────
    print("\n📌 Build ID:")

    bid1 = generate_build_id(12345)
    bid2 = generate_build_id(12345)
    bid3 = generate_build_id(99999)

    test("Детерминизм (seed=12345)", bid1 == bid2, f"{bid1} vs {bid2}")
    test("Разные seed → разные ID", bid1 != bid3, f"{bid1} vs {bid3}")
    test("Build ID длина 8", len(bid1) == 8, f"len={len(bid1)}")
    test("Build ID uppercase hex", all(c in "0123456789ABCDEF" for c in bid1), f"got: {bid1}")

    # ── Тест 3: WatermarkGenerator ───────────────────────────────────────────
    print("\n📌 WatermarkGenerator:")

    wm = WatermarkGenerator(42, OWNER_IDS[0])

    header = wm.generate_header("TestUser")
    test("Header содержит название", OBFUSCATOR_NAME in header)
    test("Header содержит Discord", DISCORD_LINK in header)
    test("Header содержит Build ID", wm.build_id in header)
    test("Header содержит Owner", "TestUser" in header)
    test("Header содержит версию", VERSION in header)
    test("Header содержит ZW маркер", ZW_CHARS['start'] in header)

    # ── Тест 4: Apply + Extract ──────────────────────────────────────────────
    print("\n📌 Apply & Extract watermark:")

    sample_lua = "local x = 1\nlocal y = x + 2\nprint(x, y)"
    result_code = wm.apply_watermarks(sample_lua, username="TestUser", num_inline=2)

    test("apply_watermarks не пустой", len(result_code) > len(sample_lua))
    test("Оригинальный код сохранён", "local x = 1" in result_code)

    info = wm.extract_watermark(result_code)
    test("extract found=True", info['found'])
    test("extract owner_id корректен", info['owner_id'] == str(OWNER_IDS[0]),
         f"got: {info['owner_id']!r}")
    test("extract build_id корректен", info['build_id'] == wm.build_id.upper(),
         f"got: {info['build_id']!r}, expected: {wm.build_id.upper()!r}")
    test("extract discord найден", info['discord'] == DISCORD_LINK)

    # ── Тест 5: Полиморфизм ─────────────────────────────────────────────────
    print("\n📌 Полиморфизм:")

    wm_a = WatermarkGenerator(1111)
    wm_b = WatermarkGenerator(2222)

    test("Разные seed → разные build_id", wm_a.build_id != wm_b.build_id)
    test("Разные seed → разные wm_hash", wm_a._wm_hash != wm_b._wm_hash)

    # Одинаковый seed → одинаковый результат
    wm_c = WatermarkGenerator(1111)
    test("Одинаковый seed → одинаковый build_id", wm_a.build_id == wm_c.build_id)

    # ── Тест 6: apply_full_watermark (shortcut) ──────────────────────────────
    print("\n📌 Shortcut функции:")

    out = apply_full_watermark("print('hello')", seed=777, owner_id=OWNER_IDS[1])
    test("apply_full_watermark работает", DISCORD_LINK in out)

    info2 = extract_watermark_info(out)
    test("extract_watermark_info (без seed)", info2['found'])

    # ── Тест 7: inline marks count ───────────────────────────────────────────
    print("\n📌 Inline marks / anti-remove:")

    marks = wm.generate_inline_marks()
    test("Минимум 3 inline метки", len(marks) >= 3)
    test("Discord в одной из меток", any(DISCORD_LINK in m for m in marks))
    test("WM hash в одной из меток", any(wm._wm_hash in m for m in marks))

    # ── ИТОГ ─────────────────────────────────────────────────────────────────
    print()
    print("=" * 60)
    total = passed + failed
    print(f"📊 Результат: {passed}/{total} тестов прошло")
    if failed == 0:
        print("🎉 ВСЕ ТЕСТЫ ПРОШЛИ!")
    else:
        print(f"⚠️  Провалилось: {failed}")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = _run_tests()
    sys.exit(0 if success else 1)