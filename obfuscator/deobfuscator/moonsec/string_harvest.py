"""MoonSec V3 string-table harvester (Sprint 7, slice 2).

MoonSec V3 decrypts its string array AT RUNTIME: the bootstrap builds a
table of plaintext strings through a PRNG-driven loop (hot closures
``d = d + 1`` / ``e = r + e``), and the VM then indexes that table for every
string constant.  There is no loadstring layer, so the dynamic decryptor
(dynamic_decrypt.py) sees nothing -- but every plaintext string passes
through a table write.

This module executes the sample in the Lua sandbox with LuaTable.rawset
hooked class-wide, records every string value written per table (insertion
order, first-write step), and returns the tables that look like string
arrays: >= min_strings distinct string keys and string-key ratio >=
str_ratio.  For MoonSec V3 that is exactly the decrypted string table.

Usage:
    py -m obfuscator.deobfuscator.moonsec.string_harvest --test
    py -m obfuscator.deobfuscator.moonsec.string_harvest path\\sample.lua --max-steps 12000000 --outdir out

Heavy runs (real samples) are agent-side only; the --test self-test is
synthetic and finishes in seconds.
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


class HarvestResult(object):
    """Outcome of a string-harvest run."""

    def __init__(self):
        self.tables = []      # list of dict: strings/first_step/string_keys/all_keys
        self.steps = 0
        self.elapsed = 0.0
        self.error = None


class _Recorder(object):
    """Class-wide LuaTable.rawset hook collecting string writes per table."""

    def __init__(self, sb):
        self._sb = sb
        self._orig = LuaTable.rawset
        self.by_id = {}

    def install(self):
        rec = self
        orig = self._orig

        def wrapper(tbl, key, value):
            r = orig(tbl, key, value)
            ent = rec.by_id.get(id(tbl))
            if ent is None:
                ent = {'tbl': tbl, 'order': [], 'keys_str': set(),
                       'keys_all': set(), 'first': rec._sb._steps}
                rec.by_id[id(tbl)] = ent
            ent['keys_all'].add(key)
            if isinstance(value, str) and value:
                if key not in ent['keys_str']:
                    ent['keys_str'].add(key)
                    ent['order'].append(value)
            return r

        self._wrapper = wrapper
        LuaTable.rawset = wrapper

    def restore(self):
        LuaTable.rawset = self._orig

    def candidates(self, min_strings, str_ratio):
        out = []
        for ent in self.by_id.values():
            nk = len(ent['keys_str'])
            if nk < min_strings:
                continue
            ratio = nk / max(1, len(ent['keys_all']))
            if ratio < str_ratio:
                continue
            out.append({'strings': list(ent['order']), 'first_step': ent['first'],
                        'string_keys': nk, 'all_keys': len(ent['keys_all'])})
        out.sort(key=lambda d: d['first_step'])
        return out


def harvest_strings(source, max_steps=12000000, min_strings=50, str_ratio=0.8):
    """Run `source` in the sandbox and harvest runtime-built string tables."""
    res = HarvestResult()
    t0 = time.time()
    chunk = Parser(Lexer(source).tokenize()).parse()
    sb = LuaSandbox()
    sb.MAX_STEPS = max_steps
    env = dict(sb._globals)
    env['_G'] = _EnvTable(env)
    for g in ROBLOX_GLOBALS:
        if env.get(g) is None:
            env[g] = make_mock(sb, g)
    rec = _Recorder(sb)
    rec.install()
    try:
        sb._exec_chunk(chunk, env)
    except LuaReturn:
        pass
    except Exception as e:
        res.error = '%s: %s' % (type(e).__name__, str(e)[:200])
    finally:
        rec.restore()
    res.steps = sb._steps
    res.elapsed = time.time() - t0
    res.tables = rec.candidates(min_strings, str_ratio)
    return res


# --------------------------------------------------------------------------- #
# self-test
# --------------------------------------------------------------------------- #

_T1 = '''
local T = {}
for i = 1, 40 do
  local d = tostring(i)
  if #d < 2 then d = '0' .. d end
  T[i] = 's' .. d
end
local acc = ''
for i = 1, 40 do acc = acc .. T[i] .. ',' end
return #acc
'''

_T2 = '''
local M = {}
for i = 1, 60 do
  if i % 2 == 0 then M[i] = 'x' .. i else M[i] = i end
end
local N = {}
for i = 1, 80 do N[i] = i * 2 end
return M[2] + N[4]
'''

_T3 = '''
local t = {}
local i = 0
while true do
  i = i + 1
  t[i] = 'v' .. i
end
'''


def _selftest():
    fails = []

    def chk(tag, cond, extra=''):
        print(('[OK] ' if cond else '[XX] ') + tag + (' ' + extra if extra else ''))
        if not cond:
            fails.append(tag)

    orig_rawset = LuaTable.rawset

    r1 = harvest_strings(_T1, max_steps=2000000, min_strings=10)
    ok = (not r1.error and len(r1.tables) >= 1 and
          r1.tables[0]['strings'][:5] == ['s01', 's02', 's03', 's04', 's05'] and
          len(r1.tables[0]['strings']) == 40)
    chk('T1 synthetic string table harvested in order', ok,
        'n=%d err=%s' % (len(r1.tables[0]['strings']) if r1.tables else -1, r1.error))

    r2 = harvest_strings(_T2, max_steps=2000000, min_strings=10, str_ratio=0.8)
    chk('T2 mixed/numeric tables rejected by ratio+min', len(r2.tables) == 0,
        'tables=%d' % len(r2.tables))

    r3 = harvest_strings(_T3, max_steps=200000, min_strings=10)
    ok3 = (r3.error is not None and len(r3.tables) >= 1 and
           len(r3.tables[0]['strings']) > 1000)
    chk('T3 step cap stops infinite builder, partial harvest kept', ok3,
        'err=%s n=%d' % (str(r3.error)[:40], len(r3.tables[0]['strings']) if r3.tables else -1))

    chk('T4 rawset restored after runs', LuaTable.rawset is orig_rawset)

    r5 = harvest_strings('local a = 1 return a + 1', max_steps=100000, min_strings=5)
    chk('T5 clean source yields no tables, no error',
        (not r5.error) and len(r5.tables) == 0)

    print('')
    print('Result: %d/5' % (5 - len(fails)))
    if fails:
        print('[XX] FAILURES: %d' % len(fails))
        return 1
    print('[OK] ALL PASSED')
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description='MoonSec string-table harvester')
    ap.add_argument('sample', nargs='?')
    ap.add_argument('--test', action='store_true')
    ap.add_argument('--max-steps', type=int, default=12000000)
    ap.add_argument('--min-strings', type=int, default=50)
    ap.add_argument('--str-ratio', type=float, default=0.8)
    ap.add_argument('--outdir', default=None)
    a = ap.parse_args(argv)
    if a.test:
        return _selftest()
    if not a.sample:
        ap.error('sample path required (or --test)')
    src = open(a.sample, encoding='utf-8', errors='replace').read()
    print('harvest: %s (max_steps=%d min_strings=%d)' % (a.sample, a.max_steps, a.min_strings))
    res = harvest_strings(src, max_steps=a.max_steps, min_strings=a.min_strings,
                          str_ratio=a.str_ratio)
    print('tables=%d steps=%d elapsed=%.1fs error=%s' %
          (len(res.tables), res.steps, res.elapsed, res.error))
    for i, t in enumerate(res.tables[:5]):
        print('  #%d first_step=%d string_keys=%d all_keys=%d head=%s' %
              (i, t['first_step'], t['string_keys'], t['all_keys'],
               json.dumps(t['strings'][:6], ensure_ascii=False)[:220]))
    if a.outdir:
        if not os.path.isdir(a.outdir):
            os.makedirs(a.outdir)
        with open(os.path.join(a.outdir, 'strings.json'), 'w', encoding='utf-8') as fh:
            json.dump({'tables': res.tables, 'steps': res.steps,
                       'elapsed': res.elapsed, 'error': res.error}, fh,
                      ensure_ascii=False, indent=1)
        print('saved -> %s' % os.path.join(a.outdir, 'strings.json'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
