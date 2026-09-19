"""
NZL Studio Obfuscator v9 — Self-decrypting runtime (Luraph-style)

ARCHITECTURE:
  return setmetatable({
    j=[=[encrypted payload blob]=],     -- Layer 2 data
    c=[=[encrypted runtime code]=],     -- Layer 1 code (encrypted!)
    [1]=string.byte, [2]=string.char, [3]=setmetatable, ...
    [10]=seed1, [11]=seed2, ...
  }, {__index=bootstrap}):O()(...)

TWO-STAGE EXECUTION:
  Stage 1 (bootstrap in __index):
    1. Simple XOR decrypt of t.c → runtime Lua code
    2. loadstring(runtime_code) → compiled function
    3. Call it with table t

  Stage 2 (decrypted runtime):
    1. Base85 decode t.j → encrypted bytes
    2. Anti-tamper check (blob hash)
    3. Generate crypto material from seeds
    4. 5-layer decryption
    5. Integrity check (DJB2 hash)
    6. loadstring(payload) → execute

ANALYST MUST:
  1. Understand bootstrap (simple, but seeds are computed)
  2. Decrypt runtime code (XOR with key from seeds)
  3. Understand runtime (5 layers + state machine logic)
  4. Decrypt payload blob
  5. Get source code

This is essentially what Luraph does — code inside data inside code.
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

    # ── Payload encryption params ──
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

    # ── Runtime encryption params ──
    rt_key_seed = rng.randint(1, 2**30)
    rt_key = _lcg_bytes(rt_key_seed, 32)

    # ── Encrypt payload (5 layers) ──
    key1 = _lcg_bytes(P['key1'], 32)
    key2 = _lcg_bytes(P['key2'], 64)
    sbox1 = _lcg_shuffle(P['sbox1'], 256)
    sbox2 = _lcg_shuffle(P['sbox2'], 256)
    sbox3 = _lcg_shuffle(P['sbox3'], 256)
    rot_table = _lcg_bytes(P['rot'], 256)
    perm = _lcg_shuffle(P['shuffle'], 256)

    enc = bytearray(len(data))
    for i in range(len(data)):
        k = key1[i % 32]
        enc[i] = data[i] ^ sbox1[(k + i) % 256] ^ ((k * (i + 1)) % 256)

    for i in range(len(enc)):
        rot = rot_table[i % 256] % 8
        b = enc[i]
        enc[i] = b if rot == 0 else ((b << rot) | (b >> (8 - rot))) % 256
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
    payload_blob = header + bytes(shuffled)
    blob_hash = _djb2_hash(payload_blob)
    payload_b85 = _b85_encode(payload_blob)

    # ── Build Stage 2 runtime code (will be encrypted) ──
    rt_code = _build_stage2(P, blob_hash, checksum, rng)

    # ── Encrypt runtime code with XOR stream ──
    rt_enc = bytearray(len(rt_code))
    for i in range(len(rt_code)):
        rt_enc[i] = ord(rt_code[i]) ^ rt_key[i % 32]
    rt_b85 = _b85_encode(bytes(rt_enc))

    return _build_output(payload_b85, rt_b85, rt_key_seed, P, rng)


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
#  Stage 2: Full decryptor (this code gets encrypted)
# ═══════════════════════════════════════════════════════

def _build_stage2(P, blob_hash, checksum, rng):
    """Build the Stage 2 Lua code that will be encrypted and stored in t.c"""
    
    # Use short variable names to keep encrypted size small
    code = (
        'return function(t)'
        # Helpers
        'local sb,sc,sg,ss,tc,bx,ls,sm,fl=t[1],t[2],t[3],t[4],t[5],t[6],t[7],t[8],t[9]'
        # b4: int to 4 bytes LE
        'local function b4(v)return sc(v%256,fl(v/256)%256,fl(v/65536)%256,fl(v/16777216)%256)end'
        # LCG permutation
        f'local function lcg_p(sd)local p={{}}for i=0,255 do p[i]=i end local s=sd%2147483647 if s==0 then s=1 end for i=255,1,-1 do s=(s*16807)%2147483647 local j=s%(i+1)p[i],p[j]=p[j],p[i]end return p end'
        # LCG bytes
        f'local function lcg_b(sd,n)local o={{}}local s=sd%2147483647 if s==0 then s=1 end for i=1,n do s=(s*16807)%2147483647 o[i]=s%256 end return o end'
        # Hash
        'local function bh(d)local h=5381 for i=1,#d do h=(h*31+sb(d,i))%4294967296 end return h end'
        # Base85 decoder
        'local function b85(s)s=sg(s,"z","!!!!!")return(sg(s,".....",sm({},{__index=function(c,k)local a,b,d,e,f=sb(k,1,5)local v=(a-33)*52200625+(b-33)*614125+(d-33)*7225+(e-33)*85+(f-33)c[k]=b4(v)return b4(v)end})))end'
        # Decode payload blob
        'local raw=b85(t.j)'
        # Anti-tamper
        f'if bh(raw)~={_split(blob_hash, rng)}then error("x")end'
        # Read header
        'local n=sb(raw,1)+sb(raw,2)*256+sb(raw,3)*65536+sb(raw,4)*16777216'
        'local cs=sb(raw,5)+sb(raw,6)*256+sb(raw,7)*65536+sb(raw,8)*16777216'
        'local p=ss(raw,9)'
        # Generate crypto
        f'local sbox1=lcg_p({_split(P["sbox1"], rng)})'
        f'local sbox2=lcg_p({_split(P["sbox2"], rng)})'
        f'local sbox3=lcg_p({_split(P["sbox3"], rng)})'
        f'local key1=lcg_b({_split(P["key1"], rng)},32)'
        f'local key2=lcg_b({_split(P["key2"], rng)},64)'
        f'local rot=lcg_b({_split(P["rot"], rng)},256)'
        f'local sh=lcg_p({_split(P["shuffle"], rng)})'
        # Reverse shuffle
        'local tt={}for i=1,n do local bl=fl((i-1)/256)local ps=(i-1)%256 tt[i]=sb(p,bl*256+sh[ps]+1)end'
        # Reverse position XOR
        f'for i=1,n do tt[i]=bx(tt[i],({_split(P["xor_a"], rng)}+(i-1)*{_split(P["xor_b"], rng)}+((i-1)*(i-1))%256*{_split(P["xor_c"], rng)})%256)end'
        # Reverse Layer 5
        'local is3={}for i=0,255 do is3[sbox3[i]]=i end '
        'for i=1,n do tt[i]=(is3[tt[i]]-(i-1)*3+512)%256 end'
        # Reverse Layer 4
        'local rolling=0 for i=1,n do local k=key2[(i-1)%64+1]local ev=tt[i]tt[i]=bx(tt[i],(k+rolling)%256)rolling=(rolling+ev)%256 end'
        # Reverse Layer 3
        'local is2={}for i=0,255 do is2[sbox2[i]]=i end '
        'for i=1,n do tt[i]=(is2[tt[i]]-(i-1)+256)%256 end'
        # Reverse Layer 2
        'local prev=0 for i=1,n do local v=bx(tt[i],prev)prev=tt[i]local r=rot[(i-1)%256+1]%8 if r==0 then tt[i]=v else tt[i]=(fl(v/(2^r))+(v*(2^(8-r)))%256)%256 end end'
        # Reverse Layer 1
        'local rr={}for i=1,n do local k=key1[(i-1)%32+1]tt[i]=bx(tt[i],sbox1[(k+(i-1))%256])tt[i]=bx(tt[i],(k*i)%256)rr[i]=sc(tt[i])end'
        # Concat
        'local out=""for i=1,n,7997 do local e=i+7996 if e>n then e=n end local s={}for j=i,e do s[#s+1]=rr[j]end out=out..tc(s)end'
        # Verify hash
        'local h=5381 for i=1,n do h=(h*31+sb(out,i))%4294967296 end '
        'if h~=cs then error("x")end'
        # Execute
        'local f,e=ls(out)if not f then error(e)end return f()'
        'end'
    )
    return code


# ═══════════════════════════════════════════════════════
#  Output builder
# ═══════════════════════════════════════════════════════

def _build_output(payload_b85, rt_b85, rt_key_seed, P, rng):
    # ── Long string levels ──
    level_j = 1
    while (']' + '=' * level_j + ']') in payload_b85:
        level_j += 1
    eq_j = '=' * level_j

    level_c = 1
    while (']' + '=' * level_c + ']') in rt_b85:
        level_c += 1
    eq_c = '=' * level_c

    # ── Table key assignments ──
    keys = list(range(1, 30))
    rng.shuffle(keys)
    K = {}
    names = ['sb', 'sc', 'sg', 'ss', 'tc', 'bx', 'ls', 'sm', 'fl',
             'rt_key_seed']
    for i, name in enumerate(names):
        K[name] = keys[i]

    # ── Build table entries ──
    entries = []
    entries.append(f'q="Decompression Error"')
    entries.append(f'j=[{eq_j}[{payload_b85}]{eq_j}]')
    entries.append(f'c=[{eq_c}[{rt_b85}]{eq_c}]')

    # Functions
    func_map = {
        'sb': 'string.byte', 'sc': 'string.char', 'sg': 'string.gsub',
        'ss': 'string.sub', 'tc': 'table.concat', 'bx': 'bit32.bxor',
        'ls': 'loadstring', 'sm': 'setmetatable', 'fl': 'math.floor',
    }
    for name, func in func_map.items():
        entries.append(f'[{K[name]}]={func}')

    # Runtime key seed
    entries.append(f'[{K["rt_key_seed"]}]={_split(rt_key_seed, rng)}')

    rng.shuffle(entries)
    table_str = '{' + ','.join(entries) + '}'

    # ── Bootstrap (__index) ──
    # Stage 1: Decrypt t.c using XOR with key from LCG seed
    # Then loadstring and call with table t
    sb = f't[{K["sb"]}]'
    sc = f't[{K["sc"]}]'
    sg = f't[{K["sg"]}]'
    ss = f't[{K["ss"]}]'
    tc = f't[{K["tc"]}]'
    bx = f't[{K["bx"]}]'
    ls = f't[{K["ls"]}]'
    sm = f't[{K["sm"]}]'
    fl = f't[{K["fl"]}]'
    rt_ks = f't[{K["rt_key_seed"]}]'

    bootstrap = (
        f'function(t,k)'
        f'if k=="O" then return function()'
        # b4 helper
        f'local function b4(v)return {sc}(v%256,{fl}(v/256)%256,{fl}(v/65536)%256,{fl}(v/16777216)%256)end'
        # Base85 decoder
        f'local function b85(s)s={sg}(s,"z","!!!!!")return({sg}(s,".....",{sm}({{}},{{__index=function(c,k)local a,b,d,e,f={sb}(k,1,5)local v=(a-33)*52200625+(b-33)*614125+(d-33)*7225+(e-33)*85+(f-33)c[k]=b4(v)return b4(v)end}})))end'
        # Generate XOR key from seed
        f'local rk={{}}local s={rt_ks}%2147483647 if s==0 then s=1 end for i=1,32 do s=(s*16807)%2147483647 rk[i]=s%256 end'
        # Decode encrypted runtime
        f'local enc=b85(t.c)'
        # XOR decrypt
        f'local rt={{}}for i=1,#enc do rt[i]={sc}({bx}({sb}(enc,i),rk[(i-1)%32+1]))end'
        # Build string (batch)
        f'local code=""for i=1,#rt,7997 do local e=i+7996 if e>#rt then e=#rt end local s={{}}for j=i,e do s[#s+1]=rt[j]end code=code..{tc}(s)end'
        # Load and execute stage 2
        f'local fn,err={ls}(code)if not fn then error(err)end return fn()(t)'
        f'end end end'
    )

    return f'return {sm}({table_str},{{__index={bootstrap}}}):O()(...);'
