from obfuscator.lexer import Lexer
from obfuscator.parser import Parser

src = "return 2 + 3 * 4"
tokens = Lexer(src).tokenize()
ast = Parser(tokens).parse()

print(f"AST type: {type(ast).__name__}")
print(f"AST repr: {ast!r}")
print()

# Смотрим что внутри
def walk(node, depth=0):
    indent = "  " * depth
    cls = type(node).__name__
    print(f"{indent}{cls}")
    for attr in dir(node):
        if attr.startswith('_'):
            continue
        val = getattr(node, attr, None)
        if callable(val):
            continue
        if isinstance(val, list):
            print(f"{indent}  .{attr} = [list of {len(val)}]")
            for item in val:
                if hasattr(item, '__class__') and not isinstance(item, (str, int, float, bool)):
                    walk(item, depth + 2)
        elif hasattr(val, '__class__') and not isinstance(val, (str, int, float, bool, type(None))):
            print(f"{indent}  .{attr} =")
            walk(val, depth + 2)
        else:
            print(f"{indent}  .{attr} = {val!r}")

walk(ast)