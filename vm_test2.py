"""
NZL VM Extended Test — factory wrapper edition
"""

from obfuscator.lexer import Lexer
from obfuscator.parser import Parser
from obfuscator.vm.compiler import compile_function
from obfuscator.vm.runtime_lua import RuntimeGenerator


TEST_CASES = [
    ("simple_return", """
local function fn()
    return 42
end
""", "42"),

    ("arithmetic", """
local function fn()
    return 10 * 5 + 3
end
""", "53"),

    ("if_else", """
local function fn(x)
    if x > 0 then return "positive"
    elseif x < 0 then return "negative"
    else return "zero" end
end
""", "positive"),

    ("while_loop", """
local function fn()
    local sum = 0
    local i = 1
    while i <= 10 do
        sum = sum + i
        i = i + 1
    end
    return sum
end
""", "55"),

    ("numeric_for", """
local function fn()
    local sum = 0
    for i = 1, 100 do
        sum = sum + i
    end
    return sum
end
""", "5050"),

    ("string_concat", """
local function fn(name)
    return "Hello, " .. name .. "!"
end
""", "Hello, World!"),

    ("table_access", """
local function fn()
    local t = {10, 20, 30}
    return t[1] + t[2] + t[3]
end
""", "60"),

    ("nested_function", """
local function fn()
    local function inner(x)
        return x * x
    end
    return inner(7)
end
""", "49"),

    ("recursion", """
local function fn(n)
    if n <= 1 then return 1 end
    return n * fn(n - 1)
end
""", "120"),
]


def _parse_factory_func(src: str):
    original_ast = Parser(Lexer(src).tokenize()).parse()
    if not original_ast.body.statements:
        raise ValueError('Empty source')

    local_fn = original_ast.body.statements[0]
    fn_name = getattr(local_fn, 'name', None)
    if not fn_name:
        raise ValueError('Expected LocalFunctionStat as first statement')

    wrapped_src = f'''
local function __vm_factory__()
{src.strip()}
    return {fn_name}
end
'''
    wrapped_ast = Parser(Lexer(wrapped_src).tokenize()).parse()
    return wrapped_ast.body.statements[0].func


def build_test_script():
    lua_parts = []
    log_lines = []

    for i, (name, src, expected) in enumerate(TEST_CASES):
        try:
            factory_func = _parse_factory_func(src)
            proto = compile_function(factory_func, name=f"{name}_factory")
        except Exception as e:
            print(f"  WARN {name}: compile FAIL -- {e}")
            continue

        gen = RuntimeGenerator(seed=i + 100)
        factory_name = f"vm_{name}_factory"
        vm_name = f"vm_{name}"

        vm_code = gen.generate_vm_wrapper(proto, fn_name=factory_name)
        lua_parts.append(vm_code)
        lua_parts.append(f'local {vm_name} = {factory_name}()')

        if name == "if_else":
            call = f'{vm_name}(5)'
        elif name == "string_concat":
            call = f'{vm_name}("World")'
        elif name == "recursion":
            call = f'{vm_name}(5)'
        else:
            call = f'{vm_name}()'

        lua_parts.append(f'print("[{name}] =", {call})')
        log_lines.append(f"  {name:20s} -> expected: {expected}")

    lua_parts.append('print("=== ALL VM TESTS COMPLETE ===")')

    final = "-- NZL VM Extended Tests\n\n" + "\n\n".join(lua_parts)

    with open("vm_test2.lua", "w", encoding="utf-8") as f:
        f.write(final)

    print(f"OK vm_test2.lua created ({len(final)} chars)")
    print(f"OK {len(TEST_CASES)} tests")
    print()
    print("Expected output:")
    for line in log_lines:
        print(line)
    print()
    print("Copy:")
    print("  Get-Content vm_test2.lua | Set-Clipboard")


if __name__ == "__main__":
    build_test_script()