"""WeAreDevs v1 string-array tracer (Sprint 7, slice 4).

WeAreDevs obfuscation keeps one big cipher string array (entries look like
'M!KPLo6s^ff:7H!') and an anti-tamper ROTATION loop that swaps head/tail
counters towards each other for millions of sandbox steps before the VM
starts resolving strings.  Plaintext never lands in a table during rotation.

This module hooks LuaTable.rawset from step 0 and reports, for a run:

  * the cipher array: table with the most cipher-prefix string writes, its
    size (max integer key) and how many cipher writes happened (rotation
    progress proxy);
  * every PLAINTEXT string write (value not matching the cipher prefix) --
    these appear once the VM phase starts resolving constants;
  * per-table registry for orientation.

Usage:
    py -m obfuscator.deobfuscator.wearedevs.array_trace --test
    py -m obfuscator.deobfuscator.wearedevs.array_trace path\\sample.lua --max-steps 4000000 --outdir out
"""

import os
import re
import sys
import json
import time
import argparse

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from obfuscator.lexer import Lexer
from obfuscator.parser import Parser
from obfuscator.deobfuscator.core.lua_sandbox import LuaSandbox, LuaTable, LuaReturn, _EnvTable
from obfuscator.deobfuscator.dynamic_decrypt import make_mock, ROBLOX_GLOBALS

_CIPHER_RE = re.compile(r'^M')


class ArrayResult(object):
    def __init__(self):
        self.cipher_tbl = None     # id of the cipher array table
        self.cipher_size = 0       # max integer key seen on it
        self.cipher_writes = 0
        self.plain = []            # [step, value]
        self.tables = {}           # id -> [gets, sets]
        self.steps = 0
        self.elapsed = 0.0
        self.error = None


def trace_array(source, max_steps=4000000, cipher_re=None, max_plain=2000):
    res = ArrayResult()
    rx = re.compile(cipher_re) if cipher_re else _CIPHER_RE
    t0 = time.time()
    chunk = Parser(Lexer(source).tokenize()).parse()
    per = {}

    class ASB(LuaSandbox):
        def __init__(s):
            super().__init__()
            s.MAX_STEPS = max_steps
            s._orig = LuaTable.rawset
            s._hooked = False

        def _make_hook(s):
            orig = s._orig

            def hook(tbl, key, value):
                r = orig(tbl, key, value)
                tid = id(tbl)
                e = per.get(tid)
                if e is None:
                    e = {'g': 0, 's': 0, 'cw': 0, 'maxk': 0}
                    per[tid] = e
                e['s'] += 1
                if isinstance(key, int) and key > e['maxk']:
                    e['maxk'] = key
                if isinstance(value, str):
                    if rx.match(value):
                        e['cw'] += 1
                    elif len(res.plain) < max_plain:
                        res.plain.append([s._steps, value])
                return r

            return hook

        def _step(s):
            super()._step()
            if not s._hooked:
                LuaTable.rawset = s._make_hook()
                s._hooked = True

    sb = ASB()
    env = dict(sb._globals)
    env['_G'] = _EnvTable(env)
    for g in ROBLOX_GLOBALS:
        if env.get(g) is None:
            env[g] = make_mock(sb, g)
    try:
        sb._exec_chunk(chunk, env)
    except LuaReturn:
        pass
    except Exception as e:
        res.error = '%s: %s' % (type(e).__name__, str(e)[:200])
    finally:
        if sb._hooked:
            LuaTable.rawset = sb._orig
    best, bestcw = None, 0
    for tid, e in per.items():
        if e['cw'] > bestcw:
            best, bestcw = tid, e['cw']
    res.cipher_tbl = best
    if best is not None:
        res.cipher_size = per[best]['maxk']
        res.cipher_writes = per[best]['cw']
    res.tables = {tid: [e['g'], e['s']] for tid, e in per.items()}
    res.steps = sb._steps
    res.elapsed = time.time() - t0
    return res


# --------------------------------------------------------------------------- #
# self-test
# --------------------------------------------------------------------------- #

_SYNTH = '''
local V = {}
for i = 1, 60 do V[i] = 'M' .. string.char(33 + (i % 60)) .. 'x' .. i end
local a, b = 1, 60
local j = 0
while j < 20 do
  local t = V[a]
  V[a] = V[b]
  V[b] = t
  a = a + 1
  b = b - 1
  j = j + 1
end
local P = {}
for i = 1, 5 do P[i] = 'plain' .. i end
return V[1]
'''


def _selftest():
    fails = []

    def chk(tag, cond, extra=''):
        print(('[OK] ' if cond else '[XX] ') + tag + (' ' + extra if extra else ''))
        if not cond:
            fails.append(tag)

    r = trace_array(_SYNTH, max_steps=500000)
    chk('T1 cipher array found, size 60', (not r.error) and r.cipher_tbl is not None
        and r.cipher_size == 60, 'size=%s err=%s' % (r.cipher_size, r.error))
    chk('T2 cipher writes counted (60 build + 40 swap)', r.cipher_writes >= 90,
        'cw=%d' % r.cipher_writes)
    pv = [p[1] for p in r.plain]
    chk('T3 plaintext writes captured', pv == ['plain%d' % i for i in range(1, 6)], str(pv))
    r4 = trace_array('local x = { 1, 2, 3 } return x[2]', max_steps=100000)
    chk('T4 clean source: no cipher, no plain', (not r4.error) and r4.cipher_writes == 0
        and len(r4.plain) == 0)
    from obfuscator.deobfuscator.core.lua_sandbox import LuaTable as LT
    chk('T5 rawset restored', LT.rawset.__name__ == 'rawset')

    print('')
    print('Result: %d/5' % (5 - len(fails)))
    if fails:
        print('[XX] FAILURES: %d' % len(fails))
        return 1
    print('[OK] ALL PASSED')
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description='WeAreDevs string-array tracer')
    ap.add_argument('sample', nargs='?')
    ap.add_argument('--test', action='store_true')
    ap.add_argument('--max-steps', type=int, default=4000000)
    ap.add_argument('--cipher-re', default=None)
    ap.add_argument('--outdir', default=None)
    a = ap.parse_args(argv)
    if a.test:
        return _selftest()
    if not a.sample:
        ap.error('sample path required (or --test)')
    src = open(a.sample, encoding='utf-8', errors='replace').read()
    print('array trace: %s (max_steps=%d)' % (a.sample, a.max_steps))
    res = trace_array(src, max_steps=a.max_steps, cipher_re=a.cipher_re)
    print('cipher_tbl=%s size=%d cipher_writes=%d plain=%d steps=%d elapsed=%.1fs error=%s' %
          (('%x' % res.cipher_tbl) if res.cipher_tbl else None, res.cipher_size,
           res.cipher_writes, len(res.plain), res.steps, res.elapsed, res.error))
    for p in res.plain[:10]:
        print('  plain step=%d %r' % (p[0], p[1][:60]))
    if a.outdir:
        if not os.path.isdir(a.outdir):
            os.makedirs(a.outdir)
        with open(os.path.join(a.outdir, 'array.json'), 'w', encoding='utf-8') as fh:
            json.dump({'cipher_size': res.cipher_size, 'cipher_writes': res.cipher_writes,
                       'plain': res.plain, 'steps': res.steps, 'error': res.error},
                      fh, ensure_ascii=False)
        print('saved -> %s' % os.path.join(a.outdir, 'array.json'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
