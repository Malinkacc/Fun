"""
NZL Studio Obfuscator — Luraph VM Test Suite

Тесты для Luraph-style VM обфускации.
"""

import sys
import os
import re

# Bootstrap для запуска как `py test_luraph_vm.py --test`
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from obfuscator.luraph_vm import LuraphVMObfuscator, obfuscate_script


def _test():
    passed = 0
    failed = 0

    def ok(label):
        nonlocal passed
        passed += 1
        print(f'  [OK] {label}')

    def fail(label, detail=''):
        nonlocal failed
        failed += 1
        print(f'  [XX] {label}' + (f' -- {detail}' if detail else ''))

    def check(label, cond, detail=''):
        if cond:
            ok(label)
        else:
            fail(label, detail)

    print('\n' + '=' * 60)
    print('  NZL Luraph VM Obfuscator -- Tests')
    print('=' * 60)

    # T1: Basic obfuscation
    print('\n[T1] Basic obfuscation')
    source = 'local x = 10\nprint(x)'
    result = obfuscate_script(source, seed=42)
    check('T1a: non-empty result', len(result) > 100)
    check('T1b: starts with branding', result.startswith('-- NZL Studio'))
    check('T1c: ends with branding', result.rstrip().endswith('discord.gg/c3kBtN9vXb'))
    check('T1d: contains v0 prelude', 'local v0=' in result)

    # T2: Variable naming v0..vN
    print('\n[T2] Variable naming')
    vars_found = set(re.findall(r'\bv(\d+)\b', result))
    max_var = max(int(v) for v in vars_found)
    check('T2a: uses v-numbering', max_var > 50, f'max=v{max_var}')
    check('T2b: no readable names in body', 
          'string_byte' not in result and 'string_byte' not in result,
          'found readable names')

    # T3: Structure verification
    print('\n[T3] Structure verification')
    check('T3a: contains encrypted bytecode', '\\\\' in result or '\\1' in result)
    check('T3b: contains while true do', 'while true do' in result)
    check('T3c: contains flattened dispatch', result.count('if ') > 30)
    check('T3d: contains bit32.bxor', 'bit32.bxor' in result)
    check('T3e: contains string.byte', 'string.byte' in result)

    # T4: Polymorphism
    print('\n[T4] Polymorphism')
    r1 = obfuscate_script(source, seed=1)
    r2 = obfuscate_script(source, seed=2)
    r3 = obfuscate_script(source, seed=1)
    check('T4a: different seeds -> different code', r1 != r2)
    check('T4b: same seed -> same code', r1 == r3)

    # T5: Complex script
    print('\n[T5] Complex script')
    complex_source = '''
local function add(a, b)
    return a + b
end

local function factorial(n)
    if n <= 1 then return 1 end
    return n * factorial(n - 1)
end

local result = add(10, 20)
print("Result: " .. result)
print("Factorial: " .. factorial(5))
'''
    result = obfuscate_script(complex_source, seed=100)
    check('T5a: complex script ok', len(result) > 500)
    check('T5b: contains VM call', '(...)' in result)

    # T6: No comments in output (except branding)
    print('\n[T6] No readable comments')
    lines = result.split('\n')
    comment_lines = [l for l in lines if l.strip().startswith('--') and 'NZL Studio' not in l and 'discord.gg' not in l]
    check('T6a: no extra comments', len(comment_lines) == 0, f'found {len(comment_lines)}')

    # T7: Discord branding
    print('\n[T7] Branding')
    check('T7a: contains discord link', 'discord.gg/c3kBtN9vXb' in result)
    check('T7b: contains NZL Studio', 'NZL Studio' in result)

    # T8: Engine integration
    print('\n[T8] Engine integration (insane level)')
    from obfuscator.engine import Obfuscator
    obf = Obfuscator(seed=42, verbose=False)
    engine_result = obf.obfuscate(source, level='insane')
    check('T8a: engine insane uses LuraphVM', 'LuraphVM' in [s[0] for s in obf.stats['stages']])
    check('T8b: engine insane output valid', len(engine_result) > 100)
    check('T8c: engine insane has v0', 'local v0=' in engine_result)

    # T9: LuraphVMObfuscator direct
    print('\n[T9] Direct LuraphVMObfuscator')
    from obfuscator.lexer import Lexer
    from obfuscator.parser import Parser
    from obfuscator.ast_nodes import FunctionExpr
    
    fn_source = 'local function test(x) return x * 2 end'
    ast = Parser(Lexer(fn_source).tokenize()).parse()
    func = ast.body.statements[0].func
    
    luraph = LuraphVMObfuscator(seed=999)
    fn_result = luraph.obfuscate(func, 'test')
    check('T9a: function obfuscation ok', len(fn_result) > 100)
    check('T9b: returns function', 'return v' in fn_result)

    # T10: Junk branches
    print('\n[T10] Junk branches and obfuscation')
    check('T10a: contains obfuscated numbers', '(+' in result or '(-' in result or 'bxor' in result)
    check('T10b: dispatch has many branches', result.count('if ') > 50)

    total = passed + failed
    print('\n' + '=' * 60)
    print(f'  Result: {passed}/{total} passed', end='')
    if failed == 0:
        print(' -- ALL GREEN')
    else:
        print(f' ({failed} failed)')
    print('=' * 60)

    return failed == 0


if __name__ == '__main__':
    if '--test' in sys.argv:
        success = _test()
        sys.exit(0 if success else 1)
    else:
        print('Usage: python test_luraph_vm.py --test')
