"""
NZL Studio Obfuscator — VM-Based Obfuscator (Roblox Compatible)

Style: Massive base85 blob, single-letter vars, one continuous line
- Uses existing VM infrastructure for correct bytecode compilation
- Post-processes output to match desired style:
  * Single-letter variables only
  * Dense minified output (one massive line)
  * Base85 encoded bytecode blobs in [=[...]=]
- Roblox compatible (no loadstring, no require)
"""

from __future__ import annotations

import random
import sys
import os
import re
import struct
from typing import Dict, List
from collections import Counter

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)


# Base85 alphabet (ASCII printable, safe for Lua long strings)
_B85 = "!\"#$%&'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`abcdefghijklmnopqrstuvwxyz{|}~"


def _encode_base85(data: bytes) -> str:
    """Encode bytes to base85 string."""
    result = []
    padding = (4 - len(data) % 4) % 4
    data = data + b'\x00' * padding
    for i in range(0, len(data), 4):
        chunk = struct.unpack('>I', data[i:i+4])[0]
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
        
        # Post-process to match desired style
        output = _post_process_vm_output(vm_output)
        
        return output
        
    except Exception as e:
        # Fallback: return source with minimal obfuscation
        return f'-- Obfuscation failed: {e}\n{source}'


def obfuscate_script(source: str, seed: int = None) -> str:
    """
    Main entry point for the obfuscator engine.
    
    Args:
        source: Lua source code to obfuscate
        seed: Random seed (optional)
    
    Returns:
        Obfuscated Lua code as one massive line
    """
    if seed is not None:
        random.seed(seed)
    return obfuscate(source)


def _post_process_vm_output(vm_output: str) -> str:
    """
    Post-process VM output to match desired style:
    - Remove comments
    - Rename variables to single letters
    - Convert bytecode string to base85 in [=[...]=]
    - Minify to one line (dense, no spaces where possible)
    """
    # Step 1: Remove comments
    lines = []
    for line in vm_output.split('\n'):
        if '--' in line:
            line = line[:line.index('--')]
        lines.append(line.strip())
    
    code = ' '.join(line for line in lines if line)
    
    # Step 2: Find and convert bytecode string to base85
    # Pattern: "..." with escape sequences like \123
    bytecode_pattern = r'"((?:\\.|[^"\\])*)"'
    
    def convert_to_base85(match):
        escaped_str = match.group(1)
        # Decode Lua escape sequences
        try:
            # Convert \123 to actual bytes
            decoded = []
            i = 0
            while i < len(escaped_str):
                if escaped_str[i] == '\\' and i+1 < len(escaped_str):
                    if escaped_str[i+1].isdigit():
                        # \123 format
                        num_str = ''
                        j = i + 1
                        while j < len(escaped_str) and j < i + 4 and escaped_str[j].isdigit():
                            num_str += escaped_str[j]
                            j += 1
                        if num_str:
                            decoded.append(int(num_str))
                            i = j
                            continue
                    else:
                        # Other escapes like \n, \t, etc
                        decoded.append(ord(escaped_str[i+1]))
                        i += 2
                        continue
                decoded.append(ord(escaped_str[i]))
                i += 1
            
            # Add entropy padding to make blob larger (like the user's example)
            # Pad to at least 8000 bytes
            target_size = max(len(decoded), 8000)
            if len(decoded) < target_size:
                # Add random padding bytes
                padding = bytes(random.randint(0, 255) for _ in range(target_size - len(decoded)))
                decoded.extend(padding)
            
            # Encode as base85
            b85 = _encode_base85(bytes(decoded))
            return f'[==[{b85}]==]'
        except:
            # If conversion fails, keep original
            return match.group(0)
    
    # Only convert long strings (likely bytecode)
    # Find strings longer than 100 chars
    def selective_convert(match):
        if len(match.group(1)) > 100:
            return convert_to_base85(match)
        return match.group(0)
    
    code = re.sub(bytecode_pattern, selective_convert, code)
    
    # Step 3: Rename ALL variables to single letters
    # Find all identifiers (local variables, function names, etc.)
    # Reserved words that should NOT be renamed
    reserved = {
        'function', 'local', 'return', 'end', 'then', 'else', 'elseif', 
        'while', 'repeat', 'until', 'for', 'if', 'do', 'string', 'table', 
        'math', 'bit32', 'error', 'print', 'tostring', 'tonumber', 'type', 
        'pcall', 'xpcall', 'select', 'unpack', 'pairs', 'ipairs', 'next',
        'getmetatable', 'setmetatable', 'rawget', 'rawset', 'coroutine', 
        'nil', 'true', 'false', 'and', 'or', 'not', 'break', 'in',
        '__main__', '__fn__', 'concat', 'insert', 'remove',
        'byte', 'char', 'sub', 'find', 'match', 'gmatch', 'gsub', 'format',
        'abs', 'floor', 'ceil', 'sqrt', 'min', 'max', 'random', 'huge',
        'bxor', 'band', 'bor', 'bnot', 'lshift', 'rshift', 'lrotate', 'rrotate',
        'assert', 'collectgarbage', 'dofile', 'gcinfo', 'loadfile', 'loadstring',
        'module', 'newproxy', 'rawequal', 'require', 'setfenv', 'getfenv',
        'debug', 'io', 'os', 'package', '_G', '_VERSION', 'arg', 'stdin', 'stdout', 'stderr'
    }
    
    # Find all identifiers
    id_pattern = r'\b([a-zA-Z_][a-zA-Z0-9_]*)\b'
    all_identifiers = set(re.findall(id_pattern, code))
    
    # Filter to only user-defined variables (not reserved, not single letters already)
    user_vars = [v for v in all_identifiers if v not in reserved and len(v) >= 1]
    
    # Sort by frequency (most common first) and then by length
    from collections import Counter
    freq = Counter(re.findall(id_pattern, code))
    user_vars = sorted(user_vars, key=lambda x: (-freq[x], -len(x)))
    
    all_vars = user_vars
    
    # Create mapping to single letters
    single_letters = 'abcdefghijklmnopqrstuvwxyz'
    var_map = {}
    for i, var in enumerate(all_vars):
        if i < len(single_letters):
            var_map[var] = single_letters[i]
        else:
            # Two-letter combinations
            var_map[var] = single_letters[i % len(single_letters)] + single_letters[(i // len(single_letters)) % len(single_letters)]
    
    # Replace variables (longest first to avoid partial replacements)
    for old, new in var_map.items():
        # Use word boundaries to avoid partial replacements
        code = re.sub(rf'\b{re.escape(old)}\b', new, code)
    
    # Step 4: Aggressive minification
    # Remove all newlines and extra spaces
    code = re.sub(r'\s+', ' ', code)
    
    # Remove spaces around most operators
    code = re.sub(r'\s*([=+\-*/<>~#.,;:{}()\[\]])\s*', r'\1', code)
    
    # Keep spaces only where syntactically required
    keywords = ['local', 'function', 'end', 'then', 'else', 'elseif', 'do', 
                'for', 'if', 'while', 'repeat', 'until', 'return', 'in', 
                'or', 'and', 'not', 'break', 'true', 'false', 'nil']
    
    for kw in keywords:
        # Add space after keyword if followed by letter/digit
        code = re.sub(rf'\b{kw}\b(?=[a-zA-Z0-9_])', f'{kw} ', code)
        # Add space before keyword if preceded by letter/digit/closing paren
        code = re.sub(rf'(?<=[a-zA-Z0-9_\)])\b{kw}\b', f' {kw}', code)
    
    # Fix specific patterns
    code = code.replace('function(', 'function(')  # No space before (
    code = code.replace('end)', 'end)')
    code = code.replace('then)', 'then)')
    code = code.replace('do)', 'do)')
    
    # Remove all unnecessary spaces
    code = re.sub(r'  +', ' ', code)
    code = code.strip()
    
    # Step 5: Ensure output is truly one line
    code = code.replace('\n', '').replace('\r', '')
    
    return code
