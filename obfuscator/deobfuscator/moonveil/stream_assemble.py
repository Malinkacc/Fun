"""MoonVeil 2.x decoded-stream assembler (Sprint 7, slice 3c).

vm_state.py (slice 3b) proved that every call of the MoonVeil state-machine
closure either

  * decrypts ONE raw cipher chunk (single string argument) and returns the
    keystream-xored bytes, or
  * transforms/concatenates previously returned raw chunks (two or more
    string arguments) into a plaintext unit (env name, keyword, piece of the
    embedded program).

This module re-runs the sample and records the ordered unit stream:
(step, kind, text) with kind in {'raw', 'xform'}, i.e. the decoded payload
stream as the VM sees it, without any step-limit guessing about tables.

Usage:
    py -m obfuscator.deobfuscator.moonveil.stream_assemble --test
    py -m obfuscator.deobfuscator.moonveil.stream_assemble path\\sample.lua --max-steps 8000000 --outdir out
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
from obfuscator.deobfuscator.core.lua_sandbox import LuaSandbox, LuaTable, LuaFunction, LuaReturn, _EnvTable
from obfuscator.deobfuscator.dynamic_decrypt import make_mock, ROBLOX_GLOBALS

_SM_RE = re.compile(r'repeat\s+if\s+_')


class StreamResult(object):
    def __init__(self):
        self.units = []     # [step, kind, text]
        self.steps = 0
        self.elapsed = 0.0
        self.error = None

    def raws(self):
        return [u[2] for u in self.units if u[1] == 'raw']

    def xforms(self):
        return [u[2] for u in self.units if u[1] == 'xform']


def assemble_stream(source, max_steps=8000000, sm_pattern=None):
    res = StreamResult()
    t0 = time.time()
    rx = re.compile(sm_pattern) if sm_pattern else _SM_RE
    chunk = Parser(Lexer(source).tokenize()).parse()
    from obfuscator.ast_unparser import ASTUnparser
    up = ASTUnparser(minified=True)
    cache = {}

    class ASB(LuaSandbox):
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
                if rx.search(txt):
                    r = super()._call_function(fn, args, env)
                    v = r[0] if isinstance(r, list) else r
                    if isinstance(v, str):
                        nstr = sum(1 for a in args if isinstance(a, str))
                        kind = 'raw' if nstr <= 1 else 'xform'
                        res.units.append([s._steps, kind, v])
                    return r
            return super()._call_function(fn, args, env)

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
    res.steps = sb._steps
    res.elapsed = time.time() - t0
    return res


# --------------------------------------------------------------------------- #
# self-test
# --------------------------------------------------------------------------- #

_SYNTH = '''
local KT = { aa = 'hello', bb = 'world' }
local function decraw(s)
  local _, out = 1, ''
  repeat
    out = out .. string.char(string.byte(s, _) - 1)
    _ = _ + 1
  until _ > #s
  return out
end
local function xform(a, b)
  local _ = 0
  repeat _ = _ + 1 until _ > 1
  return KT[a] .. KT[b]
end
local p1 = decraw('bb')
local p2 = decraw('cc')
local msg = xform(p1, p2)
return msg
'''


def _selftest():
    fails = []

    def chk(tag, cond, extra=''):
        print(('[OK] ' if cond else '[XX] ') + tag + (' ' + extra if extra else ''))
        if not cond:
            fails.append(tag)

    r = assemble_stream(_SYNTH, max_steps=500000, sm_pattern=r'repeat')
    kinds = [u[1] for u in r.units]
    chk('T1 unit kinds raw,raw,xform', (not r.error) and kinds == ['raw', 'raw', 'xform'],
        'kinds=%s err=%s' % (kinds, r.error))
    chk('T2 raw units decoded by shift-1', r.raws() == ['aa', 'bb'], str(r.raws()))
    chk('T3 xform unit = plaintext concat', r.xforms() == ['helloworld'], str(r.xforms()))
    r4 = assemble_stream('local a = 1 repeat a = a + 1 until a > 2 return a',
                         max_steps=100000, sm_pattern=r'repeat\s+if\s+_')
    chk('T4 default SM regex ignores plain repeat', (not r4.error) and len(r4.units) == 0)
    r5 = assemble_stream('local i = 0 local t = {} repeat i = i + 1 t[i] = i until i > 500000 return t[1]',
                         max_steps=200000, sm_pattern=r'repeat')
    chk('T5 step cap safe, no str units', r5.error is not None and len(r5.units) == 0,
        'err=%s' % str(r5.error)[:40])

    print('')
    print('Result: %d/5' % (5 - len(fails)))
    if fails:
        print('[XX] FAILURES: %d' % len(fails))
        return 1
    print('[OK] ALL PASSED')
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description='MoonVeil decoded-stream assembler')
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
    print('stream: %s (max_steps=%d)' % (a.sample, a.max_steps))
    res = assemble_stream(src, max_steps=a.max_steps, sm_pattern=a.sm_pattern)
    print('units=%d raw=%d xform=%d steps=%d elapsed=%.1fs error=%s' %
          (len(res.units), len(res.raws()), len(res.xforms()), res.steps,
           res.elapsed, res.error))
    for u in res.units[:14]:
        print('  step=%-9d %-5s %r' % (u[0], u[1], u[2][:60]))
    if a.outdir:
        if not os.path.isdir(a.outdir):
            os.makedirs(a.outdir)
        with open(os.path.join(a.outdir, 'stream.json'), 'w', encoding='utf-8') as fh:
            json.dump({'units': res.units, 'steps': res.steps, 'error': res.error},
                      fh, ensure_ascii=False)
        print('saved -> %s' % os.path.join(a.outdir, 'stream.json'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
