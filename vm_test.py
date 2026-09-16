"""
NZL VM Real-World Test
Компилирует Lua функцию в VM и генерирует полный тестовый скрипт для Roblox.

Ожидаемый вывод в Potassium:
    add(2, 3) = 5
    add(10, 20) = 30
    add(-5, 15) = 10
"""

from obfuscator.lexer import Lexer
from obfuscator.parser import Parser
from obfuscator.vm.compiler import compile_function
from obfuscator.vm.runtime_lua import RuntimeGenerator


def main():
    # Простейшая функция для теста
    source = """
local function add(a, b)
    return a + b
end
"""
    
    print("=" * 60)
    print("NZL VM Real-World Test")
    print("=" * 60)
    print(f"\n📄 Исходный код:\n{source}")
    
    # Парсим
    ast = Parser(Lexer(source).tokenize()).parse()
    
    # Достаём FunctionExpr из LocalFunctionStat
    local_fn_stat = ast.body.statements[0]
    func_expr = local_fn_stat.func
    fn_name = local_fn_stat.name
    
    # Компилируем в bytecode
    proto = compile_function(func_expr, name=fn_name)
    
    print(f"📦 Скомпилировано в {len(proto.code)} инструкций")
    print(f"📦 Констант: {len(proto.constants)}")
    print(f"📦 max_stack: {proto.max_stack}")
    print()
    print("Bytecode dump:")
    print(proto.dump())
    
    # Генерируем Lua VM
    gen = RuntimeGenerator(seed=42)
    vm_code = gen.generate_vm_wrapper(proto, fn_name='vmAdd')
    
    # Финальный скрипт для Potassium
    final_lua = f"""-- NZL VM Test
{vm_code}

-- Вызываем VM-функцию
print("VM add(2, 3) =", vmAdd(2, 3))
print("VM add(10, 20) =", vmAdd(10, 20))
print("VM add(-5, 15) =", vmAdd(-5, 15))
print("Test complete!")
"""
    
    # Сохраняем
    with open('vm_test.lua', 'w', encoding='utf-8') as f:
        f.write(final_lua)
    
    print()
    print("=" * 60)
    print(f"✅ vm_test.lua создан ({len(final_lua)} символов)")
    print("=" * 60)
    print()
    print("Скопируй в Potassium:")
    print("  Get-Content vm_test.lua | Set-Clipboard")
    print()
    print("Ожидаемый вывод:")
    print("  VM add(2, 3) = 5")
    print("  VM add(10, 20) = 30")
    print("  VM add(-5, 15) = 10")
    print("  Test complete!")


if __name__ == "__main__":
    main()