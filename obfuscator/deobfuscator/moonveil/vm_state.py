"""MoonVeil 2.x state-machine tracer (Sprint 7, slice 3b).

The MoonVeil VM core is one giant state-machine closure of the shape

    local _, i, p, m, a, n, b, j, h, e, k, d, f
    _ = 0xc5
    repeat
      if _ < 0xc5 then ... o[2][2][o[2][3]] ... n(d, h) ... end
    until ...

called once per VM step; it fetches encoded words from bytecode tables and
writes decoded results into register/env tables.  vm_trace.py (slice 3a)
captures the bootstrap phase; this module captures the VM phase:

  * every call of the state-machine body: step, numeric/table/string argument
    summary and return value;
  * every table write (LuaTable.rawset) performed inside such a call window:
    (table id, key, value) -- i.e. the decoded register/env writes.

The per-call write log IS the lifted instruction effect trace.

Usage:
    py -m obfuscator.deobfuscator.moonveil.vm_state --test
    py -m obfuscator.deobfuscator.moonveil.vm_state path\\sample.lua --max-steps 8000000 --outdir out
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

_SM_RE = re.compile(r'repeat\s+if\s+_')


class StateResult(object):
    def __init__(self):
        self.calls = []      # [step, args_summary, ret_summary, writes]
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
        return ['T', id(v), v.length()]
    if isinstance(v, LuaFunction):
        return ['F', id(v.body)]
    return ['?', type(v).__name__]


def trace_state(source, max_steps=8000000, sm_pattern=None):
    res = StateResult()
    t0 = time.time()
    rx = re.compile(sm_pattern) if sm_pattern else _SM_RE
    chunk = Parser(Lexer(source).tokenize()).parse()
    up = ASTUnparser(minified=True)
    cache = {}

    class SSB(LuaSandbox):
        def __init__(s):
            super().__init__()
            s.MAX_STEPS = max_steps
            s._depth = 0
            s._rec = None
            s._orig_rawset = LuaTable.rawset
            s._hooked = False

        def _make_hook(s):
            orig = s._orig_rawset

            def hook(tbl, key, value):
                r = orig(tbl, key, value)
                if s._rec is not None:
                    s._rec[3].append([id(tbl), key if not isinstance(key, LuaTable) else 'T',
                                      _summ(value)])
                return r

            return hook

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
                if rx.search(txt):
                    rec = [s._steps, [_summ(a) for a in args], None, []]
                    res.calls.append(rec)
                    s._depth += 1
                    prev = s._rec
                    s._rec = rec
                    if not s._hooked:
                        LuaTable.rawset = s._make_hook()
                        s._hooked = True
                    try:
                        r = super()._call_function(fn, args, env)
                    finally:
                        s._depth -= 1
                        s._rec = prev
                        if s._depth == 0 and s._hooked:
                            LuaTable.rawset = s._orig_rawset
                            s._hooked = False
                    rec[2] = _summ(r[0] if isinstance(r, list) else r)
                    return r
            return super()._call_function(fn, args, env)

    sb = SSB()
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
            LuaTable.rawset = sb._orig_rawset
    res.steps = sb._steps
    res.elapsed = time.time() - t0
    return res


# --------------------------------------------------------------------------- #
# self-test: synthetic state machine writing a register file
# --------------------------------------------------------------------------- #

_SYNTH = '''
local o = { {101, 97, 145, 3}, {102, 99, 111, 4}, {103, 130, 110, 5} }
local H = {}
local K = 0x5a
local function sm(op, key)
  local _, i, a, b
  _ = 1
  repeat
    if _ <= 3 then
      i = o[_][1]
      a = o[_][2] - K
      b = o[_][3] - K
      if i == op then H[key] = a + b end
    end
    _ = _ + 1
  until _ > 3
  return H[key]
end
local acc = 0
acc = acc + sm(101, 1)
acc = acc + sm(102, 2)
acc = acc + sm(103, 3)
return acc
'''


def _selftest():
    fails = []

    def chk(tag, cond, extra=''):
        print(('[OK] ' if cond else '[XX] ') + tag + (' ' + extra if extra else ''))
        if not cond:
            fails.append(tag)

    r = trace_state(_SYNTH, max_steps=500000, sm_pattern=r'repeat\s+if\s+_')
    chk('T1 state machine calls captured (3)', (not r.error) and len(r.calls) == 3,
        'n=%d err=%s' % (len(r.calls), r.error))
    ok2 = len(r.calls) == 3 and r.calls[0][1][0][:1] == ['n'] and r.calls[0][1][0][1] == 101
    chk('T2 arg summary carries opcode number', ok2,
        str(r.calls[0][1] if r.calls else None))
    w0 = r.calls[0][3] if r.calls else []
    vals = [w[2][1] for w in w0 if w[2][0] == 'n']
    chk('T3 register writes captured with decoded value (7+55=62)',
        len(vals) >= 1 and vals[0] == 62,
        'vals=%s' % vals[:3])
    chk('T4 return summary numeric', len(r.calls) == 3 and r.calls[2][2][0] == 'n',
        str(r.calls[2][2] if len(r.calls) == 3 else None))
    r5 = trace_state('local x = 1 for i = 1, 3 do x = x + i end return x', max_steps=100000)
    chk('T5 non-SM source yields no calls', (not r5.error) and len(r5.calls) == 0)
    from obfuscator.deobfuscator.core.lua_sandbox import LuaTable as LT
    chk('T6 rawset hook restored', LT.rawset is not None and not getattr(LT.rawset, '__name__', '').startswith('_rawset'))

    print('')
    print('Result: %d/6' % (6 - len(fails)))
    if fails:
        print('[XX] FAILURES: %d' % len(fails))
        return 1
    print('[OK] ALL PASSED')
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description='MoonVeil state-machine tracer')
    ap.add_argument('sample', nargs='?')
    ap.add_argument('--test', action='store_true')
    ap.add_argument('--max-steps', type=int, default=8000000)
    ap.add_argument('--sm-pattern', default=None)
    ap.add_argument('--outdir', default=None)
    a = ap.parse_args(argv)
    if a.test:
        return _selftest()
    if not a.sample:
        ap.error('sample path required (or --test)')
    src = open(a.sample, encoding='utf-8', errors='replace').read()
    print('state trace: %s (max_steps=%d)' % (a.sample, a.max_steps))
    res = trace_state(src, max_steps=a.max_steps, sm_pattern=a.sm_pattern)
    nw = sum(len(c[3]) for c in res.calls)
    print('sm_calls=%d writes=%d steps=%d elapsed=%.1fs error=%s' %
          (len(res.calls), nw, res.steps, res.elapsed, res.error))
    for c in res.calls[:6]:
        print('  step=%d args=%s ret=%s writes=%d' % (c[0], c[1][:4], c[2], len(c[3])))
    if a.outdir:
        if not os.path.isdir(a.outdir):
            os.makedirs(a.outdir)
        with open(os.path.join(a.outdir, 'state.json'), 'w', encoding='utf-8') as fh:
            json.dump({'calls': res.calls[:20000], 'steps': res.steps,
                       'error': res.error}, fh, ensure_ascii=False)
        print('saved -> %s' % os.path.join(a.outdir, 'state.json'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
