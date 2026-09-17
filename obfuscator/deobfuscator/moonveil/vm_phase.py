"""MoonVeil 2.x VM-phase helper tracer (Sprint 7, slice 3d).

After the bootstrap (decoded by stream_assemble.py, ends ~450k steps) the
MoonVeil VM loop no longer calls the state-machine body.  Its hot helpers are

  * two one-expression wrappers whose bodies unparse to '' (the minified
    unparser drops bare ReturnStat) -- these fetch/decode instruction words;
  * a guard closure of the exact shape ``if j > k then return end``.

This module records every call of those helpers in order:
[step, kind, args_summary, ret_summary], so the VM-phase decoded word stream
and its per-instruction rhythm become observable.

Usage:
    py -m obfuscator.deobfuscator.moonveil.vm_phase --test
    py -m obfuscator.deobfuscator.moonveil.vm_phase path\\sample.lua --max-steps 4000000 --outdir out
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
from obfuscator.ast_unparser import ASTUnparser
from obfuscator.deobfuscator.core.lua_sandbox import LuaSandbox, LuaTable, LuaFunction, LuaReturn, _EnvTable
from obfuscator.deobfuscator.dynamic_decrypt import make_mock, ROBLOX_GLOBALS

_GUARD_RE = re.compile(r'^if\s+\w+\s*>\s*\w+\s*then\s*return\s*end$')


class PhaseResult(object):
    def __init__(self):
        self.seq = []       # [step, kind, args, ret]
        self.steps = 0
        self.elapsed = 0.0
        self.error = None


def _summ(v):
    if isinstance(v, bool):
        return ['b', v]
    if isinstance(v, (int, float)):
        return ['n', v]
    if isinstance(v, str):
        return ['s', v[:24]]
    if isinstance(v, LuaTable):
        return ['T', v.length()]
    if isinstance(v, list):
        return ['L', len(v)]
    return ['?', type(v).__name__]


def trace_phase(source, max_steps=4000000):
    res = PhaseResult()
    t0 = time.time()
    chunk = Parser(Lexer(source).tokenize()).parse()
    up = ASTUnparser(minified=True)
    cache = {}

    class PSB(LuaSandbox):
        def __init__(s):
            super().__init__()
            s.MAX_STEPS = max_steps

        def _call_function(s, fn, args, env=None):
            if isinstance(fn, LuaFunction) and fn.body is not None:
                bid = id(fn.body)
                txt = cache.get(bid)
                if txt is None:
                    try:
                        txt = ' '.join(up.unparse(x) for x in fn.body.statements)
                    except Exception:
                        txt = ''
                    cache[bid] = txt
                kind = None
                if txt == '':
                    kind = 'empty'
                elif _GUARD_RE.match(txt.strip()):
                    kind = 'guard'
                if kind:
                    r = super()._call_function(fn, args, env)
                    v = r[0] if isinstance(r, list) else r
                    res.seq.append([s._steps, kind, [_summ(a) for a in args], _summ(v)])
                    return r
            return super()._call_function(fn, args, env)

    sb = PSB()
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
    res.steps = sb._steps
    res.elapsed = time.time() - t0
    return res


# --------------------------------------------------------------------------- #
# self-test
# --------------------------------------------------------------------------- #

_SYNTH = '''
local W = { 131, 232, 333 }
local K = 30
local function fA(x, k) return x - k end
local function fB(x, k) return x + k end
local function g(j, k) if j > k then return end end
local acc = 0
for i = 1, 3 do
  local a = fA(W[i], K)
  g(a, 500)
  local b = fB(a, K)
  g(1, b)
  acc = acc + b
end
return acc
'''


def _selftest():
    fails = []

    def chk(tag, cond, extra=''):
        print(('[OK] ' if cond else '[XX] ') + tag + (' ' + extra if extra else ''))
        if not cond:
            fails.append(tag)

    r = trace_phase(_SYNTH, max_steps=500000)
    kinds = [e[1] for e in r.seq]
    want = ['empty', 'guard', 'empty', 'guard'] * 3
    chk('T1 helper call rhythm empty/guard x3 instrs', (not r.error) and kinds == want,
        'kinds=%s err=%s' % (kinds[:14], r.error))
    vals = [e[3][1] for e in r.seq if e[1] == 'empty']
    chk('T2 decoded words in order (101,131,202,232,303,333)', vals == [101, 131, 202, 232, 303, 333],
        str(vals))
    ok3 = r.seq[0][2] == [['n', 131], ['n', 30]]
    chk('T3 args summary captured', ok3, str(r.seq[0][2] if r.seq else None))
    r4 = trace_phase('local x = 0 for i = 1, 5 do x = x + i end return x', max_steps=100000)
    chk('T4 source without helpers yields empty seq', (not r4.error) and len(r4.seq) == 0)
    r5 = trace_phase('local j = 0 local function h(a, b) return a + b end '
                     'local z = 0 repeat j = j + 1; z = h(j, 1) until j > 400000 return z',
                     max_steps=200000)
    chk('T5 step cap safe with many helper calls', r5.error is not None and len(r5.seq) > 1000,
        'n=%d' % len(r5.seq))

    print('')
    print('Result: %d/5' % (5 - len(fails)))
    if fails:
        print('[XX] FAILURES: %d' % len(fails))
        return 1
    print('[OK] ALL PASSED')
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description='MoonVeil VM-phase helper tracer')
    ap.add_argument('sample', nargs='?')
    ap.add_argument('--test', action='store_true')
    ap.add_argument('--max-steps', type=int, default=4000000)
    ap.add_argument('--outdir', default=None)
    a = ap.parse_args(argv)
    if a.test:
        return _selftest()
    if not a.sample:
        ap.error('sample path required (or --test)')
    src = open(a.sample, encoding='utf-8', errors='replace').read()
    print('phase trace: %s (max_steps=%d)' % (a.sample, a.max_steps))
    res = trace_phase(src, max_steps=a.max_steps)
    ne = sum(1 for e in res.seq if e[1] == 'empty')
    ng = sum(1 for e in res.seq if e[1] == 'guard')
    print('calls=%d empty=%d guard=%d steps=%d elapsed=%.1fs error=%s' %
          (len(res.seq), ne, ng, res.steps, res.elapsed, res.error))
    for e in res.seq[:16]:
        print('  step=%-9d %-5s args=%s ret=%s' % (e[0], e[1], e[2][:4], e[3]))
    if a.outdir:
        if not os.path.isdir(a.outdir):
            os.makedirs(a.outdir)
        with open(os.path.join(a.outdir, 'phase.json'), 'w', encoding='utf-8') as fh:
            json.dump({'seq': res.seq, 'steps': res.steps, 'error': res.error},
                      fh, ensure_ascii=False)
        print('saved -> %s' % os.path.join(a.outdir, 'phase.json'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
