"""
NZL Studio Obfuscator — Luraph-style (loadstring-based)

Simple but effective:
1. Take source code as string (works with ANY Lua code)
2. Encrypt (RC4 + XOR + shuffle)
3. Encode to base85
4. Wrap in long string [=[...]=]
5. Runtime: base85 decode → decrypt → loadstring → execute

No parser, no compiler, no VM needed!
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
        
        # Convert source to bytes
        source_bytes = source.encode('utf-8')
        
        # Multi-layer encryption
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
        
        # Generate runtime
        runtime = _generate_runtime(
            base85_blob=base85_blob,
            key=key,
            xor_seed=xor_seed,
            shuffle_perm=shuffle_perm,
            seed=seed,
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
    
    # Remove padding from last group
    if padding > 0:
        last = result[-1]
        result[-1] = last[:5-padding]
    
    return ''.join(result)


def _generate_runtime(base85_blob: str, key: bytes, xor_seed: int, shuffle_perm: list, seed: int, rng: random.Random) -> str:
    """Generate Luraph-style runtime."""
    
    # Generate unique random names
    used_names = set()
    def gen_name():
        letters = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
        while True:
            name = ''.join(rng.choice(letters) for _ in range(rng.randint(2, 3)))
            if name not in used_names:
                used_names.add(name)
                return name
    
    # Aliases
    setmetatable = gen_name()
    tostring = gen_name()
    string_sub = gen_name()
    string_char = gen_name()
    string_gsub = gen_name()
    unpack_name = gen_name()
    type_name = gen_name()
    loadstring_name = gen_name()
    pcall_name = gen_name()
    string_pack = gen_name()
    string_byte = gen_name()
    
    # Function names
    base85_decode = gen_name()
    decrypt = gen_name()
    rc4_decrypt = gen_name()
    
    # Variable names
    blob = gen_name()
    decoded = gen_name()
    decrypted = gen_name()
    
    # Build shuffle table
    shuffle_table = ','.join(str(x) for x in shuffle_perm)
    
    # Build key as escaped string
    key_escaped = ''.join(f'\\{b:03d}' for b in key)
    
    # Check if blob contains ]] and adjust level
    level = 1  # Start with level 1 to be safe
    marker = ']' + '=' * level + ']'
    while marker in base85_blob:
        level += 1
        marker = ']' + '=' * level + ']'
    
    eq = '=' * level
    blob_wrapped = f'[{eq}[{base85_blob}]{eq}]'
    
    runtime = f'''-- This file was protected using NZL Studio Obfuscator v2.0

return(function()
local {setmetatable},{tostring},{string_sub},{string_char},{string_gsub},{unpack_name},{type_name},{loadstring_name},{pcall_name},{string_pack},{string_byte}=setmetatable,tostring,string.sub,string.char,string.gsub,table.unpack or unpack,type,loadstring,pcall,string.pack,string.byte

-- Base85 decoder
local {base85_decode}=function(u)
u={string_sub}(u,1)
u={string_gsub}(u,"z","!!!!!")
return {string_gsub}(u,".....",{setmetatable}({{}},{{__index=function(q,W)
local p,u,S,h,l={string_byte}(W,1,5)
local X=(l-33)+(h-33)*85+(S-33)*7225+(u-33)*614125+(p-33)*52200625
p={string_pack}("<I4",X)
q[W]=p
return p
end}}))
end

-- RC4 decryptor
local {rc4_decrypt}=function(data,key)
local s={{}}
for i=0,255 do s[i]=i end
local j=0
local k_len=#key
for i=0,255 do
j=(j+s[i]+{string_byte}(key,(i%k_len)+1))%256
s[i],s[j]=s[j],s[i]
end
local out={{}}
local i2=0
local j2=0
for idx=1,#data do
i2=(i2+1)%256
j2=(j2+s[i2])%256
s[i2],s[j2]=s[j2],s[i2]
local tmp=s[(s[i2]+s[j2])%256]
out[idx]={string_char}(bit32.bxor({string_byte}(data,idx),tmp))
end
return table.concat(out)
end

-- Multi-layer decryptor
local {decrypt}=function(data,key)
-- Read original length (first 4 bytes, big-endian)
local orig_len={string_byte}(data,1)*16777216+{string_byte}(data,2)*65536+{string_byte}(data,3)*256+{string_byte}(data,4)
local payload={string_sub}(data,5)

-- Layer 3: Reverse shuffle
local unshuffle=""
local shuffle={{{shuffle_table}}}
for i=1,orig_len do
local block=math.floor((i-1)/256)
local pos_in_block=(i-1)%256
local new_pos=block*256+shuffle[pos_in_block+1]+1
unshuffle=unshuffle..{string_char}({string_byte}(payload,new_pos))
end

-- Layer 2: Reverse XOR
local unxor=""
for i=1,#unshuffle do
unxor=unxor..{string_char}(bit32.bxor({string_byte}(unshuffle,i),(i-1+{xor_seed})%256))
end

-- Layer 1: RC4
local rc4_dec={rc4_decrypt}(unxor,key)

return rc4_dec
end

-- Decode blob
local {blob}={blob_wrapped}
local {decoded}={base85_decode}({blob})

-- Decrypt
local {decrypted}={decrypt}({decoded},"{key_escaped}")

-- Load and execute
local fn,err={loadstring_name}({decrypted})
if not fn then error("Load error: "..tostring(err)) end
return fn()
end)()
'''
    
    return runtime
