"""Sprint-7 decompiler commands for the NZL Discord bot (slice 2e-1).

Adds three slash commands WITHOUT touching any existing bot code:

* ``/moonsec  file [struct]`` -- MoonSec V3 -> readable Lua
  (one-command chain, slice 2b-11/2b-12);
* ``/wdmap    file``          -- WeAreDevs closure map of the flattened
  program (495 closures, per-closure BFS, slice 2c-5);
* ``/coverage``               -- Sprint 7 coverage panel, live metrics
  (slice 2d-1).

The bot wires them with (appended at the end of bot/bot.py)::

    from bot.sprint7 import register_sprint7
    register_sprint7(bot, globals())

``register_sprint7(bot, g)`` pulls the bot's own helpers (check_access,
embed builders, fmt_size, decode_bytes, colors) from ``g`` so the new
commands behave exactly like the built-in ones.  Heavy work runs in the
executor with generous timeouts (the tools are seconds-fast on real
samples).  The core functions below are discord-free, so ``--test``
runs head-less:

    py -m bot.sprint7 --test
"""

import io
import os
import sys
import time

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

_SAMPLES = os.path.join(_REPO_ROOT, 'obfuscator', 'deobfuscator', 'samples')


# --------------------------------------------------------------------------- #
# discord-free core (unit-testable)
# --------------------------------------------------------------------------- #

def run_moonsec(src, struct=True):
    """MoonSec V3 decompile -> (stats_lines, lua_text)."""
    from obfuscator.deobfuscator.moonsec.decompile import decompile_source
    text, _stats, info = decompile_source(src, structured=struct)
    lines = ['blob=%d chars ; seed=%s ; consumed %d/%d (%.1f%%)'
             % (info['blob_chars'], info['seed'], info['consumed'],
                info['total'], info['consume_pct']),
             'protos=%d ; slots=%d ; macros=%d ; dead=%d (%.1f%%) ; filler(op24)=%d'
             % (info['protos'], info['slots'], info['macros'], info['dead'],
                100.0 * info['dead'] / max(1, info['slots']), info['filler'])]
    if struct and 'struct' in info:
        st = info['struct']
        lines.append('structured: if=%d ifelse=%d ifret=%d repeat=%d ; fallback gotos=%d'
                     % (st.get('if', 0), st.get('ifelse', 0), st.get('ifret', 0),
                        st.get('repeat', 0), st.get('goto', 0)))
    return lines, text


def run_coverage():
    """Coverage panel -> (families_line, overall_pct, markdown)."""
    from obfuscator.deobfuscator.coverage_panel import build_panel, render_md
    panel = build_panel()
    md = render_md(panel)
    fams = []
    for f in panel['families']:
        cov = f['coverage']
        fams.append('%s=%s' % (f['family'].split()[0],
                               ('%.1f%%' % cov) if cov is not None else 'n/a'))
    return ', '.join(fams), panel['overall'], md


def run_wdmap(src):
    """WeAreDevs closure map -> (report_lines, closures_json_dict)."""
    from obfuscator.deobfuscator.wearedevs.dispatch_map import extract_entry
    from obfuscator.deobfuscator.wearedevs.closures import build_closure_map
    _fn, main_state = extract_entry(src)
    res = build_closure_map(src, main_state=main_state)
    cls = res['closures']
    reg = sorted(((int(st), e['regions']) for st, e in cls.items()),
                 key=lambda kv: -kv[1])
    total_regions = sum(e['regions'] for e in cls.values())
    lines = ['creations=%d ; closures=%d ; main=%s (%d regions)'
             % (res['creations'], len(cls), main_state,
                cls.get(main_state, {}).get('regions', 0)),
             'tree partition: %d/%d leaves (%.1f%%)'
             % (total_regions, res['n_leaves'],
                100.0 * total_regions / max(1, res['n_leaves'])),
             'biggest: ' + ', '.join('%d@%d' % (r, st) for st, r in reg[:8])]
    out = {'creations': res['creations'], 'main': main_state,
           'closures': {str(st): e for st, e in cls.items()}}
    return lines, out


# --------------------------------------------------------------------------- #
# head-less self-test on the in-repo real samples
# --------------------------------------------------------------------------- #

def _selftest():
    fails = []

    def chk(tag, cond, extra=''):
        print(('[OK] ' if cond else '[XX] ') + tag + (' ' + extra if extra else ''))
        if not cond:
            fails.append(tag)

    with open(os.path.join(_SAMPLES, 'other', 'moonsec_v3.lua'),
              encoding='utf-8', errors='replace') as f:
        ms = f.read()
    t0 = time.perf_counter()
    lines, text = run_moonsec(ms, struct=True)
    dt = time.perf_counter() - t0
    joined = '\n'.join(lines)
    chk('T1 moonsec core', 'protos=14' in joined and 'consumed 6843/6843' in joined
        and 'structured:' in joined and len(text) > 5000,
        '%.1fs' % dt)

    t0 = time.perf_counter()
    fams, overall, md = run_coverage()
    dt = time.perf_counter() - t0
    chk('T2 coverage core', overall > 90.0 and 'MoonVeil' in md and 'n/a' in md,
        'overall=%.1f%% %.1fs | %s' % (overall, dt, fams))

    with open(os.path.join(_SAMPLES, 'other', 'wearedevs.lua'),
              encoding='utf-8', errors='replace') as f:
        wd = f.read()
    t0 = time.perf_counter()
    lines, out = run_wdmap(wd)
    dt = time.perf_counter() - t0
    joined = '\n'.join(lines)
    chk('T3 wdmap core', 'closures=495' in joined and '99.8%' in joined
        and len(out['closures']) == 495, '%.1fs' % dt)

    print('')
    print('Result: %d/3' % (3 - len(fails)))
    if fails:
        print('[XX] FAILURES: %d' % len(fails))
        return 1
    print('[OK] ALL PASSED')
    return 0


# --------------------------------------------------------------------------- #
# discord wiring (lazy discord import -- keeps --test head-less)
# --------------------------------------------------------------------------- #

def register_sprint7(bot, g):
    import discord
    from discord import app_commands

    check_access = g['check_access']
    make_error_embed = g['make_error_embed']
    fmt_size = g['fmt_size']
    decode_bytes = g['decode_bytes']
    config = g['config']
    COLOR_OK = g['COLOR_OK']
    COLOR_ERR = g['COLOR_ERR']
    COLOR_INFO = g['COLOR_INFO']
    DISCORD_LINK = g['DISCORD_LINK']
    BOT_VERSION = g['BOT_VERSION']

    MAX_CODE_SIZE = g['MAX_CODE_SIZE']

    def _access_or_fail(interaction):
        allowed, reason = check_access(interaction)
        if not allowed:
            raise PermissionError(reason)
        return True

    async def _read_src(interaction, file):
        _access_or_fail(interaction)
        if not (file.filename.endswith('.lua') or file.filename.endswith('.txt')):
            raise ValueError('Только `.lua` или `.txt` файлы')
        if file.size > MAX_CODE_SIZE:
            raise ValueError('Файл слишком большой: максимум %s, твой %s'
                             % (fmt_size(MAX_CODE_SIZE), fmt_size(file.size)))
        raw = await file.read()
        return decode_bytes(raw)

    async def _in_executor(fn, timeout):
        import asyncio
        loop = asyncio.get_running_loop()
        return await asyncio.wait_for(loop.run_in_executor(None, fn),
                                      timeout=timeout)

    # ------------------------- /moonsec ---------------------------------- #
    @bot.tree.command(name='moonsec',
                      description='MoonSec V3: декомпиляция в читаемый Lua')
    @app_commands.describe(
        file='Обфусцированный MoonSec .lua/.txt',
        struct='Структурные ветвления if/else/repeat (по умолчанию вкл)',
    )
    async def cmd_moonsec(interaction: discord.Interaction,
                          file: discord.Attachment, struct: bool = True):
        await interaction.response.defer(thinking=True)
        try:
            src = await _read_src(interaction, file)
        except PermissionError as e:
            await interaction.followup.send(
                embed=make_error_embed('Нет доступа', str(e)), ephemeral=True)
            return
        except ValueError as e:
            await interaction.followup.send(
                embed=make_error_embed('Неверный файл', str(e)), ephemeral=True)
            return
        except Exception as e:  # noqa: BLE001
            await interaction.followup.send(
                embed=make_error_embed('Ошибка чтения', str(e)), ephemeral=True)
            return

        t0 = time.perf_counter()
        try:
            lines, text = await _in_executor(lambda: run_moonsec(src, struct), 120.0)
        except Exception as e:  # noqa: BLE001
            tb = g['traceback'].format_exc()
            print('[bot] ❌ moonsec:\\n' + tb)
            await interaction.followup.send(
                embed=make_error_embed(
                    'MoonSec: не декомпилировано',
                    'Файл не похож на MoonSec V3 или цепочка упала:\\n```\\n'
                    + str(e)[:400] + '\\n```'),
                ephemeral=True)
            return
        dt = time.perf_counter() - t0

        embed = discord.Embed(title='🌙 MoonSec V3 — декомпиляция готова',
                              color=COLOR_OK)
        embed.add_field(name='📄 Файл', value='`%s`' % file.filename, inline=True)
        embed.add_field(name='⏱ Время', value='`%.1f сек`' % dt, inline=True)
        embed.add_field(name='📥 Вход', value='`%s`' % fmt_size(len(src)), inline=True)
        embed.add_field(name='📤 Выход', value='`%s`' % fmt_size(len(text)), inline=True)
        embed.add_field(name='📋 Статистика',
                        value='```\n' + '\n'.join(lines)[:900] + '\n```',
                        inline=False)
        embed.set_footer(text='NZL Sprint7 v%s • %s • %s'
                         % (BOT_VERSION, DISCORD_LINK,
                            interaction.user.display_name))
        base = file.filename.rsplit('.', 1)[0]
        await interaction.followup.send(
            embed=embed,
            file=discord.File(io.BytesIO(text.encode('utf-8')),
                              filename=base + '_moonsec_decompiled.lua'))

    # ------------------------- /wdmap ------------------------------------ #
    @bot.tree.command(name='wdmap',
                      description='WeAreDevs: карта замыканий flattened-программы')
    @app_commands.describe(file='WeAreDevs-обфусцированный .lua/.txt')
    async def cmd_wdmap(interaction: discord.Interaction,
                        file: discord.Attachment):
        await interaction.response.defer(thinking=True)
        try:
            src = await _read_src(interaction, file)
        except PermissionError as e:
            await interaction.followup.send(
                embed=make_error_embed('Нет доступа', str(e)), ephemeral=True)
            return
        except ValueError as e:
            await interaction.followup.send(
                embed=make_error_embed('Неверный файл', str(e)), ephemeral=True)
            return
        except Exception as e:  # noqa: BLE001
            await interaction.followup.send(
                embed=make_error_embed('Ошибка чтения', str(e)), ephemeral=True)
            return

        t0 = time.perf_counter()
        try:
            lines, out = await _in_executor(lambda: run_wdmap(src), 240.0)
        except Exception as e:  # noqa: BLE001
            tb = g['traceback'].format_exc()
            print('[bot] ❌ wdmap:\\n' + tb)
            await interaction.followup.send(
                embed=make_error_embed(
                    'WeAreDevs: карта не построена',
                    'Файл не похож на WeAreDevs v1 или анализ упал:\\n```\\n'
                    + str(e)[:400] + '\\n```'),
                ephemeral=True)
            return
        dt = time.perf_counter() - t0

        embed = discord.Embed(
            title='🗺️ WeAreDevs — карта замыканий готова', color=COLOR_OK)
        embed.add_field(name='📄 Файл', value='`%s`' % file.filename, inline=True)
        embed.add_field(name='⏱ Время', value='`%.1f сек`' % dt, inline=True)
        embed.add_field(name='📊 Разбор',
                        value='```\n' + '\n'.join(lines)[:900] + '\n```',
                        inline=False)
        embed.set_footer(text='NZL Sprint7 v%s • %s • %s'
                         % (BOT_VERSION, DISCORD_LINK,
                            interaction.user.display_name))
        await interaction.followup.send(
            embed=embed,
            file=discord.File(io.BytesIO(
                g['json'].dumps(out, ensure_ascii=False, indent=1).encode('utf-8')),
                filename='wd_closures.json'))

    # ------------------------- /coverage --------------------------------- #
    @bot.tree.command(name='coverage',
                      description='Sprint 7: панель покрытия (живые метрики)')
    async def cmd_coverage(interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        try:
            _access_or_fail(interaction)
        except PermissionError as e:
            await interaction.followup.send(
                embed=make_error_embed('Нет доступа', str(e)), ephemeral=True)
            return
        t0 = time.perf_counter()
        try:
            fams, overall, md = await _in_executor(run_coverage, 300.0)
        except Exception as e:  # noqa: BLE001
            tb = g['traceback'].format_exc()
            print('[bot] ❌ coverage:\\n' + tb)
            await interaction.followup.send(
                embed=make_error_embed('Панель покрытия', str(e)[:400]),
                ephemeral=True)
            return
        dt = time.perf_counter() - t0

        embed = discord.Embed(title='📏 Панель покрытия Sprint 7', color=COLOR_INFO)
        embed.add_field(name='⏱ Время', value='`%.1f сек`' % dt, inline=True)
        embed.add_field(name='🏆 Overall',
                        value='`%.1f%%` (baseline ~15%%)' % overall, inline=True)
        embed.add_field(name='Семейства', value='`' + fams + '`', inline=False)
        embed.set_footer(text='NZL Sprint7 v%s • %s • %s'
                         % (BOT_VERSION, DISCORD_LINK,
                            interaction.user.display_name))
        await interaction.followup.send(
            embed=embed,
            file=discord.File(io.BytesIO(md.encode('utf-8')),
                              filename='coverage.md'))

    names = ['moonsec', 'wdmap', 'coverage']
    print('[bot] Sprint-7 команды зарегистрированы: ' + ', '.join('/' + n for n in names))
    return names


if __name__ == '__main__':
    sys.exit(_selftest())
