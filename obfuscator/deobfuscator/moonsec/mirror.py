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


def parse_stream(stream, transformer=None, globals_map=None, initial_env=None):
    """Mirror of the MoonSec env-stream parser; returns (h, d).
    d is seeded from globals_map (getfenv stand-in); h can be seeded from a
    previous stage (the real Lua reuses one h table across c(r) and c(S));
    \\002 uses the transformer slot already installed into h."""
    pos = 0
    d = dict(globals_map or {})
    h = dict(initial_env or {})

    def take(k):
        nonlocal pos
        s = stream[pos:pos + k]
        pos += k
        return s

    while True:
        m = take(1)
        if m == b'\x05' or m == '\x05':
            break
        ln = take(1)
        ln = ln[0] if isinstance(ln, (bytes, bytearray)) else ord(ln)
        val = take(ln)
        if m == b'\x02' or m == '\x02':
            fn = transformer or h.get(b'YZOfVgIl') or h.get('YZOfVgIl')
            val = fn(val) if fn else val
        elif m == b'\x03' or m == '\x03':
            val = val != (b'\x00' if isinstance(val, bytes) else '\x00')
        elif m == b'\x06' or m == '\x06':
            d[val] = ('wrapper', val)
            val = ('wrapper', val)
        elif m == b'\x04' or m == '\x04':
            val = d.get(val)
        elif m == b'\x00' or m == '\x00':
            ln2 = take(1)
            ln2 = ln2[0] if isinstance(ln2, (bytes, bytearray)) else ord(ln2)
            name = take(ln2)
            base = d.get(val)
            if isinstance(base, dict):
                val = base.get(name)
            else:
                val = (base, name)
        key = take(8)
        h[key] = val
    return h, d


def parse_lua_escapes(text):
    """Decode a Lua string literal body with decimal escapes (\\116) to bytes."""
    out = bytearray()
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == '\\' and i + 1 < len(text):
            j = i + 1
            if text[j].isdigit():
                k = j
                while k < len(text) and k - j < 3 and text[k].isdigit():
                    k += 1
                out.append(int(text[j:k]) & 0xff)
                i = k
                continue
            if text[j] == 'n':
                out.append(10); i = j + 1; continue
            if text[j] == 't':
                out.append(9); i = j + 1; continue
            out.append(ord(text[j])); i = j + 1; continue
        out.append(ord(ch) & 0xff)
        i += 1
    return bytes(out)


def decode_payload(enc, f):
    """Mirror of the MoonSec payload decoder t(f, enc):
    sbox = first 16 chars mapped to 0..15; then char pairs -> nibbles ->
    byte = (hi*16 + lo + c) % 256 with carry c = f*(k+1)."""
    n3 = {}
    for i in range(16):
        n3[enc[i:i + 1] if isinstance(enc, str) else enc[i:i + 1].decode('latin1')] = i
    body = enc[16:] if isinstance(enc, str) else enc[16:].decode('latin1')
    out = bytearray()
    c = 0
    for k in range(0, len(body) - 1, 2):
        idx = k // 2
        c = f + c
        hi = n3.get(body[k], 0)
        lo = n3.get(body[k + 1], 0)
        out.append((hi * 16 + lo + c) % 256)
    return bytes(out)


def extract_literals(source):
    """Pull the env-stream literal r="..." and the payload call t(NN, "...")."""
    import re
    m = re.search(r'\br="([^"]*)"', source)
    r_lit = parse_lua_escapes(m.group(1)) if m else None
    payloads = [(int(m.group(1)), parse_lua_escapes(m.group(2)))
                for m in re.finditer(r'\bt\((\d+),"([^"]*)"', source)]
    f = payloads[0][0] if payloads else None
    enc = payloads[0][1] if payloads else None
    return r_lit, f, enc, payloads


_BASE_GLOBALS = {
    b'tonumber': lambda b: float(b) if b'.' in b else int(b),
    b'string': {b'char': lambda b: bytes([b[0]]) if isinstance(b, (bytes, bytearray)) else bytes([ord(b[0])]),
                b'sub': None, b'byte': None},
    b'table': {b'concat': None, b'insert': None},
}


def bootstrap_env(r_lit):
    """Run the env stream through parse_stream with getfenv-like globals."""
    glo = dict(_BASE_GLOBALS)
    h, d = parse_stream(r_lit, transformer=None, globals_map=glo)
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

    r_syn = (b'\x04\x08tonumberYZOfVgIl'
             b'\x00\x06string\x04charDXLBIEVz'
             b'\x05')
    glo = {b'tonumber': lambda b: int(b), b'string': {b'char': 'CHARFN'}}
    h6, d6 = parse_stream(r_syn, globals_map=glo)
    ok6 = h6.get(b'YZOfVgIl') is glo[b'tonumber'] and h6.get(b'DXLBIEVz') == 'CHARFN'
    chk('T6 bootstrap env: global + method entries', ok6, str(list(h6.items())[:2]))

    sbox = 'abcdefghijklmnop'
    plain = b'HI!'
    f = 107
    body = []
    c = 0
    for k, b in enumerate(plain):
        c = f + c
        raw = (b - c) % 256
        body.append(sbox[raw // 16])
        body.append(sbox[raw % 16])
    enc = sbox + ''.join(body)
    got = decode_payload(enc, f)
    chk('T7 decode_payload round-trips synthetic bytes', got == plain, '%r' % got)

    syn = 'local x = t(107,"abc") local y = t(145,"defgh") return x'
    rl, ff, ee, pl = extract_literals(syn)
    chk('T8 extract_literals finds both payloads', ff == 107 and ee == b'abc'
        and [p[0] for p in pl] == [107, 145] and pl[1][1] == b'defgh', str(pl))

    print('')
    print('Result: %d/8' % (8 - len(fails)))
    if fails:
        print('[XX] FAILURES: %d' % len(fails))
        return 1
    print('[OK] ALL PASSED')
    return 0


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description='MoonSec Python mirror')
    ap.add_argument('--test', action='store_true')
    ap.add_argument('--sample', default=None)
    a = ap.parse_args(argv)
    if a.test:
        return _selftest()
    if a.sample:
        src = open(a.sample, encoding='utf-8', errors='replace').read()
        r_lit, f, enc, payloads = extract_literals(src)
        print('r_lit=%s f=%s enc=%s' % (len(r_lit) if r_lit else None, f,
                                        len(enc) if enc else None))
        if not (r_lit and enc):
            print('[XX] literals not found')
            return 1
        glo = dict(_BASE_GLOBALS)
        h1, d1 = parse_stream(r_lit, globals_map=glo)
        print('stage1 env entries=%d keys=%s' % (len(h1), sorted(h1.keys())))
        s_stream = decode_payload(enc, f)
        print('decoded stream bytes=%d head=%r' % (len(s_stream), s_stream[:48]))
        glo2 = dict(glo)
        glo2.update(h1)
        h2, d2 = parse_stream(s_stream, globals_map=glo2, initial_env=h1)
        print('stage2 entries=%d' % len(h2))
        strs = [v for v in h2.values() if isinstance(v, bytes)]
        print('stage2 string values=%d sample=%s' % (len(strs), [x[:24] for x in strs[:6]]))
        for pi, (pf, penc) in enumerate(payloads[1:], start=3):
            sx = decode_payload(penc, pf)
            print('stage%d: f=%d decoded=%d head=%r' % (pi, pf, len(sx), sx[:40]))
            gloN = dict(glo2)
            gloN.update(h2)
            hN, dN = parse_stream(sx, globals_map=gloN, initial_env=dict(h2))
            kinds = {}
            for v in hN.values():
                kinds[type(v).__name__] = kinds.get(type(v).__name__, 0) + 1
            print('stage%d entries=%d kinds=%s' % (pi, len(hN), kinds))
            sb = [v for v in hN.values() if isinstance(v, bytes) and len(v) > 32]
            print('stage%d long strings=%d sample=%s' % (pi, len(sb), [x[:60] for x in sb[:3]]))
        return 0
    ap.error('use --test or --sample')


if __name__ == '__main__':
    sys.exit(main())
