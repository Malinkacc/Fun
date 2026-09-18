"""
NZL Studio Obfuscator — VM-Based Obfuscator (Roblox Compatible)

Style: Massive base85 blob from start to finish
- Entire VM output encoded as base85
- Tiny obfuscated bootstrap that decodes and executes
- One continuous massive line
- No readable code at the beginning
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


# Base85 alphabet (ASCII printable, safe for Lua long strings)
_B85 = "!\"#$%&'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`abcdefghijklmnopqrstuvwxyz{|}~"


def _encode_base85(data: bytes) -> str:
    """Encode bytes to base85 string (little-endian to match Lua decoder)."""
    result = []
    padding = (4 - len(data) % 4) % 4
    data = data + b'\x00' * padding
    for i in range(0, len(data), 4):
        chunk = struct.unpack('<I', data[i:i+4])[0]  # Little-endian
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
    """
    Obfuscate Lua source code using VM-based approach.
    
    Returns one massive line of obfuscated Lua (Roblox compatible).
    """
    from obfuscator.lexer import Lexer
    from obfuscator.parser import Parser
    from obfuscator.vm.compiler import compile_function
    from obfuscator.vm.runtime_lua import generate_vm_code
    
    # Wrap source in function for compilation
    wrapped = f'local function __main__() {source} end'
    
    try:
        tokens = Lexer(wrapped).tokenize()
        ast = Parser(tokens).parse()
        func_ast = ast.body.statements[0].func
        
        # Compile to bytecode and generate VM wrapper
        proto = compile_function(func_ast)
        seed = random.randint(1, 2**31)
        vm_output = generate_vm_code(proto, seed=seed)
        
        # Encode entire VM output as base85 and wrap with bootstrap
        output = _wrap_with_bootstrap(vm_output)
        
        return output
        
    except Exception as e:
        # Fallback: return source with minimal obfuscation
        return f'-- Obfuscation failed: {e}\n{source}'


def obfuscate_script(source: str, seed: int = None) -> str:
    """
    Main entry point for the obfuscator engine.
    """
    if seed is not None:
        random.seed(seed)
    return obfuscate(source)


def _wrap_with_bootstrap(vm_code: str) -> str:
    """
    Encode entire VM code as base85 and create a tiny bootstrap.
    
    The bootstrap:
    1. Decodes the base85 blob
    2. Constructs loadstring via string.char (hidden)
    3. Executes the decoded code
    """
    # Encode entire VM code as base85
    vm_bytes = vm_code.encode('utf-8')
    b85_blob = _encode_base85(vm_bytes)
    
    # Add padding to make blob larger (match user's example size)
    if len(b85_blob) < 10000:
        padding_size = 10000 - len(b85_blob)
        padding = ''.join(random.choice(_B85) for _ in range(padding_size))
        b85_blob = b85_blob + padding
    
    # Create obfuscated bootstrap
    # Single-letter variables
    v_decode = 'a'
    v_blob = 'b'
    v_result = 'c'
    v_i = 'd'
    v_chunk = 'e'
    v_chars = 'f'
    v_j = 'g'
    v_loadstring = 'h'
    v_code = 'i'
    
    # Build loadstring via string.char to hide it
    # "loadstring" = [108, 111, 97, 100, 115, 116, 114, 105, 110, 103]
    loadstring_chars = ','.join(str(ord(c)) for c in 'loadstring')
    
    # Bootstrap code (minified)
    # Uses while loop to handle variable-length chunks ("z" = 1 char, normal = 5 chars)
    bootstrap = f'''local {v_decode}=function({v_blob})local {v_result}={{}}local {v_i}=1 while {v_i}<=#{v_blob} do if {v_blob}:sub({v_i},{v_i})=="z"then for {v_j}=1,4 do {v_result}[#{v_result}+1]=string.char(0)end {v_i}={v_i}+1 else local {v_chunk}={v_blob}:sub({v_i},{v_i}+4)local {v_chars}=0 for {v_j}=1,5 do {v_chars}={v_chars}*85+(string.byte({v_chunk},{v_j})-33)end for {v_j}=1,4 do {v_result}[#{v_result}+1]=string.char({v_chars}%256){v_chars}=math.floor({v_chars}/256)end {v_i}={v_i}+5 end end return table.concat({v_result})end local {v_loadstring}=string.char({loadstring_chars})local {v_code}={v_decode}([==[{b85_blob}]==])_G[{v_loadstring}]({v_code})()'''
    
    # Minify further - remove all unnecessary spaces
    bootstrap = bootstrap.replace('\n', '').replace('  ', ' ')
    
    return bootstrap
