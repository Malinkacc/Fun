"""MoonSec V3 proto-stream decoder (Sprint 7, slices 2b-5 / 2b-6).

Completes the mirror chain started in slices 2b-1..2b-4:

    env literal r  -> stage1 primitives (mirror.py)
    t(107, enc)    -> stage2 constants  (mirror.py)
    t(145, enc)    -> stage3 toolbelt   (mirror.py)
    de(u, ...)     -> THIS MODULE: decodes the 13702-char proto blob with the
                      same payload decoder (seed auto-discovered) and runs the
                      ee() proto assembler in Python.

Reader set inside de() (all mirrored here, positions 1-based like Lua):

    posfn(x, flag)  flag truthy -> query position; else advance by x
    o()  = 1 byte                    (factory mode 5)
    t()  = 2-byte little-endian      (local reader in de)
    n()  = 4-byte LITTLE-endian      (factory mode 4: (h*2^24)+(f*2^16)+(n*256)+e
                                      over string.byte(a, pos, pos+3) => the
                                      first byte is the least-significant, so
                                      the dword is little-endian)
    l()  = bit-range extractor       (factory mode 1, mirrored in mirror.py)
    _()  = IEEE754 double: two n() words, low word first => a standard
           little-endian 64-bit float (struct '<d')
    p(m) = string: m = n() length (0 -> ''), slice of the decoded blob

ee() proto assembler (u = anti-tamper table with u[2]=2, u[3]=3):

    const pool: n() entries; per entry a tag byte o():
        2 -> boolean (o() ~= 0), 1 -> double (_()), 0 -> string (p())
    instructions: n() headers; header byte hd = o():
        bit(hd,1)==1 -> header is data, skipped
        fk = bits(hd,2,3): operand-B kind
            0 -> B=t(), C=t()   1 -> B=n()
            2 -> B=n()-2^16     3 -> B=n()-2^16, C=t()
        ok = bits(hd,4,6): constant substitution flags for fields 1/2/3
            bit1 -> op   = const[op]      (1-based in Lua)
            bit2 -> B    = const[B]
            bit3 -> C    = const[C]
        instruction = {opcode=t(), A=t(), B, C}   (Lua e[d],d=2 => A)
    nested protos: n() recursive ee() calls (0-based list in Lua m[e-1])
    nparams: o()

REAL SHIPPED BLOB (moonsec_v3.lua) -- SOLVED.  The whole stream is little-
endian.  Seed 252 decodes the 13702-char blob to 6843 bytes that parse as a
single top-level proto consuming the stream EXACTLY (pos 6843/6843):

    70 consts (43 strings + 27 numbers), 284 instructions, 7 nested protos.

The seed is unique: it is the only candidate whose decode both (a) starts a
structurally valid ee() stream that consumes ~100% of the bytes and (b)
exposes the real VM API string constants (print, string, pcall, loadstring,
getfenv, setmetatable, ...) plus MoonSec internals (MoonSec_StringsHiddenAttr)
and anti-tamper taunts (Federal was here, the webcam ASCII art).  find_seed
does the structural scan; find_seed_by_tokens is the content-based fallback.

Usage:
    py -m obfuscator.deobfuscator.moonsec.proto_decode --test
    py -m obfuscator.deobfuscator.moonsec.proto_decode --sample path\\moonsec_v3.lua --outdir out
"""

import os
import re
import sys
import json
import math
import struct
import argparse
from collections import Counter

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from obfuscator.deobfuscator.moonsec.mirror import decode_payload, bit_range


class StreamError(Exception):
    pass


class Stream:
    """Position-scanned byte stream with the MoonSec reader set (1-based).

    All multi-byte integers are LITTLE-endian (factory mode 4 = n() builds the
    dword with the first byte as the least-significant one)."""

    def __init__(self, data, pos=1):
        self.d = data
        self.pos = pos

    def remaining(self):
        # pos is 1-based: pos == len+1 means fully consumed
        return len(self.d) - self.pos + 1 if self.pos <= len(self.d) else 0

    def query(self):
        return self.pos

    def advance(self, k):
        self.pos += k

    def byte1(self):
        if self.pos < 1 or self.pos > len(self.d):
            raise StreamError('byte1 out of range at %d' % self.pos)
        b = self.d[self.pos - 1]
        self.pos += 1
        return b

    def word2le(self):
        if self.pos < 1 or self.pos + 1 > len(self.d):
            raise StreamError('word2le out of range at %d' % self.pos)
        lo = self.d[self.pos - 1]
        hi = self.d[self.pos]
        self.pos += 2
        return hi * 256 + lo

    def word4le(self):
        if self.pos < 1 or self.pos + 3 > len(self.d):
            raise StreamError('word4le out of range at %d' % self.pos)
        b = self.d[self.pos - 1:self.pos + 3]
        self.pos += 4
        return b[0] | (b[1] << 8) | (b[2] << 16) | (b[3] << 24)

    def float64(self):
        # _() reads two n() words, low word first -> a standard LE double.
        if self.pos < 1 or self.pos + 7 > len(self.d):
            raise StreamError('float64 out of range at %d' % self.pos)
        b = self.d[self.pos - 1:self.pos + 7]
        self.pos += 8
        return struct.unpack('<d', bytes(b))[0]

    def string(self, n=None):
        if n is None:
            n = self.word4le()
            if n == 0:
                return b''
        if n < 0 or self.pos - 1 + n > len(self.d):
            raise StreamError('string out of range at %d len %s' % (self.pos, n))
        s = self.d[self.pos - 1:self.pos - 1 + n]
        self.pos += n
        return s


def decode_proto(st, u2=2, u3=3, int_fix=True):
    """Mirror of ee(): one function proto from the stream."""
    consts = []
    cnt = st.word4le()
    if cnt < 0 or cnt > 1 << 20:
        raise StreamError('const count %d' % cnt)
    for _i in range(cnt):
        tag = st.byte1()
        if tag == 2:
            v = st.byte1() != 0
        elif tag == 1:
            v = st.float64()
            if int_fix and isinstance(v, float) and float(v).is_integer() \
                    and abs(v) < 2 ** 53:
                v = int(v)
        elif tag == 0:
            v = st.string()
        else:
            raise StreamError('bad const tag %d at %d' % (tag, st.query()))
        consts.append(v)

    instrs = []
    icnt = st.word4le()
    if icnt < 0 or icnt > 1 << 24:
        raise StreamError('instr count %d' % icnt)
    for _i in range(icnt):
        hd = st.byte1()
        if bit_range(hd, 1, 1) != 0:
            continue  # data header, not an instruction
        fk = bit_range(hd, 2, 3)
        ok = bit_range(hd, 4, 6)
        ins = [st.word2le(), st.word2le(), None, None]
        if fk == 0:
            ins[2] = st.word2le()
            ins[3] = st.word2le()
        elif fk == 1:
            ins[2] = st.word4le()
        elif fk == u2:
            ins[2] = st.word4le() - 65536
        elif fk == u3:
            ins[2] = st.word4le() - 65536
            ins[3] = st.word2le()
        else:
            raise StreamError('bad operand kind %d' % fk)
        if bit_range(ok, 1, 1) == 1:
            ins[0] = _subst(consts, ins[0])
        if bit_range(ok, 2, 2) == 1:
            ins[2] = _subst(consts, ins[2])
        if bit_range(ok, 3, 3) == 1:
            ins[3] = _subst(consts, ins[3])
        instrs.append(ins)

    nested = []
    ncnt = st.word4le()
    if ncnt < 0 or ncnt > 1 << 16:
        raise StreamError('nested count %d' % ncnt)
    for _i in range(ncnt):
        nested.append(decode_proto(st, u2, u3, int_fix))

    nparams = st.byte1()
    return {'instrs': instrs, 'consts': consts, 'nested': nested, 'nparams': nparams}


def _subst(consts, idx):
    if isinstance(idx, int) and 1 <= idx <= len(consts):
        return consts[idx - 1]
    return None


def decode_all(data, pos=1, max_protos=4096):
    """Decode successive top-level protos until the stream is exhausted."""
    st = Stream(data, pos)
    protos = []
    while st.remaining() > 0 and len(protos) < max_protos:
        protos.append(decode_proto(st))
    return protos


def decode_full(data, pos=1):
    """Decode ONE top-level proto and report (proto, consumed, total).  The
    real shipped blob is a single nested proto tree that consumes the stream
    exactly, so consumed/total == 1.0 is the structural validity signal."""
    st = Stream(data, pos)
    proto = decode_proto(st)
    consumed = st.query() - pos
    return proto, consumed, len(data)


# --------------------------------------------------------------------------- #
# blob extraction + seed discovery
# --------------------------------------------------------------------------- #

_BLOB_RE = re.compile(r'local function de\(u,\.\.\.\)local a=t\(e,"([^"]*)"')


def extract_blob(source):
    m = _BLOB_RE.search(source)
    return m.group(1) if m else None


def _nibbles(blob):
    sbox = {}
    for i in range(16):
        sbox[blob[i]] = i
    body = blob[16:]
    base = []
    for k in range(0, len(body) - 1, 2):
        hi = sbox.get(body[k], 0)
        lo = sbox.get(body[k + 1], 0)
        base.append(hi * 16 + lo)
    return base


def find_seed(blob, seed_max=1024, head=12, min_frac=0.9):
    """Discover the payload seed f such that decode_payload(blob, f) is a
    structurally valid ee() stream.  A cheap head filter (small LE const count
    + valid first tag) selects candidates; each survivor is fully parsed and
    scored by the fraction of the stream it consumes.  The real blob parses to
    exactly 1.0; the best candidate is returned."""
    base = _nibbles(blob)
    if len(base) < head:
        return None, None
    cands = []
    for f in range(seed_max):
        bs = [(base[i] + f * (i + 1)) % 256 for i in range(head)]
        cc = bs[0] | (bs[1] << 8) | (bs[2] << 16) | (bs[3] << 24)   # LE32
        if not (1 <= cc <= 4096):
            continue
        if bs[4] not in (0, 1, 2):
            continue
        cands.append(f)
    best = None
    for f in cands:
        data = decode_payload(blob, f)
        try:
            proto, consumed, total = decode_full(data)
        except (StreamError, IndexError, ValueError, OverflowError, struct.error):
            continue
        frac = consumed / total if total else 0.0
        if frac >= min_frac and _plausible_proto(proto):
            if best is None or frac > best[0]:
                best = (frac, f, [proto])
    if best is not None:
        return best[1], best[2]
    return None, None


def _plausible_proto(proto, min_instr=4):
    """Reject accidental parses: require a minimal amount of real content."""
    total = [0]

    def walk(p):
        total[0] += len(p['instrs'])
        for q in p['nested']:
            walk(q)

    walk(proto)
    return total[0] >= min_instr


def _plausible(protos, min_instr=4):
    total = [0]

    def walk(p):
        total[0] += len(p['instrs'])
        for q in p['nested']:
            walk(q)

    for p in protos:
        walk(p)
    return total[0] >= min_instr


# --------------------------------------------------------------------------- #
# real-sample blob: token-based seed discovery + string-constant extraction
# --------------------------------------------------------------------------- #
#
# Content-based fallback for seed discovery: the correct seed is the unique one
# whose decode exposes the VM's real string-constant table (stdlib/import names
# the VM imports).  Used when the structural scan is inconclusive.

_API_TOKENS = (
    b'print', b'string', b'pcall', b'loadstring', b'getfenv',
    b'setmetatable', b'type', b'char', b'load', b'match', b'ldexp', b'dump',
)


def _token_hits(data):
    return sum(1 for t in _API_TOKENS if t in data)


def _longest_run(data):
    best = 0
    run = 0
    for b in data:
        if 32 <= b < 127:
            run += 1
            if run > best:
                best = run
        else:
            run = 0
    return best


def find_seed_by_tokens(blob, seed_max=256, min_tokens=3):
    """Discover the blob seed by scoring each candidate decode for the presence
    of real VM API string constants.  Returns (seed, decoded_bytes) or (None,
    None)."""
    best = None
    for s in range(seed_max):
        data = decode_payload(blob, s)
        hits = _token_hits(data)
        if hits < min_tokens:
            continue
        run = _longest_run(data)
        key = (hits, run)
        if best is None or key > best[0]:
            best = (key, s, data)
    if best is None:
        return None, None
    return best[1], best[2]


def extract_blob_strings(data, min_len=4):
    """Extract the VM string-constant table from a decoded blob as maximal
    printable-ASCII runs (>= min_len)."""
    out = []
    for m in re.finditer(rb'[ -~]{%d,}' % min_len, data):
        try:
            out.append(m.group().decode('ascii'))
        except UnicodeDecodeError:
            out.append(repr(m.group()))
    return out


# --------------------------------------------------------------------------- #
# stats / rendering
# --------------------------------------------------------------------------- #

def proto_stats(protos):
    n_instr = n_const = n_proto = 0
    opcodes = Counter()
    strings = []

    def walk(p):
        nonlocal n_instr, n_const, n_proto
        n_proto += 1
        n_instr += len(p['instrs'])
        n_const += len(p['consts'])
        for ins in p['instrs']:
            if isinstance(ins[0], int):
                opcodes[ins[0]] += 1
        for c in p['consts']:
            if isinstance(c, bytes) and c:
                try:
                    strings.append(c.decode('utf-8'))
                except UnicodeDecodeError:
                    strings.append(repr(c[:32]))
        for q in p['nested']:
            walk(q)

    for p in protos:
        walk(p)
    return {
        'protos': n_proto,
        'instrs': n_instr,
        'consts': n_const,
        'distinct_opcodes': len(opcodes),
        'opcode_range': [min(opcodes), max(opcodes)] if opcodes else None,
        'top_opcodes': opcodes.most_common(16),
        'strings': strings,
    }


def _jsonable(v):
    if isinstance(v, bytes):
        try:
            return v.decode('utf-8')
        except UnicodeDecodeError:
            return {'__bytes__': v.hex()}
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return str(v)
    return v


def dump_json(protos, path):
    def conv(p):
        return {
            'nparams': p['nparams'],
            'consts': [_jsonable(c) for c in p['consts']],
            'instrs': [[_jsonable(x) for x in i] for i in p['instrs']],
            'nested': [conv(q) for q in p['nested']],
        }
    json.dump([conv(p) for p in protos], open(path, 'w', encoding='utf-8'))


# --------------------------------------------------------------------------- #
# self-test: synthetic stream writer + round-trip
# --------------------------------------------------------------------------- #

def _w_byte(out, b):
    out.append(b & 0xff)


def _w2le(out, v):
    out.append(v & 0xff)
    out.append((v >> 8) & 0xff)


def _w4le(out, v):
    out.append(v & 0xff)
    out.append((v >> 8) & 0xff)
    out.append((v >> 16) & 0xff)
    out.append((v >> 24) & 0xff)


def _w_float(out, v):
    out.extend(struct.pack('<d', v))


def _w_str(out, s):
    b = s.encode('latin1')
    _w4le(out, len(b))
    out.extend(b)


def _synth_stream():
    """One proto: 3 consts (bool/number/string), 5 instruction kinds,
    one nested proto, 2 params."""
    out = bytearray()
    # consts
    _w4le(out, 3)
    _w_byte(out, 2); _w_byte(out, 1)          # True
    _w_byte(out, 1); _w_float(out, 3.5)       # number
    _w_byte(out, 0); _w_str(out, 'abc')       # string
    # instructions (6 headers: 5 real + 1 data header with bit0=1)
    _w4le(out, 6)
    _w_byte(out, 0b0000000)                   # fk=0 ok=0
    _w2le(out, 40); _w2le(out, 1); _w2le(out, 2); _w2le(out, 3)
    _w_byte(out, 0b0000001 << 1)              # fk=1: bits2-3=01
    _w2le(out, 41); _w2le(out, 2); _w4le(out, 70000)
    _w_byte(out, 0b010 << 1)                  # fk=2 signed
    _w2le(out, 42); _w2le(out, 3); _w4le(out, 65536 + 1234)
    _w_byte(out, 0b011 << 1)                  # fk=3 signed + C
    _w2le(out, 43); _w2le(out, 4); _w4le(out, 65536 + 77); _w2le(out, 9)
    _w_byte(out, 0b0111 << 3)                 # fk=0, ok=7: substitute all
    _w2le(out, 1); _w2le(out, 5)              # opcode<-const1 (True->bool!)
    _w2le(out, 3); _w2le(out, 2)              # B<-const3 'abc', C<-const2 3.5
    # data header (bit0=1) interleaved before nested count
    _w_byte(out, 0b1)
    # nested: 1 proto with 0 consts 0 instrs 0 nested 1 param
    _w4le(out, 1)
    _w4le(out, 0)
    _w4le(out, 0)
    _w4le(out, 0)
    _w_byte(out, 1)
    _w_byte(out, 2)                           # nparams of outer
    return bytes(out)


def _selftest():
    fails = []

    def chk(tag, cond, extra=''):
        print(('[OK] ' if cond else '[XX] ') + tag + (' ' + extra if extra else ''))
        if not cond:
            fails.append(tag)

    st = Stream(b'\x01\x02\x03\x04\x05\x06\x07')
    chk('T1 readers: byte/word2le/word4le/bit range',
        st.byte1() == 1 and st.word2le() == 0x0302 and st.word4le() == 0x07060504
        and bit_range(0b10110, 2, 3) == 0b11 and st.remaining() == 0)
    out = bytearray(); _w_float(out, 3.5); _w_float(out, -0.0); _w_float(out, 2.0)
    st = Stream(bytes(out))
    chk('T2 float64 reader (3.5, -0.0, 2.0)',
        st.float64() == 3.5 and math.copysign(1, st.float64()) == -1.0
        and st.float64() == 2.0)
    out = bytearray(); _w_str(out, 'hello'); _w4le(out, 0)
    st = Stream(bytes(out))
    chk('T3 string reader + zero-length',
        st.string() == b'hello' and st.string() == b'')
    protos = decode_all(_synth_stream())
    chk('T4 proto round-trip: consts/instrs/nested/params',
        len(protos) == 1
        and protos[0]['consts'] == [True, 3.5, b'abc']
        and len(protos[0]['instrs']) == 5
        and protos[0]['instrs'][0] == [40, 1, 2, 3]
        and protos[0]['instrs'][1] == [41, 2, 70000, None]
        and protos[0]['instrs'][2] == [42, 3, 1234, None]
        and protos[0]['instrs'][3] == [43, 4, 77, 9]
        and len(protos[0]['nested']) == 1 and protos[0]['nparams'] == 2,
        str(protos[0]['instrs']) + ' nested=%d' % len(protos[0]['nested']))
    sub = protos[0]['instrs'][4]
    chk('T5 constant substitution via ok bits',
        sub == [True, 5, b'abc', 3.5], str(sub))
    # seed discovery on a synthetic blob: encode synth stream with a known seed
    seed = 1234
    sbox = 'abcdefghijklmnop'
    body = []
    c = 0
    for k, b in enumerate(_synth_stream()):
        c = seed + c
        raw = (b - c) % 256
        body.append(sbox[raw // 16])
        body.append(sbox[raw % 16])
    blob = sbox + ''.join(body)
    f, protos2 = find_seed(blob, seed_max=4096)
    # NOTE: the payload cipher is degenerate in the seed: carry = f*(k+1)
    # mod 256, and 1024*(k+1) % 256 == 0, so seeds f and f+1024 decode
    # identically.  Discovery therefore returns the smallest equivalent.
    chk('T6 seed auto-discovery on synthetic blob',
        f is not None and f % 1024 == seed % 1024
        and protos2 and protos2[0]['consts'] == [True, 3.5, b'abc'],
        'seed=%s (equiv class mod 1024 of %d)' % (f, seed))

    # T7: real-blob path -- token-based seed discovery + string extraction.
    plain = (b'\x46\x00\x00\x00'                       # LE count header
             b'\x00print\x00string\x00pcall'
             b'\x00loadstring\x00getfenv\x00setmetatable'
             b'\x00MoonSec_StringsHiddenAttr')
    seed7 = 252
    sbox7 = '>4^Kcmin{?U-lwZ3'
    body7 = []
    c7 = 0
    for k, b in enumerate(plain):
        c7 = (seed7 + c7) % 256
        raw = (b - c7) % 256
        body7.append(sbox7[raw // 16])
        body7.append(sbox7[raw % 16])
    blob7 = sbox7 + ''.join(body7)
    f7, data7 = find_seed_by_tokens(blob7)
    strs7 = extract_blob_strings(data7) if data7 else []
    joined7 = b''.join(s.encode('ascii', 'replace') for s in strs7)
    chk('T7 real-blob token seed discovery + string extraction',
        f7 == seed7 and data7 == plain
        and b'loadstring' in joined7 and b'getfenv' in joined7
        and b'MoonSec_StringsHiddenAttr' in joined7,
        'seed=%s runs=%d' % (f7, len(strs7)))

    # T8: real-blob STRUCTURAL discovery -- a single LE proto (one substituted
    # string const + 5 instructions, like the shipped blob's shape) encoded at
    # seed 252 must be found by find_seed and consume the stream exactly.
    p8 = bytearray()
    _w4le(p8, 1)                              # const count = 1 (small, LE)
    _w_byte(p8, 0); _w_str(p8, 'MoonSec_StringsHiddenAttr')   # const[0] string
    _w4le(p8, 5)                              # instr count = 5
    _w_byte(p8, 0b10 << 3)                    # fk=0, ok bit2 -> substitute B
    _w2le(p8, 8); _w2le(p8, 0); _w2le(p8, 1); _w2le(p8, 0)
    for _op in (18, 5, 26, 12):                # 4 plain fk=0 instructions
        _w_byte(p8, 0)
        _w2le(p8, _op); _w2le(p8, 0); _w2le(p8, 0); _w2le(p8, 0)
    _w4le(p8, 0)                              # nested count = 0
    _w_byte(p8, 0)                            # nparams
    p8 = bytes(p8)
    seed8 = 252
    body8 = []
    c8 = 0
    for k, b in enumerate(p8):
        c8 = (seed8 + c8) % 256
        raw = (b - c8) % 256
        body8.append(sbox7[raw // 16])
        body8.append(sbox7[raw % 16])
    blob8 = sbox7 + ''.join(body8)
    f8, protos8 = find_seed(blob8)
    consumed8 = total8 = 0
    if f8 is not None:
        _pr, consumed8, total8 = decode_full(decode_payload(blob8, f8))
    chk('T8 real-blob structural discovery consumes stream exactly',
        f8 is not None and f8 % 1024 == seed8 % 1024
        and protos8 and consumed8 == total8
        and protos8[0]['instrs'][0][2] == b'MoonSec_StringsHiddenAttr',
        'seed=%s consumed=%d/%d' % (f8, consumed8, total8))

    print('')
    print('Result: %d/8' % (8 - len(fails)))
    if fails:
        print('[XX] FAILURES: %d' % len(fails))
        return 1
    print('[OK] ALL PASSED')
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description='MoonSec proto-stream decoder')
    ap.add_argument('--test', action='store_true')
    ap.add_argument('--sample', default=None)
    ap.add_argument('--outdir', default='out')
    ap.add_argument('--show', type=int, default=24)
    a = ap.parse_args(argv)
    if a.test:
        return _selftest()
    if not a.sample:
        print('need --sample path (or --test)')
        return 2
    src = open(a.sample, encoding='utf-8', errors='replace').read()
    blob = extract_blob(src)
    if not blob:
        print('[XX] proto blob not found')
        return 1
    print('blob chars=%d alphabet=%d' % (len(blob), len(set(blob))))

    f, protos = find_seed(blob)
    if f is not None:
        proto, consumed, total = decode_full(decode_payload(blob, f))
        print('seed f=%d  STRUCTURAL ee parse: consumed %d/%d (%.1f%%)' % (
            f, consumed, total, 100.0 * consumed / total))
        st = proto_stats(protos)
        print('protos(total)=%d instrs=%d consts=%d opcodes=%d range=%s' % (
            st['protos'], st['instrs'], st['consts'], st['distinct_opcodes'],
            st['opcode_range']))
        print('top opcodes:', st['top_opcodes'][:10])
        print('string consts: %d, first %d:' % (len(st['strings']), a.show))
        for s in st['strings'][:a.show]:
            print('  %r' % s[:60])
        os.makedirs(a.outdir, exist_ok=True)
        p1 = os.path.join(a.outdir, 'protos.json')
        dump_json(protos, p1)
        p2 = os.path.join(a.outdir, 'proto_stats.json')
        json.dump({k: v for k, v in st.items() if k != 'strings'},
                  open(p2, 'w', encoding='utf-8'), indent=1)
        p3 = os.path.join(a.outdir, 'blob_decoded.bin')
        open(p3, 'wb').write(decode_payload(blob, f))
        print('saved ->', p1, p2, p3)
        return 0

    # Fallback: content-based seed discovery + raw string extraction.
    f, data = find_seed_by_tokens(blob)
    if f is None:
        print('[XX] seed not found (neither structural nor token match)')
        return 1
    strings = extract_blob_strings(data)
    print('seed f=%d (token match)  decoded bytes=%d' % (f, len(data)))
    print('word0: LE32=%d  api-tokens=%d/%d  longest-ascii-run=%d' % (
        int.from_bytes(data[0:4], 'little'), _token_hits(data),
        len(_API_TOKENS), _longest_run(data)))
    print('string constants: %d (first %d):' % (len(strings), a.show))
    for s in strings[:a.show]:
        print('  %r' % s[:70])
    os.makedirs(a.outdir, exist_ok=True)
    p1 = os.path.join(a.outdir, 'blob_strings.json')
    json.dump({'seed': f, 'decoded_len': len(data),
               'api_token_hits': _token_hits(data),
               'longest_run': _longest_run(data), 'strings': strings},
              open(p1, 'w', encoding='utf-8'), indent=1)
    p2 = os.path.join(a.outdir, 'blob_decoded.bin')
    open(p2, 'wb').write(data)
    print('saved ->', p1, p2)
    return 0


if __name__ == '__main__':
    sys.exit(main())
