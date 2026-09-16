import sys, random
sys.path.insert(0, '.')
from obfuscator.lexer import Lexer
from obfuscator.parser import Parser
from obfuscator.ast_unparser import unparse
from obfuscator.transformers.string_encryptor import encrypt_strings_in_chunk

code = 'print(\"Hello\")\n'
ast = Parser(Lexer(code).tokenize()).parse()
rng = random.Random(42)
ast, dec, _ = encrypt_strings_in_chunk(ast, rng=rng)
out = (dec or '') + '\n' + unparse(ast)
open('mini.lua', 'w', encoding='utf-8').write(out)
print('OK: mini.lua')
print('=== CONTENT ===')
print(out)
