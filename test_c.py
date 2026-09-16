import sys
sys.path.insert(0, '.')
from obfuscator.lexer import Lexer
from obfuscator.parser import Parser
from obfuscator.ast_unparser import unparse
from obfuscator.transformers.variable_renamer import VariableRenamer

code = open('stress_test.lua', 'r', encoding='utf-8').read()
ast = Parser(Lexer(code).tokenize()).parse()
VariableRenamer(seed=42).transform(ast)
out = unparse(ast)
open('test_c.lua', 'w', encoding='utf-8').write(out)
print('OK: test_c.lua created')
