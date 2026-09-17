"""MoonVeil 2.x VM-phase table-I/O tracer (Sprint 7, slice 3e).

The MoonVeil VM phase (after the ~450k-step bootstrap) makes NO function
calls at all: it is an inline loop reading/writing Lua tables (bytecode
array, register file, env).  The only observable left is table access, so
this module hooks LuaTable.rawget/rawset class-wide from `start_step` on and
records [step, 'g'/'s', table_id, key, value] plus a per-table op registry.

The hottest tables are the VM register file / bytecode array; their op
sequence (sequential reads with a stride = pc) is the raw material for the
lift in slice 3f.

Usage:
    py -m obfuscator.deobfuscator.moonveil.vm_tables --test
    py -m obfuscator.deobfuscator.moonveil.vm_tables path\\sample.lua --max-steps 4000000 --start-step 450000 --outdir out
"""

import os
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


class TablesResult(object):
    def __init__(self):
        self.ops = []        # [step, 'g'/'s', tbl_id, key, value]
        self.tables = {}     # tbl_id -> [first_step, gets, sets]
        self.steps = 0
        self.elapsed = 0.0
        self.error = None


def _summ(v):
    if isinstance(v, bool):
        return ['b', v]
    if isinstance(v, (int, float)):
        return ['n', v]
    if isinstance(v, str):
        return ['s', v[:20]]
    if isinstance(v, LuaTable):
        return ['T', v.length()]
    if isinstance(v, list):
        return ['L', len(v)]
    return ['?', type(v).__name__]


def trace_tables(source, max_steps=4000000, start_step=0, max_ops=400000):
    res = TablesResult()
    t0 = time.time()
    chunk = Parser(Lexer(source).tokenize()).parse()

    class TSB(LuaSandbox):
        def __init__(s):
            super().__init__()
            s.MAX_STEPS = max_steps
            s._orig_get = LuaTable.rawget
            s._orig_set = LuaTable.rawset
            s._hooked = False

        def _make_hooks(s):
            og, os_ = s._orig_get, s._orig_set
            reg = res.tables
            ops = res.ops

            def hook_get(tbl, key):
                r = og(tbl, key)
                if len(ops) < max_ops:
                    tid = id(tbl)
                    e = reg.get(tid)
                    if e is None:
                        e = [s._steps, 0, 0]
                        reg[tid] = e
                    e[1] += 1
                    ops.append([s._steps, 'g', tid, _summ(key), _summ(r)])
                return r

            def hook_set(tbl, key, value):
                r = os_(tbl, key, value)
                if len(ops) < max_ops:
                    tid = id(tbl)
                    e = reg.get(tid)
                    if e is None:
                        e = [s._steps, 0, 0]
                        reg[tid] = e
                    e[2] += 1
                    ops.append([s._steps, 's', tid, _summ(key), _summ(value)])
                return r

            return hook_get, hook_set

        def _step(s):
            super()._step()
            if not s._hooked and s._steps >= start_step:
                hg, hs = s._make_hooks()
                LuaTable.rawget = hg
                LuaTable.rawset = hs
                s._hooked = True

    sb = TSB()
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
            LuaTable.rawget = sb._orig_get
            LuaTable.rawset = sb._orig_set
    res.steps = sb._steps
    res.elapsed = time.time() - t0
    return res


# --------------------------------------------------------------------------- #
# self-test
# --------------------------------------------------------------------------- #

_SYNTH = '''
local R = {}
local B = { 11, 22, 33, 44 }
local pc = 1
for i = 1, 40 do
  local op = B[pc]
  R[pc] = op * 2
  pc = pc % 4 + 1
end
return R[1]
'''


def _selftest():
    fails = []

    def chk(tag, cond, extra=''):
        print(('[OK] ' if cond else '[XX] ') + tag + (' ' + extra if extra else ''))
        if not cond:
            fails.append(tag)

    r = trace_tables(_SYNTH, max_steps=500000, start_step=0, max_ops=100000)
    chk('T1 reads and writes recorded', (not r.error) and len(r.ops) > 40,
        'ops=%d err=%s' % (len(r.ops), r.error))
    sets = [o for o in r.ops if o[1] == 's']
    gets = [o for o in r.ops if o[1] == 'g']
    chk('T2 write values = doubled bytecode (22 present)', len(sets) >= 1 and
        any(x[4] == ['n', 22] for x in sets[:10]),
        str([x[4] for x in sets[:4]]))
    tids = set(o[2] for o in r.ops)
    chk('T3 two hot tables registered (R and B)', len(tids) >= 2 and
        all(len(v) == 3 for v in r.tables.values()), 'tids=%d' % len(tids))
    r4 = trace_tables(_SYNTH, max_steps=500000, start_step=10 ** 9)
    chk('T4 start_step gate suppresses recording', (not r4.error) and len(r4.ops) == 0,
        'ops=%d' % len(r4.ops))
    from obfuscator.deobfuscator.core.lua_sandbox import LuaTable as LT
    chk('T5 hooks restored', LT.rawget.__name__ == 'rawget' and LT.rawset.__name__ == 'rawset')

    print('')
    print('Result: %d/5' % (5 - len(fails)))
    if fails:
        print('[XX] FAILURES: %d' % len(fails))
        return 1
    print('[OK] ALL PASSED')
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description='MoonVeil VM-phase table-I/O tracer')
    ap.add_argument('sample', nargs='?')
    ap.add_argument('--test', action='store_true')
    ap.add_argument('--max-steps', type=int, default=4000000)
    ap.add_argument('--start-step', type=int, default=0)
    ap.add_argument('--max-ops', type=int, default=400000)
    ap.add_argument('--outdir', default=None)
    a = ap.parse_args(argv)
    if a.test:
        return _selftest()
    if not a.sample:
        ap.error('sample path required (or --test)')
    src = open(a.sample, encoding='utf-8', errors='replace').read()
    print('table trace: %s (max_steps=%d start_step=%d)' % (a.sample, a.max_steps, a.start_step))
    res = trace_tables(src, max_steps=a.max_steps, start_step=a.start_step, max_ops=a.max_ops)
    print('ops=%d tables=%d steps=%d elapsed=%.1fs error=%s' %
          (len(res.ops), len(res.tables), res.steps, res.elapsed, res.error))
    top = sorted(res.tables.items(), key=lambda kv: -(kv[1][1] + kv[1][2]))[:6]
    for tid, e in top:
        print('  tbl %x first=%d gets=%d sets=%d' % (tid, e[0], e[1], e[2]))
    if top:
        hot = top[0][0]
        print('  hot op sample:')
        n = 0
        for o in res.ops:
            if o[2] == hot:
                print('    %s key=%s val=%s' % (o[1], o[3], o[4]))
                n += 1
                if n >= 12:
                    break
    if a.outdir:
        if not os.path.isdir(a.outdir):
            os.makedirs(a.outdir)
        with open(os.path.join(a.outdir, 'tables.json'), 'w', encoding='utf-8') as fh:
            json.dump({'ops': res.ops[:200000],
                       'tables': {'%x' % k: v for k, v in res.tables.items()},
                       'steps': res.steps, 'error': res.error}, fh, ensure_ascii=False)
        print('saved -> %s' % os.path.join(a.outdir, 'tables.json'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
