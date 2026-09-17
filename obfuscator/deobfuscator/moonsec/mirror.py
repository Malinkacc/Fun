"""MoonSec V3 Python mirror (Sprint 7, slice 2b).

Interpreter execution of MoonSec is infeasible in CPython (payload stage
self-invokes f(8, nil, f, e, n) per element, see SPRINT7_NOTES.md), so the
decoder is re-implemented here as deterministic Python.

Mirrored pieces (extracted from the real sample AST):

1. Bit reader closure ``function(l, e, n)`` over the payload NUMBER l:
       with n:  floor(l / 2^(e-1)) % 2^((n-1)-(e-1)+1)     -- bits e..n
       else :  (l % (e+e) >= e) and 1 or 0                 -- single bit
   bit_range()/bit_get() below reproduce it exactly (1-based bit indexes).

2. Stream parser ``c = function(l)``: reads the env-building stream with a
   1-based cursor (n(k) = l:sub(pos, pos+k-1)), markers:
       \\005          end of stream
       \\002 + len    value transformed by the h transformer (YZOfVgIl slot)
       \\003 + len    boolean (value ~= '\\000')
       \\006 + len    install wrapper d[name] = function(n, e) return f(8,...) end
       \\004 + len    value = d[name]
       \\000 + len    value = d[name][sub(byte)]
     then key = next 8 bytes, h[key] = value.
   parse_stream() mirrors it with the transformer injected.

Self-test cross-validates the bit mirror against the REAL Lua closure
executed in the sandbox, and parse_stream against a synthetic stream.

Usage:
    py -m obfuscator.deobfuscator.moonsec.mirror --test
"""

import os
import sys

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

_LUA_BITREADER = (
    "local f = function(l, e, n)\n"
    "  if n then\n"
    "    local e = (l / 2 ^ (e - 1)) % 2 ^ ((n - 1) - (e - 1) + 1)\n"
    "    return e - e % 1\n"
    "  else\n"
    "    local e = 2 ^ (e - 1)\n"
    "    return (l % (e + e) >= e) and 1 or 0\n"
    "  end\n"
    "end\n"
)


def _lua_src(l, e, n):
    call = 'f(%r, %d, %d)' % (l, e, n) if n is not None else 'f(%r, %d)' % (l, e)
    return _LUA_BITREADER + 'return ' + call + '\n'


def bit_range(l, e, n):
    """Mirror of the Lua bit-range branch (1-based inclusive bit indexes)."""
    v = (l / 2.0 ** (e - 1)) % 2.0 ** ((n - 1) - (e - 1) + 1)
    return int(v - (v % 1))


def bit_get(l, e):
    """Mirror of the Lua single-bit branch."""
    p = 2 ** (e - 1)
    return 1 if (l % (p + p)) >= p else 0


def parse_stream(stream, transformer=None):
    """Mirror of the MoonSec env-stream parser; returns (h, d)."""
    pos = 0

    def take(k):
        nonlocal pos
        s = stream[pos:pos + k]
        pos += k
        return s

    h, d = {}, {}
    while True:
        m = take(1)
        if m == b'\x05' or m == '\x05':
            break
        ln = take(1)
        ln = ln[0] if isinstance(ln, (bytes, bytearray)) else ord(ln)
        val = take(ln)
        if m == b'\x02' or m == '\x02':
            val = transformer(val) if transformer else val
        elif m == b'\x03' or m == '\x03':
            val = val != (b'\x00' if isinstance(val, bytes) else '\x00')
        elif m == b'\x06' or m == '\x06':
            d[val] = ('wrapper', val)
            val = ('wrapper', val)
        elif m == b'\x04' or m == '\x04':
            val = d.get(val)
        elif m == b'\x00' or m == '\x00':
            k2 = take(1)
            k2 = k2[0] if isinstance(k2, (bytes, bytearray)) else ord(k2)
            base = d.get(val)
            val = (base, k2)
        key = take(8)
        h[key] = val
    return h, d


# --------------------------------------------------------------------------- #
# self-test
# --------------------------------------------------------------------------- #

def _selftest():
    fails = []

    def chk(tag, cond, extra=''):
        print(('[OK] ' if cond else '[XX] ') + tag + (' ' + extra if extra else ''))
        if not cond:
            fails.append(tag)

    from obfuscator.deobfuscator.core.lua_sandbox import LuaSandbox, _EnvTable, LuaReturn
    from obfuscator.lexer import Lexer
    from obfuscator.parser import Parser

    def lua_call(l, e, n=None):
        sb = LuaSandbox()
        sb.MAX_STEPS = 100000
        env = dict(sb._globals)
        env['_G'] = _EnvTable(env)
        chunk = Parser(Lexer(_lua_src(l, e, n)).tokenize()).parse()
        try:
            r = sb._exec_chunk(chunk, env)
        except LuaReturn as lr:
            r = lr.args[0] if lr.args else None
        if isinstance(r, list):
            r = r[0]
        return r

    vecs = [(0b10110011, 1, 8), (0b10110011, 3, 6), (123456789, 4, 20),
            (2 ** 40 + 7, 5, 33), (0b1111, 1, 1)]
    ok1 = all(bit_range(l, e, n) == lua_call(l, e, n) for l, e, n in vecs)
    chk('T1 bit_range matches real Lua closure', ok1,
        str([(l, e, n, bit_range(l, e, n), lua_call(l, e, n)) for l, e, n in vecs[:2]]))
    ok2 = all(bit_get(l, e) == lua_call(l, e) for l, e, n in vecs for e in (1, 2, 5, 8))
    chk('T2 bit_get matches real Lua closure', ok2)
    chk('T3 single bit via range equals bit_get',
        all(bit_range(0b10110011, i, i) == bit_get(0b10110011, i) for i in range(1, 9)))
    big = (1 << 62) + 0b10101010101010101010
    chk('T4 64-bit-scale value matches Lua', bit_range(big, 10, 30) == lua_call(big, 10, 30),
        '%d vs %s' % (bit_range(big, 10, 30), lua_call(big, 10, 30)))

    stream = (b'\x03\x04ABCDKEY1KEY1'      # bool true under key 'KEY1KEY1'
              b'\x06\x03xyzKEY2KEY2'       # wrapper installed as d['xyz']
              b'\x04\x03xyzKEY3KEY3'       # reference to d['xyz']
              b'\x05')
    h, d = parse_stream(stream, transformer=lambda b: b[::-1])
    vals = list(h.values())
    chk('T5 stream parser: 3 entries, bool/wrapper/ref semantics',
        len(h) == 3 and vals[0] is True and vals[1] == ('wrapper', b'xyz')
        and vals[2] == ('wrapper', b'xyz'), str(vals))

    print('')
    print('Result: %d/5' % (5 - len(fails)))
    if fails:
        print('[XX] FAILURES: %d' % len(fails))
        return 1
    print('[OK] ALL PASSED')
    return 0


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description='MoonSec Python mirror')
    ap.add_argument('--test', action='store_true')
    a = ap.parse_args(argv)
    if a.test:
        return _selftest()
    ap.error('use --test')


if __name__ == '__main__':
    sys.exit(main())
