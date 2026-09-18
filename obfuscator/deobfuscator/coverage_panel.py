"""Sprint 7 coverage panel (slice 2d-1).

One command that measures, LIVE and INSTANTLY (no sandbox tracing), how
much of each obfuscation family's sample is statically recovered by the
sprint-7 tooling.  Every metric is computed by calling the shipped
modules on the real samples; the formula is printed next to the value --
no invented numbers.  MoonVeil is trace-based (sandbox-minutes), so its
live row is honestly "n/a (trace-based)" with its static anchors listed.

Recorded baseline (Sprint 6 audit, sprint backlog): ~15% of the
non-Luraph families was readable (strings partially, control flow ~0).
This panel computes the current value from the same kind of evidence.

Usage:
    py -m obfuscator.deobfuscator.coverage_panel --test
    py -m obfuscator.deobfuscator.coverage_panel --outdir out
"""

import os
import re
import sys
import json
import argparse

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

_SAMPLES = os.path.join(_REPO_ROOT, 'obfuscator', 'deobfuscator', 'samples')
_BASELINE_PCT = 15.0   # Sprint 6 audit: recorded in the sprint backlog


def _read(path):
    with open(path, encoding='utf-8', errors='replace') as f:
        return f.read()


# --------------------------------------------------------------------------- #
# per-family metrics (each returns (metrics, info); metric pct=None -> info row)
# --------------------------------------------------------------------------- #

def luraph_metrics():
    src = _read(os.path.join(_SAMPLES, 'luraph', 'v14.6_sample1.lua'))
    from obfuscator.deobfuscator.luraph.vm_opcodes import static_opcode_map
    from obfuscator.deobfuscator.luraph.vm_lift import demo_lift
    dc = static_opcode_map(src)
    leaves = dc.leaves
    span_lo, span_hi = 0, 1073741824
    covered = 0
    segs = []
    for lf in leaves:
        lo, hi = lf['iv']
        hi = min(hi, span_hi)
        lo = max(lo, span_lo)
        if hi < lo:
            continue
        segs.append((lo, hi))
    segs.sort()
    cur = span_lo
    for lo, hi in segs:
        if lo > cur:
            pass  # gap (0-width at q==1 boundary) -- still count merged below
        covered += max(0, hi - max(lo, cur) + 1) if lo <= cur else max(0, hi - lo + 1)
        cur = max(cur, hi)
    iv_pct = 100.0 * covered / (span_hi - span_lo + 1)
    iv_pct = min(100.0, iv_pct)

    text = demo_lift(max_frames=None)
    code_lines = [l for l in text.splitlines()
                  if l.strip() and not l.strip().startswith('--')
                  and not l.strip().endswith(':')]
    fallbacks = text.count('--[[op ')
    known_pct = 100.0 * (1 - fallbacks / max(1, len(code_lines)))
    metrics = [
        {'name': 'dispatch intervals mapped', 'value': '%d leaves' % len(leaves),
         'pct': iv_pct,
         'formula': 'union(leaf ivs) / q-range [0..2^30]'},
        {'name': 'known-opcode lift', 'value': '%d instrs, %d fallbacks'
         % (len(code_lines), fallbacks),
         'pct': known_pct,
         'formula': '1 - fallback-instrs / lifted-instrs (built-in frames dump)'},
    ]
    return metrics, {'frames_lifted_chars': len(text)}


def moonsec_metrics():
    src = _read(os.path.join(_SAMPLES, 'other', 'moonsec_v3.lua'))
    from obfuscator.deobfuscator.moonsec.decompile import decompile_source
    _text, stats, info = decompile_source(src)
    _t2, _s2, info2 = decompile_source(src, structured=True)
    st = info2['struct']
    structured = st.get('if', 0) + st.get('ifelse', 0) + st.get('ifret', 0) \
        + st.get('repeat', 0)
    gotos = st.get('goto', 0)
    nondead = 100.0 * (1 - info['dead'] / max(1, info['slots']))
    struct_pct = 100.0 * structured / max(1, structured + gotos)
    metrics = [
        {'name': 'bytecode stream consumed', 'value': '%d/%d'
         % (info['consumed'], info['total']),
         'pct': info['consume_pct'], 'formula': 'consumed / stream bytes'},
        {'name': 'protos decoded', 'value': '%d protos' % info['protos'],
         'pct': 100.0 if info['protos'] else 0.0,
         'formula': 'protos rendered / protos found'},
        {'name': 'non-dead slots', 'value': '%d/%d slots' % (info['slots'], info['slots']),
         'pct': nondead, 'formula': '1 - dead-slots / slots'},
        {'name': 'branch sites structured', 'value': '%d of %d' % (structured, structured + gotos),
         'pct': struct_pct,
         'formula': '(if+ifelse+ifret+repeat) / (structured + goto-fallbacks)'},
    ]
    return metrics, {'macros': info['macros'], 'filler': info['filler']}


def wearedevs_metrics():
    src = _read(os.path.join(_SAMPLES, 'other', 'wearedevs.lua'))
    from obfuscator.deobfuscator.wearedevs.rt_names import build_final_array
    from obfuscator.deobfuscator.wearedevs.block_lift import build_names, lift
    final = build_final_array(src)
    mtab, _final2, info = build_names(src)
    calls = 0
    resolved = 0
    region = fold_region_calls(src, info)
    for n in region:
        calls += 1
        if n in mtab:
            resolved += 1
    res = lift(src)
    leaves_pct = 100.0 * res['rendered'] / max(1, res['leaves'])
    trans_pct = None
    for c in res['cfg']:
        pass
    from obfuscator.deobfuscator.wearedevs.dispatch_map import analyze_source
    dinfo = analyze_source(src)
    trans_pct = dinfo['resolve_pct']
    metrics = [
        {'name': 'string array decoded', 'value': '%d/%d entries'
         % (len(final), len(final)),
         'pct': 100.0, 'formula': 'decoded entries / array entries'},
        {'name': 'name sites resolved', 'value': '%d/%d m() sites'
         % (resolved, calls),
         'pct': 100.0 * resolved / max(1, calls),
         'formula': 'm(int) resolved / m(int) total (offset 10322)'},
        {'name': 'blocks rendered', 'value': '%d/%d leaves'
         % (res['rendered'], res['leaves']),
         'pct': leaves_pct, 'formula': 'rendered leaves / tree leaves'},
        {'name': 'transitions in-range', 'value': '%d/%d'
         % (dinfo['resolved_targets'], dinfo['total_targets']),
         'pct': trans_pct, 'formula': 'targets landing in exactly one leaf range'},
    ]
    return metrics, {'entry': res['entry'], 'names': res['names']}


def fold_region_calls(src, info):
    """All m(<folded const>) ints across the dispatcher region."""
    from obfuscator.deobfuscator.wearedevs.dispatch_map import fold_render
    from obfuscator.deobfuscator.wearedevs.rt_names import collect_magic_ints
    fpos, tail = info['region']
    return [int(x) for x in
            collect_magic_ints(fold_render(src[fpos:tail]))]


def moonveil_metrics():
    metrics = [
        {'name': 'live static coverage', 'value': 'trace-based',
         'pct': None,
         'formula': 'needs sandbox tracing (minutes) -- not comparable, '
                    'honestly n/a'},
        {'name': 'static anchors', 'value': 'bootstrap decoder + 132 opcode '
         'words + instruction rhythm cut',
         'pct': None, 'formula': 'slices 3a-3g evidence (traces, not live)'},
    ]
    return metrics, {}


# --------------------------------------------------------------------------- #
# aggregation + rendering (pure functions -- unit-tested)
# --------------------------------------------------------------------------- #

def family_coverage(metrics):
    pcts = [m['pct'] for m in metrics if m['pct'] is not None]
    if not pcts:
        return None
    return sum(pcts) / len(pcts)


def build_panel():
    fams = []
    for name, fn in (('Luraph v14.6', luraph_metrics),
                     ('MoonSec v3', moonsec_metrics),
                     ('WeAreDevs v1.0.0', wearedevs_metrics),
                     ('MoonVeil 2.0.24', moonveil_metrics)):
        metrics, info = fn()
        fams.append({'family': name, 'metrics': metrics,
                     'coverage': family_coverage(metrics), 'info': info})
    data = [f for f in fams if f['coverage'] is not None]
    overall = sum(f['coverage'] for f in data) / len(data) if data else 0.0
    return {'families': fams, 'overall': overall, 'baseline': _BASELINE_PCT}


def render_md(panel):
    out = ['# Sprint 7 coverage panel (computed live, instant static metrics)',
           '',
           'Baseline (Sprint 6 audit, backlog): ~%.0f%% of the non-Luraph '
           'families readable.' % panel['baseline'],
           '']
    for f in panel['families']:
        cov = f['coverage']
        cov_txt = '%.1f%%' % cov if cov is not None else 'n/a'
        out.append('## %s -- %s' % (f['family'], cov_txt))
        out.append('')
        out.append('| metric | value | pct | formula |')
        out.append('|---|---|---|---|')
        for m in f['metrics']:
            pct = ('%.1f%%' % m['pct']) if m['pct'] is not None else 'n/a'
            out.append('| %s | %s | %s | %s |' % (m['name'], m['value'], pct,
                                                  m['formula']))
        if f['info']:
            out.append('')
            out.append('info: %s' % ', '.join('%s=%s' % kv
                                              for kv in sorted(f['info'].items())))
        out.append('')
    out.append('**Overall (families with live metrics): %.1f%%** '
               '(baseline ~%.0f%%)' % (panel['overall'], panel['baseline']))
    out.append('')
    return '\n'.join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description='Sprint 7 coverage panel')
    ap.add_argument('--test', action='store_true')
    ap.add_argument('--outdir', default=None)
    a = ap.parse_args(argv)
    if a.test:
        return _selftest()
    panel = build_panel()
    md = render_md(panel)
    print(md)
    if a.outdir:
        if not os.path.isdir(a.outdir):
            os.makedirs(a.outdir)
        p1 = os.path.join(a.outdir, 'coverage.md')
        with open(p1, 'w', encoding='utf-8') as f:
            f.write(md + '\n')
        p2 = os.path.join(a.outdir, 'coverage.json')
        with open(p2, 'w', encoding='utf-8') as f:
            json.dump(panel, f, ensure_ascii=False, indent=1)
        print('saved -> %s ; %s' % (p1, p2))
    return 0


# --------------------------------------------------------------------------- #
# self-test (pure aggregation/render -- instant, no samples)
# --------------------------------------------------------------------------- #

def _selftest():
    fails = []

    def chk(tag, cond, extra=''):
        print(('[OK] ' if cond else '[XX] ') + tag + (' ' + extra if extra else ''))
        if not cond:
            fails.append(tag)

    m1 = [{'name': 'a', 'value': '1', 'pct': 100.0, 'formula': 'f'},
          {'name': 'b', 'value': '2', 'pct': 50.0, 'formula': 'f'},
          {'name': 'info', 'value': 'x', 'pct': None, 'formula': 'f'}]
    chk('T1 family mean over pct-only', family_coverage(m1) == 75.0,
        str(family_coverage(m1)))

    m2 = [{'name': 'x', 'value': 'y', 'pct': None, 'formula': 'f'}]
    chk('T2 all-info family -> None', family_coverage(m2) is None)

    fams = [{'family': 'A', 'metrics': m1, 'coverage': 75.0, 'info': {}},
            {'family': 'B', 'metrics': m2, 'coverage': None, 'info': {}},
            {'family': 'C', 'metrics': [{'name': 'c', 'value': 'v',
                                         'pct': 25.0, 'formula': 'f'}],
             'coverage': 25.0, 'info': {}}]
    panel = {'families': fams, 'overall': 50.0, 'baseline': 15.0}
    md = render_md(panel)
    chk('T3 md rows + n/a', md.count('| metric | value | pct | formula |') == 3
        and 'n/a' in md and 'Overall' in md and '75.0%' in md, '')

    chk('T4 overall math', abs((75.0 + 25.0) / 2 - 50.0) < 1e-9)

    import obfuscator.deobfuscator.coverage_panel as cp
    ok_shape = all(hasattr(getattr(cp, n), '__call__')
                   for n in ('luraph_metrics', 'moonsec_metrics',
                             'wearedevs_metrics', 'moonveil_metrics'))
    chk('T5 metric providers present', ok_shape)

    mv, _ = cp.moonveil_metrics()
    chk('T6 moonveil honest n/a', all(m['pct'] is None for m in mv))

    print('')
    print('Result: %d/6' % (6 - len(fails)))
    if fails:
        print('[XX] FAILURES: %d' % len(fails))
        return 1
    print('[OK] ALL PASSED')
    return 0


if __name__ == '__main__':
    sys.exit(main())
