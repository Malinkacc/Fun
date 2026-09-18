"""
NZL Studio Obfuscator — Discord Bot
discord.gg/c3kBtN9vXb
"""

import asyncio
import io
import json
import os
import random
import sys
import time
import traceback

import discord
from discord import app_commands
from discord.ext import commands

# ── Путь к obfuscator ──────────────────────────────────────────────────────────
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

print("[bot] 🔥 Прогрев модулей обфускатора...")
_t_import = time.perf_counter()

from obfuscator.engine import Obfuscator
from obfuscator.protection.watermark import DISCORD_LINK, OWNER_IDS
from obfuscator.utils.code_shaper import (
    get_available_masks,
    get_random_mask_name,
    shape_code,
)
from obfuscator.deobfuscator.engine import DeobfuscatorEngine  # v3.0 REAL

# Прогрев — прогоняем пустышку, чтобы все ленивые импорты сработали
try:
    _warm = Obfuscator(seed=1, verbose=False)
    _warm.obfuscate("local x = 1\nprint(x)", level="medium")
    print(f"[bot] ✅ Прогрев завершён за {(time.perf_counter() - _t_import) * 1000:.0f} мс")
except Exception as _e:
    print(f"[bot] ⚠️ Ошибка прогрева: {_e}")

# ── Константы ──────────────────────────────────────────────────────────────────
TOKEN = "MTEwMTkyNTQwNzUyNTE4MzY3Mg.GXTSzE.5MTlGmMbZ79iNvZqMfgx1vIfG9nd-F2bv0DS1Q"
GUILD_ID = 1123677106799394888
BOT_VERSION = "1.2"

COLOR_OK = 0x00FF88
COLOR_ERR = 0xFF4444
COLOR_INFO = 0x0099FF
COLOR_WARN = 0xFFAA00
COLOR_OWNER = 0x9B59B6

MAX_FILE_SIZE = 25 * 1024 * 1024
MAX_CODE_SIZE = 5 * 2000 * 2000

LEVEL_META = {
    "medium": {"emoji": "🟡", "title": "Medium", "short": "быстро и надёжно"},
    "hard": {"emoji": "🔴", "title": "Hard", "short": "усиленная защита"},
    "insane": {"emoji": "🔥", "title": "Insane", "short": "VM protection + максимум"},
}

LEVEL_CHOICES = [
    app_commands.Choice(name="🟡 Medium — быстро и надёжно", value="medium"),
    app_commands.Choice(name="🔴 Hard — усиленная защита", value="hard"),
    app_commands.Choice(name="🔥 Insane — VM protection + максимум", value="insane"),
]

DEOBF_LEVEL_CHOICES = [
    app_commands.Choice(name="🟢 Basic  — убрать мусор (любой Lua)", value="basic"),
    app_commands.Choice(name="🟡 Full   — + расшифровать строки (NZL)", value="full"),
    app_commands.Choice(name="🔴 VM     — + декомпилировать VM (NZL insane)", value="vm"),
]

_SHAPE_CHOICES = [
    app_commands.Choice(name="⬛ Без фигурки", value="none"),
    app_commands.Choice(name="🎲 Случайная", value="random"),
    app_commands.Choice(name="🐙 Осьминог", value="octopus"),
    app_commands.Choice(name="💀 Череп", value="skull"),
    app_commands.Choice(name="😈 Демон", value="demon"),
    app_commands.Choice(name="🐺 Волк", value="wolf"),
    app_commands.Choice(name="🕷️ Паук", value="spider"),
    app_commands.Choice(name="🐉 Дракон", value="dragon"),
    app_commands.Choice(name="❤️ Сердце", value="heart"),
]

SHAPE_EMOJI_MAP = {
    "octopus": "🐙", "skull": "💀", "demon": "😈", "wolf": "🐺",
    "spider": "🕷️", "dragon": "🐉", "heart": "❤️",
}

# ── Config ─────────────────────────────────────────────────────────────────────
CONFIG_FILE = os.path.join(os.path.dirname(__file__), "bot_config.json")


def load_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        if "owner_id" in data and "owner_ids" not in data:
            data["owner_ids"] = [data["owner_id"]] if data["owner_id"] else []
            del data["owner_id"]

        data.setdefault("allowed_channels", [])
        data.setdefault("allowed_roles", [])
        data.setdefault("owner_ids", list(OWNER_IDS))
        return data

    return {
        "allowed_channels": [],
        "allowed_roles": [],
        "owner_ids": list(OWNER_IDS),
    }


def save_config(cfg: dict) -> None:
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


config = load_config()
save_config(config)

# ── Bot ────────────────────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)


# ── Доступ ─────────────────────────────────────────────────────────────────────
def is_owner(interaction: discord.Interaction) -> bool:
    return interaction.user.id in config.get("owner_ids", [])


def check_access(interaction: discord.Interaction) -> tuple[bool, str]:
    if is_owner(interaction):
        return True, ""

    if config["allowed_channels"]:
        if interaction.channel_id not in config["allowed_channels"]:
            clist = " ".join(f"<#{c}>" for c in config["allowed_channels"])
            return False, f"❌ Команда работает только в каналах: {clist}"

    if config["allowed_roles"]:
        user_roles = getattr(interaction.user, "roles", [])
        user_role_ids = {r.id for r in user_roles}
        if not user_role_ids.intersection(config["allowed_roles"]):
            rlist = " ".join(f"<@&{r}>" for r in config["allowed_roles"])
            return False, f"❌ Нужна одна из ролей: {rlist}"

    return True, ""


# ── Хелперы ────────────────────────────────────────────────────────────────────
def fmt_size(n: int) -> str:
    if n < 1024:
        return f"{n} Б"
    if n < 1024 * 1024:
        return f"{n / 1024:.1f} КБ"
    return f"{n / 1024 / 1024:.1f} МБ"


def fmt_ratio(inp: int, out: int) -> str:
    if inp == 0:
        return "—"
    return f"×{out / inp:.1f}"


def make_error_embed(title: str, desc: str) -> discord.Embed:
    return discord.Embed(title=f"❌ {title}", description=desc, color=COLOR_ERR)


def get_level_emoji(level_name: str) -> str:
    return LEVEL_META.get(level_name, {}).get("emoji", "⚙️")


def decode_bytes(raw: bytes) -> str:
    """Автоопределение кодировки файла."""
    if raw.startswith(b'\xff\xfe'):
        return raw[2:].decode("utf-16-le", errors="replace")
    if raw.startswith(b'\xfe\xff'):
        return raw[2:].decode("utf-16-be", errors="replace")
    if raw.startswith(b'\xef\xbb\xbf'):
        return raw[3:].decode("utf-8", errors="replace")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("cp1251", errors="replace")


# ── События ────────────────────────────────────────────────────────────────────
@bot.event
async def on_ready():
    print("╔════════════════════════════════════════════╗")
    print(f"║  NZL Studio Obfuscator Bot v{BOT_VERSION:<15}║")
    print("║  discord.gg/c3kBtN9vXb                    ║")
    print("╚════════════════════════════════════════════╝")
    print(f"✅ Бот {bot.user} запущен!")
    print(f"📡 Серверов: {len(bot.guilds)}")
    print(f"👑 Владельцы: {config.get('owner_ids', [])}")

    try:
        guild = discord.Object(id=GUILD_ID)
        bot.tree.copy_global_to(guild=guild)
        synced = await bot.tree.sync(guild=guild)
        print(f"🔄 Синхронизировано {len(synced)} slash-команд")
    except Exception as e:
        print(f"❌ Ошибка синхронизации: {e}")


# ── /ping ──────────────────────────────────────────────────────────────────────
@bot.tree.command(name="ping", description="Проверка работы бота")
async def cmd_ping(interaction: discord.Interaction):
    ms = round(bot.latency * 1000)
    embed = discord.Embed(
        title="🏓 Pong!",
        description=f"Задержка: `{ms} мс`",
        color=COLOR_OK if ms < 200 else COLOR_WARN,
    )
    embed.set_footer(text=f"NZL Obfuscator v{BOT_VERSION}")
    await interaction.response.send_message(embed=embed)


# ── /help ──────────────────────────────────────────────────────────────────────
@bot.tree.command(name="help", description="Список команд")
async def cmd_help(interaction: discord.Interaction):
    embed = discord.Embed(
        title="📖 NZL Obfuscator — Помощь",
        description=(
            f"Обфускатор Lua/Luau уровня **Luraph Premium**\n"
            f"{DISCORD_LINK}"
        ),
        color=COLOR_INFO,
    )

    embed.add_field(
        name="/obfuscate",
        value=(
            "Обфусцировать `.lua` / `.txt` файл\n"
            "`level` — `medium`, `hard` или `insane`\n"
            "`shape` — фигурка животного из кода (опционально)\n"
            "`username` — имя в header (опционально)\n\n"
            "**Insane:** функции с маркером `-- @vm` автоматически\n"
            "компилируются в VM bytecode."
        ),
        inline=False,
    )
    embed.add_field(
        name="/deobfuscate",
        value=(
            "Деобфусцировать `.lua` / `.txt` файл\n"
            "`level` — `basic`, `full` или `vm`\n\n"
            "Поддерживает: **Luraph, IronBrew, NZL, Prometheus, MoonSec**\n"
            "9-этапный pipeline: cleanup → decrypt → unflatten → rename → beautify"
        ),
        inline=False,
    )
    embed.add_field(name="/levels", value="Описание уровней обфускации", inline=False)
    embed.add_field(name="/shapes", value="Список доступных фигурок", inline=False)
    embed.add_field(name="/ping", value="Проверка работы бота", inline=False)
    embed.add_field(name="/settings", value="Настройки бота (только владелец)", inline=False)

    embed.set_footer(text=f"NZL Obfuscator v{BOT_VERSION} • {DISCORD_LINK}")
    await interaction.response.send_message(embed=embed)


# ── /levels ────────────────────────────────────────────────────────────────────
@bot.tree.command(name="levels", description="Описание уровней обфускации")
async def cmd_levels(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🛡️ Уровни обфускации NZL",
        description="Выбери уровень защиты для своего скрипта:",
        color=COLOR_INFO,
    )

    embed.add_field(
        name="🟡 medium",
        value=(
            "• Шифрование строк (XOR/RC4/Base85)\n"
            "• Обфускация чисел\n"
            "• Переименование переменных\n"
            "• Мусорный код\n"
            "• Header + Watermark\n"
            "• Environment checks\n"
            "⏱ Быстро | Размер ×3–5"
        ),
        inline=False,
    )

    embed.add_field(
        name="🔴 hard",
        value=(
            "• Всё из medium\n"
            "• Control Flow Flattening\n"
            "• Anti-tamper + Honeypots\n"
            "• Anti-hook + Debug detection\n"
            "• Integrity checks\n"
            "• Minified output\n"
            "⏱ Медленнее | Размер ×5–10"
        ),
        inline=False,
    )

    embed.add_field(
        name="🔥 insane",
        value=(
            "• Всё из hard\n"
            "• VM Protection по маркеру `-- @vm`\n"
            "• Автокомпиляция отмеченных функций в VM bytecode\n"
            "• Работает в Roblox / Luau\n"
            "• Рекурсия поддерживается\n"
            "• Лучший вариант для критичных функций\n"
            "⏱ Самый тяжёлый | Размер может быть ×20–100+"
        ),
        inline=False,
    )

    embed.set_footer(text="Target: Luau (Roblox) • VM работает через @vm-маркеры")
    await interaction.response.send_message(embed=embed)


# ── /shapes ────────────────────────────────────────────────────────────────────
@bot.tree.command(name="shapes", description="Список доступных фигурок кода")
async def cmd_shapes(interaction: discord.Interaction):
    masks = get_available_masks()

    embed = discord.Embed(
        title="🎨 Фигурки кода (Code Shaper)",
        description=(
            "Код визуально складывается в силуэт животного — как у Luraph!\n"
            "Каждая '#' клетка = реальный рабочий Lua-код.\n"
            "Используй опцию `shape` в `/obfuscate`."
        ),
        color=COLOR_INFO,
    )

    shapes_text = "\n".join(f"{SHAPE_EMOJI_MAP.get(m, '•')} `{m}`" for m in masks)
    shapes_text += "\n🎲 `random` — случайная фигурка"
    shapes_text += "\n⬛ `none` — без фигурки"

    embed.add_field(name="Доступные маски", value=shapes_text, inline=False)
    embed.set_footer(text="Фигурки обёрнуты в do...end — не влияют на работу скрипта")
    await interaction.response.send_message(embed=embed)


# ── /obfuscate ─────────────────────────────────────────────────────────────────
@bot.tree.command(name="obfuscate", description="Обфусцировать Lua/Luau скрипт")
@app_commands.describe(
    file="Прикрепи .lua или .txt файл",
    level="Уровень защиты",
    shape="Фигурка животного из кода (опционально)",
    username="Имя в header (опционально)",
)
@app_commands.choices(
    level=LEVEL_CHOICES,
    shape=_SHAPE_CHOICES,
)
async def cmd_obfuscate(
    interaction: discord.Interaction,
    file: discord.Attachment,
    level: app_commands.Choice[str],
    shape: app_commands.Choice[str] | None = None,
    username: str | None = None,
):
    await interaction.response.defer(thinking=True)

    allowed, reason = check_access(interaction)
    if not allowed:
        await interaction.followup.send(
            embed=make_error_embed("Нет доступа", reason),
            ephemeral=True,
        )
        return

    if not (file.filename.endswith(".lua") or file.filename.endswith(".txt")):
        await interaction.followup.send(
            embed=make_error_embed("Неверный формат", "Только `.lua` или `.txt`"),
            ephemeral=True,
        )
        return

    if file.size > MAX_FILE_SIZE:
        await interaction.followup.send(
            embed=make_error_embed("Файл слишком большой", f"Максимум: {fmt_size(MAX_FILE_SIZE)}"),
            ephemeral=True,
        )
        return

    try:
        raw = await file.read()
        code = raw.decode("utf-8")
    except UnicodeDecodeError:
        await interaction.followup.send(
            embed=make_error_embed("Ошибка кодировки", "Файл должен быть UTF-8."),
            ephemeral=True,
        )
        return

    if len(code) > MAX_CODE_SIZE:
        await interaction.followup.send(
            embed=make_error_embed(
                "Скрипт слишком большой",
                f"Максимум: {fmt_size(MAX_CODE_SIZE)}\nТвой файл: {fmt_size(len(code))}",
            ),
            ephemeral=True,
        )
        return

    seed = random.randint(0, 2**32 - 1)
    owner_id = interaction.user.id if is_owner(interaction) else None
    uname = username or interaction.user.display_name
    level_val = level.value

    print(f"\n[bot] ═══════════════════════════════════════════════")
    print(f"[bot] 🔄 START obfuscate: {file.filename}")
    print(f"[bot]    size={fmt_size(len(code))}, level={level_val}, seed={seed}")
    print(f"[bot]    user={interaction.user.name} ({interaction.user.id})")

    def _do_obfuscate():
        obf = Obfuscator(seed=seed, owner_id=owner_id, username=uname, verbose=True)
        result = obf.obfuscate(code, level=level_val)
        stats = obf.get_stats()
        build_id = obf.watermark.build_id if hasattr(obf, "watermark") else "????????"
        return result, stats, build_id

    t0 = time.perf_counter()
    try:
        loop = asyncio.get_running_loop()
        result, stats, build_id = await asyncio.wait_for(
            loop.run_in_executor(None, _do_obfuscate),
            timeout=120.0,
        )
    except asyncio.TimeoutError:
        print("[bot] ⏱ ТАЙМАУТ: > 120 сек")
        await interaction.followup.send(
            embed=make_error_embed("Таймаут", "Обфускация заняла > 2 минут."),
            ephemeral=True,
        )
        return
    except Exception as e:
        tb = traceback.format_exc()
        print(f"[bot] ❌ Ошибка:\n{tb}")
        await interaction.followup.send(
            embed=make_error_embed("Ошибка обфускации", f"```\n{str(e)[:400]}\n```"),
            ephemeral=True,
        )
        return

    elapsed_ms = (time.perf_counter() - t0) * 1000
    print(f"[bot] ✅ ГОТОВО за {elapsed_ms:.1f} мс → {fmt_size(len(result))}\n")

    shape_name = shape.value if shape else "none"
    shape_used = None

    if shape_name != "none":
        try:
            rng = random.Random(seed)
            if shape_name == "random":
                shape_name = get_random_mask_name(rng)
            result = shape_code(shape_name, rng=rng, real_code=result)
            shape_used = shape_name
        except Exception as e:
            print(f"[bot] ⚠️ Ошибка code_shaper ({shape_name}): {e}")

    input_size = stats.get("input_size", len(code))
    output_size = stats.get("output_size", len(result))
    stages = stats.get("stages", {})

    level_emoji = get_level_emoji(level_val)

    embed = discord.Embed(
        title="✅ Обфускация завершена!",
        color=COLOR_OK,
    )
    embed.add_field(name="📄 Файл", value=f"`{file.filename}`", inline=True)
    embed.add_field(name=f"{level_emoji} Уровень", value=f"`{level_val}`", inline=True)
    embed.add_field(name="⏱ Время", value=f"`{elapsed_ms:.1f} мс`", inline=True)
    embed.add_field(name="📥 Вход", value=f"`{fmt_size(input_size)}`", inline=True)
    embed.add_field(name="📤 Выход", value=f"`{fmt_size(output_size)}`", inline=True)
    embed.add_field(name="📊 Раздутость", value=f"`{fmt_ratio(input_size, output_size)}`", inline=True)
    embed.add_field(name="🔑 Build ID", value=f"`{build_id}`", inline=True)
    embed.add_field(name="👤 Owner", value=f"`{uname}`", inline=True)

    if level_val == "insane":
        embed.add_field(
            name="🧠 VM Protection",
            value="`-- @vm` функции будут завернуты в VM",
            inline=True,
        )

    if shape_used:
        shape_emoji = SHAPE_EMOJI_MAP.get(shape_used, "🎨")
        embed.add_field(name="🎨 Фигурка", value=f"{shape_emoji} `{shape_used}`", inline=True)

    if stages:
        stage_items = []

        if isinstance(stages, dict):
            stage_items = list(stages.items())
        elif isinstance(stages, list):
            for item in stages:
                if isinstance(item, dict):
                    name = item.get("name") or item.get("stage") or str(item)
                    tm = item.get("time_ms") or item.get("ms") or item.get("time") or 0
                    stage_items.append((name, tm))
                elif isinstance(item, (tuple, list)) and len(item) >= 2:
                    stage_items.append((item[0], item[1]))
                else:
                    stage_items.append((str(item), None))

        stages_text = "\n".join(
            f"✅ {k}: `{v:.1f} мс`" if isinstance(v, (int, float)) else f"✅ {k}"
            for k, v in stage_items[:12]
        )

        if stages_text:
            embed.add_field(name="📋 Стадии", value=stages_text, inline=False)

    embed.set_footer(
        text=f"NZL v{BOT_VERSION} • {DISCORD_LINK} • {interaction.user.display_name}"
    )

    out_name = f"nzl_{level_val}_{file.filename}"
    out_buffer = io.BytesIO(result.encode("utf-8"))

    await interaction.followup.send(
        embed=embed,
        file=discord.File(out_buffer, filename=out_name),
    )


# ── /deobfuscate ───────────────────────────────────────────────────────────────
# ── /deobfuscate ───────────────────────────────────────────────────────────────
@bot.tree.command(name="deobfuscate", description="Деобфусцировать Lua скрипт")
@app_commands.describe(
    file="Обфусцированный .lua или .txt файл",
    level="Уровень деобфускации",
)
@app_commands.choices(level=DEOBF_LEVEL_CHOICES)
async def cmd_deobfuscate(
    interaction: discord.Interaction,
    file: discord.Attachment,
    level: app_commands.Choice[str],
):
    await interaction.response.defer(thinking=True)

    allowed, reason = check_access(interaction)
    if not allowed:
        await interaction.followup.send(
            embed=make_error_embed("Нет доступа", reason), ephemeral=True)
        return

    if not (file.filename.endswith(".lua") or file.filename.endswith(".txt")):
        await interaction.followup.send(
            embed=make_error_embed("Неверный формат", "Только `.lua` или `.txt` файлы"),
            ephemeral=True)
        return

    if file.size > MAX_CODE_SIZE:
        await interaction.followup.send(
            embed=make_error_embed(
                "Файл слишком большой",
                f"Максимум: {fmt_size(MAX_CODE_SIZE)}\nТвой файл: {fmt_size(file.size)}",
            ), ephemeral=True)
        return

    try:
        raw = await file.read()
        source = decode_bytes(raw)
    except Exception as e:
        await interaction.followup.send(
            embed=make_error_embed("Ошибка чтения", str(e)), ephemeral=True)
        return

    level_val = level.value
    input_size = len(source)

    print(f"\n[bot] ═══════════════════════════════════════════════")
    print(f"[bot] 🔍 START deobfuscate: {file.filename}")
    print(f"[bot]    size={fmt_size(input_size)}, level={level_val}")
    print(f"[bot]    user={interaction.user.name} ({interaction.user.id})")

    # Warning для больших файлов
    if input_size > 100 * 1024:
        warn_embed = discord.Embed(
            title="⏳ Обрабатываю большой файл...",
            description=(
                f"**Файл:** `{file.filename}` ({fmt_size(input_size)})\n"
                f"**Уровень:** `{level_val}`\n\n"
                f"⚠️ Файл большой — может занять несколько минут.\n"
                f"Не закрывай Discord."
            ),
            color=COLOR_WARN,
        )
        progress_msg = await interaction.followup.send(embed=warn_embed)
    else:
        progress_msg = None

    def _do_deobfuscate():
        engine = DeobfuscatorEngine(level=level_val, verbose=False)
        return engine.deobfuscate(source)

    t0 = time.perf_counter()
    try:
        loop = asyncio.get_running_loop()
        # 10 минут для VM level, 5 минут для остальных
        timeout = 600.0 if level_val == "vm" else 300.0
        result, logs = await asyncio.wait_for(
            loop.run_in_executor(None, _do_deobfuscate),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        print(f"[bot] ⏱ ТАЙМАУТ деобфускации: > {timeout} сек")
        err_embed = make_error_embed(
            "Таймаут",
            f"Деобфускация заняла > {int(timeout/60)} минут.\n"
            f"Попробуй уровень `basic` для быстрой обработки."
        )
        if progress_msg:
            await progress_msg.edit(embed=err_embed)
        else:
            await interaction.followup.send(embed=err_embed, ephemeral=True)
        return
    except Exception as e:
        tb = traceback.format_exc()
        print(f"[bot] ❌ Ошибка деобфускации:\n{tb}")
        err_embed = make_error_embed("Ошибка деобфускации", f"```\n{str(e)[:400]}\n```")
        if progress_msg:
            await progress_msg.edit(embed=err_embed)
        else:
            await interaction.followup.send(embed=err_embed, ephemeral=True)
        return

    elapsed_ms = (time.perf_counter() - t0) * 1000
    output_size = len(result)
    reduction = round((1 - output_size / max(input_size, 1)) * 100, 1)

    print(f"[bot] ✅ ГОТОВО за {elapsed_ms:.1f} мс → {fmt_size(output_size)} (-{reduction}%)\n")

    clean_logs = [l for l in logs if l.strip()]
    log_text = "\n".join(clean_logs)
    if len(log_text) > 900:
        log_text = log_text[:900] + "\n... (обрезано)"

    deobf_level_emoji = {"basic": "🟢", "full": "🟡", "vm": "🔴"}.get(level_val, "⚙️")

    embed = discord.Embed(title="🔍 Деобфускация завершена!", color=COLOR_OK)
    embed.add_field(name="📄 Файл", value=f"`{file.filename}`", inline=True)
    embed.add_field(name=f"{deobf_level_emoji} Уровень", value=f"`{level_val}`", inline=True)
    embed.add_field(name="⏱ Время", value=f"`{elapsed_ms/1000:.1f} сек`", inline=True)
    embed.add_field(name="📥 Вход", value=f"`{fmt_size(input_size)}`", inline=True)
    embed.add_field(name="📤 Выход", value=f"`{fmt_size(output_size)}`", inline=True)
    embed.add_field(
        name="📊 Сжатие",
        value=f"`-{reduction}%`" if reduction > 0 else f"`+{abs(reduction)}%`",
        inline=True,
    )
    embed.add_field(name="📋 Pipeline лог", value=f"```\n{log_text}\n```", inline=False)
    embed.set_footer(
        text=f"NZL Deobfuscator v2.0 • {DISCORD_LINK} • {interaction.user.display_name}"
    )

    base = file.filename.rsplit(".", 1)[0]
    out_name = f"{base}_deobf_{level_val}.lua"
    out_buffer = io.BytesIO(result.encode("utf-8"))
    out_file = discord.File(out_buffer, filename=out_name)

    if progress_msg:
        await progress_msg.edit(embed=embed, attachments=[out_file])
    else:
        await interaction.followup.send(embed=embed, file=out_file)

    # ── Проверка доступа ──
    allowed, reason = check_access(interaction)
    if not allowed:
        await interaction.followup.send(
            embed=make_error_embed("Нет доступа", reason),
            ephemeral=True,
        )
        return

    # ── Проверка формата ──
    if not (file.filename.endswith(".lua") or file.filename.endswith(".txt")):
        await interaction.followup.send(
            embed=make_error_embed("Неверный формат", "Только `.lua` или `.txt` файлы"),
            ephemeral=True,
        )
        return

    if file.size > MAX_CODE_SIZE:
        await interaction.followup.send(
            embed=make_error_embed(
                "Файл слишком большой",
                f"Максимум: {fmt_size(MAX_CODE_SIZE)}\nТвой файл: {fmt_size(file.size)}",
            ),
            ephemeral=True,
        )
        return

    # ── Читаем файл ──
    try:
        raw = await file.read()
        source = decode_bytes(raw)
    except Exception as e:
        await interaction.followup.send(
            embed=make_error_embed("Ошибка чтения", str(e)),
            ephemeral=True,
        )
        return

    level_val = level.value
    input_size = len(source)

    print(f"\n[bot] ═══════════════════════════════════════════════")
    print(f"[bot] 🔍 START deobfuscate: {file.filename}")
    print(f"[bot]    size={fmt_size(input_size)}, level={level_val}")
    print(f"[bot]    user={interaction.user.name} ({interaction.user.id})")

    def _do_deobfuscate():
        engine = DeobfuscatorEngine(level=level_val, verbose=False)
        return engine.deobfuscate(source)

    t0 = time.perf_counter()
    try:
        loop = asyncio.get_running_loop()
        result, logs = await asyncio.wait_for(
            loop.run_in_executor(None, _do_deobfuscate),
            timeout=120.0,
        )
    except asyncio.TimeoutError:
        print("[bot] ⏱ ТАЙМАУТ деобфускации: > 120 сек")
        await interaction.followup.send(
            embed=make_error_embed("Таймаут", "Деобфускация заняла > 2 минут."),
            ephemeral=True,
        )
        return
    except Exception as e:
        tb = traceback.format_exc()
        print(f"[bot] ❌ Ошибка деобфускации:\n{tb}")
        await interaction.followup.send(
            embed=make_error_embed("Ошибка деобфускации", f"```\n{str(e)[:400]}\n```"),
            ephemeral=True,
        )
        return

    elapsed_ms = (time.perf_counter() - t0) * 1000
    output_size = len(result)
    reduction = round((1 - output_size / max(input_size, 1)) * 100, 1)

    print(f"[bot] ✅ ГОТОВО за {elapsed_ms:.1f} мс → {fmt_size(output_size)} (-{reduction}%)\n")

    # ── Форматируем лог ──
    clean_logs = [l for l in logs if l.strip()]
    log_text = "\n".join(clean_logs)
    if len(log_text) > 900:
        log_text = log_text[:900] + "\n... (обрезано)"

    # ── Embed ──
    deobf_level_emoji = {"basic": "🟢", "full": "🟡", "vm": "🔴"}.get(level_val, "⚙️")

    embed = discord.Embed(
        title="🔍 Деобфускация завершена!",
        color=COLOR_OK,
    )
    embed.add_field(name="📄 Файл", value=f"`{file.filename}`", inline=True)
    embed.add_field(name=f"{deobf_level_emoji} Уровень", value=f"`{level_val}`", inline=True)
    embed.add_field(name="⏱ Время", value=f"`{elapsed_ms:.1f} мс`", inline=True)
    embed.add_field(name="📥 Вход", value=f"`{fmt_size(input_size)}`", inline=True)
    embed.add_field(name="📤 Выход", value=f"`{fmt_size(output_size)}`", inline=True)
    embed.add_field(
        name="📊 Сжатие",
        value=f"`-{reduction}%`" if reduction > 0 else f"`+{abs(reduction)}%`",
        inline=True,
    )
    embed.add_field(name="📋 Pipeline лог", value=f"```\n{log_text}\n```", inline=False)
    embed.set_footer(
        text=f"NZL Deobfuscator v2.0 • {DISCORD_LINK} • {interaction.user.display_name}"
    )

    # ── Имя выходного файла (работает и с .lua и с .txt) ──
    base = file.filename.rsplit(".", 1)[0]
    out_name = f"{base}_deobf_{level_val}.lua"
    out_buffer = io.BytesIO(result.encode("utf-8"))

    await interaction.followup.send(
        embed=embed,
        file=discord.File(out_buffer, filename=out_name),
    )


# ── /settings ──────────────────────────────────────────────────────────────────
settings_group = app_commands.Group(
    name="settings",
    description="Настройки бота (только владелец)",
)


@settings_group.command(name="add_channel", description="Добавить разрешённый канал")
@app_commands.describe(channel="Канал, где бот будет работать")
async def sg_add_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    if not is_owner(interaction):
        await interaction.response.send_message("❌ Только владелец бота", ephemeral=True)
        return
    if channel.id in config["allowed_channels"]:
        await interaction.response.send_message(f"⚠️ Канал {channel.mention} уже в whitelist", ephemeral=True)
        return
    config["allowed_channels"].append(channel.id)
    save_config(config)
    await interaction.response.send_message(f"✅ Канал {channel.mention} добавлен", ephemeral=True)


@settings_group.command(name="remove_channel", description="Убрать канал из whitelist")
@app_commands.describe(channel="Канал для удаления")
async def sg_remove_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    if not is_owner(interaction):
        await interaction.response.send_message("❌ Только владелец бота", ephemeral=True)
        return
    if channel.id not in config["allowed_channels"]:
        await interaction.response.send_message(f"⚠️ Канала {channel.mention} нет в whitelist", ephemeral=True)
        return
    config["allowed_channels"].remove(channel.id)
    save_config(config)
    await interaction.response.send_message(f"✅ Канал {channel.mention} удалён", ephemeral=True)


@settings_group.command(name="clear_channels", description="Очистить whitelist каналов")
async def sg_clear_channels(interaction: discord.Interaction):
    if not is_owner(interaction):
        await interaction.response.send_message("❌ Только владелец бота", ephemeral=True)
        return
    config["allowed_channels"] = []
    save_config(config)
    await interaction.response.send_message("✅ Whitelist каналов очищен", ephemeral=True)


@settings_group.command(name="add_role", description="Добавить разрешённую роль")
@app_commands.describe(role="Роль, которая получит доступ")
async def sg_add_role(interaction: discord.Interaction, role: discord.Role):
    if not is_owner(interaction):
        await interaction.response.send_message("❌ Только владелец бота", ephemeral=True)
        return
    if role.id in config["allowed_roles"]:
        await interaction.response.send_message(f"⚠️ Роль {role.mention} уже в whitelist", ephemeral=True)
        return
    config["allowed_roles"].append(role.id)
    save_config(config)
    await interaction.response.send_message(f"✅ Роль {role.mention} добавлена", ephemeral=True)


@settings_group.command(name="remove_role", description="Убрать роль из whitelist")
@app_commands.describe(role="Роль для удаления")
async def sg_remove_role(interaction: discord.Interaction, role: discord.Role):
    if not is_owner(interaction):
        await interaction.response.send_message("❌ Только владелец бота", ephemeral=True)
        return
    if role.id not in config["allowed_roles"]:
        await interaction.response.send_message(f"⚠️ Роли {role.mention} нет в whitelist", ephemeral=True)
        return
    config["allowed_roles"].remove(role.id)
    save_config(config)
    await interaction.response.send_message(f"✅ Роль {role.mention} удалена", ephemeral=True)


@settings_group.command(name="clear_roles", description="Очистить whitelist ролей")
async def sg_clear_roles(interaction: discord.Interaction):
    if not is_owner(interaction):
        await interaction.response.send_message("❌ Только владелец бота", ephemeral=True)
        return
    config["allowed_roles"] = []
    save_config(config)
    await interaction.response.send_message("✅ Whitelist ролей очищен", ephemeral=True)


@settings_group.command(name="add_owner", description="Добавить со-владельца бота")
@app_commands.describe(user="Пользователь, которому дать права владельца")
async def sg_add_owner(interaction: discord.Interaction, user: discord.User):
    if not is_owner(interaction):
        await interaction.response.send_message("❌ Только владелец бота", ephemeral=True)
        return
    if user.id in config["owner_ids"]:
        await interaction.response.send_message(f"⚠️ {user.mention} уже владелец", ephemeral=True)
        return
    config["owner_ids"].append(user.id)
    save_config(config)
    await interaction.response.send_message(f"👑 {user.mention} теперь со-владелец", ephemeral=True)


@settings_group.command(name="remove_owner", description="Убрать со-владельца")
@app_commands.describe(user="Пользователь для удаления из владельцев")
async def sg_remove_owner(interaction: discord.Interaction, user: discord.User):
    if not is_owner(interaction):
        await interaction.response.send_message("❌ Только владелец бота", ephemeral=True)
        return
    if user.id not in config["owner_ids"]:
        await interaction.response.send_message(f"⚠️ {user.mention} не владелец", ephemeral=True)
        return
    if len(config["owner_ids"]) <= 1:
        await interaction.response.send_message("❌ Нельзя удалить последнего владельца!", ephemeral=True)
        return
    config["owner_ids"].remove(user.id)
    save_config(config)
    await interaction.response.send_message(f"✅ {user.mention} больше не владелец", ephemeral=True)


@settings_group.command(name="show", description="Показать текущие настройки")
async def sg_show(interaction: discord.Interaction):
    if not is_owner(interaction):
        await interaction.response.send_message("❌ Только владелец бота", ephemeral=True)
        return

    embed = discord.Embed(title="⚙️ Настройки бота", color=COLOR_OWNER)

    if config["allowed_channels"]:
        ch_text = "\n".join(f"• <#{c}>" for c in config["allowed_channels"])
    else:
        ch_text = "*Все каналы разрешены*"
    embed.add_field(name="📺 Каналы", value=ch_text, inline=False)

    if config["allowed_roles"]:
        ro_text = "\n".join(f"• <@&{r}>" for r in config["allowed_roles"])
    else:
        ro_text = "*Все роли разрешены*"
    embed.add_field(name="👥 Роли", value=ro_text, inline=False)

    if config.get("owner_ids"):
        ow_text = "\n".join(f"• <@{o}>" for o in config["owner_ids"])
    else:
        ow_text = "*Не установлены*"
    embed.add_field(name="👑 Владельцы", value=ow_text, inline=False)

    embed.set_footer(text=f"NZL Obfuscator v{BOT_VERSION}")
    await interaction.response.send_message(embed=embed, ephemeral=True)


bot.tree.add_command(settings_group)


# ── Запуск ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    bot.run(TOKEN)

# -- Sprint 7 tools (slice 2e-1): /moonsec /wdmap /coverage --
# loaded by path so `py bot\bot.py` (script-style launch) works too
import importlib.util as _ilu
_s7p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sprint7.py")
_s7spec = _ilu.spec_from_file_location("nzl_sprint7", _s7p)
_s7 = _ilu.module_from_spec(_s7spec)
_s7spec.loader.exec_module(_s7)
_s7.register_sprint7(bot, globals())
