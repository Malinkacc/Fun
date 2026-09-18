"""
NZL Studio Obfuscator — Full Encryption (Roblox Executor Compatible)

Everything encrypted with RC4 → encoded as base85 → massive blob.
Tiny bootstrap decodes + decrypts + loadstring.
No visible string tables, no visible VM runtime.
Works in Roblox executors (Synapse, Krnl, Script-Ware, etc.)
"""

from __future__ import annotations

import random
import sys
import os
import struct
import hashlib
from typing import List

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)


# ═══════════════════════════════════════════════════════════════════════
# BASE85 ENCODER
# ═══════════════════════════════════════════════════════════════════════

_B85 = (
    "!\"#$%&'()*+,-./0123456789:;<=>?@"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`"
    "abcdefghijklmnopqrstuvwxyz{|}~"
)


def _b85_encode(data: bytes) -> str:
    """Encode bytes → base85 string (little-endian, always 5 chars per 4 bytes)."""
    out: List[str] = []
    pad = (4 - len(data) % 4) % 4
    data += b'\x00' * pad
    for i in range(0, len(data), 4):
        n = struct.unpack('<I', data[i:i+4])[0]
        c = []
        for _ in range(5):
            c.append(_B85[n % 85])
            n //= 85
        out.append(''.join(reversed(c)))
    return ''.join(out)


# ═══════════════════════════════════════════════════════════════════════
# RC4 ENCRYPTION (Python side)
# ═══════════════════════════════════════════════════════════════════════

def _rc4(data: bytes, key: bytes) -> bytes:
    """RC4 encrypt/decrypt."""
    S = list(range(256))
    j = 0
    for i in range(256):
        j = (j + S[i] + key[i % len(key)]) % 256
        S[i], S[j] = S[j], S[i]
    
    out = bytearray(len(data))
    i = j = 0
    for k in range(len(data)):
        i = (i + 1) % 256
        j = (j + S[i]) % 256
        S[i], S[j] = S[j], S[i]
        out[k] = data[k] ^ S[(S[i] + S[j]) % 256]
    return bytes(out)


# ═══════════════════════════════════════════════════════════════════════
# MAIN OBFUSCATOR
# ═══════════════════════════════════════════════════════════════════════

def obfuscate(source: str) -> str:
    """
    Obfuscate Lua source → one massive base85 blob.
    
    Pipeline:
    1. Compile source → VM bytecode
    2. Generate VM runtime + wrapper (full working Lua code)
    3. RC4-encrypt the entire output
    4. Base85-encode the encrypted bytes
    5. Wrap with tiny bootstrap (decode → decrypt → loadstring)
    """
    from obfuscator.lexer import Lexer
    from obfuscator.parser import Parser
    from obfuscator.vm.compiler import compile_function
    from obfuscator.vm.runtime_lua import generate_vm_code
    
    wrapped = f'local function __main__() {source} end'
    
    try:
        tokens = Lexer(wrapped).tokenize()
        ast = Parser(tokens).parse()
        func_ast = ast.body.statements[0].func
        
        proto = compile_function(func_ast)
        seed = random.randint(1, 2**31)
        vm_output = generate_vm_code(proto, seed=seed)
        
        # Remove comments from VM output
        clean_lines = []
        for line in vm_output.split('\n'):
            if '--' in line:
                line = line[:line.index('--')]
            clean_lines.append(line.rstrip())
        vm_clean = '\n'.join(clean_lines).strip()
        
        return _build_encrypted_blob(vm_clean)
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return f'-- Error: {e}\n{source}'


def obfuscate_script(source: str, seed: int = None) -> str:
    if seed is not None:
        random.seed(seed)
    return obfuscate(source)


# ═══════════════════════════════════════════════════════════════════════
# BUILD ENCRYPTED OUTPUT
# ═══════════════════════════════════════════════════════════════════════

def _build_encrypted_blob(vm_code: str) -> str:
    """
    Build the final output:
    - RC4 encrypt the VM code
    - Base85 encode
    - Add padding
    - Wrap with tiny bootstrap
    """
    # Generate random RC4 key (16-32 bytes)
    key_len = random.randint(16, 32)
    key_bytes = bytes(random.randint(1, 254) for _ in range(key_len))
    
    # RC4 encrypt the VM code
    vm_bytes = vm_code.encode('utf-8')
    encrypted = _rc4(vm_bytes, key_bytes)
    
    # Base85 encode the encrypted data
    b85_blob = _b85_encode(encrypted)
    
    # Add padding to make blob larger (match commercial obfuscator output size)
    target = max(len(b85_blob), 12000)
    if len(b85_blob) < target:
        # Pad with random base85 chars BEFORE encoding (add to encrypted data)
        extra_bytes = bytes(random.randint(0, 255) for _ in range((target - len(b85_blob)) * 4 // 5 + 100))
        encrypted_padded = encrypted + extra_bytes
        b85_blob = _b85_encode(encrypted_padded)
    
    # Build the key as Lua byte sequence
    key_lua = ','.join(str(b) for b in key_bytes)
    
    # Build bootstrap
    # Variable names: single letters
    bootstrap = _build_bootstrap(b85_blob, key_lua, len(vm_bytes))
    
    return bootstrap


def _build_bootstrap(b85_blob: str, key_lua: str, orig_len: int) -> str:
    """
    Build the tiny bootstrap that:
    1. Decodes base85 → encrypted bytes
    2. RC4 decrypts → original VM code
    3. Uses loadstring to execute
    
    All variable names are single letters.
    loadstring is accessed directly (works in executors).
    """
    # The bootstrap is a self-contained Lua script
    # It decodes the base85 blob, RC4 decrypts it, and executes via loadstring
    
    parts = []
    
    # RC4 decrypt function + base85 decoder + loadstring call
    # All in one compact script with single-letter vars
    
    # Variable assignments
    parts.append('local a,b,c,d,e,f,g,h,i,j,k={},{},{},{},{},{},{},{},{},{},{}')
    
    # Base85 decode function (simplified: all chunks are exactly 5 chars)
    parts.append(
        'local function l(m)'
        'local n=""'
        'for o=1,#m,5 do '
        'local q=m:sub(o,o+4)'
        'local r=0 '
        'for p=1,5 do r=r*85+(q:byte(p)-33) end '
        'for p=1,4 do n=n..string.char(r%256) r=math.floor(r/256) end '
        'end '
        'return n '
        'end'
    )
    
    # RC4 decrypt function (with bit32 fallback)
    parts.append(
        'local function t(u,v)'
        'local w={}'
        'for x=0,255 do w[x]=x end '
        'local y=0 '
        'for x=0,255 do '
        'y=(y+w[x]+v:byte(x%#v+1))%256 '
        'w[x],w[y]=w[y],w[x] '
        'end '
        'local z="" '
        'local x2,y2=0,0 '
        'local bxor=bit32 and bit32.bxor or function(a,b) '
        'local r,c,l=0,1,1 '
        'while a>0 or b>0 do '
        'if (a%2)~=(b%2) then r=r+c end '
        'a,b,c=math.floor(a/2),math.floor(b/2),c*2 '
        'end '
        'return r end '
        'for x=1,#u do '
        'x2=(x2+1)%256 '
        'y2=(y2+w[x2])%256 '
        'w[x2],w[y2]=w[y2],w[x2] '
        'local aa=w[(w[x2]+w[y2])%256] '
        'z=z..string.char(bxor(u:byte(x),aa)) '
        'end '
        'return z '
        'end'
    )
    
    # Decode base85 blob
    parts.append(f'local bb=l([==[{b85_blob}]==])')
    
    # RC4 key
    parts.append(f'local cc=string.char({key_lua})')
    
    # Decrypt
    parts.append(f'local dd=t(bb:sub(1,{orig_len}),cc)')
    
    # Execute via loadstring (try multiple methods for executor compatibility)
    parts.append(
        'local ee=loadstring or load '
        'if ee then ee(dd)() '
        'else '
        'local ff=getfenv and getfenv() or _G '
        'local gg=ff["\\108\\111\\97\\100\\115\\116\\114\\105\\110\\103"] '
        'if gg then gg(dd)() end '
        'end'
    )
    
    # Join everything
    result = ' '.join(parts)
    
    # Minify: remove unnecessary spaces
    result = result.replace('  ', ' ')
    
    return result
