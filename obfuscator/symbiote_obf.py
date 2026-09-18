"""
NZL Studio Obfuscator — VM-Based Obfuscator (Roblox Compatible, No loadstring)

Style: Heavily obfuscated VM runtime + base85 bytecode blob
- VM runtime code is itself obfuscated (encrypted strings, junk, etc.)
- Bytecode encoded as base85 in [=[...]=]
- One continuous massive line
- No loadstring (works in standard Roblox)
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
    """Obfuscate Lua source code using VM approach (no loadstring)."""
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
        
        # Heavy post-processing to make VM runtime unreadable
        output = _heavy_obfuscate_vm(vm_output)
        
        return output
        
    except Exception as e:
        return f'-- Obfuscation failed: {e}\n{source}'


def obfuscate_script(source: str, seed: int = None) -> str:
    if seed is not None:
        random.seed(seed)
    return obfuscate(source)


def _heavy_obfuscate_vm(vm_output: str) -> str:
    """
    Heavily obfuscate the VM runtime code:
    1. Collect all string literals and encrypt them
    2. Add a string decryption function
    3. Replace all string literals with encrypted calls
    4. Rename all variables to short names
    5. Add junk code
    6. Minify to one line
    """
    # Step 1: Remove comments
    lines = []
    for line in vm_output.split('\n'):
        if '--' in line:
            line = line[:line.index('--')]
        lines.append(line.strip())
    code = ' '.join(line for line in lines if line)
    
    # Step 2: Collect all string literals
    str_pattern = r'"((?:\\.|[^"\\])*)"'
    all_strings = re.findall(str_pattern, code)
    
    # Deduplicate and create string table
    unique_strings = list(dict.fromkeys(all_strings))  # Preserve order, dedupe
    
    # Encrypt strings with XOR key
    xor_key = random.randint(1, 254)
    
    def encrypt_string(s: str) -> bytes:
        """Encrypt a string with XOR."""
        result = []
        for ch in s:
            # Handle escape sequences
            if ch == '\\':
                continue  # Skip for now, handle below
            result.append(ord(ch) ^ xor_key)
        return bytes(result)
    
    def decode_lua_escapes(s: str) -> str:
        """Decode Lua escape sequences."""
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
    
    # Build encrypted string table
    # Format: each string is XOR-encrypted and stored as byte sequence
    str_table_entries = []
    for s in unique_strings:
        encrypted = decode_lua_escapes(s)
        # Encode as Lua byte sequence
        byte_seq = ','.join(str(b) for b in encrypted)
        str_table_entries.append(f'string.char({byte_seq})')
    
    # Generate string table variable name
    st_var = 'Q'  # String table
    dec_var = 'R'  # Decrypt function
    key_var = 'S'  # XOR key
    
    # Build string table initialization
    str_table_code = f'local {st_var}={{'
    for i, entry in enumerate(str_table_entries):
        str_table_code += entry
        if i < len(str_table_entries) - 1:
            str_table_code += ','
    str_table_code += '}'
    
    # Build decrypt function (XOR decrypt)
    # The decrypt function takes an index and returns the decrypted string
    decrypt_code = f'local {dec_var}=function(n)local s={st_var}[n]local r={{}}for i=1,#s do r[i]=string.char(bit32.bxor(string.byte(s,i),{xor_key}))end return table.concat(r)end'
    
    # Step 3: Replace string literals with encrypted calls
    # Create a mapping from string to index
    str_to_idx = {s: i+1 for i, s in enumerate(unique_strings)}
    
    def replace_string(match):
        s = match.group(1)
        idx = str_to_idx.get(s)
        if idx is not None:
            return f'{dec_var}({idx})'
        return match.group(0)
    
    code = re.sub(str_pattern, replace_string, code)
    
    # Step 4: Prepend string table and decrypt function
    code = str_table_code + ' ' + decrypt_code + ' ' + code
    
    # Step 5: Convert long escaped strings to base85 blobs
    # Find patterns like "\123\456\789..." that are long (bytecode data)
    long_esc_pattern = r'"((?:\\\d{1,3}){50,})"'
    
    def convert_long_to_base85(match):
        escaped = match.group(1)
        # Decode escape sequences
        decoded = []
        i = 0
        while i < len(escaped):
            if escaped[i] == '\\' and i+1 < len(escaped) and escaped[i+1].isdigit():
                num_str = ''
                j = i + 1
                while j < len(escaped) and j < i + 4 and escaped[j].isdigit():
                    num_str += escaped[j]
                    j += 1
                if num_str:
                    decoded.append(int(num_str))
                    i = j
                    continue
            i += 1
        
        if len(decoded) > 50:
            # Add padding
            target = max(len(decoded), 8000)
            while len(decoded) < target:
                decoded.append(random.randint(0, 255))
            
            b85 = _encode_base85(bytes(decoded))
            return f'[==[{b85}]==]'
        return match.group(0)
    
    code = re.sub(long_esc_pattern, convert_long_to_base85, code)
    
    # Step 6: Rename variables
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
    
    # Map to short names
    letters = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
    var_map = {}
    for i, var in enumerate(user_vars):
        if i < len(letters):
            var_map[var] = letters[i]
        else:
            var_map[var] = letters[i % len(letters)] + str(i // len(letters))
    
    for old, new in var_map.items():
        code = re.sub(rf'\b{re.escape(old)}\b', new, code)
    
    # Step 7: Add junk code
    junk_parts = []
    for _ in range(5):
        jv = ''.join(random.choices('abcdefghij', k=2))
        jn = random.randint(1000, 9999)
        junk_parts.append(f'local {jv}={jn}+{random.randint(1,999)}')
    junk = ' '.join(junk_parts)
    code = junk + ' ' + code
    
    # Step 8: Minify
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
