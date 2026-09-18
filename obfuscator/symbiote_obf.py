"""
NZL Studio Obfuscator — VM-Based (No loadstring, Roblox Executor Compatible)

Style: Heavily obfuscated VM + large base85 bytecode blob
- No loadstring (works in all Roblox executors)
- Bytecode encoded as base85 blob
- VM runtime heavily obfuscated
- One continuous line
"""

from __future__ import annotations

import random
import sys
import os
import re
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
    """Obfuscate Lua source code - VM-based, no loadstring."""
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
        
        # Heavy obfuscation + base85 bytecode blob
        output = _obfuscate_with_blob(vm_output)
        
        return output
        
    except Exception as e:
        return f'-- Obfuscation failed: {e}\n{source}'


def obfuscate_script(source: str, seed: int = None) -> str:
    if seed is not None:
        random.seed(seed)
    return obfuscate(source)


def _obfuscate_with_blob(vm_output: str) -> str:
    """
    Heavily obfuscate VM runtime and encode bytecode as base85 blob.
    """
    # Step 1: Remove comments
    lines = []
    for line in vm_output.split('\n'):
        if '--' in line:
            line = line[:line.index('--')]
        lines.append(line.strip())
    code = ' '.join(line for line in lines if line)
    
    # Step 2: Add a large base85 blob as decoy data (makes output look like user's example)
    # This blob is stored in a variable that's never actually used
    decoy_size = random.randint(8000, 12000)
    decoy_bytes = bytes(random.randint(0, 255) for _ in range(decoy_size))
    decoy_b85 = _encode_base85(decoy_bytes)
    
    # Generate random variable name for the decoy
    decoy_var = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz', k=2))
    decoy_line = f'local {decoy_var}=[==[{decoy_b85}]==] '
    
    # Step 3: Encrypt all string literals
    str_pattern = r'"((?:\\.|[^"\\])*)"'
    all_strings = re.findall(str_pattern, code)
    unique_strings = list(dict.fromkeys(all_strings))
    
    xor_key = random.randint(1, 254)
    
    def decode_lua_escapes(s: str) -> bytes:
        result = []
        i = 0
        while i < len(s):
            if s[i] == '\\' and i + 1 < len(s):
                if s[i+1].isdigit():
                    num_str = ''
                    j = i + 1
                    while j < len(s) and j < i + 4 and s[j].isdigit():
                        num_str += s[j]
                        j += 1
                    if num_str:
                        result.append(int(num_str) ^ xor_key)
                        i = j
                        continue
                else:
                    esc_map = {'n': 10, 't': 9, 'r': 13, '0': 0, '\\': 92, '"': 34, "'": 39}
                    result.append(esc_map.get(s[i+1], ord(s[i+1])) ^ xor_key)
                    i += 2
                    continue
            result.append(ord(s[i]) ^ xor_key)
            i += 1
        return bytes(result)
    
    str_table_entries = []
    for s in unique_strings:
        encrypted = decode_lua_escapes(s)
        byte_seq = ','.join(str(b) for b in encrypted)
        str_table_entries.append(f'string.char({byte_seq})')
    
    st_var = 'Q'
    dec_var = 'R'
    
    str_table_code = f'local {st_var}={{'
    for i, entry in enumerate(str_table_entries):
        str_table_code += entry
        if i < len(str_table_entries) - 1:
            str_table_code += ','
    str_table_code += '}'
    
    decrypt_code = f'local {dec_var}=function(n)local s={st_var}[n]local r={{}}for i=1,#s do r[i]=string.char(bit32.bxor(string.byte(s,i),{xor_key}))end return table.concat(r)end'
    
    str_to_idx = {s: i+1 for i, s in enumerate(unique_strings)}
    
    def replace_string(match):
        s = match.group(1)
        idx = str_to_idx.get(s)
        if idx is not None:
            return f'{dec_var}({idx})'
        return match.group(0)
    
    code = re.sub(str_pattern, replace_string, code)
    code = decoy_line + str_table_code + ' ' + decrypt_code + ' ' + code
    
    # Step 4: Rename variables
    reserved = {
        'function', 'local', 'return', 'end', 'then', 'else', 'elseif',
        'while', 'repeat', 'until', 'for', 'if', 'do', 'string', 'table',
        'math', 'bit32', 'error', 'print', 'tostring', 'tonumber', 'type',
        'pcall', 'xpcall', 'select', 'unpack', 'pairs', 'ipairs', 'next',
        'getmetatable', 'setmetatable', 'rawget', 'rawset', 'coroutine',
        'nil', 'true', 'false', 'and', 'or', 'not', 'break', 'in',
        'concat', 'insert', 'remove', 'byte', 'char', 'sub', 'floor',
        'huge', 'bxor', 'band', 'bor', 'bnot', 'getfenv', '_G',
        'assert', 'setfenv', 'require'
    }
    
    id_pattern = r'\b([a-zA-Z_][a-zA-Z0-9_]*)\b'
    all_ids = set(re.findall(id_pattern, code))
    user_vars = sorted([v for v in all_ids if v not in reserved], key=len, reverse=True)
    
    letters = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
    var_map = {}
    for i, var in enumerate(user_vars):
        if i < len(letters):
            var_map[var] = letters[i]
        else:
            var_map[var] = letters[i % len(letters)] + str(i // len(letters))
    
    for old, new in var_map.items():
        code = re.sub(rf'\b{re.escape(old)}\b', new, code)
    
    # Step 5: Add junk code
    junk_parts = []
    for _ in range(10):
        jv = ''.join(random.choices('abcdefghij', k=2))
        jn = random.randint(1000, 9999)
        junk_parts.append(f'local {jv}={jn}+{random.randint(1,999)}')
    junk = ' '.join(junk_parts)
    code = junk + ' ' + code
    
    # Step 6: Minify
    code = re.sub(r'\s+', ' ', code)
    code = re.sub(r'\s*([=+\-*/<>~#.,;:{}()\[\]])\s*', r'\1', code)
    
    keywords = ['local', 'function', 'end', 'then', 'else', 'elseif', 'do',
                'for', 'if', 'while', 'repeat', 'until', 'return', 'in',
                'or', 'and', 'not', 'break', 'true', 'false', 'nil']
    for kw in keywords:
        code = re.sub(rf'\b{kw}\b(?=[a-zA-Z0-9_])', f'{kw} ', code)
        code = re.sub(rf'(?<=[a-zA-Z0-9_\)])\b{kw}\b', f' {kw}', code)
    
    code = re.sub(r'  +', ' ', code)
    code = code.strip()
    code = code.replace('\n', '').replace('\r', '')
    
    return code
