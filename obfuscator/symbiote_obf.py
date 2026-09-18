"""
NZL Studio Obfuscator — Luraph-style (loadstring-based)

Optimized for Roblox executors:
- Table-based string building (O(n) not O(n²))
- No string.pack (manual byte conversion)
- Single-line output like Luraph
- No comments
"""

from __future__ import annotations

import random
import sys
import os

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)


def obfuscate(source: str) -> str:
    """Obfuscate any Lua code using loadstring-based approach."""
    from obfuscator.utils.crypto import rc4_encrypt, gen_random_key

    try:
        seed = random.randint(1, 2**31)
        rng = random.Random(seed)

        source_bytes = source.encode('utf-8')

        key = gen_random_key(16, rng=rng)
        xor_seed = rng.randint(0, 255)
        shuffle_perm = list(range(256))
        rng.shuffle(shuffle_perm)

        # Layer 1: RC4
        encrypted = rc4_encrypt(source_bytes, key)

        # Layer 2: XOR with position
        encrypted2 = bytearray(encrypted)
        for i in range(len(encrypted2)):
            encrypted2[i] ^= (i + xor_seed) % 256

        # Pad to multiple of 256
        original_len = len(encrypted2)
        pad_len = (256 - (original_len % 256)) % 256
        encrypted2.extend([0] * pad_len)

        # Layer 3: Byte shuffle
        encrypted3 = bytearray(len(encrypted2))
        for i in range(len(encrypted2)):
            block = i // 256
            pos_in_block = i % 256
            new_pos_in_block = shuffle_perm[pos_in_block]
            new_pos = block * 256 + new_pos_in_block
            encrypted3[new_pos] = encrypted2[i]

        # Add length prefix (big-endian u32)
        length_bytes = original_len.to_bytes(4, 'big')
        final_data = bytes(length_bytes) + bytes(encrypted3)

        # Encode to base85
        base85_blob = _encode_base85(final_data)

        # Generate single-line runtime
        runtime = _generate_runtime(
            base85_blob=base85_blob,
            key=key,
            xor_seed=xor_seed,
            shuffle_perm=shuffle_perm,
            rng=rng
        )

        return runtime

    except Exception as e:
        import traceback
        traceback.print_exc()
        return f'-- Error: {e}\n{source}'


def obfuscate_script(source: str, seed: int = None) -> str:
    if seed is not None:
        random.seed(seed)
    return obfuscate(source)


def _encode_base85(data: bytes) -> str:
    """Encode bytes to base85 (ASCII85 variant)."""
    result = []
    padding = (4 - len(data) % 4) % 4
    data = data + b'\x00' * padding

    for i in range(0, len(data), 4):
        chunk = data[i:i+4]
        value = int.from_bytes(chunk, 'big')

        if value == 0:
            result.append('z')
        else:
            chars = []
            for _ in range(5):
                chars.append(chr(value % 85 + 33))
                value //= 85
            result.append(''.join(reversed(chars)))

    if padding > 0:
        last = result[-1]
        result[-1] = last[:5-padding]

    return ''.join(result)


def _generate_runtime(base85_blob: str, key: bytes, xor_seed: int, shuffle_perm: list, rng: random.Random) -> str:
    """Generate Luraph-style single-line runtime."""

    used_names = set()
    def gen_name(length=2):
        letters = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
        while True:
            name = ''.join(rng.choice(letters) for _ in range(length))
            if name not in used_names and not name.isalpha():
                pass  # ensure mixed
            if name not in used_names:
                used_names.add(name)
                return name

    # Short aliases
    sm = gen_name()   # setmetatable
    ss = gen_name()   # string.sub
    sc = gen_name()   # string.char
    sg = gen_name()   # string.gsub
    sb = gen_name()   # string.byte
    ls = gen_name()   # loadstring
    pk = gen_name()   # pcall
    bx = gen_name()   # bit32.bxor

    # Function names
    b85 = gen_name()  # base85 decoder
    rc4 = gen_name()  # RC4 decryptor
    dec = gen_name()  # multi-layer decryptor

    # Shuffle table
    shuffle_table = ','.join(str(x) for x in shuffle_perm)

    # Key as escaped string
    key_escaped = ''.join(f'\\{b:03d}' for b in key)

    # Base85 to 4-byte converter (no string.pack!)
    # Manual: pack 4 bytes as little-endian int32
    # We need to convert base85 decoded int to 4-byte LE string
    # Lua: local function b4(x) return sc(x%256,math.floor(x/256)%256,math.floor(x/65536)%256,math.floor(x/16777216)%256) end

    # Long string for blob
    level = 1
    marker = ']' + '=' * level + ']'
    while marker in base85_blob:
        level += 1
        marker = ']' + '=' * level + ']'
    eq = '=' * level

    # Build runtime as single line (like Luraph)
    parts = []

    # Header
    parts.append(f'return(function()')

    # Aliases
    parts.append(f'local {sm},{ss},{sc},{sg},{sb},{ls},{pk},{bx}=setmetatable,string.sub,string.char,string.gsub,string.byte,loadstring,pcall,bit32.bxor')

    # Helper: int32 to 4-byte LE string (replaces string.pack)
    b4fn = gen_name()
    parts.append(f'local function {b4fn}(x)return {sc}(x%256,math.floor(x/256)%256,math.floor(x/65536)%256,math.floor(x/16777216)%256)end')

    # Base85 decoder
    parts.append(f'local {b85}=function(u)u={ss}(u,1)u={sg}(u,"z","!!!!!")return {sg}(u,".....",{sm}({{}},{{__index=function(q,W)local p,u,S,h,l={sb}(W,1,5)local X=(l-33)+(h-33)*85+(S-33)*7225+(u-33)*614125+(p-33)*52200625 q[W]={b4fn}(X)return {b4fn}(X)end}}))end')

    # RC4 decryptor (table-based for speed)
    parts.append(f'local {rc4}=function(d,k)local s={{}}for i=0,255 do s[i]=i end local j=0 for i=0,255 do j=(j+s[i]+{sb}(k,(i%#k)+1))%256 s[i],s[j]=s[j],s[i]end local o={{}}local a,b=0,0 for i=1,#d do a=(a+1)%256 b=(b+s[a])%256 s[a],s[b]=s[b],s[a]o[i]={sc}({bx}({sb}(d,i),s[(s[a]+s[b])%256]))end return table.concat(o)end')

    # Multi-layer decryptor (TABLE-BASED for speed, not string concat!)
    parts.append(f'local {dec}=function(d,k)')

    # Read length
    parts.append(f'local n={sb}(d,1)*16777216+{sb}(d,2)*65536+{sb}(d,3)*256+{sb}(d,4)')
    parts.append(f'local p={ss}(d,5)')

    # Reverse shuffle (TABLE-BASED!)
    parts.append(f'local t={{}}local sh={{{shuffle_table}}}')
    parts.append(f'for i=1,n do local bl=math.floor((i-1)/256)local ps=(i-1)%256 local np=bl*256+sh[ps+1]+1 t[i]={sb}(p,np)end')

    # Reverse XOR (TABLE-BASED!)
    parts.append(f'local u={{}}for i=1,n do u[i]={bx}(t[i],(i-1+{xor_seed})%256)end')

    # Convert to string (batch for speed, like Luraph)
    xfn = gen_name()
    parts.append(f'local {xfn}="" for i=1,n,7997 do local e=i+7996 if e>n then e=n end local s="" for j=i,e do s=s..{sc}(u[j])end {xfn}={xfn}..s end')

    # RC4
    parts.append(f'return {rc4}({xfn},k)end')

    # Variable names for blob/decoded/decrypted
    blob_var = gen_name()
    decoded_var = gen_name()
    decrypted_var = gen_name()

    # Decode blob
    parts.append(f'local {blob_var}=[{eq}[{base85_blob}]{eq}]')
    parts.append(f'local {decoded_var}={b85}({blob_var})')

    # Decrypt
    parts.append(f'local {decrypted_var}={dec}({decoded_var},"{key_escaped}")')

    # Load and execute
    parts.append(f'local f,e={ls}({decrypted_var})if not f then error(e)end return f()end)()')

    # Join everything into one line (with spaces between parts)
    return ' '.join(parts)
