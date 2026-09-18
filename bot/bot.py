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
from obfuscator.deobfuscator.engine import DeobfuscatorEngine  # v3.0 REAL

# Прогрев — прогоняем пустышку, чтобы все ленивые импорты сработали
try:
    _warm = Obfuscator(seed=1, verbose=False)
    _warm.obfuscate("local x = 1\nprint(x)", level="medium")
    print(f"[bot] ✅ Прогрев завершён за {(time.perf_counter() - _t_import) * 1000:.0f} мс")
except Exception as _e:
    print(f"[bot] ⚠️ Ошибка прогрева: {_e}")

# ── Константы ──────────────────────────────────────────────────────────────────
# Secrets live OUTSIDE git: env var -> bot/bot_secret.json -> empty.
# bot.py itself never contains a real token (repo is public).
def _nzl_secrets() -> dict:
    try:
        with open(os.path.join(os.path.dirname(__file__), "bot_secret.json"),
                  encoding="utf-8-sig") as _f:
            return json.load(_f)
    except Exception:
        return {}


_nzl_sec = _nzl_secrets()
TOKEN = str(os.environ.get("NZL_DISCORD_TOKEN") or _nzl_sec.get("token") or "").strip()
GUILD_ID = str(os.environ.get("NZL_GUILD_ID") or _nzl_sec.get("guild_id") or "").strip()
if not TOKEN:
    print("=" * 60)
    print("\u041d\u0435\u0442 \u0442\u043e\u043a\u0435\u043d\u0430! \u0421\u043e\u0437\u0434\u0430\u0439 \u0444\u0430\u0439\u043b bot\\bot_secret.json:")
    print('  {"token": "\u0422\u041e\u041a\u0415\u041d", "guild_id": "ID_\u0421\u0415\u0420\u0412\u0415\u0420\u0410"}')
    print("\u0422\u043e\u043a\u0435\u043d: Discord Developer Portal -> Bot -> Reset Token -> Copy")
    print("ID \u0441\u0435\u0440\u0432\u0435\u0440\u0430: \u0412\u043a\u043b\u044e\u0447\u0438 \u0420\u0435\u0436\u0438\u043c \u0440\u0430\u0437\u0440\u0430\u0431\u043e\u0442\u0447\u0438\u043a\u0430, \u041f\u041a\u041c \u043f\u043e \u0441\u0435\u0440\u0432\u0435\u0440\u0443 -> \u041a\u043e\u043f\u0438\u0440\u043e\u0432\u0430\u0442\u044c ID")
    print("=" * 60)
    raise SystemExit(1)
if not GUILD_ID:
    print("\u041d\u0435\u0442 GUILD_ID! \u0414\u043e\u0431\u0430\u0432\u044c \u0432 bot\\bot_secret.json \u043f\u043e\u043b\u0435 \"guild_id\".")
    raise SystemExit(1)
GUILD_ID = int(GUILD_ID)
BOT_VERSION = "1.2"

COLOR_OK = 0x00FF88
COLOR_ERR = 0xFF4444
COLOR_INFO = 0x0099FF
COLOR_WARN = 0xFFAA00
COLOR_OWNER = 0x9B59B6

MAX_FILE_SIZE = 25 * 1024 * 1024
MAX_CODE_SIZE = 5 * 2000 * 2000

SINGLE_LEVEL = "insane"
SINGLE_USERNAME = "NZL Studio"

DEOBF_LEVEL_CHOICES = [
    app_commands.Choice(name="🟢 Basic  — убрать мусор (любой Lua)", value="basic"),
    app_commands.Choice(name="🟡 Full   — + расшифровать строки (NZL)", value="full"),
    app_commands.Choice(name="🔴 VM     — + декомпилировать VM (NZL insane)", value="vm"),
]

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


# ── /obfuscate ─────────────────────────────────────────────────────────────────
@bot.tree.command(name="obfuscate", description="Обфусцировать Lua/Luau скрипт")
@app_commands.describe(file="Прикрепи .lua или .txt файл")
async def cmd_obfuscate(
    interaction: discord.Interaction,
    file: discord.Attachment,
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
    uname = SINGLE_USERNAME
    level_val = SINGLE_LEVEL

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
            timeout=300.0,
        )
    except asyncio.TimeoutError:
        print("[bot] ⏱ ТАЙМАУТ: > 300 сек")
        await interaction.followup.send(
            embed=make_error_embed("Таймаут", "Обфускация заняла > 5 минут."),
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

    input_size = stats.get("input_size", len(code))
    output_size = stats.get("output_size", len(result))
    stages = stats.get("stages", {})

    embed = discord.Embed(
        title="✅ Обфускация завершена!",
        color=COLOR_OK,
    )
    embed.add_field(name="📄 Файл", value=f"`{file.filename}`", inline=True)
    embed.add_field(name="🔥 Профиль", value=f"`{SINGLE_LEVEL} • максимум`", inline=True)
    embed.add_field(name="⏱ Время", value=f"`{elapsed_ms:.1f} мс`", inline=True)
    embed.add_field(name="📥 Вход", value=f"`{fmt_size(input_size)}`", inline=True)
    embed.add_field(name="📤 Выход", value=f"`{fmt_size(output_size)}`", inline=True)
    embed.add_field(name="📊 Раздутость", value=f"`{fmt_ratio(input_size, output_size)}`", inline=True)
    embed.add_field(name="🔑 Build ID", value=f"`{build_id}`", inline=True)

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
        text=f"NZL v{BOT_VERSION} • {DISCORD_LINK}"
    )

    out_name = f"nzl_{file.filename}"
    out_buffer = io.BytesIO(result.encode("utf-8"))

    await interaction.followup.send(
        embed=embed,
        file=discord.File(out_buffer, filename=out_name),
    )


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
        auto = _s7.deobf_auto(source)
        if auto is not None:
            return {'kind': auto[0], 'text': auto[1], 'info': auto[2]}
        engine = DeobfuscatorEngine(level=level_val, verbose=False)
        result, logs = engine.deobfuscate(source)
        return {'kind': 'engine', 'text': result,
                'info': '\n'.join([l for l in logs if l.strip()])}

    t0 = time.perf_counter()
    try:
        loop = asyncio.get_running_loop()
        # 10 минут для VM level, 5 минут для остальных
        timeout = 600.0 if level_val == "vm" else 300.0
        out = await asyncio.wait_for(
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
    kind = out['kind']
    text = out['text']
    info_text = out['info']
    output_size = len(text)
    reduction = round((1 - output_size / max(input_size, 1)) * 100, 1)

    print(f"[bot] ✅ ГОТОВО за {elapsed_ms:.1f} мс → {fmt_size(output_size)} (-{reduction}%)\n")

    clean_logs = [l for l in info_text.splitlines() if l.strip()]
    log_text = "\n".join(clean_logs)
    if len(log_text) > 900:
        log_text = log_text[:900] + "\n... (обрезано)"

    deobf_level_emoji = {"basic": "🟢", "full": "🟡", "vm": "🔴"}.get(level_val, "⚙️")

    _titles = {'moonsec': '🌙 MoonSec V3 — декомпиляция готова!',
               'wearedevs': '🗺️ WeAreDevs — программа восстановлена!',
               'engine': '🔍 Деобфускация завершена!'}
    embed = discord.Embed(title=_titles.get(kind, '🔍 Деобфускация завершена!'), color=COLOR_OK)
    embed.add_field(name="📄 Файл", value=f"`{file.filename}`", inline=True)
    disp = kind if kind != 'engine' else level_val
    embed.add_field(name=f"{deobf_level_emoji} Уровень", value=f"`{disp}`", inline=True)
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
    _suffix = {'moonsec': '_moonsec', 'wearedevs': '_wd'}.get(kind, '_deobf_' + level_val)
    out_name = f"{base}{_suffix}.lua"
    out_buffer = io.BytesIO(result.encode("utf-8"))
    out_file = discord.File(out_buffer, filename=out_name)

    if progress_msg:
        await progress_msg.edit(embed=embed, attachments=[out_file])
    else:
        await interaction.followup.send(embed=embed, file=out_file)

# -- Sprint 7 tools (slices 2e-1..2e-4): family auto-detect inside /deobfuscate --
# loaded by path so `py bot\bot.py` (script-style launch) works too
import importlib.util as _ilu
_s7p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sprint7.py")
_s7spec = _ilu.spec_from_file_location("nzl_sprint7", _s7p)
_s7 = _ilu.module_from_spec(_s7spec)
_s7spec.loader.exec_module(_s7)

# ── Запуск ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    bot.run(TOKEN)

