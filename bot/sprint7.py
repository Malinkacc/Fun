"""Sprint-7 deobfuscation core for the NZL Discord bot (slices 2e-1..2e-4).

The bot exposes ONLY three slash commands: /obfuscate, /deobfuscate,
/ping.  Family detection lives INSIDE /deobfuscate via deobf_auto():

* MoonSec V3 -> full chain decompile (bytecode stream consumed 100%,
  readable Lua, structured control flow where the CFG proves it);
* WeAreDevs  -> flattened-program block lift (every leaf rendered as
  readable pseudo-Lua with decoded names) + closure creations count;
* anything else -> None (the bot falls back to its own engine pipeline).

The core below is discord-free and runs head-less on the in-repo real
samples:

    py -m bot.sprint7 --test
"""

import os
import sys
import time

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

_SAMPLES = os.path.join(_REPO_ROOT, 'obfuscator', 'deobfuscator', 'samples')


def _moonsec_stats(info):
    lines = ['blob=%d chars ; seed=%s ; consumed %d/%d (%.1f%%)'
             % (info['blob_chars'], info['seed'], info['consumed'],
                info['total'], info['consume_pct']),
             'protos=%d ; slots=%d ; macros=%d ; dead=%d (%.1f%%) ; filler(op24)=%d'
             % (info['protos'], info['slots'], info['macros'], info['dead'],
                100.0 * info['dead'] / max(1, info['slots']), info['filler'])]
    st = info.get('struct')
    if st:
        lines.append('structured: if=%d ifelse=%d ifret=%d repeat=%d ; fallback gotos=%d'
                     % (st.get('if', 0), st.get('ifelse', 0), st.get('ifret', 0),
                        st.get('repeat', 0), st.get('goto', 0)))
    return lines


def run_moonsec(src, struct=True):
    """MoonSec V3 decompile -> (stats_lines, lua_text)."""
    from obfuscator.deobfuscator.moonsec.decompile import decompile_source
    text, _stats, info = decompile_source(src, structured=struct)
    return _moonsec_stats(info), text


def run_coverage():
    """Coverage panel -> (families_line, overall_pct, markdown)."""
    from obfuscator.deobfuscator.coverage_panel import build_panel, render_md
    panel = build_panel()
    md = render_md(panel)
    fams = ', '.join(
        '%s=%s' % (f['family'].split()[0],
                   ('%.1f%%' % f['coverage']) if f['coverage'] is not None else 'n/a')
        for f in panel['families'])
    return fams, panel['overall'], md


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


def deobf_auto(src):
    """Auto-detect a sprint-7 family.  Returns (kind, text, info) or None.

    kind = 'moonsec' | 'wearedevs'.  Non-members (Luraph, NZL, plain
    scripts) return None so the bot can use its own engine pipeline."""
    # ---- MoonSec V3: the exact chain, refuses anything else ----
    try:
        from obfuscator.deobfuscator.moonsec.decompile import decompile_source
        text, _stats, info = decompile_source(src, structured=True)
    except Exception:
        text = None
    if text is not None and info.get('consume_pct', 0.0) >= 90.0:
        return ('moonsec', text, '\n'.join(_moonsec_stats(info)))
    # ---- WeAreDevs: header marker + block lift ----
    if 'wearedevs.net/obfuscator' in src[:4000].lower():
        from obfuscator.deobfuscator.wearedevs.block_lift import lift
        from obfuscator.deobfuscator.wearedevs.closures import collect_creations
        from obfuscator.deobfuscator.wearedevs.dispatch_map import analyze_source
        res = lift(src)
        info = analyze_source(src)
        creations = collect_creations(src, info)
        lines = ['blocks rendered: %d/%d leaves ; name sites decoded: %d'
                 % (res['rendered'], res['leaves'], res['m_subs']),
                 'closure creations: %d (direct maker calls)' % len(creations)]
        return ('wearedevs', '\n'.join(res['lines']), '\n'.join(lines))
    return None


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
        and 'structured:' in joined and len(text) > 5000, '%.1fs' % dt)

    t0 = time.perf_counter()
    fams, overall, md = run_coverage()
    dt = time.perf_counter() - t0
    chk('T2 coverage core', overall > 90.0 and 'MoonVeil' in md and 'n/a' in md,
        'overall=%.1f%% %.1fs | %s' % (overall, dt, fams))

    t0 = time.perf_counter()
    kind, wtext, winfo = deobf_auto(ms)
    dt = time.perf_counter() - t0
    chk('T3 deobf_auto -> moonsec', kind == 'moonsec' and 'protos=14' in winfo
        and len(wtext) > 5000, '%.1fs' % dt)

    with open(os.path.join(_SAMPLES, 'other', 'wearedevs.lua'),
              encoding='utf-8', errors='replace') as f:
        wd = f.read()
    t0 = time.perf_counter()
    kind, btext, binfo = deobf_auto(wd)
    dt = time.perf_counter() - t0
    chk('T4 deobf_auto -> wearedevs', kind == 'wearedevs'
        and 'blocks rendered: 3362/3362' in binfo
        and 'closure creations: 494' in binfo and len(btext) > 100000,
        '%.1fs' % dt)

    with open(os.path.join(_SAMPLES, 'luraph', 'v14.6_sample1.lua'),
              encoding='utf-8', errors='replace') as f:
        lp = f.read()
    t0 = time.perf_counter()
    kind = deobf_auto(lp)
    dt = time.perf_counter() - t0
    chk('T5 deobf_auto -> None on Luraph', kind is None, '%.1fs' % dt)

    t0 = time.perf_counter()
    lines, out = run_wdmap(wd)
    dt = time.perf_counter() - t0
    joined = '\n'.join(lines)
    chk('T6 wdmap core', 'closures=495' in joined and '99.8%' in joined
        and len(out['closures']) == 495, '%.1fs' % dt)

    print('')
    print('Result: %d/6' % (6 - len(fails)))
    if fails:
        print('[XX] FAILURES: %d' % len(fails))
        return 1
    print('[OK] ALL PASSED')
    return 0


if __name__ == '__main__':
    sys.exit(_selftest())
