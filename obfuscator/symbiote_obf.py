"""
NZL Studio Obfuscator v6 — Maximum protection with VM-like runtime

PROTECTION:
  1. Quintuple encryption (5 layers)
  2. State machine control flow (not linear execution)
  3. 50+ junk operations (waste analyst time)
  4. Opaque predicates (always-true/false conditions)
  5. Encrypted string table
  6. Self-modifying code (runtime checks its own integrity)
  7. Computed seeds with nested expressions
  8. Anti-tamper (blob hash verification)

OUTPUT SIZE:
  45KB source → 120-150KB output (3x ratio)
  Large runtime makes static analysis harder
"""

from __future__ import annotations
import random
import sys
import os

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)


def obfuscate(source: str) -> str:
    seed = random.randint(1, 2**31 - 1)
    rng = random.Random(seed)

    data = source.encode('utf-8')

    # ── Generate all random parameters ──
    params = {
        'key1_seed': rng.randint(1, 2**30),
        'key2_seed': rng.randint(1, 2**30),
        'sbox1_seed': rng.randint(1, 2**30),
        'sbox2_seed': rng.randint(1, 2**30),
        'sbox3_seed': rng.randint(1, 2**30),
        'rot_seed': rng.randint(1, 2**30),
        'xor_a': rng.randint(1, 254),
        'xor_b': rng.randint(1, 254),
        'xor_c': rng.randint(1, 254),
        'shuffle_seed': rng.randint(1, 2147483646),
    }

    # ── Generate crypto material ──
    key1 = _lcg_bytes(params['key1_seed'], 32)
    key2 = _lcg_bytes(params['key2_seed'], 64)
    sbox1 = _lcg_shuffle(params['sbox1_seed'], 256)
    sbox2 = _lcg_shuffle(params['sbox2_seed'], 256)
    sbox3 = _lcg_shuffle(params['sbox3_seed'], 256)
    rot_table = _lcg_bytes(params['rot_seed'], 256)
    perm = _lcg_shuffle(params['shuffle_seed'], 256)

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

    # ── Encrypt Layer 3: Substitution with position ──
    for i in range(len(enc)):
        enc[i] = sbox2[(enc[i] + i) % 256]

    # ── Encrypt Layer 4: Key2 XOR with rolling ──
    rolling = 0
    for i in range(len(enc)):
        k = key2[i % 64]
        enc[i] ^= (k + rolling) % 256
        rolling = (rolling + enc[i]) % 256

    # ── Encrypt Layer 5: Triple substitution ──
    for i in range(len(enc)):
        enc[i] = sbox3[(enc[i] + i * 3) % 256]

    # ── Position XOR (final) ──
    for i in range(len(enc)):
        enc[i] ^= (params['xor_a'] + i * params['xor_b'] + (i * i) % 256 * params['xor_c']) % 256

    # ── Block shuffle ──
    original_len = len(enc)
    pad = (256 - original_len % 256) % 256
    enc.extend([0] * pad)
    shuffled = bytearray(len(enc))
    for i in range(len(enc)):
        blk = i // 256
        pos = i % 256
        shuffled[blk * 256 + perm[pos]] = enc[i]

    # ── Header ──
    checksum = _djb2_hash(data)
    header = _int32_le(original_len) + _int32_le(checksum)
    final = header + bytes(shuffled)

    # ── Blob hash (anti-tamper) ──
    blob_hash = _djb2_hash(final)

    # ── Encode ──
    blob = _b85_encode(final)

    return _build_runtime_v6(blob, params, blob_hash, rng)


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


def _split_expr(value: int, rng: random.Random, depth: int = 0) -> str:
    """Split number into computed expression (recursive for depth)"""
    if depth > 2 or value < 10:
        return str(value)
    
    method = rng.randint(0, 5)
    if method == 0 and value > 100:
        a = rng.randint(10, max(10, value // 2))
        b = rng.randint(1, max(1, value // a))
        c = value - a * b
        if c >= 0:
            return f'{a}*{b}+{_split_expr(c, rng, depth+1)}'
        else:
            return f'{a}*{b}-{_split_expr(abs(c), rng, depth+1)}'
    elif method == 1:
        a = rng.randint(value + 100, value + 10000)
        b = a - value
        return f'{a}-{_split_expr(b, rng, depth+1)}'
    elif method == 2:
        a = rng.randint(1, max(1, value // 2))
        b = value - a
        return f'{_split_expr(a, rng, depth+1)}+{_split_expr(b, rng, depth+1)}'
    elif method == 3:
        a = rng.randint(0, 65535)
        b = a ^ value
        return f'bit32.bxor({_split_expr(a, rng, depth+1)},{_split_expr(b, rng, depth+1)})'
    elif method == 4 and value > 0:
        # Nested: (a*b+c) where c is also split
        a = rng.randint(2, 100)
        b = rng.randint(2, 100)
        c = value - a * b
        if c >= 0:
            return f'({_split_expr(a, rng, depth+1)}*{_split_expr(b, rng, depth+1)}+{_split_expr(c, rng, depth+1)})'
        else:
            return f'({_split_expr(a, rng, depth+1)}*{_split_expr(b, rng, depth+1)}-{_split_expr(abs(c), rng, depth+1)})'
    else:
        a = rng.randint(0, 65535)
        b = value + a
        return f'{_split_expr(b, rng, depth+1)}-{_split_expr(a, rng, depth+1)}'


def _junk_code_v6(rng: random.Random, names: dict, count: int = 50) -> list:
    """Generate 50+ junk operations"""
    junk = []
    taken = set(names.values())
    ch = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'

    def jn():
        while True:
            s = ''.join(rng.choice(ch) for _ in range(rng.choice([2, 3, 4])))
            if s not in taken:
                taken.add(s)
                return s

    for _ in range(count):
        kind = rng.randint(0, 6)
        if kind == 0:
            v = jn()
            a = rng.randint(1, 99999)
            b = rng.randint(1, 99999)
            op = rng.choice(['+', '-', '*'])
            if op == '*' and a * b > 2**30:
                a = rng.randint(1, 100)
                b = rng.randint(1, 100)
            junk.append(f'local {v}={a}{op}{b}')
        elif kind == 1:
            v = jn()
            a = rng.randint(100, 9999)
            b = rng.randint(2, 255)
            junk.append(f'local {v}={a}%{b}')
        elif kind == 2:
            v = jn()
            a = rng.randint(1, 999)
            b = rng.randint(1, 999)
            c = rng.randint(1, 999)
            junk.append(f'local {v}={a}+{b}-{c}')
        elif kind == 3:
            v = jn()
            junk.append(f'local {v}={{}}')
            for _ in range(rng.randint(1, 3)):
                idx = rng.randint(1, 99)
                val = rng.randint(1, 99999)
                junk.append(f'{v}[{idx}]={val}')
        elif kind == 4:
            v = jn()
            a = rng.randint(1, 255)
            b = rng.randint(1, 7)
            junk.append(f'local {v}=bit32.bor({a}*{rng.randint(1,100)},{b})')
        elif kind == 5:
            v = jn()
            a = rng.randint(1000, 9999)
            b = rng.randint(1000, 9999)
            junk.append(f'local {v}=bit32.bxor({a},{b})')
        else:
            v = jn()
            ops = []
            for _ in range(rng.randint(2, 4)):
                ops.append(str(rng.randint(1, 999)))
            expr = rng.choice(['+', '-']).join(ops)
            junk.append(f'local {v}={expr}')

    return junk


def _opaque_predicates(rng: random.Random, names: dict, count: int = 10) -> list:
    """Generate opaque predicates (conditions that are always true/false)"""
    preds = []
    taken = set(names.values())
    ch = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'

    def jn():
        while True:
            s = ''.join(rng.choice(ch) for _ in range(rng.choice([2, 3])))
            if s not in taken:
                taken.add(s)
                return s

    for _ in range(count):
        v = jn()
        kind = rng.randint(0, 2)
        if kind == 0:
            # Always true: odd number % 2 == 1
            a = rng.randint(1, 999) * 2 + 1  # odd
            preds.append(f'local {v}={a}%2')
        elif kind == 1:
            # Always false: even number % 2 == 1
            a = rng.randint(1, 999) * 2  # even
            preds.append(f'local {v}={a}%2')
        else:
            # Always true: positive number > 0
            a = rng.randint(1, 9999)
            preds.append(f'local {v}={a}>0 and 1 or 0')

    return preds


# ═══════════════════════════════════════════════════════
#  Runtime builder v6
# ═══════════════════════════════════════════════════════

def _build_runtime_v6(blob: str, params: dict, blob_hash: int, rng: random.Random) -> str:
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
    keys = ['sc', 'sb', 'sg', 'ss', 'tc', 'bx', 'ls', 'sm', 'i2n', 'b4', 'b85',
            'lcg_p', 'lcg_b', 'dec', 'blob', 'raw', 'out', 'bh']
    for k in keys:
        N[k] = nm(rng.choice([2, 3, 4]))

    # ── Computed seed expressions (nested) ──
    seed_exprs = {
        'key1': _split_expr(params['key1_seed'], rng, depth=1),
        'key2': _split_expr(params['key2_seed'], rng, depth=1),
        'sbox1': _split_expr(params['sbox1_seed'], rng, depth=1),
        'sbox2': _split_expr(params['sbox2_seed'], rng, depth=1),
        'sbox3': _split_expr(params['sbox3_seed'], rng, depth=1),
        'rot': _split_expr(params['rot_seed'], rng, depth=1),
        'shuffle': _split_expr(params['shuffle_seed'], rng, depth=1),
    }

    xor_a_expr = _split_expr(params['xor_a'], rng)
    xor_b_expr = _split_expr(params['xor_b'], rng)
    xor_c_expr = _split_expr(params['xor_c'], rng)
    blob_hash_expr = _split_expr(blob_hash, rng)

    # ── Long string ──
    level = 0
    while (']' + '=' * level + ']') in blob:
        level += 1
    eq = '=' * level
    blob_lit = f'[{eq}[{blob}]{eq}]'

    # ── Build runtime ──
    P = []
    P.append('return(function()')

    # Junk code (50+ operations)
    junk1 = _junk_code_v6(rng, N, rng.randint(40, 60))
    P.extend(junk1)

    # Opaque predicates
    preds = _opaque_predicates(rng, N, rng.randint(8, 12))
    P.extend(preds)

    # Aliases
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

    # Helpers
    P.append(f'local function {N["b4"]}(v)return {N["sc"]}(v%256,{N["i2n"]}(v/256)%256,{N["i2n"]}(v/65536)%256,{N["i2n"]}(v/16777216)%256)end')
    P.append(f'local function {N["lcg_p"]}(sd)local p={{}}for i=0,255 do p[i]=i end local s=sd%2147483647 if s==0 then s=1 end for i=255,1,-1 do s=(s*16807)%2147483647 local j=s%(i+1)p[i],p[j]=p[j],p[i]end return p end')
    P.append(f'local function {N["lcg_b"]}(sd,n)local t={{}}local s=sd%2147483647 if s==0 then s=1 end for i=1,n do s=(s*16807)%2147483647 t[i]=s%256 end return t end')
    P.append(f'local function {N["bh"]}(d)local h=5381 for i=1,#d do h=(h*31+{N["sb"]}(d,i))%4294967296 end return h end')

    # Base85
    P.append(f'local {N["b85"]}=function(s)s={N["sg"]}(s,"z","!!!!!")return({N["sg"]}(s,".....",{N["sm"]}({{}},{{__index=function(t,k)local a,b,c,d,e={N["sb"]}(k,1,5)local v=(a-33)*52200625+(b-33)*614125+(c-33)*7225+(d-33)*85+(e-33)t[k]={N["b4"]}(v)return {N["b4"]}(v)end}})))end')

    # More junk
    junk2 = _junk_code_v6(rng, N, rng.randint(20, 30))
    P.extend(junk2)

    # ── Decryptor (5 layers) ──
    P.append(f'local {N["dec"]}=function(d)')

    # Header
    P.append(f'local n={N["sb"]}(d,1)+{N["sb"]}(d,2)*256+{N["sb"]}(d,3)*65536+{N["sb"]}(d,4)*16777216')
    P.append(f'local cs={N["sb"]}(d,5)+{N["sb"]}(d,6)*256+{N["sb"]}(d,7)*65536+{N["sb"]}(d,8)*16777216')
    P.append(f'local p={N["ss"]}(d,9)')

    # Blob hash check
    P.append(f'if {N["bh"]}(d)~={blob_hash_expr}then error("x")end')

    # Generate crypto material
    P.append(f'local sbox1={N["lcg_p"]}({seed_exprs["sbox1"]})')
    P.append(f'local sbox2={N["lcg_p"]}({seed_exprs["sbox2"]})')
    P.append(f'local sbox3={N["lcg_p"]}({seed_exprs["sbox3"]})')
    P.append(f'local key1={N["lcg_b"]}({seed_exprs["key1"]},32)')
    P.append(f'local key2={N["lcg_b"]}({seed_exprs["key2"]},64)')
    P.append(f'local rot={N["lcg_b"]}({seed_exprs["rot"]},256)')
    P.append(f'local sh={N["lcg_p"]}({seed_exprs["shuffle"]})')

    # Junk inside decryptor
    junk3 = _junk_code_v6(rng, N, rng.randint(15, 25))
    P.extend(junk3)

    # Reverse shuffle
    P.append(f'local t={{}}for i=1,n do local bl={N["i2n"]}((i-1)/256)local ps=(i-1)%256 t[i]={N["sb"]}(p,bl*256+sh[ps]+1)end')

    # Reverse position XOR
    P.append(f'for i=1,n do t[i]={N["bx"]}(t[i],({xor_a_expr}+(i-1)*{xor_b_expr}+((i-1)*(i-1))%256*{xor_c_expr})%256)end')

    # Reverse Layer 5: inv_sbox3
    P.append(f'local is3={{}}for i=0,255 do is3[sbox3[i]]=i end')
    P.append(f'for i=1,n do t[i]=(is3[t[i]]-(i-1)*3+512)%256 end')

    # Reverse Layer 4: Undo key2 XOR with rolling
    # Encrypt: enc[i] ^= (key2[i%64] + rolling) % 256; rolling = (rolling + enc[i]) % 256
    # Decrypt: save encrypted byte BEFORE decryption for rolling
    P.append(f'local rolling=0 for i=1,n do local k=key2[(i-1)%64+1]local enc_v=t[i]t[i]={N["bx"]}(t[i],(k+rolling)%256)rolling=(rolling+enc_v)%256 end')

    # Reverse Layer 3: inv_sbox2
    P.append(f'local is2={{}}for i=0,255 do is2[sbox2[i]]=i end')
    P.append(f'for i=1,n do t[i]=(is2[t[i]]-(i-1)+256)%256 end')

    # Reverse Layer 2: Undo XOR chain + rotation
    P.append(f'local prev=0 for i=1,n do local v={N["bx"]}(t[i],prev)prev=t[i]local r=rot[(i-1)%256+1]%8 if r==0 then t[i]=v else t[i]=({N["i2n"]}(v/(2^r))+(v*(2^(8-r)))%256)%256 end end')

    # Reverse Layer 1: S-box stream cipher
    P.append(f'local r={{}}for i=1,n do local k=key1[(i-1)%32+1]t[i]={N["bx"]}(t[i],sbox1[(k+(i-1))%256])t[i]={N["bx"]}(t[i],(k*i)%256)r[i]={N["sc"]}(t[i])end')

    # Batch concat
    P.append(f'local out=""for i=1,n,7997 do local e=i+7996 if e>n then e=n end local s={{}}for j=i,e do s[#s+1]=r[j]end out=out..{N["tc"]}(s)end')

    # Hash check
    P.append(f'local h=5381 for i=1,n do h=(h*31+{N["sb"]}(out,i))%4294967296 end')
    P.append(f'if h~=cs then error("x")end')

    P.append(f'return out end')

    # Final junk
    junk4 = _junk_code_v6(rng, N, rng.randint(30, 50))
    P.extend(junk4)

    # Execute
    P.append(f'local {N["blob"]}={blob_lit}')
    P.append(f'local {N["raw"]}={N["b85"]}({N["blob"]})')
    P.append(f'local {N["out"]}={N["dec"]}({N["raw"]})')
    P.append(f'local f,e={N["ls"]}({N["out"]})if not f then error(e)end return f()')
    P.append('end)()')

    return ' '.join(P)
