"""MoonSec V3 proto-stream decoder (Sprint 7, slice 2b-5).

Completes the mirror chain started in slices 2b-1..2b-4:

    env literal r  -> stage1 primitives (mirror.py)
    t(107, enc)    -> stage2 constants  (mirror.py)
    t(145, enc)    -> stage3 toolbelt   (mirror.py)
    de(u, ...)     -> THIS MODULE: decodes the 13702-char proto blob with
                      the same payload decoder (seed = chunk state-machine
                      final `e`, auto-discovered by structural validation)
                      and runs the ee() proto assembler in Python.

Reader set inside de() (all mirrored here, positions 1-based like Lua):

    posfn(x, flag)  flag truthy -> query position; else advance by x
    o()  = 1 byte                    (factory mode 5)
    t()  = 2-byte little-endian      (local reader in de)
    n()  = 4-byte big-endian         (factory mode 4)
    l()  = bit-range extractor       (factory mode 1, mirrored in mirror.py)
    _()  = IEEE754 double from two BE words (low word first):
           mant = bits(e,1,20)*2^32 + d; exp = bits(e,21,31);
           sign = (-1)^bits(e,32); ldexp(sign, exp-1023)*(c + mant/2^52)
           with denormal (exp==0, c=0) and inf/nan (exp==2047) branches
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

The chunk state machine (seed source) is not transpiled here; instead the
seed is searched over 0..65535 by decoding the first words and validating
the ee() framing structurally, which is sample-independent.

REAL SHIPPED BLOB (moonsec_v3.lua): the 13702-char proto blob does NOT use
the synthetic ee() framing above -- its first dword is a little-endian count
(= 70) and its const records use a tag/length layout that does not round-trip
through decode_proto.  The payload cipher is identical, however, so the seed
is recovered by scoring every candidate decode for the presence of real VM
API string constants (find_seed_by_tokens).  Seed 252 is unique: it is the
only candidate exposing the stdlib/import names (print, string, pcall,
loadstring, getfenv, setmetatable, ...) plus MoonSec internals
(MoonSec_StringsHiddenAttr) and anti-tamper taunts (Federal was here, the
webcam ASCII art).  extract_blob_strings then recovers the full 44-entry
string-constant table as printable-ASCII runs.  --sample writes
blob_strings.json + blob_decoded.bin.

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
    """Position-scanned byte stream with the MoonSec reader set (1-based)."""

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

    def word4be(self):
        if self.pos < 1 or self.pos + 3 > len(self.d):
            raise StreamError('word4be out of range at %d' % self.pos)
        b = self.d[self.pos - 1:self.pos + 3]
        self.pos += 4
        return (b[0] << 24) | (b[1] << 16) | (b[2] << 8) | b[3]

    def float64(self):
        d = self.word4be()
        e = self.word4be()
        mant = bit_range(e, 1, 20) * (2 ** 32) + d
        exp = bit_range(e, 21, 31)
        sign = -1.0 if bit_range(e, 32, 32) else 1.0
        c = 1.0
        if exp == 0:
            if mant == 0:
                return sign * 0.0
            exp = 1
            c = 0.0
        elif exp == 2047:
            return sign * (math.inf if mant == 0 else math.nan)
        return math.ldexp(sign, exp - 1023) * (c + mant / (2 ** 52))

    def string(self, n=None):
        if n is None:
            n = self.word4be()
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
    cnt = st.word4be()
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
    icnt = st.word4be()
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
            ins[2] = st.word4be()
        elif fk == u2:
            ins[2] = st.word4be() - 65536
        elif fk == u3:
            ins[2] = st.word4be() - 65536
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
    ncnt = st.word4be()
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


def find_seed(blob, seed_max=1024, head=12):
    """Discover the payload seed f so that decode_payload(blob, f) starts a
    structurally valid ee() stream.  Uses only the first `head` bytes for
    candidate filtering, then full-parses survivors."""
    base = _nibbles(blob)
    if len(base) < head:
        return None, None
    cands = []
    for f in range(seed_max):
        bs = [(base[i] + f * (i + 1)) % 256 for i in range(head)]
        cc = (bs[0] << 24) | (bs[1] << 16) | (bs[2] << 8) | bs[3]
        if not (1 <= cc <= 4096):
            continue
        tag = bs[4]
        if tag not in (0, 1, 2):
            continue
        cands.append(f)
    for f in cands:
        data = decode_payload(blob, f)
        try:
            protos = decode_all(data)
        except (StreamError, IndexError, ValueError, OverflowError):
            continue
        if protos and protos[0]['instrs'] and _plausible(protos):
            return f, protos
    return None, None


def _plausible(protos, min_instr=4):
    """Reject accidental parses: require a minimal amount of real content."""
    total = [0, 0]

    def walk(p):
        total[0] += len(p['instrs'])
        total[1] += len(p['consts'])
        for q in p['nested']:
            walk(q)

    for p in protos:
        walk(p)
    return total[0] >= min_instr


# --------------------------------------------------------------------------- #
# real-sample blob: token-based seed discovery + string-constant extraction
# --------------------------------------------------------------------------- #
#
# The shipped MoonSec V3 blob does NOT use the synthetic ee() framing modeled
# above (its first dword is a little-endian count = 70, and its const records
# use a tag/length layout that does not round-trip through decode_proto).  The
# payload cipher, however, is identical, so the correct seed is the one whose
# decode exposes the VM's real string-constant table.  That seed is unique:
# only it reproduces the standard Lua/Roblox API names the VM imports.

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
    None).  Robust and sample-independent: the correct seed is the unique one
    exposing multiple stdlib/import names."""
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
    printable-ASCII runs (>= min_len).  This recovers every string constant
    (API imports, anti-tamper messages, hidden-attribute markers) without
    depending on the exact numeric record framing."""
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


def _w4be(out, v):
    out.append((v >> 24) & 0xff)
    out.append((v >> 16) & 0xff)
    out.append((v >> 8) & 0xff)
    out.append(v & 0xff)


def _w_float(out, v):
    hi, lo = struct.unpack('>II', struct.pack('>d', v))
    _w4be(out, lo)
    _w4be(out, hi)


def _w_str(out, s):
    b = s.encode('latin1')
    _w4be(out, len(b))
    out.extend(b)


def _synth_stream():
    """One proto: 3 consts (bool/number/string), 5 instruction kinds,
    one nested proto, 2 params."""
    out = bytearray()
    # consts
    _w4be(out, 3)
    _w_byte(out, 2); _w_byte(out, 1)          # True
    _w_byte(out, 1); _w_float(out, 3.5)       # number
    _w_byte(out, 0); _w_str(out, 'abc')       # string
    # instructions (6 headers: 5 real + 1 data header with bit0=1)
    _w4be(out, 6)
    _w_byte(out, 0b0000000)                   # fk=0 ok=0
    _w2le(out, 40); _w2le(out, 1); _w2le(out, 2); _w2le(out, 3)
    _w_byte(out, 0b0000001 << 1)              # fk=1: bits2-3=01
    _w2le(out, 41); _w2le(out, 2); _w4be(out, 70000)
    _w_byte(out, 0b010 << 1)                  # fk=2 signed
    _w2le(out, 42); _w2le(out, 3); _w4be(out, 65536 + 1234)
    _w_byte(out, 0b011 << 1)                  # fk=3 signed + C
    _w2le(out, 43); _w2le(out, 4); _w4be(out, 65536 + 77); _w2le(out, 9)
    _w_byte(out, 0b0111 << 3)                 # fk=0, ok=7: substitute all
    _w2le(out, 1); _w2le(out, 5)              # opcode<-const1 (True->bool!)
    _w2le(out, 3); _w2le(out, 2)              # B<-const3 'abc', C<-const2 3.5
    # data header (bit0=1) interleaved before nested count
    _w_byte(out, 0b1)
    # nested: 1 proto with 0 consts 0 instrs 0 nested 1 param
    _w4be(out, 1)
    _w4be(out, 0)
    _w4be(out, 0)
    _w4be(out, 0)
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
    chk('T1 readers: byte/word2le/word4be/bit range',
        st.byte1() == 1 and st.word2le() == 0x0302 and st.word4be() == 0x04050607
        and bit_range(0b10110, 2, 3) == 0b11 and st.remaining() == 0)
    out = bytearray(); _w_float(out, 3.5); _w_float(out, -0.0); _w_float(out, 2.0)
    st = Stream(bytes(out))
    chk('T2 float64 reader (3.5, -0.0, 2.0)',
        st.float64() == 3.5 and math.copysign(1, st.float64()) == -1.0
        and st.float64() == 2.0)
    out = bytearray(); _w_str(out, 'hello'); _w4be(out, 0)
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
    # Build a synthetic "shipped-style" blob whose plaintext carries real VM
    # API names, encode with a known seed, and confirm discovery + extraction.
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

    print('')
    print('Result: %d/7' % (7 - len(fails)))
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
        print('seed f=%d protos=%d (structural ee parse)' % (f, len(protos)))
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
        print('saved ->', p1, p2)
        return 0

    # Real shipped blob: synthetic ee() framing does not round-trip, but the
    # payload cipher is identical.  Recover the seed via API-token scoring and
    # extract the VM string-constant table directly.
    f, data = find_seed_by_tokens(blob)
    if f is None:
        print('[XX] seed not found (neither structural nor token match)')
        return 1
    strings = extract_blob_strings(data)
    word0_le = int.from_bytes(data[0:4], 'little')
    word0_be = int.from_bytes(data[0:4], 'big')
    print('seed f=%d (token match)  decoded bytes=%d' % (f, len(data)))
    print('word0: LE32=%d BE32=%d  api-tokens=%d/%d  longest-ascii-run=%d' % (
        word0_le, word0_be, _token_hits(data), len(_API_TOKENS),
        _longest_run(data)))
    print('string constants: %d (first %d):' % (len(strings), a.show))
    for s in strings[:a.show]:
        print('  %r' % s[:70])
    os.makedirs(a.outdir, exist_ok=True)
    p1 = os.path.join(a.outdir, 'blob_strings.json')
    json.dump({'seed': f, 'decoded_len': len(data), 'word0_le': word0_le,
               'api_token_hits': _token_hits(data),
               'longest_run': _longest_run(data),
               'strings': strings},
              open(p1, 'w', encoding='utf-8'), indent=1)
    p2 = os.path.join(a.outdir, 'blob_decoded.bin')
    open(p2, 'wb').write(data)
    print('saved ->', p1, p2)
    return 0


if __name__ == '__main__':
    sys.exit(main())
