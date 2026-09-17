import sys, random
sys.path.insert(0, '.')
from obfuscator.lexer import Lexer
from obfuscator.parser import Parser
from obfuscator.ast_unparser import unparse
from obfuscator.transformers.number_obfuscator import obfuscate_numbers_in_chunk

code = open('stress_test.lua', 'r', encoding='utf-8').read()
ast = Parser(Lexer(code).tokenize()).parse()
rng = random.Random(42)
result = obfuscate_numbers_in_chunk(ast, rng=rng)
ast = result[0] if isinstance(result, tuple) else result
out = unparse(ast)
open('test_b.lua', 'w', encoding='utf-8').write(out)
print('OK: test_b.lua created')
