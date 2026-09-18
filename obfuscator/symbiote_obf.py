"""
NZL Studio Obfuscator — Simple VM (No loadstring, No string tables)

Just minified VM code with renamed variables.
No string encryption, no base85 blobs, no junk.
Works in ALL executors.
"""

from __future__ import annotations

import random
import sys
import os
import re

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)


def obfuscate(source: str) -> str:
    """Obfuscate using VM runtime directly — minimal post-processing."""
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
        
        # Simple post-processing: remove comments, rename vars, minify
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
    """Simple post-processing: remove comments, rename vars, minify."""
    
    # Step 1: Remove comments
    lines = []
    for line in vm_output.split('\n'):
        if '--' in line:
            line = line[:line.index('--')]
        lines.append(line.strip())
    code = ' '.join(line for line in lines if line)
    
    # Step 2: Rename variables
    reserved = {
        'function', 'local', 'return', 'end', 'then', 'else', 'elseif',
        'while', 'repeat', 'until', 'for', 'if', 'do', 'string', 'table',
        'math', 'bit32', 'error', 'print', 'tostring', 'tonumber', 'type',
        'pcall', 'xpcall', 'select', 'unpack', 'pairs', 'ipairs', 'next',
        'getmetatable', 'setmetatable', 'rawget', 'rawset', 'coroutine',
        'nil', 'true', 'false', 'and', 'or', 'not', 'break', 'in',
        'concat', 'insert', 'remove', 'byte', 'char', 'sub', 'floor',
        'huge', 'bxor', 'band', 'bor', 'bnot', 'lshift', 'rshift',
        'lrotate', 'rrotate', 'getfenv', '_G', 'assert', 'setfenv',
        'require', 'protectedFn', 'lrotate', 'rrotate'
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
    
    # Step 3: Minify
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
