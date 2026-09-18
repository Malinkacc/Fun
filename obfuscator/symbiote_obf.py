"""
NZL Studio Obfuscator — Symbiote-style Control Flow Flattening

Style:
- return({key=function(_,c)return function()local a=STATE while true do if a<=X then if a<=Y then ...
- Opaque predicates: a = cond and STATE_A or STATE_B  
- Binary/hex literals: 0b10, 0x9a
- Helpers: _.c() pack, _.d() unpack
- Deeply nested if-else state dispatch tree
"""

from __future__ import annotations

import random
import sys
import os
import re
from typing import Dict, List, Optional, Tuple, Any

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from obfuscator.utils.random_gen import make_rng


class SymbioteObfuscator:
    """Symbiote-style control flow flattening obfuscator."""
    
    def __init__(self, seed: Optional[int] = None):
        if seed is None:
            seed = random.randint(0, 2**32 - 1)
        self.seed = seed
        self.rng = make_rng(seed)
    
    def _gen_num(self, value: int) -> str:
        """Generate obfuscated number literal"""
        choice = self.rng.randint(0, 4)
        if choice == 0:
            return f"0x{value:x}"
        elif choice == 1:
            return f"0b{value:b}"
        elif choice == 2:
            return str(value)
        elif choice == 3:
            if value > 0:
                a = self.rng.randint(0, min(value, 999))
                b = value - a
                if b < 0:
                    return f"0x{value:x}"
                return f"{a}+{b}"
            return str(value)
        else:
            if 0 < value < 65536:
                a = self.rng.randint(0, 255)
                b = value ^ a
                return f"bit32.bxor({a},{b})"
            return f"0x{value:x}"
    
    def _alloc_state(self) -> int:
        return self.rng.randint(0x10, 0xFFFF)
    
    def _split_statements(self, code: str) -> List[str]:
        """
        Split Lua code into top-level statements,
        keeping block structures (if/for/while/function/do) intact.
        """
        lines = code.split('\n')
        statements = []
        current_lines = []
        depth = 0
        
        # Keywords that increase depth
        openers = re.compile(r'^\s*(if|for|while|repeat|function|do)\b')
        # Keywords that decrease depth
        closers = re.compile(r'^\s*(end|until)\b')
        # Keywords that are neutral but start new blocks
        mid = re.compile(r'^\s*(else|elseif)\b')
        
        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith('--'):
                continue
            
            # Check if this line closes a block
            if closers.match(stripped):
                depth -= 1
                current_lines.append(line)
                if depth <= 0:
                    depth = 0
                    stmt = '\n'.join(current_lines).strip()
                    if stmt:
                        statements.append(stmt)
                    current_lines = []
                continue
            
            # Check if this line is mid-block (else/elseif)
            if mid.match(stripped) and depth > 0:
                current_lines.append(line)
                continue
            
            # Check if this line opens a block
            if openers.match(stripped):
                if current_lines and depth == 0:
                    stmt = '\n'.join(current_lines).strip()
                    if stmt:
                        statements.append(stmt)
                    current_lines = []
                current_lines.append(line)
                depth += 1
                continue
            
            # Regular statement
            if depth == 0:
                if current_lines:
                    stmt = '\n'.join(current_lines).strip()
                    if stmt:
                        statements.append(stmt)
                    current_lines = []
                current_lines.append(line)
                # Check if complete (doesn't end with continuation)
                if not stripped.endswith((',', 'and', 'or', '..', 'then', 'do')):
                    stmt = '\n'.join(current_lines).strip()
                    if stmt:
                        statements.append(stmt)
                    current_lines = []
            else:
                current_lines.append(line)
        
        if current_lines:
            stmt = '\n'.join(current_lines).strip()
            if stmt:
                statements.append(stmt)
        
        return statements
    
    def _flatten_block(self, statements: List[str], indent: str = "        ") -> str:
        """Flatten statements into a state machine."""
        
        if not statements:
            return f"{indent}return"
        
        n = len(statements)
        states = [self._alloc_state() for _ in range(n + 1)]
        initial = states[0]
        exit_state = states[n]
        
        # Create (state, index) pairs sorted by state value
        indexed = sorted([(states[i], i) for i in range(n)])
        
        # Build the result
        result = f"{indent}local a={self._gen_num(initial)}\n"
        result += f"{indent}while true do\n"
        result += self._build_dispatch_tree(indexed, statements, states, exit_state, indent + "    ")
        result += f"{indent}end"
        
        return result
    
    def _build_dispatch_tree(self, indexed: List[Tuple[int, int]], 
                             statements: List[str], all_states: List[int],
                             exit_state: int, indent: str) -> str:
        """Build binary search tree for state dispatch."""
        
        if not indexed:
            return f"{indent}return\n"
        
        if len(indexed) == 1:
            state_val, stmt_idx = indexed[0]
            stmt = statements[stmt_idx].replace('\n', '\n' + indent + "    ")
            next_state = all_states[stmt_idx + 1] if stmt_idx + 1 < len(all_states) else exit_state
            
            result = f"{indent}if a<={self._gen_num(state_val)} then\n"
            result += f"{indent}    {stmt}\n"
            
            # Opaque transition
            cond_var = f"a"
            junk_state = self._alloc_state()
            result += f"{indent}    a=({cond_var}=={cond_var}) and {self._gen_num(next_state)} or {self._gen_num(junk_state)}\n"
            result += f"{indent}else\n"
            result += f"{indent}    return\n"
            result += f"{indent}end\n"
            return result
        
        mid = len(indexed) // 2
        median_val = indexed[mid][0]
        
        left = indexed[:mid]
        right = indexed[mid:]
        
        result = f"{indent}if a<={self._gen_num(median_val)} then\n"
        result += self._build_dispatch_tree(left, statements, all_states, exit_state, indent + "    ")
        result += f"{indent}else\n"
        result += self._build_dispatch_tree(right, statements, all_states, exit_state, indent + "    ")
        result += f"{indent}end\n"
        
        return result
    
    def _gen_const_table(self) -> str:
        """Generate a decorative constant table like Symbiote uses"""
        entries = []
        for i in range(self.rng.randint(3, 8)):
            dim = self.rng.choice([1, 0b10, 0b11, 0b100, 0b101])
            d1 = self._gen_num(dim)
            d2 = self._gen_num(0b11)
            d3 = self._gen_num(0b10)
            val = self._gen_num(self.rng.randint(1, 100))
            entries.append(f"[{d1}]={{[{d2}]={{[{d3}]={val}}}}}")
        return "local c={" + ",".join(entries) + "}"
    
    def obfuscate_script(self, source: str) -> str:
        """Obfuscate a complete Lua script in Symbiote style."""
        
        # Normalize source
        from obfuscator.lexer import Lexer
        from obfuscator.parser import Parser
        from obfuscator.ast_unparser import unparse
        
        try:
            ast = Parser(Lexer(source).tokenize()).parse()
            clean_code = unparse(ast, minified=False)
        except Exception:
            clean_code = source
        
        # Split into statements
        statements = self._split_statements(clean_code)
        if not statements:
            statements = ["return"]
        
        # Flatten
        flattened = self._flatten_block(statements, "        ")
        
        # Minify the flattened code
        flat_mini = self._minify(flattened)
        
        # Build result (all on minimal lines like Symbiote)
        helpers = self._build_helpers().replace('\n', '')
        const_table = self._gen_const_table()
        
        func_key = ''.join(self.rng.choices('abcdefghijklmnopqrstuvwxyz', k=self.rng.randint(1, 3)))
        
        # Assemble everything compactly
        body = f"return({{{func_key}=function(_,c)return function(){flat_mini}end end,}})"
        
        # Fix merged keywords in body
        for _ in range(5):
            body = body.replace('endend', 'end end')
            body = body.replace('endelse', 'end else')
            body = body.replace('endelseif', 'end elseif')
        
        result = f"-- NZL Studio Obfuscator | discord.gg/c3kBtN9vXb\n"
        result += f"{helpers}\n"
        result += f"{const_table}\n"
        result += f"{body}\n"
        result += f"-- NZL Studio Obfuscator | discord.gg/c3kBtN9vXb"
        
        return result
    
    def _build_helpers(self) -> str:
        return 'local _={};' + \
               '_.c=function(...)return{[1]={...},[0b10]=select("#",...)}end;' + \
               '_.d=function(e,f,...)local h={...}local d=select("#",...)for i=1,d do e[f+i-1]=h[i]end end;' + \
               '_.b=function(e,r,E)return e,r,E end;' + \
               '_.e=function(e,f,...)local h={...}local d=select("#",...)for i=1,d do e[f+i-1]=h[i]end end'
    
    def _minify(self, code: str) -> str:
        """Minify Lua code: remove comments, extra spaces, collapse to compact form"""
        lines = code.split('\n')
        clean = []
        for line in lines:
            s = line.strip()
            if not s:
                continue
            # Remove trailing comments
            in_str = False
            str_char = None
            i = 0
            while i < len(s):
                ch = s[i]
                if in_str:
                    if ch == '\\':
                        i += 2
                        continue
                    if ch == str_char:
                        in_str = False
                else:
                    if ch in ('"', "'"):
                        in_str = True
                        str_char = ch
                    elif ch == '-' and i + 1 < len(s) and s[i + 1] == '-':
                        s = s[:i].rstrip()
                        break
                i += 1
            if s:
                clean.append(s)
        
        # Join with ; separator
        result = ';'.join(clean)
        
        # Normalize spaces around keywords
        for kw in ['local', 'return', 'function', 'end', 'then', 'else', 'elseif',
                    'do', 'if', 'while', 'for', 'and', 'or', 'not', 'in', 'repeat', 'until', 'break']:
            result = re.sub(r'\b' + kw + r'\b', f' {kw} ', result)
        
        # Remove spaces around operators
        result = re.sub(r'\s*([=+\-*/%^#<>~,;{}()\[\]])\s*', r'\1', result)
        
        # Re-add necessary spaces
        # After keywords before expressions
        result = re.sub(r'\b(local)\b', r'\1 ', result)
        result = re.sub(r'\b(return)\b', r'\1 ', result)
        result = re.sub(r'\b(function)\b', r'\1 ', result)
        result = re.sub(r'\b(if)\b', r'\1 ', result)
        result = re.sub(r'\b(while)\b', r'\1 ', result)
        result = re.sub(r'\b(for)\b', r'\1 ', result)
        result = re.sub(r'\b(in)\b', r' \1 ', result)
        result = re.sub(r'\b(do)\b', r' \1 ', result)
        result = re.sub(r'\b(then)\b', r' \1 ', result)
        result = re.sub(r'\b(else)\b', r' \1 ', result)
        result = re.sub(r'\b(and)\b', r' \1 ', result)
        result = re.sub(r'\b(or)\b', r' \1 ', result)
        result = re.sub(r'\b(not)\b', r'\1 ', result)
        result = re.sub(r'\b(end)\b', r' \1 ', result)
        
        # Fix double spaces
        result = re.sub(r'  +', ' ', result)
        # Remove space after ( and before )
        result = result.replace('( ', '(').replace(' )', ')')
        
        # FINAL PASS: fix merged keywords
        for _ in range(3):
            result = result.replace('endend', 'end end')
            result = result.replace('endelse', 'end else')
            result = result.replace('endelseif', 'end elseif')
            result = result.replace('doif', 'do if')
            result = result.replace('thenif', 'then if')
            result = result.replace('thendo', 'then do')
            result = result.replace('elseend', 'else end')
        
        return result.strip()


def obfuscate_script(source: str, seed: Optional[int] = None) -> str:
    """Convenience function"""
    obf = SymbioteObfuscator(seed=seed)
    return obf.obfuscate_script(source)


if __name__ == '__main__':
    if '--test' in sys.argv:
        test_source = '''
local x = 10
local y = 20
local sum = x + y
print("Sum = " .. sum)
for i = 1, 5 do
    print(i)
end
'''
        result = obfuscate_script(test_source, seed=42)
        print(result)
