"""
Debug script to test the encryption/decryption pipeline
"""
from obfuscator.symbiote_obf import obfuscate
import base64

def debug_obfuscate(source: str, output_file: str = "/tmp/debug_decrypted.lua"):
    """
    Obfuscate and also save the decrypted VM code for inspection
    """
    # First, let's manually do what obfuscate() does but save intermediate steps
    from obfuscator.lexer import Lexer
    from obfuscator.parser import Parser
    from obfuscator.vm.compiler import compile_function
    from obfuscator.vm.runtime_lua import generate_vm_code
    from obfuscator.symbiote_obf import _rc4, _b85_encode
    
    # Parse and compile
    wrapped = f"local function protectedFn()\n{source}\nend"
    tokens = Lexer(wrapped).tokenize()
    ast = Parser(tokens).parse()
    func = ast.body.statements[0].func
    proto = compile_function(func)
    
    # Generate VM code
    vm_code = generate_vm_code(proto)
    
    # Add the call
    vm_code += "\nprotectedFn()\n"
    
    # Save the VM code before encryption
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(vm_code)
    
    print(f"VM code saved to {output_file}")
    print(f"VM code length: {len(vm_code)} bytes")
    print(f"First 500 chars:\n{vm_code[:500]}")
    print(f"\nLast 500 chars:\n{vm_code[-500:]}")
    
    # Now obfuscate normally
    result = obfuscate(source)
    
    print(f"\nObfuscated output length: {len(result)} bytes")
    print(f"First 300 chars:\n{result[:300]}")
    
    return result

if __name__ == "__main__":
    test_source = """
print("Hello from obfuscated script!")
local x = 42
print("x =", x)
"""
    
    debug_obfuscate(test_source)
