"""
NZL Studio Obfuscator v7 — State Machine Runtime

Instead of linear code (base85 → unshuffle → unxor → decrypt → loadstring),
the runtime is a STATE MACHINE with 20+ states in random order.

Analyst CANNOT read top-to-bottom. Must reconstruct the state graph.

Each state does a small piece of work and jumps to the next state.
States are numbered randomly, transitions use computed expressions.

PROTECTION:
  1. State machine control flow (not linear)
  2. Quintuple encryption (5 layers)
  3. Computed seeds (nested expressions)
  4. Blob hash anti-tamper
  5. Integrity check (DJB2)
  6. All state IDs are computed, not sequential
  7. Context table stores intermediate results
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

    # ── Encrypt Layer 2: Rotation + XOR chain ──
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

    # ── Encrypt Layer 4: Key2 rolling XOR ──
    rolling = 0
    for i in range(len(enc)):
        k = key2[i % 64]
        enc[i] ^= (k + rolling) % 256
        rolling = (rolling + enc[i]) % 256

    # ── Encrypt Layer 5: Triple substitution ──
    for i in range(len(enc)):
        enc[i] = sbox3[(enc[i] + i * 3) % 256]

    # ── Position XOR ──
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

    checksum = _djb2_hash(data)
    header = _int32_le(original_len) + _int32_le(checksum)
    final = header + bytes(shuffled)
    blob_hash = _djb2_hash(final)
    blob = _b85_encode(final)

    return _build_runtime_sm(blob, params, blob_hash, rng)


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

def _split_expr(value, rng, depth=0):
    if depth > 2 or value < 10:
        return str(value)
    method = rng.randint(0, 4)
    if method == 0 and value > 100:
        a = rng.randint(10, max(10, value // 2))
        b = max(1, value // a)
        c = value - a * b
        return f'{a}*{b}+{_split_expr(c, rng, depth+1)}' if c >= 0 else f'{a}*{b}-{_split_expr(abs(c), rng, depth+1)}'
    elif method == 1:
        a = rng.randint(value + 100, value + 10000)
        return f'{a}-{_split_expr(a - value, rng, depth+1)}'
    elif method == 2:
        a = rng.randint(1, max(1, value // 2))
        return f'{_split_expr(a, rng, depth+1)}+{_split_expr(value - a, rng, depth+1)}'
    elif method == 3:
        a = rng.randint(0, 65535)
        return f'bit32.bxor({_split_expr(a, rng, depth+1)},{_split_expr(a ^ value, rng, depth+1)})'
    else:
        a = rng.randint(0, 65535)
        return f'{_split_expr(value + a, rng, depth+1)}-{_split_expr(a, rng, depth+1)}'


# ═══════════════════════════════════════════════════════
#  State Machine Runtime Builder
# ═══════════════════════════════════════════════════════

def _build_runtime_sm(blob, params, blob_hash, rng):
    taken = set()

    def nm(n=2):
        ch = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
        while True:
            s = ''.join(rng.choice(ch) for _ in range(n))
            if s not in taken and len(s) == n:
                taken.add(s)
                return s

    for kw in ['local','function','return','end','if','then','else','elseif',
               'for','do','while','repeat','until','and','or','not','in',
               'true','false','nil','break','string','table','math','bit32',
               'error','pcall','loadstring','setmetatable','tostring',
               'game','require','ipairs','pairs','type','select','unpack',
               'rawget','rawset','self','continue']:
        taken.add(kw)

    # ── Names ──
    N = {}
    for k in ['sc','sb','sg','ss','tc','bx','ls','sm','i2n','b4','b85',
              'lcg_p','lcg_b','bh']:
        N[k] = nm(rng.choice([2,3]))

    # Context table name
    ctx = nm(2)
    state_var = nm(2)

    # ── State IDs (random, non-sequential) ──
    used_ids = set()
    def new_state_id():
        while True:
            sid = rng.randint(100, 9999)
            if sid not in used_ids:
                used_ids.add(sid)
                return sid

    # Define states
    S = {}
    state_names = ['init', 'b85decode', 'read_header', 'hash_check',
                   'gen_crypto', 'unshuffle', 'unxor_pos',
                   'unlayer5', 'unlayer4', 'unlayer3', 'unlayer2',
                   'unlayer1', 'concat', 'verify_hash', 'execute']
    for name in state_names:
        S[name] = new_state_id()
    S['exit'] = 0

    # ── Computed expressions ──
    seed_exprs = {}
    for k in ['key1_seed','key2_seed','sbox1_seed','sbox2_seed','sbox3_seed','rot_seed','shuffle_seed']:
        seed_exprs[k] = _split_expr(params[k], rng, depth=1)
    xor_a_e = _split_expr(params['xor_a'], rng)
    xor_b_e = _split_expr(params['xor_b'], rng)
    xor_c_e = _split_expr(params['xor_c'], rng)
    blob_hash_e = _split_expr(blob_hash, rng)

    # ── Long string ──
    level = 0
    while (']' + '=' * level + ']') in blob:
        level += 1
    eq = '=' * level
    blob_lit = f'[{eq}[{blob}]{eq}]'

    # ── Build output ──
    P = []
    P.append('return(function()')

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
    P.append(f'local {",".join(a[0] for a in aliases)}={",".join(a[1] for a in aliases)}')
    P.append(f'local {N["i2n"]}=math.floor')

    # Helper functions
    P.append(f'local function {N["b4"]}(v)return {N["sc"]}(v%256,{N["i2n"]}(v/256)%256,{N["i2n"]}(v/65536)%256,{N["i2n"]}(v/16777216)%256)end')
    P.append(f'local function {N["lcg_p"]}(sd)local p={{}}for i=0,255 do p[i]=i end local s=sd%2147483647 if s==0 then s=1 end for i=255,1,-1 do s=(s*16807)%2147483647 local j=s%(i+1)p[i],p[j]=p[j],p[i]end return p end')
    P.append(f'local function {N["lcg_b"]}(sd,n)local t={{}}local s=sd%2147483647 if s==0 then s=1 end for i=1,n do s=(s*16807)%2147483647 t[i]=s%256 end return t end')
    P.append(f'local function {N["bh"]}(d)local h=5381 for i=1,#d do h=(h*31+{N["sb"]}(d,i))%4294967296 end return h end')
    P.append(f'local {N["b85"]}=function(s)s={N["sg"]}(s,"z","!!!!!")return({N["sg"]}(s,".....",{N["sm"]}({{}},{{__index=function(t,k)local a,b,c,d,e={N["sb"]}(k,1,5)local v=(a-33)*52200625+(b-33)*614125+(c-33)*7225+(d-33)*85+(e-33)t[k]={N["b4"]}(v)return {N["b4"]}(v)end}})))end')

    # Context + state
    P.append(f'local {ctx}={{}}')
    P.append(f'local {state_var}={S["init"]}')

    # State machine loop
    P.append(f'while {state_var}~={S["exit"]} do')

    # Shuffle state order for output
    state_order = list(state_names)
    rng.shuffle(state_order)

    for sname in state_order:
        sid = S[sname]

        if sname == 'init':
            P.append(f'if {state_var}=={sid} then')
            P.append(f'{ctx}.blob={blob_lit}')
            P.append(f'{state_var}={S["b85decode"]}')

        elif sname == 'b85decode':
            P.append(f'elseif {state_var}=={sid} then')
            P.append(f'{ctx}.raw={N["b85"]}({ctx}.blob)')
            P.append(f'{state_var}={S["read_header"]}')

        elif sname == 'read_header':
            P.append(f'elseif {state_var}=={sid} then')
            P.append(f'local d={ctx}.raw')
            P.append(f'{ctx}.n={N["sb"]}(d,1)+{N["sb"]}(d,2)*256+{N["sb"]}(d,3)*65536+{N["sb"]}(d,4)*16777216')
            P.append(f'{ctx}.cs={N["sb"]}(d,5)+{N["sb"]}(d,6)*256+{N["sb"]}(d,7)*65536+{N["sb"]}(d,8)*16777216')
            P.append(f'{ctx}.p={N["ss"]}(d,9)')
            P.append(f'{state_var}={S["hash_check"]}')

        elif sname == 'hash_check':
            P.append(f'elseif {state_var}=={sid} then')
            P.append(f'if {N["bh"]}({ctx}.raw)~={blob_hash_e}then error("x")end')
            P.append(f'{state_var}={S["gen_crypto"]}')

        elif sname == 'gen_crypto':
            P.append(f'elseif {state_var}=={sid} then')
            P.append(f'{ctx}.sbox1={N["lcg_p"]}({seed_exprs["sbox1_seed"]})')
            P.append(f'{ctx}.sbox2={N["lcg_p"]}({seed_exprs["sbox2_seed"]})')
            P.append(f'{ctx}.sbox3={N["lcg_p"]}({seed_exprs["sbox3_seed"]})')
            P.append(f'{ctx}.key1={N["lcg_b"]}({seed_exprs["key1_seed"]},32)')
            P.append(f'{ctx}.key2={N["lcg_b"]}({seed_exprs["key2_seed"]},64)')
            P.append(f'{ctx}.rot={N["lcg_b"]}({seed_exprs["rot_seed"]},256)')
            P.append(f'{ctx}.sh={N["lcg_p"]}({seed_exprs["shuffle_seed"]})')
            P.append(f'{state_var}={S["unshuffle"]}')

        elif sname == 'unshuffle':
            P.append(f'elseif {state_var}=={sid} then')
            P.append(f'local t={{}}local n={ctx}.n local p={ctx}.p local sh={ctx}.sh')
            P.append(f'for i=1,n do local bl={N["i2n"]}((i-1)/256)local ps=(i-1)%256 t[i]={N["sb"]}(p,bl*256+sh[ps]+1)end')
            P.append(f'{ctx}.t=t')
            P.append(f'{state_var}={S["unxor_pos"]}')

        elif sname == 'unxor_pos':
            P.append(f'elseif {state_var}=={sid} then')
            P.append(f'local t={ctx}.t local n={ctx}.n')
            P.append(f'for i=1,n do t[i]={N["bx"]}(t[i],({xor_a_e}+(i-1)*{xor_b_e}+((i-1)*(i-1))%256*{xor_c_e})%256)end')
            P.append(f'{state_var}={S["unlayer5"]}')

        elif sname == 'unlayer5':
            P.append(f'elseif {state_var}=={sid} then')
            P.append(f'local t={ctx}.t local n={ctx}.n')
            P.append(f'local is3={{}}for i=0,255 do is3[{ctx}.sbox3[i]]=i end')
            P.append(f'for i=1,n do t[i]=(is3[t[i]]-(i-1)*3+512)%256 end')
            P.append(f'{state_var}={S["unlayer4"]}')

        elif sname == 'unlayer4':
            P.append(f'elseif {state_var}=={sid} then')
            P.append(f'local t={ctx}.t local n={ctx}.n local key2={ctx}.key2')
            P.append(f'local rolling=0 for i=1,n do local k=key2[(i-1)%64+1]local ev=t[i]t[i]={N["bx"]}(t[i],(k+rolling)%256)rolling=(rolling+ev)%256 end')
            P.append(f'{state_var}={S["unlayer3"]}')

        elif sname == 'unlayer3':
            P.append(f'elseif {state_var}=={sid} then')
            P.append(f'local t={ctx}.t local n={ctx}.n')
            P.append(f'local is2={{}}for i=0,255 do is2[{ctx}.sbox2[i]]=i end')
            P.append(f'for i=1,n do t[i]=(is2[t[i]]-(i-1)+256)%256 end')
            P.append(f'{state_var}={S["unlayer2"]}')

        elif sname == 'unlayer2':
            P.append(f'elseif {state_var}=={sid} then')
            P.append(f'local t={ctx}.t local n={ctx}.n local rot={ctx}.rot')
            P.append(f'local prev=0 for i=1,n do local v={N["bx"]}(t[i],prev)prev=t[i]local r=rot[(i-1)%256+1]%8 if r==0 then t[i]=v else t[i]=({N["i2n"]}(v/(2^r))+(v*(2^(8-r)))%256)%256 end end')
            P.append(f'{state_var}={S["unlayer1"]}')

        elif sname == 'unlayer1':
            P.append(f'elseif {state_var}=={sid} then')
            P.append(f'local t={ctx}.t local n={ctx}.n local key1={ctx}.key1 local sbox1={ctx}.sbox1')
            P.append(f'local r={{}}for i=1,n do local k=key1[(i-1)%32+1]t[i]={N["bx"]}(t[i],sbox1[(k+(i-1))%256])t[i]={N["bx"]}(t[i],(k*i)%256)r[i]={N["sc"]}(t[i])end')
            P.append(f'{ctx}.r=r')
            P.append(f'{state_var}={S["concat"]}')

        elif sname == 'concat':
            P.append(f'elseif {state_var}=={sid} then')
            P.append(f'local r={ctx}.r local n={ctx}.n')
            P.append(f'local out=""for i=1,n,7997 do local e=i+7996 if e>n then e=n end local s={{}}for j=i,e do s[#s+1]=r[j]end out=out..{N["tc"]}(s)end')
            P.append(f'{ctx}.out=out')
            P.append(f'{state_var}={S["verify_hash"]}')

        elif sname == 'verify_hash':
            P.append(f'elseif {state_var}=={sid} then')
            P.append(f'local out={ctx}.out local n={ctx}.n')
            P.append(f'local h=5381 for i=1,n do h=(h*31+{N["sb"]}(out,i))%4294967296 end')
            P.append(f'if h~={ctx}.cs then error("x")end')
            P.append(f'{state_var}={S["execute"]}')

        elif sname == 'execute':
            P.append(f'elseif {state_var}=={sid} then')
            P.append(f'local f,e={N["ls"]}({ctx}.out)if not f then error(e)end')
            P.append(f'{ctx}.result=f()')
            P.append(f'{state_var}={S["exit"]}')

        P.append('end')  # close if/elseif

    P.append('end')  # close while

    P.append(f'return {ctx}.result')
    P.append('end)()')

    return ' '.join(P)
