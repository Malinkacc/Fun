from obfuscator.lexer import Lexer
from obfuscator.parser import Parser
from obfuscator.vm.compiler import compile_function
from obfuscator.vm.runtime_lua import RuntimeGenerator

src = '''
local function __vm_factory__()
    local function fn(n)
        if n <= 1 then return 1 end
        return n * fn(n - 1)
    end
    return fn
end
'''

ast = Parser(Lexer(src).tokenize()).parse()
factory = ast.body.statements[0].func
proto = compile_function(factory, 'factory')

gen = RuntimeGenerator(seed=42)
vm_code = gen.generate_vm_wrapper(proto, fn_name='vm_factory')

final = vm_code + '''

print("[DEBUG] type of vm_factory:", type(vm_factory))
local fn = vm_factory()
print("[DEBUG] type of fn:", type(fn))

print("[DEBUG] fn(1) =", fn(1))
print("[DEBUG] fn(2) =", fn(2))
print("[DEBUG] fn(3) =", fn(3))
'''

with open('mini_rec.lua', 'w', encoding='utf-8') as f:
    f.write(final)

print("mini_rec.lua created")