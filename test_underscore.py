"""
Test that underscore character survives the full encryption pipeline
"""
import sys
sys.path.insert(0, '/home/user/Fun')

from obfuscator.symbiote_obf import _rc4, _b85_encode

def test_underscore():
    # Test with a string containing underscore
    test_str = "local _0xABC_test = string.byte"
    test_bytes = test_str.encode('utf-8')
    
    print(f"Original: {test_str}")
    print(f"Original bytes: {test_bytes}")
    print(f"Underscore positions: {[i for i, b in enumerate(test_bytes) if b == 95]}")
    print()
    
    # RC4 encrypt
    key = b"testkey123456789"
    encrypted = _rc4(test_bytes, key)
    
    print(f"Encrypted bytes: {encrypted}")
    print(f"Encrypted length: {len(encrypted)}")
    print()
    
    # Base85 encode
    b85 = _b85_encode(encrypted)
    
    print(f"Base85: {b85}")
    print(f"Base85 length: {len(b85)}")
    print()
    
    # Simulate Lua decoder
    def lua_b85_decode(s):
        n = ""
        for o in range(0, len(s), 5):
            q = s[o:o+5]
            r = 0
            for p in range(5):
                if p < len(q):
                    r = r * 85 + (ord(q[p]) - 33)
            for p in range(4):
                n += chr(r % 256)
                r = r // 256
        return n
    
    decoded = lua_b85_decode(b85)
    
    print(f"Decoded (as string): {decoded[:len(test_str)]}")
    print(f"Decoded bytes: {decoded[:len(test_str)].encode('latin-1')}")
    print()
    
    # RC4 decrypt
    decrypted = _rc4(decoded[:len(test_str)].encode('latin-1'), key)
    
    print(f"Decrypted: {decrypted.decode('utf-8')}")
    print(f"Decrypted bytes: {decrypted}")
    print()
    
    # Check
    if decrypted == test_bytes:
        print("✓ Underscore survived!")
        return True
    else:
        print("✗ Underscore corrupted!")
        print(f"Expected: {test_bytes}")
        print(f"Got:      {decrypted}")
        
        # Find differences
        for i in range(min(len(test_bytes), len(decrypted))):
            if test_bytes[i] != decrypted[i]:
                print(f"Difference at byte {i}:")
                print(f"  Expected: {test_bytes[i]} ({chr(test_bytes[i]) if 32 <= test_bytes[i] < 127 else '?'})")
                print(f"  Got:      {decrypted[i]} ({chr(decrypted[i]) if 32 <= decrypted[i] < 127 else '?'})")
        return False

if __name__ == "__main__":
    success = test_underscore()
    sys.exit(0 if success else 1)
