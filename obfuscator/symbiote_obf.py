"""
NZL Studio Obfuscator v10 — VM-style output (1MB+)

CHANGES FROM v9:
  1. Payload padded to 500-800KB (random bytes) → output ~1MB
  2. 3 encrypted code stages (bootstrap → stage1 → stage2 → payload)
  3. VM-like dispatch structure in runtime
  4. Large computed expression tables
  5. Fake opcode dispatch (looks like VM, actually decryption)

OUTPUT SIZE: ~1-1.5MB (like Luraph)
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
    original_source_len = len(data)

    # ── Padding: pad to at least 800KB for 1MB+ output ──
    min_size = 800 * 1024 + rng.randint(0, 200 * 1024)
    if len(data) < min_size:
        pad_seed = rng.randint(1, 2**30)
        pad_size = min_size - len(data)
        data = data + bytes(pad_size)  # zero padding (we track original len)

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
    rt_key1_seed = rng.randint(1, 2**30)
    rt_key2_seed = rng.randint(1, 2**30)
    rt_key1 = _lcg_bytes(rt_key1_seed, 32)
    rt_key2 = _lcg_bytes(rt_key2_seed, 32)

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

    padded_len = len(enc)
    pad = (256 - padded_len % 256) % 256
    enc.extend([0] * pad)
    shuffled = bytearray(len(enc))
    for i in range(len(enc)):
        blk = i // 256
        pos = i % 256
        shuffled[blk * 256 + perm[pos]] = enc[i]

    checksum = _djb2_hash(source.encode('utf-8'))
    # Header: 4B padded_len + 4B original_source_len + 4B checksum
    header = _int32_le(padded_len) + _int32_le(original_source_len) + _int32_le(checksum)
    payload_blob = header + bytes(shuffled)
    blob_hash = _djb2_hash(payload_blob)
    payload_b85 = _b85_encode(payload_blob)

    # ── Build Stage 3 runtime (decrypts payload) ──
    stage3_code = _build_stage3(P, blob_hash, original_source_len, rng)
    # Encrypt stage 3 with rt_key2
    s3_enc = bytearray(len(stage3_code))
    for i in range(len(stage3_code)):
        s3_enc[i] = ord(stage3_code[i]) ^ rt_key2[i % 32]
    s3_b85 = _b85_encode(bytes(s3_enc))

    # ── Build Stage 2 runtime (decrypts stage 3) ──
    stage2_code = _build_stage2_bridge(rt_key2_seed, rng)
    # Encrypt stage 2 with rt_key1
    s2_enc = bytearray(len(stage2_code))
    for i in range(len(stage2_code)):
        s2_enc[i] = ord(stage2_code[i]) ^ rt_key1[i % 32]
    s2_b85 = _b85_encode(bytes(s2_enc))

    return _build_output(payload_b85, s3_b85, s2_b85, rt_key1_seed, rng)


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
#  Stage 3: Full payload decryptor (encrypted with rt_key2)
# ═══════════════════════════════════════════════════════

def _build_stage3(P, blob_hash, original_source_len, rng):
    code = (
        'return function(t)'
        'local sb,sc,sg,ss,tc,bx,ls,sm,fl=t[1],t[2],t[3],t[4],t[5],t[6],t[7],t[8],t[9]'
        # VM-like dispatch structure
        'local vm={pc=1,done=false,out=nil}'
        'local ctx={}'
        # b4
        'local function b4(v)return sc(v%256,fl(v/256)%256,fl(v/65536)%256,fl(v/16777216)%256)end'
        # LCG
        'local function lcg_p(sd)local p={}for i=0,255 do p[i]=i end local s=sd%2147483647 if s==0 then s=1 end for i=255,1,-1 do s=(s*16807)%2147483647 local j=s%(i+1)p[i],p[j]=p[j],p[i]end return p end'
        'local function lcg_b(sd,n)local o={}local s=sd%2147483647 if s==0 then s=1 end for i=1,n do s=(s*16807)%2147483647 o[i]=s%256 end return o end'
        'local function bh(d)local h=5381 for i=1,#d do h=(h*31+sb(d,i))%4294967296 end return h end'
        'local function b85(s)s=sg(s,"z","!!!!!")return(sg(s,".....",sm({},{__index=function(c,k)local a,b,d,e,f=sb(k,1,5)local v=(a-33)*52200625+(b-33)*614125+(d-33)*7225+(e-33)*85+(f-33)c[k]=b4(v)return b4(v)end})))end'
        # Opcode dispatch table
        'local ops={}'
        # OP 1: decode blob
        f'ops[1]=function()ctx.raw=b85(t.j)if bh(ctx.raw)~={_split(blob_hash, rng)}then error("x")end end'
        # OP 2: read header
        f'ops[2]=function()ctx.n=sb(ctx.raw,1)+sb(ctx.raw,2)*256+sb(ctx.raw,3)*65536+sb(ctx.raw,4)*16777216 '
        f'ctx.src_n={original_source_len} '
        f'ctx.cs=sb(ctx.raw,9)+sb(ctx.raw,10)*256+sb(ctx.raw,11)*65536+sb(ctx.raw,12)*16777216 '
        f'ctx.p=ss(ctx.raw,13)end'
        # OP 3: generate crypto
        f'ops[3]=function()ctx.sbox1=lcg_p({_split(P["sbox1"], rng)})ctx.sbox2=lcg_p({_split(P["sbox2"], rng)})ctx.sbox3=lcg_p({_split(P["sbox3"], rng)})ctx.key1=lcg_b({_split(P["key1"], rng)},32)ctx.key2=lcg_b({_split(P["key2"], rng)},64)ctx.rot=lcg_b({_split(P["rot"], rng)},256)ctx.sh=lcg_p({_split(P["shuffle"], rng)})end'
        # OP 4: reverse shuffle
        'ops[4]=function()local tt={}local n=ctx.n local p=ctx.p local sh=ctx.sh for i=1,n do local bl=fl((i-1)/256)local ps=(i-1)%256 tt[i]=sb(p,bl*256+sh[ps]+1)end ctx.t=tt end'
        # OP 5: reverse position XOR
        f'ops[5]=function()local t=ctx.t local n=ctx.n for i=1,n do t[i]=bx(t[i],({_split(P["xor_a"], rng)}+(i-1)*{_split(P["xor_b"], rng)}+((i-1)*(i-1))%256*{_split(P["xor_c"], rng)})%256)end end'
        # OP 6: reverse layer 5
        'ops[6]=function()local t=ctx.t local n=ctx.n local is3={}for i=0,255 do is3[ctx.sbox3[i]]=i end for i=1,n do t[i]=(is3[t[i]]-(i-1)*3+512)%256 end end'
        # OP 7: reverse layer 4
        'ops[7]=function()local t=ctx.t local n=ctx.n local key2=ctx.key2 local rolling=0 for i=1,n do local k=key2[(i-1)%64+1]local ev=t[i]t[i]=bx(t[i],(k+rolling)%256)rolling=(rolling+ev)%256 end end'
        # OP 8: reverse layer 3
        'ops[8]=function()local t=ctx.t local n=ctx.n local is2={}for i=0,255 do is2[ctx.sbox2[i]]=i end for i=1,n do t[i]=(is2[t[i]]-(i-1)+256)%256 end end'
        # OP 9: reverse layer 2
        'ops[9]=function()local t=ctx.t local n=ctx.n local rot=ctx.rot local prev=0 for i=1,n do local v=bx(t[i],prev)prev=t[i]local r=rot[(i-1)%256+1]%8 if r==0 then t[i]=v else t[i]=(fl(v/(2^r))+(v*(2^(8-r)))%256)%256 end end end'
        # OP 10: reverse layer 1 + string build
        'ops[10]=function()local t=ctx.t local n=ctx.n local key1=ctx.key1 local sbox1=ctx.sbox1 local rr={}for i=1,n do local k=key1[(i-1)%32+1]t[i]=bx(t[i],sbox1[(k+(i-1))%256])t[i]=bx(t[i],(k*i)%256)rr[i]=sc(t[i])end ctx.rr=rr end'
        # OP 11: concat (use src_n to only take original source bytes)
        'ops[11]=function()local rr=ctx.rr local n=ctx.src_n local out=""for i=1,n,7997 do local e=i+7996 if e>n then e=n end local s={}for j=i,e do s[#s+1]=rr[j]end out=out..tc(s)end ctx.out=out end'
        # OP 12: verify + execute
        'ops[12]=function()local out=ctx.out local n=ctx.src_n local h=5381 for i=1,n do h=(h*31+sb(out,i))%4294967296 end if h~=ctx.cs then error("x")end local f,e=ls(out)if not f then error(e)end vm.out=f()vm.done=true end'
        # VM dispatch loop
        'while not vm.done do ops[vm.pc]()vm.pc=vm.pc+1 end'
        'return vm.out'
        'end'
    )
    return code


# ═══════════════════════════════════════════════════════
#  Stage 2: Bridge (decrypts stage 3, encrypted with rt_key1)
# ═══════════════════════════════════════════════════════

def _build_stage2_bridge(rt_key2_seed, rng):
    """Stage 2 decrypts stage 3 (t.s) using rt_key2 and calls it"""
    code = (
        'return function(t)'
        'local sb,sc,sg,ss,tc,bx,ls,sm,fl=t[1],t[2],t[3],t[4],t[5],t[6],t[7],t[8],t[9]'
        'local function b4(v)return sc(v%256,fl(v/256)%256,fl(v/65536)%256,fl(v/16777216)%256)end'
        'local function b85(s)s=sg(s,"z","!!!!!")return(sg(s,".....",sm({},{__index=function(c,k)local a,b,d,e,f=sb(k,1,5)local v=(a-33)*52200625+(b-33)*614125+(d-33)*7225+(e-33)*85+(f-33)c[k]=b4(v)return b4(v)end})))end'
        # Generate key for stage 3
        f'local rk={{}}local s={_split(rt_key2_seed, rng)}%2147483647 if s==0 then s=1 end for i=1,32 do s=(s*16807)%2147483647 rk[i]=s%256 end'
        # Decrypt stage 3
        'local enc=b85(t.s)'
        'local rt={}for i=1,#enc do rt[i]=sc(bx(sb(enc,i),rk[(i-1)%32+1]))end'
        'local code=""for i=1,#rt,7997 do local e=i+7996 if e>#rt then e=#rt end local s={}for j=i,e do s[#s+1]=rt[j]end code=code..tc(s)end'
        'local fn,err=ls(code)if not fn then error(err)end return fn()(t)'
        'end'
    )
    return code


# ═══════════════════════════════════════════════════════
#  Output builder
# ═══════════════════════════════════════════════════════

def _build_output(payload_b85, s3_b85, s2_b85, rt_key1_seed, rng):
    # Long string levels
    def make_long(s):
        lv = 1
        while (']' + '=' * lv + ']') in s:
            lv += 1
        eq = '=' * lv
        return f'[{eq}[{s}]{eq}]'

    j_lit = make_long(payload_b85)
    s_lit = make_long(s3_b85)
    c_lit = make_long(s2_b85)

    # Table keys
    keys = list(range(1, 20))
    rng.shuffle(keys)
    K = {}
    names = ['sb', 'sc', 'sg', 'ss', 'tc', 'bx', 'ls', 'sm', 'fl', 'rt_key1_seed']
    for i, name in enumerate(names):
        K[name] = keys[i]

    # Table entries
    entries = []
    entries.append(f'q="Decompression Error"')
    entries.append(f'j={j_lit}')
    entries.append(f's={s_lit}')
    entries.append(f'c={c_lit}')

    func_map = {
        'sb': 'string.byte', 'sc': 'string.char', 'sg': 'string.gsub',
        'ss': 'string.sub', 'tc': 'table.concat', 'bx': 'bit32.bxor',
        'ls': 'loadstring', 'sm': 'setmetatable', 'fl': 'math.floor',
    }
    for name, func in func_map.items():
        entries.append(f'[{K[name]}]={func}')

    entries.append(f'[{K["rt_key1_seed"]}]= {_split(rt_key1_seed, rng)}')

    rng.shuffle(entries)
    table_str = '{' + ','.join(entries) + '}'

    # Bootstrap (__index)
    sb = f't[{K["sb"]}]'
    sc = f't[{K["sc"]}]'
    sg = f't[{K["sg"]}]'
    ss = f't[{K["ss"]}]'
    tc = f't[{K["tc"]}]'
    bx = f't[{K["bx"]}]'
    ls = f't[{K["ls"]}]'
    sm = f't[{K["sm"]}]'
    fl = f't[{K["fl"]}]'
    rt_ks = f't[{K["rt_key1_seed"]}]'

    bootstrap = (
        f'function(t,k)'
        f'if k=="O" then return function()'
        f'local function b4(v)return {sc}(v%256,{fl}(v/256)%256,{fl}(v/65536)%256,{fl}(v/16777216)%256)end'
        f'local function b85(s)s={sg}(s,"z","!!!!!")return({sg}(s,".....",{sm}({{}},{{__index=function(c,k)local a,b,d,e,f={sb}(k,1,5)local v=(a-33)*52200625+(b-33)*614125+(d-33)*7225+(e-33)*85+(f-33)c[k]=b4(v)return b4(v)end}})))end'
        # Decrypt stage 2 from t.c
        f'local rk={{}}local s={rt_ks}%2147483647 if s==0 then s=1 end for i=1,32 do s=(s*16807)%2147483647 rk[i]=s%256 end'
        f'local enc=b85(t.c)'
        f'local rt={{}}for i=1,#enc do rt[i]={sc}({bx}({sb}(enc,i),rk[(i-1)%32+1]))end'
        f'local code=""for i=1,#rt,7997 do local e=i+7996 if e>#rt then e=#rt end local s={{}}for j=i,e do s[#s+1]=rt[j]end code=code..{tc}(s)end'
        f'local fn,err={ls}(code)if not fn then error(err)end return fn()(t)'
        f'end end end'
    )

    return f'return {sm}({table_str},{{__index={bootstrap}}}):O()(...);'
