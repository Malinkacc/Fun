"""
NZL Studio Obfuscator — VM-Based (No loadstring, All Executors)

Uses the existing VM runtime directly. No loadstring, no encryption.
VM runtime is obfuscated (renamed vars, minified).
Works in ALL Roblox executors.
"""

from __future__ import annotations

import random
import sys
import os
import re
import struct
from typing import List

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)


# Base85 alphabet
_B85 = (
    "!\"#$%&'()*+,-./0123456789:;<=>?@"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`"
    "abcdefghijklmnopqrstuvwxyz{|}~"
)


def _b85_encode(data: bytes) -> str:
    """Encode bytes → base85 string (little-endian)."""
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


def obfuscate(source: str) -> str:
    """Obfuscate using VM runtime directly — no loadstring."""
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
        
        # Add the call
        vm_output += '\nprotectedFn()\n'
        
        # Post-process: remove comments, rename vars, minify, add base85 blob
        return _post_process(vm_output)
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return f'-- Error: {e}\n{source}'


def obfuscate_script(source: str, seed: int = None) -> str:
    if seed is not None:
        random.seed(seed)
    return obfuscate(source)


def _post_process(vm_output: str) -> str:
    """Post-process VM output: remove comments, rename vars, minify, add blob."""
    
    # Step 1: Remove comments
    lines = []
    for line in vm_output.split('\n'):
        if '--' in line:
            line = line[:line.index('--')]
        lines.append(line.strip())
    code = ' '.join(line for line in lines if line)
    
    # Step 2: Convert long escaped strings to base85 blobs
    str_pattern = r'"((?:\\.|[^"\\])*)"'
    
    def convert_long(match):
        s = match.group(1)
        if len(s) < 80:
            return match.group(0)
        
        # Decode escape sequences
        decoded = []
        i = 0
        while i < len(s):
            if s[i] == '\\' and i+1 < len(s):
                if s[i+1].isdigit():
                    num_str = ''
                    j = i + 1
                    while j < len(s) and j < i + 4 and s[j].isdigit():
                        num_str += s[j]
                        j += 1
                    if num_str:
                        decoded.append(int(num_str))
                        i = j
                        continue
                else:
                    esc_map = {'n': 10, 't': 9, 'r': 13, '0': 0, '\\': 92, '"': 34, "'": 39}
                    decoded.append(esc_map.get(s[i+1], ord(s[i+1])))
                    i += 2
                    continue
            decoded.append(ord(s[i]))
            i += 1
        
        if len(decoded) > 50:
            # Add padding
            target = max(len(decoded), 8000)
            while len(decoded) < target:
                decoded.append(random.randint(0, 255))
            
            b85 = _b85_encode(bytes(decoded))
            return f'[==[{b85}]==]'
        return match.group(0)
    
    code = re.sub(str_pattern, convert_long, code)
    
    # Step 3: Encrypt short string literals
    all_strings = re.findall(str_pattern, code)
    unique_strings = list(dict.fromkeys(all_strings))
    
    xor_key = random.randint(1, 254)
    
    def encode_str(s):
        result = []
        i = 0
        while i < len(s):
            if s[i] == '\\' and i+1 < len(s):
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
    
    str_entries = []
    for s in unique_strings:
        enc = encode_str(s)
        byte_seq = ','.join(str(b) for b in enc)
        str_entries.append(f'string.char({byte_seq})')
    
    st_var = 'Q'
    dec_var = 'R'
    
    str_table = f'local {st_var}={{'
    for i, e in enumerate(str_entries):
        str_table += e
        if i < len(str_entries) - 1:
            str_table += ','
    str_table += '}'
    
    decrypt_fn = f'local {dec_var}=function(n)local s={st_var}[n]local r={{}}for i=1,#s do r[i]=string.char(bit32.bxor(string.byte(s,i),{xor_key}))end return table.concat(r)end'
    
    str_to_idx = {s: i+1 for i, s in enumerate(unique_strings)}
    
    def replace_str(match):
        s = match.group(1)
        idx = str_to_idx.get(s)
        if idx:
            return f'{dec_var}({idx})'
        return match.group(0)
    
    code = re.sub(str_pattern, replace_str, code)
    code = str_table + ' ' + decrypt_fn + ' ' + code
    
    # Step 4: Add decoy base85 blob
    decoy_size = random.randint(5000, 8000)
    decoy_bytes = bytes(random.randint(0, 255) for _ in range(decoy_size))
    decoy_b85 = _b85_encode(decoy_bytes)
    decoy_var = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz', k=2))
    code = f'local {decoy_var}=[==[{decoy_b85}]==] ' + code
    
    # Step 5: Add junk
    junk = []
    for _ in range(8):
        jv = ''.join(random.choices('abcdefghij', k=2))
        junk.append(f'local {jv}={random.randint(1000,9999)}+{random.randint(1,999)}')
    code = ' '.join(junk) + ' ' + code
    
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
        'assert', 'setfenv', 'require', 'protectedFn'
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
    
    # Step 7: Minify
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
