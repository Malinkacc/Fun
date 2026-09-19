"""
NZL Studio Obfuscator v8 — Luraph-style table-based runtime

Structure (inspired by Luraph v15):
  return setmetatable({
    q="Error msg",
    [1]=string.byte, [2]=string.char, ...,
    j=[=[...base85 blob...]=],
    [50]=seed1, [51]=seed2, ...
  }, {__index=dispatcher}):O()(...)

The __index function contains ALL decryption logic.
When :O() is called, __index returns the decrypt+execute function.
Analyst sees: table + metatable + one function call.
Everything else is hidden inside __index.

5 ENCRYPTION LAYERS + computed seeds + anti-tamper + integrity check
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

    # ── Parameters ──
    P = {
        'key1': rng.randint(1, 2**30),
        'key2': rng.randint(1, 2**30),
        'sbox1': rng.randint(1, 2**30),
        'sbox2': rng.randint(1, 2**30),
        'sbox3': rng.randint(1, 2**30),
        'rot': rng.randint(1, 2**30),
        'xor_a': rng.randint(1, 254),
        'xor_b': rng.randint(1, 254),
        'xor_c': rng.randint(1, 254),
        'shuffle': rng.randint(1, 2147483646),
    }

    key1 = _lcg_bytes(P['key1'], 32)
    key2 = _lcg_bytes(P['key2'], 64)
    sbox1 = _lcg_shuffle(P['sbox1'], 256)
    sbox2 = _lcg_shuffle(P['sbox2'], 256)
    sbox3 = _lcg_shuffle(P['sbox3'], 256)
    rot_table = _lcg_bytes(P['rot'], 256)
    perm = _lcg_shuffle(P['shuffle'], 256)

    # ── 5-layer encryption ──
    enc = bytearray(len(data))
    for i in range(len(data)):
        k = key1[i % 32]
        enc[i] = data[i] ^ sbox1[(k + i) % 256] ^ ((k * (i + 1)) % 256)

    for i in range(len(enc)):
        rot = rot_table[i % 256] % 8
        b = enc[i]
        if rot == 0:
            enc[i] = b
        else:
            enc[i] = ((b << rot) | (b >> (8 - rot))) % 256
        if i > 0:
            enc[i] ^= enc[i - 1]

    for i in range(len(enc)):
        enc[i] = sbox2[(enc[i] + i) % 256]

    rolling = 0
    for i in range(len(enc)):
        k = key2[i % 64]
        enc[i] ^= (k + rolling) % 256
        rolling = (rolling + enc[i]) % 256

    for i in range(len(enc)):
        enc[i] = sbox3[(enc[i] + i * 3) % 256]

    for i in range(len(enc)):
        enc[i] ^= (P['xor_a'] + i * P['xor_b'] + (i * i) % 256 * P['xor_c']) % 256

    original_len = len(enc)
    pad = (256 - original_len % 256) % 256
    enc.extend([0] * pad)
    shuffled = bytearray(len(enc))
    for i in range(len(enc)):
        blk = i // 256
        pos = i % 256
        shuffled[blk * 256 + perm[pos]] = enc[i]

    checksum = _djb2_hash(data)
    header = _int32_le(original_len) + _int32_le(checksum)
    final = header + bytes(shuffled)
    blob_hash = _djb2_hash(final)
    blob = _b85_encode(final)

    return _build_runtime_table(blob, P, blob_hash, checksum, rng)


def obfuscate_script(source: str, seed: int = None) -> str:
    if seed is not None:
        random.seed(seed)
    return obfuscate(source)


# ═══════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════

def _lcg_shuffle(seed, n=256):
    perm = list(range(n))
    s = seed % 2147483647
    if s == 0: s = 1
    for i in range(n - 1, 0, -1):
        s = (s * 16807) % 2147483647
        j = s % (i + 1)
        perm[i], perm[j] = perm[j], perm[i]
    return perm

def _lcg_bytes(seed, n):
    out = []
    s = seed % 2147483647
    if s == 0: s = 1
    for _ in range(n):
        s = (s * 16807) % 2147483647
        out.append(s % 256)
    return out

def _djb2_hash(data):
    h = 5381
    if isinstance(data, str): data = data.encode('utf-8')
    for b in data:
        h = (h * 31 + b) % (1 << 32)
    return h

def _int32_le(v):
    return bytes([v % 256, (v >> 8) % 256, (v >> 16) % 256, (v >> 24) % 256])

def _b85_encode(data):
    pad = (4 - len(data) % 4) % 4
    data += b'\x00' * pad
    out = []
    for i in range(0, len(data), 4):
        v = int.from_bytes(data[i:i+4], 'little')
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

def _split(value, rng, depth=0):
    if depth > 1 or value < 10:
        return str(value)
    m = rng.randint(0, 3)
    if m == 0 and value > 100:
        a = rng.randint(10, max(10, value // 2))
        b = max(1, value // a)
        c = value - a * b
        return f'{a}*{b}+{c}' if c >= 0 else f'{a}*{b}-{abs(c)}'
    elif m == 1:
        a = rng.randint(value + 1, value + 9999)
        return f'{a}-{a - value}'
    elif m == 2:
        a = rng.randint(0, 65535)
        return f'bit32.bxor({a},{a ^ value})'
    else:
        a = rng.randint(1, max(1, value // 2))
        return f'{a}+{value - a}'


# ═══════════════════════════════════════════════════════
#  Table-based runtime (Luraph style)
# ═══════════════════════════════════════════════════════

def _build_runtime_table(blob, P, blob_hash, checksum, rng):
    # ── Long string level ──
    level = 1
    while (']' + '=' * level + ']') in blob:
        level += 1
    eq = '=' * level
    blob_lit = f'[{eq}[{blob}]{eq}]'

    # ── Table key assignments ──
    # Numeric keys for functions and seeds
    # Randomize which number maps to what
    keys = list(range(1, 60))
    rng.shuffle(keys)

    K = {}
    names = ['sb', 'sc', 'sg', 'ss', 'tc', 'bx', 'ls', 'sm',
             'i2n', 'type_f', 'pcall_f',
             'key1_s', 'key2_s', 'sbox1_s', 'sbox2_s', 'sbox3_s',
             'rot_s', 'shuffle_s',
             'xor_a', 'xor_b', 'xor_c',
             'blob_hash', 'checksum']
    for i, name in enumerate(names):
        K[name] = keys[i]

    # ── Build table entries ──
    entries = []
    entries.append(f'q="Decompression Error"')
    entries.append(f'j={blob_lit}')

    # Functions
    func_map = {
        'sb': 'string.byte', 'sc': 'string.char', 'sg': 'string.gsub',
        'ss': 'string.sub', 'tc': 'table.concat', 'bx': 'bit32.bxor',
        'ls': 'loadstring', 'sm': 'setmetatable', 'i2n': 'math.floor',
        'type_f': 'type', 'pcall_f': 'pcall',
    }
    for name, func in func_map.items():
        entries.append(f'[{K[name]}]={func}')

    # Seeds (as computed expressions)
    seed_map = {
        'key1_s': P['key1'], 'key2_s': P['key2'],
        'sbox1_s': P['sbox1'], 'sbox2_s': P['sbox2'], 'sbox3_s': P['sbox3'],
        'rot_s': P['rot'], 'shuffle_s': P['shuffle'],
    }
    for name, val in seed_map.items():
        entries.append(f'[{K[name]}]={_split(val, rng)}')

    # Constants
    entries.append(f'[{K["xor_a"]}]= {_split(P["xor_a"], rng)}')
    entries.append(f'[{K["xor_b"]}]= {_split(P["xor_b"], rng)}')
    entries.append(f'[{K["xor_c"]}]= {_split(P["xor_c"], rng)}')
    entries.append(f'[{K["blob_hash"]}]= {_split(blob_hash, rng)}')
    entries.append(f'[{K["checksum"]}]= {_split(checksum, rng)}')

    # Shuffle entries for more confusion
    rng.shuffle(entries)

    table_str = '{' + ','.join(entries) + '}'

    # ── Build __index function ──
    # This is the CORE — contains all decryption logic
    # Access table entries via t[key]
    sb = f't[{K["sb"]}]'
    sc = f't[{K["sc"]}]'
    sg = f't[{K["sg"]}]'
    ss = f't[{K["ss"]}]'
    tc = f't[{K["tc"]}]'
    bx = f't[{K["bx"]}]'
    ls = f't[{K["ls"]}]'
    sm = f't[{K["sm"]}]'
    i2n = f't[{K["i2n"]}]'

    s_key1 = f't[{K["key1_s"]}]'
    s_key2 = f't[{K["key2_s"]}]'
    s_sbox1 = f't[{K["sbox1_s"]}]'
    s_sbox2 = f't[{K["sbox2_s"]}]'
    s_sbox3 = f't[{K["sbox3_s"]}]'
    s_rot = f't[{K["rot_s"]}]'
    s_shuffle = f't[{K["shuffle_s"]}]'
    v_xor_a = f't[{K["xor_a"]}]'
    v_xor_b = f't[{K["xor_b"]}]'
    v_xor_c = f't[{K["xor_c"]}]'
    v_blob_hash = f't[{K["blob_hash"]}]'
    v_checksum = f't[{K["checksum"]}]'

    # Build the __index function
    # When k=="O", return the decryptor function
    idx_fn = (
        f'function(t,k)'
        f'if k=="O" then return function()'
        # b4 helper
        f'local function b4(v)return {sc}(v%256,{i2n}(v/256)%256,{i2n}(v/65536)%256,{i2n}(v/16777216)%256)end'
        # LCG permutation
        f'local function lcg_p(sd)local p={{}}for i=0,255 do p[i]=i end local s=sd%2147483647 if s==0 then s=1 end for i=255,1,-1 do s=(s*16807)%2147483647 local j=s%(i+1)p[i],p[j]=p[j],p[i]end return p end'
        # LCG bytes
        f'local function lcg_b(sd,n)local o={{}}local s=sd%2147483647 if s==0 then s=1 end for i=1,n do s=(s*16807)%2147483647 o[i]=s%256 end return o end'
        # Hash
        f'local function bh(d)local h=5381 for i=1,#d do h=(h*31+{sb}(d,i))%4294967296 end return h end'
        # Base85 decoder
        f'local function b85(s)s={sg}(s,"z","!!!!!")return({sg}(s,".....",{sm}({{}},{{__index=function(c,k)local a,b,d,e,f={sb}(k,1,5)local v=(a-33)*52200625+(b-33)*614125+(d-33)*7225+(e-33)*85+(f-33)c[k]=b4(v)return b4(v)end}})))end'
        # Decode blob
        f'local raw=b85(t.j)'
        # Anti-tamper
        f'if bh(raw)~={v_blob_hash}then error("x")end'
        # Read header
        f'local n={sb}(raw,1)+{sb}(raw,2)*256+{sb}(raw,3)*65536+{sb}(raw,4)*16777216'
        f'local cs={sb}(raw,5)+{sb}(raw,6)*256+{sb}(raw,7)*65536+{sb}(raw,8)*16777216'
        f'local p={ss}(raw,9)'
        # Generate crypto
        f'local sbox1=lcg_p({s_sbox1})'
        f'local sbox2=lcg_p({s_sbox2})'
        f'local sbox3=lcg_p({s_sbox3})'
        f'local key1=lcg_b({s_key1},32)'
        f'local key2=lcg_b({s_key2},64)'
        f'local rot=lcg_b({s_rot},256)'
        f'local sh=lcg_p({s_shuffle})'
        # Reverse shuffle
        f'local tt={{}}for i=1,n do local bl={i2n}((i-1)/256)local ps=(i-1)%256 tt[i]={sb}(p,bl*256+sh[ps]+1)end'
        # Reverse position XOR
        f'for i=1,n do tt[i]={bx}(tt[i],({v_xor_a}+(i-1)*{v_xor_b}+((i-1)*(i-1))%256*{v_xor_c})%256)end'
        # Reverse Layer 5
        f'local is3={{}}for i=0,255 do is3[sbox3[i]]=i end'
        f'for i=1,n do tt[i]=(is3[tt[i]]-(i-1)*3+512)%256 end'
        # Reverse Layer 4
        f'local rolling=0 for i=1,n do local k=key2[(i-1)%64+1]local ev=tt[i]tt[i]={bx}(tt[i],(k+rolling)%256)rolling=(rolling+ev)%256 end'
        # Reverse Layer 3
        f'local is2={{}}for i=0,255 do is2[sbox2[i]]=i end'
        f'for i=1,n do tt[i]=(is2[tt[i]]-(i-1)+256)%256 end'
        # Reverse Layer 2
        f'local prev=0 for i=1,n do local v={bx}(tt[i],prev)prev=tt[i]local r=rot[(i-1)%256+1]%8 if r==0 then tt[i]=v else tt[i]=({i2n}(v/(2^r))+(v*(2^(8-r)))%256)%256 end end'
        # Reverse Layer 1
        f'local rr={{}}for i=1,n do local k=key1[(i-1)%32+1]tt[i]={bx}(tt[i],sbox1[(k+(i-1))%256])tt[i]={bx}(tt[i],(k*i)%256)rr[i]={sc}(tt[i])end'
        # Concat
        f'local out=""for i=1,n,7997 do local e=i+7996 if e>n then e=n end local s={{}}for j=i,e do s[#s+1]=rr[j]end out=out..{tc}(s)end'
        # Verify
        f'local h=5381 for i=1,n do h=(h*31+{sb}(out,i))%4294967296 end'
        f'if h~=cs then error("x")end'
        # Execute
        f'return {ls}(out)end'
        f'end end'
    )

    # ── Final output ──
    return f'return {sm}({table_str},{{__index={idx_fn}}}):O()(...);'
