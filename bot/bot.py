"""
NZL Studio Obfuscator — Discord Bot
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

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

print("[bot] Loading obfuscator...")
from obfuscator.engine import Obfuscator

# Warm up
try:
    _w = Obfuscator(seed=1)
    _w.obfuscate("print(1)")
    print("[bot] Ready!")
except Exception as e:
    print(f"[bot] Warm-up error: {e}")

# Config
_secret = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bot_secret.json")
TOKEN = ""
GUILD_ID = 1123677106799394888
if os.path.exists(_secret):
    with open(_secret, "r") as f:
        s = json.load(f)
    TOKEN = s.get("token", "")
    GUILD_ID = int(s.get("guild_id", GUILD_ID))
if not TOKEN:
    print("[bot] ERROR: no token!")
    raise SystemExit(1)

MAX_SIZE = 25 * 1024 * 1024
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    print(f"Bot {bot.user} ready! Servers: {len(bot.guilds)}")
    try:
        guild = discord.Object(id=GUILD_ID)
        bot.tree.copy_global_to(guild=guild)
        await bot.tree.sync(guild=guild)
    except Exception as e:
        print(f"Sync error: {e}")


@bot.tree.command(name="ping", description="Check bot")
async def cmd_ping(interaction: discord.Interaction):
    ms = round(bot.latency * 1000)
    embed = discord.Embed(title="🏓 Pong!", description=f"Latency: `{ms} ms`", color=0x00FF88)
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="obfuscate", description="Obfuscate Lua script")
@app_commands.describe(file="Attach .lua or .txt file")
async def cmd_obfuscate(interaction: discord.Interaction, file: discord.Attachment):
    await interaction.response.defer(thinking=True)

    if not (file.filename.endswith(".lua") or file.filename.endswith(".txt")):
        await interaction.followup.send(
            embed=discord.Embed(title="❌ Wrong format", description="Only `.lua` or `.txt`", color=0xFF4444),
            ephemeral=True)
        return

    if file.size > MAX_SIZE:
        await interaction.followup.send(
            embed=discord.Embed(title="❌ Too large", description=f"Max: {MAX_SIZE//1024//1024}MB", color=0xFF4444),
            ephemeral=True)
        return

    try:
        raw = await file.read()
        code = raw.decode("utf-8")
    except UnicodeDecodeError:
        code = raw.decode("cp1251", errors="replace")

    seed = random.randint(0, 2**32 - 1)
    print(f"\n[bot] Obfuscating: {file.filename} ({len(code)} bytes)")

    def _do():
        obf = Obfuscator(seed=seed)
        return obf.obfuscate(code)

    t0 = time.perf_counter()
    try:
        loop = asyncio.get_running_loop()
        result = await asyncio.wait_for(loop.run_in_executor(None, _do), timeout=300.0)
    except asyncio.TimeoutError:
        await interaction.followup.send(
            embed=discord.Embed(title="❌ Timeout", description="Took > 5 minutes", color=0xFF4444),
            ephemeral=True)
        return
    except Exception as e:
        tb = traceback.format_exc()
        print(f"[bot] Error:\n{tb}")
        await interaction.followup.send(
            embed=discord.Embed(title="❌ Error", description=f"```\n{str(e)[:400]}\n```", color=0xFF4444),
            ephemeral=True)
        return

    elapsed = (time.perf_counter() - t0) * 1000
    print(f"[bot] Done: {len(code)} → {len(result)} bytes in {elapsed:.0f}ms")

    embed = discord.Embed(title="✅ Obfuscated!", color=0x00FF88)
    embed.add_field(name="📄 File", value=f"`{file.filename}`", inline=True)
    embed.add_field(name="⏱ Time", value=f"`{elapsed:.0f} ms`", inline=True)
    embed.add_field(name="📥 Input", value=f"`{len(code):,} bytes`", inline=True)
    embed.add_field(name="📤 Output", value=f"`{len(result):,} bytes`", inline=True)
    embed.add_field(name="📊 Ratio", value=f"`{len(result)/max(1,len(code)):.1f}x`", inline=True)
    embed.set_footer(text=f"NZL Obfuscator • {interaction.user.display_name}")

    buf = io.BytesIO(result.encode("utf-8"))
    await interaction.followup.send(
        embed=embed,
        file=discord.File(buf, filename=f"nzl_{file.filename}"))


if __name__ == "__main__":
    bot.run(TOKEN)
