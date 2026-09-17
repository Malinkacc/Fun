"""MoonVeil 2.x VM tracer (Sprint 7, slice 3a).

MoonVeil implements every VM opcode as a tiny closure of the shape

    function(a, b, c, d) a.H[d] = <expr over a.a(b, K1), a.a(c, K2)> return a.H[d] end

where ``H`` is the register file and ``a.a(x, K)`` decodes an operand
(value stored XOR/offset-masked by a per-site constant K).  Dispatch is a
table of those closures indexed by opcode, so there is no if-tree for the
static Luraph detector to find.

This module runs the sample in the Lua sandbox, classifies every called
LuaFunction body whose unparsed text looks like an opcode closure
(contains ``.H[`` and ``a.a(`/`a.g(`, short body), masks numeric literals
into a signature string, and records the call sequence: (signature,
numeric argument snapshot, step).  The sequence IS the flat VM program
trace; the signature table is the opcode catalogue.

Usage:
    py -m obfuscator.deobfuscator.moonveil.vm_trace --test
    py -m obfuscator.deobfuscator.moonveil.vm_trace path\\sample.lua --max-steps 2000000 --outdir out
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

_NUM_RE = re.compile(r'0x[0-9a-fA-F]+|\d+')


class TraceResult(object):
    def __init__(self):
        self.seq = []        # list of [sig, [nums], step]
        self.sigs = {}       # sig -> dict(count, example, body_id)
        self.steps = 0
        self.elapsed = 0.0
        self.error = None


def _sig_of(text):
    return _NUM_RE.sub('#', text)


def _looks_opcode(text):
    return ('.H[' in text and ('a.a(' in text or 'a.g(' in text) and len(text) < 240)


def _looks_decoder(text):
    return ('repeat' in text and '.H[' not in text and len(text) > 40)


def trace_vm(source, max_steps=2000000):
    res = TraceResult()
    t0 = time.time()
    chunk = Parser(Lexer(source).tokenize()).parse()
    up = ASTUnparser(minified=True)
    cache = {}

    class TSB(LuaSandbox):
        def __init__(s):
            super().__init__()
            s.MAX_STEPS = max_steps
            s._opstack = []

        def _body_text(s, fn):
            bid = id(fn.body)
            txt = cache.get(bid)
            if txt is None:
                try:
                    txt = ' '.join(up.unparse(x) for x in fn.body.statements)
                except Exception:
                    txt = ''
                cache[bid] = txt
            return txt

        def _call_function(s, fn, args, env=None):
            if isinstance(fn, LuaFunction) and fn.body is not None:
                txt = s._body_text(fn)
                nums = [a for a in args if isinstance(a, (int, float)) and not isinstance(a, bool)]
                if _looks_opcode(txt):
                    sig = _sig_of(txt)
                    if sig not in res.sigs:
                        res.sigs[sig] = {'count': 0, 'example': txt, 'body_id': id(fn.body)}
                    rec = [sig, nums, s._steps, [], None]
                    res.seq.append(rec)
                    res.sigs[sig]['count'] += 1
                    s._opstack.append(rec)
                    try:
                        r = super()._call_function(fn, args, env)
                    finally:
                        if s._opstack:
                            s._opstack.pop()
                    st = args[0] if args else None
                    if isinstance(st, LuaTable) and nums:
                        h = st.rawget('H')
                        if isinstance(h, LuaTable):
                            rec[4] = h.rawget(nums[-1])
                    return r
                if s._opstack and (txt == '' or _looks_decoder(txt)):
                    r = super()._call_function(fn, args, env)
                    v = r[0] if isinstance(r, list) else r
                    if isinstance(v, (int, float)) and not isinstance(v, bool):
                        s._opstack[-1][3].append(nums + [v])
                    return r
            return super()._call_function(fn, args, env)

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
    res.steps = sb._steps
    res.elapsed = time.time() - t0
    return res


# --------------------------------------------------------------------------- #
# self-test: synthetic MoonVeil-shaped VM
# --------------------------------------------------------------------------- #

_SYNTH = '''
local M = {}
M.H = {}
M.a = function(x, k)
  local i = 0
  local z = 41
  repeat i = i + 1 until i > 2
  z = z + x
  return x - k
end
M.g = function(x, y) return x * y end
M[1] = function(a, b, c, d) a.H[d] = a.a(b, 100) - a.a(c, 50) return a.H[d] end
M[2] = function(a, b, c, d) a.H[d] = a.a(b, 70) / a.a(c, 20) return a.H[d] end
M[3] = function(a, b, c, d) a.H[d] = a.g(a.a(b, 7), a.a(c, 3)) return a.H[d] end
local P = {
  {1, 105, 55, 1},
  {2, 170, 40, 2},
  {3, 13, 9, 3},
  {1, 200, 150, 4},
}
local acc = 0
for i = 1, #P do
  local p = P[i]
  acc = acc + M[p[1]](M, p[2], p[3], p[4])
end
return acc
'''


def _selftest():
    fails = []

    def chk(tag, cond, extra=''):
        print(('[OK] ' if cond else '[XX] ') + tag + (' ' + extra if extra else ''))
        if not cond:
            fails.append(tag)

    r = trace_vm(_SYNTH, max_steps=500000)
    chk('T1 synthetic VM traced, 4 instrs in order', (not r.error) and len(r.seq) == 4,
        'n=%d err=%s' % (len(r.seq), r.error))
    kinds = []
    for sig, nums, st, decs, post in r.seq:
        if '-' in sig and 'a.a(' in sig:
            kinds.append('SUB')
        elif '/' in sig:
            kinds.append('DIV')
        else:
            kinds.append('MUL')
    chk('T2 opcode shapes SUB/DIV/MUL in program order', kinds == ['SUB', 'DIV', 'MUL', 'SUB'],
        str(kinds))
    ok3 = len(r.seq) >= 1 and r.seq[0][1] == [105, 55, 1]
    chk('T3 operand snapshot = numeric args', ok3, str(r.seq[0][1] if r.seq else None))
    d0 = r.seq[0][3] if r.seq else []
    ok3b = d0 == [[105, 100, 5], [55, 50, 5]] and r.seq[0][4] == 0
    chk('T3b decoder calls captured with decoded results + post H[d]', ok3b,
        'decs=%s post=%s' % (d0, r.seq[0][4] if r.seq else None))
    chk('T4 signature catalogue has 3 opcodes', len(r.sigs) == 3, 'sigs=%d' % len(r.sigs))
    r5 = trace_vm('local function f(x) return x + 1 end return f(2)', max_steps=100000)
    chk('T5 plain closures not classified', (not r5.error) and len(r5.seq) == 0 and len(r5.sigs) == 0)

    print('')
    print('Result: %d/6' % (6 - len(fails)))
    if fails:
        print('[XX] FAILURES: %d' % len(fails))
        return 1
    print('[OK] ALL PASSED')
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description='MoonVeil VM tracer')
    ap.add_argument('sample', nargs='?')
    ap.add_argument('--test', action='store_true')
    ap.add_argument('--max-steps', type=int, default=2000000)
    ap.add_argument('--outdir', default=None)
    a = ap.parse_args(argv)
    if a.test:
        return _selftest()
    if not a.sample:
        ap.error('sample path required (or --test)')
    src = open(a.sample, encoding='utf-8', errors='replace').read()
    print('trace: %s (max_steps=%d)' % (a.sample, a.max_steps))
    res = trace_vm(src, max_steps=a.max_steps)
    print('instrs=%d opcodes=%d steps=%d elapsed=%.1fs error=%s' %
          (len(res.seq), len(res.sigs), res.steps, res.elapsed, res.error))
    dec_n = sum(len(e[3]) for e in res.seq)
    print('decoded operand calls: %d' % dec_n)
    top = sorted(res.sigs.items(), key=lambda kv: -kv[1]['count'])[:8]
    for sig, info in top:
        print('  %6d x %s' % (info['count'], sig[:110]))
    if a.outdir:
        if not os.path.isdir(a.outdir):
            os.makedirs(a.outdir)
        with open(os.path.join(a.outdir, 'trace.json'), 'w', encoding='utf-8') as fh:
            json.dump({'seq': res.seq, 'sigs': {k: {'count': v['count'], 'example': v['example']}
                                                for k, v in res.sigs.items()},
                       'steps': res.steps, 'error': res.error}, fh, ensure_ascii=False)
        print('saved -> %s' % os.path.join(a.outdir, 'trace.json'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
