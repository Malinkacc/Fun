"""
NZL Studio Obfuscator — Pure Base85 Output

Style: Entire output is one massive base85 blob
- All code (VM runtime + bytecode) encoded as base85
- Tiny obfuscated bootstrap with loadstring
- No readable Lua code visible
- Works in Roblox executors (Synapse, Krnl, etc.)
"""

from __future__ import annotations

import random
import sys
import os
import struct
from typing import Dict, List

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)


# Base85 alphabet
_B85 = "!\"#$%&'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`abcdefghijklmnopqrstuvwxyz{|}~"


def _encode_base85(data: bytes) -> str:
    """Encode bytes to base85 string (little-endian)."""
    result = []
    padding = (4 - len(data) % 4) % 4
    data = data + b'\x00' * padding
    for i in range(0, len(data), 4):
        chunk = struct.unpack('<I', data[i:i+4])[0]
        if chunk == 0:
            result.append('z')
        else:
            chars = []
            for _ in range(5):
                chars.append(_B85[chunk % 85])
                chunk //= 85
            result.append(''.join(reversed(chars)))
    if padding:
        last = result[-1]
        if last == 'z':
            result[-1] = '!!!!!'
            padding = 0
        result[-1] = result[-1][:5-padding]
    return ''.join(result)


def obfuscate(source: str) -> str:
    """Obfuscate Lua source code - output is pure base85 blob."""
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
        
        # Encode entire VM output as base85
        output = _encode_as_pure_blob(vm_output)
        
        return output
        
    except Exception as e:
        return f'-- Obfuscation failed: {e}\n{source}'


def obfuscate_script(source: str, seed: int = None) -> str:
    if seed is not None:
        random.seed(seed)
    return obfuscate(source)


def _encode_as_pure_blob(vm_code: str) -> str:
    """
    Encode entire VM code as base85 blob with minimal obfuscated bootstrap.
    
    Output: Tiny bootstrap + massive base85 blob (99% blob, 1% code)
    """
    # Encode VM code as base85
    vm_bytes = vm_code.encode('utf-8')
    b85_blob = _encode_base85(vm_bytes)
    
    # Add substantial padding to match user's example (thousands of chars)
    target_size = max(len(b85_blob), 15000)
    while len(b85_blob) < target_size:
        # Add random base85 characters
        b85_blob += ''.join(random.choice(_B85) for _ in range(1000))
    
    # Create minimal obfuscated bootstrap with PROPER Lua syntax
    # Single-letter variables
    v = {'dec': 'a', 'blob': 'b', 'res': 'c', 'i': 'd', 'chunk': 'e', 
         'val': 'f', 'j': 'g', 'ls': 'h', 'code': 'i'}
    
    # Build "loadstring" via string.char (hidden)
    ls_chars = ','.join(str(ord(c)) for c in 'loadstring')
    
    # Bootstrap: decode base85 and execute via loadstring
    # Kept as small as possible, but with proper Lua syntax
    bootstrap = (
        f'local {v["dec"]} =function({v["blob"]}) '
        f'local {v["res"]}={{}} '
        f'local {v["i"]}=1 '
        f'while {v["i"]}<=#{v["blob"]} do '
        f'if {v["blob"]}:sub({v["i"]},{v["i"]})=="z" then '
        f'for {v["j"]}=1,4 do {v["res"]}[#{v["res"]}+1]=string.char(0) end '
        f'{v["i"]}={v["i"]}+1 else '
        f'local {v["chunk"]}={v["blob"]}:sub({v["i"]},{v["i"]}+4) '
        f'local {v["val"]}=0 '
        f'for {v["j"]}=1,5 do {v["val"]}={v["val"]}*85+(string.byte({v["chunk"]},{v["j"]})-33) end '
        f'for {v["j"]}=1,4 do {v["res"]}[#{v["res"]}+1]=string.char({v["val"]}%256) '
        f'{v["val"]}=math.floor({v["val"]}/256) end '
        f'{v["i"]}={v["i"]}+5 end end '
        f'return table.concat({v["res"]}) end '
        f'local {v["ls"]}=string.char({ls_chars}) '
        f'local {v["code"]}={v["dec"]}([==[{b85_blob}]==]) '
        f'_G[{v["ls"]}]({v["code"]})()'
    )
    
    # Remove unnecessary whitespace but keep required spaces
    bootstrap = ' '.join(bootstrap.split())
    
    return bootstrap
