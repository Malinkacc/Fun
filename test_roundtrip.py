"""
Test the full encryption/decryption roundtrip
"""
import sys
sys.path.insert(0, '/home/user/Fun')

from obfuscator.symbiote_obf import _rc4, _b85_encode
from obfuscator.lexer import Lexer
from obfuscator.parser import Parser
from obfuscator.vm.compiler import compile_function
from obfuscator.vm.runtime_lua import generate_vm_code
import random

def test_roundtrip():
    # Simple test source
    source = 'print("Hello World")'
    
    # Wrap in function
    wrapped = f"local function protectedFn()\n{source}\nend"
    
    # Parse and compile
    tokens = Lexer(wrapped).tokenize()
    ast = Parser(tokens).parse()
    func = ast.body.statements[0].func
    proto = compile_function(func)
    
    # Generate VM code
    vm_code = generate_vm_code(proto)
    vm_code += "\nprotectedFn()\n"
    
    print(f"Original VM code length: {len(vm_code)} bytes")
    print(f"First 200 chars: {vm_code[:200]}")
    print(f"Last 200 chars: {vm_code[-200:]}")
    print()
    
    # Encrypt
    key = bytes([random.randint(1, 254) for _ in range(32)])
    encrypted = _rc4(vm_code.encode('utf-8'), key)
    
    print(f"Encrypted length: {len(encrypted)} bytes")
    print()
    
    # Encode to base85
    b85_blob = _b85_encode(encrypted)
    
    print(f"Base85 blob length: {len(b85_blob)} chars")
    print(f"First 100 chars: {b85_blob[:100]}")
    print()
    
    # Now simulate the Lua decoder
    def lua_b85_decode(s):
        """Simulate the Lua base85 decoder"""
        n = ""
        o = 0
        while o < len(s):
            q = s[o:o+5]
            r = 0
            for p in range(5):
                if p < len(q):
                    r = r * 85 + (ord(q[p]) - 33)
            for p in range(4):
                n += chr(r % 256)
                r = r // 256
            o += 5
        return n
    
    # Decode
    decoded = lua_b85_decode(b85_blob)
    
    print(f"Decoded length: {len(decoded)} bytes")
    print()
    
    # Truncate to original length (like bootstrap does)
    decoded = decoded[:len(encrypted)]
    
    print(f"Truncated to: {len(decoded)} bytes")
    print()
    
    # Decrypt
    decrypted = _rc4(decoded.encode('latin-1'), key)
    
    print(f"Decrypted length: {len(decrypted)} bytes")
    print(f"First 200 chars: {decrypted[:200]}")
    print(f"Last 200 chars: {decrypted[-200:]}")
    print()
    
    # Compare
    if decrypted.decode('utf-8') == vm_code:
        print("✓ Roundtrip successful!")
        return True
    else:
        print("✗ Roundtrip failed!")
        print(f"Original length: {len(vm_code)}")
        print(f"Decrypted length: {len(decrypted)}")
        
        # Find first difference
        orig = vm_code.encode('utf-8')
        for i in range(min(len(orig), len(decrypted))):
            if orig[i] != decrypted[i]:
                print(f"First difference at byte {i}:")
                print(f"  Original: {orig[i]} ({chr(orig[i]) if 32 <= orig[i] < 127 else '?'})")
                print(f"  Decrypted: {decrypted[i]} ({chr(decrypted[i]) if 32 <= decrypted[i] < 127 else '?'})")
                break
        
        return False

if __name__ == "__main__":
    success = test_roundtrip()
    sys.exit(0 if success else 1)
