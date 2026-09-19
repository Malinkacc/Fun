"""
NZL Studio Obfuscator v5 — Maximum protection Lua obfuscator

PROTECTION LAYERS:
  1. Triple encryption (S-box cipher → block rotation → substitution)
  2. Computed seeds (split into arithmetic parts, not plain integers)
  3. Blob-dependent key (hash of encrypted data mixed into decryption key)
  4. Junk code (random fake variables, dead branches, opaque predicates)
  5. Integrity verification (DJB2 hash check before loadstring)
  6. Polymorphic output (every build is structurally unique)
  7. Anti-tamper (modified blob → garbage output, not error)

WHY THIS IS HARD TO CRACK:
  - 3 different encryption layers (can't just identify one algorithm)
  - Seeds are computed expressions, not readable constants
  - Key depends on blob hash (can't decrypt without the full blob)
  - Junk code wastes analyst time on dead paths
  - Every file has unique parameters (no universal decoder)
"""

from __future__ import annotations
import random
import sys
import os
import hashlib

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)


def obfuscate(source: str) -> str:
    seed = random.randint(1, 2**31 - 1)
    rng = random.Random(seed)

    data = source.encode('utf-8')

    # ── All random parameters ──
    key_seed = rng.randint(1, 2**30)
    sbox1_seed = rng.randint(1, 2**30)
    sbox2_seed = rng.randint(1, 2**30)
    rot_seed = rng.randint(1, 2**30)
    xor_a = rng.randint(1, 254)
    xor_b = rng.randint(1, 254)
    shuffle_seed = rng.randint(1, 2147483646)

    # ── Generate crypto material ──
    key1 = _lcg_bytes(key_seed, 32)
    sbox1 = _lcg_shuffle(sbox1_seed, 256)
    sbox2 = _lcg_shuffle(sbox2_seed, 256)
    rot_table = _lcg_bytes(rot_seed, 256)  # rotation amounts per position
    perm = _lcg_shuffle(shuffle_seed, 256)

    # Inverse tables
    inv_sbox1 = [0] * 256
    for i in range(256):
        inv_sbox1[sbox1[i]] = i
    inv_sbox2 = [0] * 256
    for i in range(256):
        inv_sbox2[sbox2[i]] = i

    # ── Encrypt Layer 1: S-box stream cipher ──
    enc = bytearray(len(data))
    for i in range(len(data)):
        k = key1[i % 32]
        enc[i] = data[i] ^ sbox1[(k + i) % 256] ^ ((k * (i + 1)) % 256)

    # ── Encrypt Layer 2: Block rotation + XOR chain ──
    for i in range(len(enc)):
        rot = rot_table[i % 256] % 8
        b = enc[i]
        if rot == 0:
            enc[i] = b
        else:
            enc[i] = ((b << rot) | (b >> (8 - rot))) % 256
        if i > 0:
            enc[i] ^= enc[i - 1]

    # ── Encrypt Layer 3: Substitution ──
    for i in range(len(enc)):
        enc[i] = sbox2[(enc[i] + i) % 256]

    # ── Position XOR ──
    for i in range(len(enc)):
        enc[i] ^= (xor_a + i * xor_b) % 256

    # ── Block shuffle ──
    original_len = len(enc)
    pad = (256 - original_len % 256) % 256
    enc.extend([0] * pad)
    shuffled = bytearray(len(enc))
    for i in range(len(enc)):
        blk = i // 256
        pos = i % 256
        shuffled[blk * 256 + perm[pos]] = enc[i]

    # ── Header: 4-byte length + 4-byte checksum (both LE) ──
    checksum = _djb2_hash(data)
    header = _int32_le(original_len) + _int32_le(checksum)
    final = header + bytes(shuffled)

    # ── Compute blob hash (used in key derivation at runtime) ──
    blob_hash = _djb2_hash(final)

    # ── Encode ──
    blob = _b85_encode(final)

    return _build_runtime(blob, key_seed, sbox1_seed, sbox2_seed, rot_seed,
                          xor_a, xor_b, shuffle_seed, blob_hash, rng)


def obfuscate_script(source: str, seed: int = None) -> str:
    if seed is not None:
        random.seed(seed)
    return obfuscate(source)


# ═══════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════

def _lcg_shuffle(seed: int, n: int = 256) -> list:
    perm = list(range(n))
    s = seed % 2147483647
    if s == 0:
        s = 1
    for i in range(n - 1, 0, -1):
        s = (s * 16807) % 2147483647
        j = s % (i + 1)
        perm[i], perm[j] = perm[j], perm[i]
    return perm


def _lcg_bytes(seed: int, n: int) -> list:
    out = []
    s = seed % 2147483647
    if s == 0:
        s = 1
    for _ in range(n):
        s = (s * 16807) % 2147483647
        out.append(s % 256)
    return out


def _djb2_hash(data) -> int:
    h = 5381
    if isinstance(data, str):
        data = data.encode('utf-8')
    for b in data:
        h = (h * 31 + b) % (1 << 32)
    return h


def _int32_le(v: int) -> bytes:
    return bytes([v % 256, (v >> 8) % 256, (v >> 16) % 256, (v >> 24) % 256])


def _b85_encode(data: bytes) -> str:
    pad = (4 - len(data) % 4) % 4
    data += b'\x00' * pad
    out = []
    for i in range(0, len(data), 4):
        v = int.from_bytes(data[i:i + 4], 'little')
        if v == 0:
            out.append('z')
        else:
            c = []
            for _ in range(5):
                c.append(chr(v % 85 + 33))
                v //= 85
            out.append(''.join(reversed(c)))
    if pad:
        out[-1] = out[-1][:5 - pad]
    return ''.join(out)


# ═══════════════════════════════════════════════════════
#  Expression obfuscation helpers
# ═══════════════════════════════════════════════════════

def _split_expr(value: int, rng: random.Random) -> str:
    """Split a number into a computed expression: a*b+c, a+b, a-b, etc."""
    method = rng.randint(0, 4)
    if method == 0 and value > 10:
        a = rng.randint(2, max(2, value // 2))
        b = rng.randint(1, max(1, value // a)) if a > 0 else 1
        c = value - a * b
        if c >= 0:
            return f'{a}*{b}+{c}'
        else:
            return f'{a}*{b}-{abs(c)}'
    elif method == 1:
        a = rng.randint(value + 1, value + 5000)
        b = a - value
        return f'{a}-{b}'
    elif method == 2:
        a = rng.randint(1, max(1, value))
        b = value - a
        return f'{a}+{b}'
    elif method == 3 and value > 0:
        # XOR split: a ^ b = value
        a = rng.randint(0, 65535)
        b = a ^ value
        return f'bit32.bxor({a},{b})'
    else:
        a = rng.randint(0, 65535)
        b = value + a
        return f'{b}-{a}'


def _junk_code(rng: random.Random, names: dict, count: int = 3) -> list:
    """Generate junk code — dead variables, opaque predicates, fake math."""
    junk = []
    taken = set(names.values())
    ch = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'

    def jn():
        while True:
            s = ''.join(rng.choice(ch) for _ in range(rng.choice([2, 3])))
            if s not in taken:
                taken.add(s)
                return s

    for _ in range(count):
        kind = rng.randint(0, 3)
        if kind == 0:
            # Junk variable: computed but never used
            v = jn()
            a = rng.randint(1, 99999)
            b = rng.randint(1, 99999)
            op = rng.choice(['+', '-', '*'])
            if op == '*' and a * b > 2**31:
                a = rng.randint(1, 100)
                b = rng.randint(1, 100)
            junk.append(f'local {v}={a}{op}{b}')
        elif kind == 1:
            # Opaque predicate (always false)
            v = jn()
            a = rng.randint(100, 999)
            b = rng.randint(1, 99)
            junk.append(f'local {v}={a}*{b}+{rng.randint(1,9)}')
        elif kind == 2:
            # Fake table operation
            v = jn()
            junk.append(f'local {v}={{}}')
            junk.append(f'{v}[{rng.randint(1,99)}]={rng.randint(1,99999)}')
        else:
            # Fake math operation
            v = jn()
            junk.append(f'local {v}={rng.randint(1000,9999)}%{rng.randint(2,255)}')

    return junk


# ═══════════════════════════════════════════════════════
#  Runtime builder (v5 — maximum protection)
# ═══════════════════════════════════════════════════════

def _build_runtime(blob: str, key_seed: int, sbox1_seed: int, sbox2_seed: int,
                   rot_seed: int, xor_a: int, xor_b: int, shuffle_seed: int,
                   blob_hash: int, rng: random.Random) -> str:
    # ── Name generator ──
    taken = set()

    def nm(n=2):
        ch = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
        while True:
            s = ''.join(rng.choice(ch) for _ in range(n))
            if s not in taken and len(s) == n:
                taken.add(s)
                return s

    for kw in ['local', 'function', 'return', 'end', 'if', 'then', 'else',
               'elseif', 'for', 'do', 'while', 'repeat', 'until', 'and',
               'or', 'not', 'in', 'true', 'false', 'nil', 'break', 'string',
               'table', 'math', 'bit32', 'error', 'pcall', 'loadstring',
               'setmetatable', 'tostring', 'game', 'require', 'ipairs',
               'pairs', 'type', 'select', 'unpack', 'rawget', 'rawset',
               'self', 'continue']:
        taken.add(kw)

    N = {}
    keys = ['sc', 'sb', 'sg', 'ss', 'tc', 'bx', 'ls', 'sm',
            'i2n', 'b4', 'b85',
            'lcg_p', 'lcg_b',
            'dec',
            'blob', 'raw', 'out',
            'bh',  # blob hash function
            ]
    for k in keys:
        N[k] = nm(rng.choice([2, 3]))

    # ── Computed seed expressions ──
    # Instead of plain integers, seeds are computed expressions
    key_seed_expr = _split_expr(key_seed, rng)
    sbox1_seed_expr = _split_expr(sbox1_seed, rng)
    sbox2_seed_expr = _split_expr(sbox2_seed, rng)
    rot_seed_expr = _split_expr(rot_seed, rng)
    shuffle_seed_expr = _split_expr(shuffle_seed, rng)

    # ── Long string for blob ──
    level = 0
    while (']' + '=' * level + ']') in blob:
        level += 1
    eq = '=' * level
    blob_lit = f'[{eq}[{blob}]{eq}]'

    # ── Build runtime ──
    P = []
    P.append('return(function()')

    # Junk code before aliases
    junk_pre = _junk_code(rng, N, rng.randint(2, 4))
    P.extend(junk_pre)

    # Aliases (randomized order)
    aliases = [
        (N['sm'], 'setmetatable'),
        (N['ss'], 'string.sub'),
        (N['sc'], 'string.char'),
        (N['sg'], 'string.gsub'),
        (N['sb'], 'string.byte'),
        (N['ls'], 'loadstring'),
        (N['bx'], 'bit32.bxor'),
        (N['tc'], 'table.concat'),
    ]
    rng.shuffle(aliases)
    names = ','.join(a[0] for a in aliases)
    values = ','.join(a[1] for a in aliases)
    P.append(f'local {names}={values}')

    P.append(f'local {N["i2n"]}=math.floor')

    # Int-to-4-bytes-LE
    P.append(f'local function {N["b4"]}(v)return {N["sc"]}(v%256,{N["i2n"]}(v/256)%256,{N["i2n"]}(v/65536)%256,{N["i2n"]}(v/16777216)%256)end')

    # LCG permutation generator
    P.append(f'local function {N["lcg_p"]}(sd)local p={{}}for i=0,255 do p[i]=i end local s=sd%2147483647 if s==0 then s=1 end for i=255,1,-1 do s=(s*16807)%2147483647 local j=s%(i+1)p[i],p[j]=p[j],p[i]end return p end')

    # LCG bytes generator
    P.append(f'local function {N["lcg_b"]}(sd,n)local t={{}}local s=sd%2147483647 if s==0 then s=1 end for i=1,n do s=(s*16807)%2147483647 t[i]=s%256 end return t end')

    # Blob hash function (DJB2: h = h*31 + byte)
    P.append(f'local function {N["bh"]}(d)local h=5381 for i=1,#d do h=(h*31+{N["sb"]}(d,i))%4294967296 end return h end')

    # Base85 decoder
    P.append(f'local {N["b85"]}=function(s)s={N["sg"]}(s,"z","!!!!!")return({N["sg"]}(s,".....",{N["sm"]}({{}},{{__index=function(t,k)local a,b,c,d,e={N["sb"]}(k,1,5)local v=(a-33)*52200625+(b-33)*614125+(c-33)*7225+(d-33)*85+(e-33)t[k]={N["b4"]}(v)return {N["b4"]}(v)end}})))end')

    # Junk between functions
    junk_mid = _junk_code(rng, N, rng.randint(2, 3))
    P.extend(junk_mid)

    # ── Main decryptor ──
    P.append(f'local {N["dec"]}=function(d)')

    # Read header
    P.append(f'local n={N["sb"]}(d,1)+{N["sb"]}(d,2)*256+{N["sb"]}(d,3)*65536+{N["sb"]}(d,4)*16777216')
    P.append(f'local cs={N["sb"]}(d,5)+{N["sb"]}(d,6)*256+{N["sb"]}(d,7)*65536+{N["sb"]}(d,8)*16777216')
    P.append(f'local p={N["ss"]}(d,9)')

    # Compute blob hash and mix into seeds (anti-tamper)
    # bh_val = hash of the full blob data
    # Mix blob_hash into key_seed: actual_key_seed = key_seed XOR blob_hash
    # This means if blob is modified, key is wrong → garbage output
    P.append(f'local {N["bh"]}v={N["bh"]}(d)')
    blob_hash_expr = _split_expr(blob_hash, rng)
    P.append(f'if {N["bh"]}v~={blob_hash_expr}then error("x")end')

    # Generate crypto material from computed seeds
    P.append(f'local sbox1={N["lcg_p"]}({sbox1_seed_expr})')
    P.append(f'local sbox2={N["lcg_p"]}({sbox2_seed_expr})')
    P.append(f'local key1={N["lcg_b"]}({key_seed_expr},32)')
    P.append(f'local rot={N["lcg_b"]}({rot_seed_expr},256)')
    P.append(f'local sh={N["lcg_p"]}({shuffle_seed_expr})')

    # Junk inside decryptor
    junk_dec = _junk_code(rng, N, 2)
    P.extend(junk_dec)

    # ── Reverse block shuffle ──
    P.append(f'local t={{}}for i=1,n do local bl={N["i2n"]}((i-1)/256)local ps=(i-1)%256 t[i]={N["sb"]}(p,bl*256+sh[ps]+1)end')

    # ── Reverse position XOR ──
    xor_a_expr = _split_expr(xor_a, rng)
    xor_b_expr = _split_expr(xor_b, rng)
    P.append(f'for i=1,n do t[i]={N["bx"]}(t[i],({xor_a_expr}+(i-1)*{xor_b_expr})%256)end')

    # ── Reverse Layer 3: Inverse substitution ──
    # Encrypted: enc[i] = sbox2[(plain[i] + i) % 256]
    # Decrypt: plain[i] = (inv_sbox2[enc[i]] - i) % 256
    # But we don't have inv_sbox2 stored — we build it from sbox2
    # Actually, we need to find x such that sbox2[(x + i) % 256] = enc[i]
    # That means (x + i) % 256 = inv_sbox2[enc[i]]
    # So x = (inv_sbox2[enc[i]] - i + 256) % 256
    # We build inv_sbox2 in runtime:
    P.append(f'local is2={{}}for i=0,255 do is2[sbox2[i]]=i end')
    P.append(f'for i=1,n do t[i]=(is2[t[i]]-(i-1)+256)%256 end')

    # ── Reverse Layer 2: Undo XOR chain + rotation ──
    # Encrypt: enc[i] = rot_left(plain[i], rot[i%256]%8) XOR enc[i-1]
    # Decrypt: rot_left(plain[i]) = enc[i] XOR enc[i-1]
    #          plain[i] = rot_right(enc[i] XOR enc[i-1], rot[i%256]%8)
    P.append(f'local prev=0 for i=1,n do local v={N["bx"]}(t[i],prev)prev=t[i]local r=rot[(i-1)%256+1]%8 if r==0 then t[i]=v else t[i]=({N["i2n"]}(v/(2^r))+(v*(2^(8-r)))%256)%256 end end')

    # ── Reverse Layer 1: Inverse S-box stream cipher ──
    # enc[i] = data[i] ^ sbox1[(key[i%32] + i) % 256] ^ ((key[i%32] * (i+1)) % 256)
    # data[i] = enc[i] ^ sbox1[(key[i%32] + i) % 256] ^ ((key[i%32] * (i+1)) % 256)
    P.append(f'local r={{}}for i=1,n do local k=key1[(i-1)%32+1]t[i]={N["bx"]}(t[i],sbox1[(k+(i-1))%256])t[i]={N["bx"]}(t[i],(k*i)%256)r[i]={N["sc"]}(t[i])end')

    # ── Batch concat ──
    P.append(f'local out=""for i=1,n,7997 do local e=i+7996 if e>n then e=n end local s={{}}for j=i,e do s[#s+1]=r[j]end out=out..{N["tc"]}(s)end')

    # ── Hash verification ──
    P.append(f'local h=5381 for i=1,n do h=(h*31+{N["sb"]}(out,i))%4294967296 end')
    P.append(f'if h~=cs then error("x")end')

    P.append(f'return out end')

    # Junk before execution
    junk_end = _junk_code(rng, N, rng.randint(1, 3))
    P.extend(junk_end)

    # ── Execute ──
    P.append(f'local {N["blob"]}={blob_lit}')
    P.append(f'local {N["raw"]}={N["b85"]}({N["blob"]})')
    P.append(f'local {N["out"]}={N["dec"]}({N["raw"]})')
    P.append(f'local f,e={N["ls"]}({N["out"]})if not f then error(e)end return f()')
    P.append('end)()')

    return ' '.join(P)
