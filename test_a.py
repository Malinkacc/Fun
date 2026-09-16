import sys, random
sys.path.insert(0, '.')
from obfuscator.lexer import Lexer
from obfuscator.parser import Parser
from obfuscator.ast_unparser import unparse
from obfuscator.transformers.string_encryptor import encrypt_strings_in_chunk

code = open('stress_test.lua', 'r', encoding='utf-8').read()
ast = Parser(Lexer(code).tokenize()).parse()
rng = random.Random(42)
ast, dec, _ = encrypt_strings_in_chunk(ast, rng=rng)
out = (dec or '') + '\n' + unparse(ast)
open('test_a.lua', 'w', encoding='utf-8').write(out)
print('OK: test_a.lua created')
