"""
Generate obfuscated code and also save the decrypted version for inspection
"""
import sys
sys.path.insert(0, '/home/user/Fun')

from obfuscator.engine import Obfuscator

def main():
    obf = Obfuscator(seed=42)
    source = 'print("hello world")'
    
    # Generate obfuscated output
    result = obf.obfuscate(source)
    
    # Save obfuscated output
    with open('/tmp/obfuscated_output.lua', 'w', encoding='utf-8') as f:
        f.write(result)
    
    print(f"Obfuscated output saved to /tmp/obfuscated_output.lua")
    print(f"Length: {len(result)} bytes")
    print(f"First 300 chars:\n{result[:300]}")
    print(f"\nLast 300 chars:\n{result[-300:]}")
    
    # Now let's manually extract and decrypt the blob
    # Find the base85 blob
    blob_start = result.find('[==[') + 4
    blob_end = result.find(']==]')
    b85_blob = result[blob_start:blob_end]
    
    print(f"\n\nBase85 blob length: {len(b85_blob)} chars")
    print(f"First 100 chars: {b85_blob[:100]}")
    
    # Find the RC4 key - it's after "local cc=string.char("
    key_marker = 'local cc=string.char('
    key_start = result.find(key_marker) + len(key_marker)
    key_end = result.find(')', key_start)
    key_str = result[key_start:key_end]
    key_bytes = bytes([int(x.strip()) for x in key_str.split(',')])
    
    print(f"\nRC4 key length: {len(key_bytes)} bytes")
    print(f"RC4 key: {key_bytes.hex()}")
    
    # Find the original length
    len_start = result.find('bb:sub(1,') + 9
    len_end = result.find(')', len_start)
    orig_len = int(result[len_start:len_end])
    
    print(f"\nOriginal length: {orig_len} bytes")
    
    # Decode base85
    from obfuscator.symbiote_obf import _b85_encode
    import struct
    
    def lua_b85_decode(s):
        """Simulate the Lua base85 decoder"""
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
    
    decoded = lua_b85_decode(b85_blob)
    print(f"\nDecoded length: {len(decoded)} bytes")
    
    # Truncate
    decoded = decoded[:orig_len]
    print(f"Truncated to: {len(decoded)} bytes")
    
    # Decrypt
    from obfuscator.symbiote_obf import _rc4
    decrypted = _rc4(decoded.encode('latin-1'), key_bytes)
    
    print(f"\nDecrypted length: {len(decrypted)} bytes")
    print(f"First 500 chars:\n{decrypted[:500].decode('utf-8', errors='replace')}")
    print(f"\nLast 500 chars:\n{decrypted[-500:].decode('utf-8', errors='replace')}")
    
    # Save decrypted version
    with open('/tmp/decrypted_vm.lua', 'wb') as f:
        f.write(decrypted)
    
    print(f"\n\nDecrypted VM code saved to /tmp/decrypted_vm.lua")

if __name__ == "__main__":
    main()
