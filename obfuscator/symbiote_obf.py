"""
NZL Studio Obfuscator — Advanced VM Obfuscator

Style: Luraph/Symbiote hybrid
- Single-letter variables (l,e,d,n,f,t,h,s,r,o,a,c)
- Base85 bytecode encoding in long strings [=[...]=]
- Dense minified output
- Nested junk loops
- Binary/hex state values
"""

from __future__ import annotations

import random
import sys
import os
import struct
import re
from typing import Dict, List, Optional, Tuple, Any

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from obfuscator.utils.random_gen import make_rng


# Base85 alphabet (ASCII printable, no quotes/backslash)
_B85 = "!\"#$%&'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`abcdefghijklmnopqrstuvwxyz{|}~"


def _encode_base85(data: bytes) -> str:
    """Encode bytes to base85 string (Ascii85 variant)."""
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
    # Remove padding chars from last group
    if padding:
        last = result[-1]
        if last == 'z':
            result[-1] = '!!!!!'
        result[-1] = result[-1][:5 - padding]
    return ''.join(result)


class AdvancedObfuscator:
    """Advanced VM-style obfuscator."""

    # Single-letter var pool
    VARS = list('abcdefghijklmnopqrstuvwxyz')

    def __init__(self, seed: Optional[int] = None):
        if seed is None:
            seed = random.randint(0, 2**32 - 1)
        self.seed = seed
        self.rng = make_rng(seed)
        self._vi = 0

    def _v(self) -> str:
        """Next single-letter variable."""
        v = self.VARS[self._vi % len(self.VARS)]
        self._vi += 1
        return v

    def _num(self, n: int) -> str:
        """Obfuscated number literal."""
        c = self.rng.randint(0, 5)
        if c == 0:
            return f"0x{n:x}"
        elif c == 1:
            return f"0b{n:b}"
        elif c == 2 and n > 0:
            a = self.rng.randint(0, min(n, 9999))
            return f"{a}+{n-a}"
        elif c == 3 and 0 < n < 65536:
            a = self.rng.randint(0, 255)
            return f"bit32.bxor({a},{n^a})"
        elif c == 4 and n > 0:
            a = self.rng.randint(n, n + 5000)
            return f"{a}-{a-n}"
        else:
            return str(n)

    def _state(self) -> int:
        return self.rng.randint(0x10, 0xFFFF)

    def _split_stmts(self, code: str) -> List[str]:
        """Split code into top-level statements."""
        lines = code.split('\n')
        stmts = []
        buf = []
        depth = 0
        openers = re.compile(r'^\s*(if|for|while|repeat|function|do)\b')
        closers = re.compile(r'^\s*(end|until)\b')
        mid = re.compile(r'^\s*(else|elseif)\b')

        for line in lines:
            s = line.strip()
            if not s or s.startswith('--'):
                continue
            if closers.match(s):
                depth -= 1
                buf.append(line)
                if depth <= 0:
                    depth = 0
                    stmt = '\n'.join(buf).strip()
                    if stmt:
                        stmts.append(stmt)
                    buf = []
                continue
            if mid.match(s) and depth > 0:
                buf.append(line)
                continue
            if openers.match(s):
                if buf and depth == 0:
                    stmt = '\n'.join(buf).strip()
                    if stmt:
                        stmts.append(stmt)
                    buf = []
                buf.append(line)
                depth += 1
                continue
            if depth == 0:
                if buf:
                    stmt = '\n'.join(buf).strip()
                    if stmt:
                        stmts.append(stmt)
                    buf = []
                buf.append(line)
                if not s.endswith((',', 'and', 'or', '..', 'then', 'do')):
                    stmt = '\n'.join(buf).strip()
                    if stmt:
                        stmts.append(stmt)
                    buf = []
            else:
                buf.append(line)
        if buf:
            stmt = '\n'.join(buf).strip()
            if stmt:
                stmts.append(stmt)
        return stmts

    def _flatten(self, stmts: List[str]) -> str:
        """Flatten statements into nested state machine."""
        if not stmts:
            return "return"

        n = len(stmts)
        states = [self._state() for _ in range(n + 1)]
        init = states[0]
        exit_s = states[n]

        # Sort for binary dispatch tree
        indexed = sorted([(states[i], i) for i in range(n)])

        # Pick var names
        sv = self._v()  # state variable
        nv = self._v()  # next
        ev = self._v()  # temp
        lv = self._v()  # registers table
        tv = self._v()  # dispatch table

        result = f"local {sv},{lv}={self._num(init)},{{}}"
        result += f"\nwhile true do"
        result += self._dispatch(indexed, stmts, states, exit_s, sv, lv, "    ")
        result += f"\nend"
        return result

    def _dispatch(self, indexed, stmts, states, exit_s, sv, lv, ind):
        """Build binary dispatch tree."""
        if not indexed:
            return f"\n{ind}return"

        if len(indexed) == 1:
            sval, si = indexed[0]
            stmt = stmts[si]
            nxt = states[si + 1] if si + 1 < len(states) else exit_s
            junk = self._state()

            r = f"\n{ind}if {sv}<={self._num(sval)} then"
            # Junk loop before real code
            jv = self._v()
            r += f"\n{ind}for {jv}={self._num(self.rng.randint(40,90))},{self._num(self.rng.randint(100,150))} do"
            r += f" if {sv}>{self._num(self._state())} then {sv}={self._num(self._state())};break;end"
            r += f" {lv}[{sv}]={sv};break;end"
            r += f"\n{ind}{stmt}"
            # Opaque transition
            cond = f"{sv}~={self._num(0)}"
            r += f"\n{ind}{sv}={cond} and {self._num(nxt)} or {self._num(junk)}"
            r += f"\n{ind}else"
            r += f"\n{ind}return"
            r += f"\n{ind}end"
            return r

        mid = len(indexed) // 2
        median = indexed[mid][0]

        r = f"\n{ind}if {sv}<={self._num(median)} then"
        r += self._dispatch(indexed[:mid], stmts, states, exit_s, sv, lv, ind + "    ")
        r += f"\n{ind}else"
        r += self._dispatch(indexed[mid:], stmts, states, exit_s, sv, lv, ind + "    ")
        r += f"\n{ind}end"
        return r

    def _minify(self, code: str) -> str:
        """Aggressive minification."""
        lines = code.split('\n')
        clean = []
        for line in lines:
            s = line.strip()
            if not s:
                continue
            # Strip comments
            in_str = False
            sc = None
            i = 0
            while i < len(s):
                ch = s[i]
                if in_str:
                    if ch == '\\':
                        i += 2
                        continue
                    if ch == sc:
                        in_str = False
                else:
                    if ch in ('"', "'"):
                        in_str = True
                        sc = ch
                    elif ch == '-' and i + 1 < len(s) and s[i+1] == '-':
                        s = s[:i].rstrip()
                        break
                i += 1
            if s:
                clean.append(s)

        r = ';'.join(clean)

        # Add spaces around keywords
        for kw in ['local', 'return', 'function', 'end', 'then', 'else', 'elseif',
                    'do', 'if', 'while', 'for', 'and', 'or', 'not', 'in', 'repeat',
                    'until', 'break']:
            r = re.sub(r'\b' + kw + r'\b', f' {kw} ', r)

        # Remove spaces around operators
        r = re.sub(r'\s*([=+\-*/%^#<>~,;{}()\[\].])\s*', r'\1', r)

        # Re-add needed spaces
        for kw in ['local', 'return', 'function', 'if', 'while', 'for', 'in',
                    'do', 'then', 'else', 'and', 'or', 'not', 'end']:
            r = re.sub(r'\b(' + kw + r')\b', r' \1 ', r)

        # Fix merged keywords
        for _ in range(5):
            r = r.replace('endend', 'end end')
            r = r.replace('endelse', 'end else')
            r = r.replace('endelseif', 'end elseif')
            r = r.replace('doif', 'do if')
            r = r.replace('thenif', 'then if')
            r = r.replace('thendo', 'then do')
            r = r.replace('elseend', 'else end')

        r = re.sub(r'  +', ' ', r)
        r = r.replace('( ', '(').replace(' )', ')')
        return r.strip()

    def obfuscate(self, source: str) -> str:
        """Main entry: obfuscate Lua source code."""
        from obfuscator.lexer import Lexer
        from obfuscator.parser import Parser
        from obfuscator.ast_unparser import unparse

        try:
            ast = Parser(Lexer(source).tokenize()).parse()
            code = unparse(ast, minified=False)
        except Exception:
            code = source

        stmts = self._split_stmts(code)
        if not stmts:
            stmts = ["return"]

        flattened = self._flatten(stmts)
        mini = self._minify(flattened)

        # Build helpers (single-letter style)
        h = self._build_helpers()

        # Build bytecode blob (base85 in long string)
        blob = self._build_bytecode_blob(source)

        # Assemble
        body = f"return(function(){h}\n{blob}\n{mini}\nend)()"

        # Fix merged keywords in final body
        for _ in range(5):
            body = body.replace('endend', 'end end')
            body = body.replace('endelse', 'end else')

        return f"-- NZL Studio | discord.gg/c3kBtN9vXb\n{body}\n-- NZL Studio | discord.gg/c3kBtN9vXb"

    def _build_helpers(self) -> str:
        """Build single-letter helper functions."""
        return (
            'local l,e,d,a,c={},{},function(...)return{[1]={...},[0b10]=select("#",...)}end,'
            'function(e,f,...)local h={...}local d=select("#",...)for i=1,d do e[f+i-1]=h[i]end end,'
            'function(e,r,E)return e,r,E end;'
        )

    def _build_bytecode_blob(self, source: str) -> str:
        """Build encrypted bytecode blob in base85 long string."""
        # Encode source as "bytecode" (simplified: just the source bytes)
        raw = source.encode('utf-8')
        b85 = _encode_base85(raw)

        # Split into chunks for readability
        chunk_size = 80
        chunks = [b85[i:i+chunk_size] for i in range(0, len(b85), chunk_size)]
        blob_str = '\\\n'.join(chunks)

        return f"local n=[==[{blob_str}]==]"


def obfuscate_script(source: str, seed: Optional[int] = None) -> str:
    """Convenience function."""
    obf = AdvancedObfuscator(seed=seed)
    return obf.obfuscate(source)


if __name__ == '__main__':
    if '--test' in sys.argv:
        test = '''
local x = 10
local y = 20
local sum = x + y
print("Sum = " .. sum)
for i = 1, 5 do
    print(i)
end
'''
        result = obfuscate_script(test, seed=42)
        print(result[:1500])
        print(f"\n... total {len(result)} chars")
