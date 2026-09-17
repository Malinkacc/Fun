import re, sys, os

with open('stress_out.lua', 'r', encoding='utf-8') as f:
    content = f.read()

print('=' * 60)
print('УМНАЯ ПРОВЕРКА obfуcкатора')
print('=' * 60)

# 1. Строки в опасных местах (после =, {, [)
suspicious = []
for m in re.finditer(r'(?:\[|=|\{|,)\s*("[^"]*\\[0-9]{1,3}[^"]*")', content):
    suspicious.append(m.group(1))

if suspicious:
    print(f'\n[!] Найдено {len(suspicious)} строк с \\NNN в подозрительных местах:')
    for s in suspicious[:10]:
        print(f'    {s[:100]}')
else:
    print('\n[OK] Все \\NNN строки — внутри вызовов функций (это норма для RC4)')

# 2. Известные ключи которые НЕ должны быть в открытом виде
print('\n[Проверка утечек ключей и строк]')
known_leaks = [
    'ItemNames', 'MobsTarget', 'AutoFarm', 'Radius', 'Speed',
    'Golden Ring', 'Silver Coin', 'Bronze Jar', 'Kaigaku', 'Akaza',
    'Hello, World', 'HumanoidRootPart',
]
leaks_found = []
for key in known_leaks:
    if f'"{key}"' in content:
        leaks_found.append(key)

if leaks_found:
    print(f'  [!] {len(leaks_found)} строк НЕ зашифрованы (открытым текстом):')
    for k in leaks_found:
        print(f'      "{k}"')
else:
    print('  [OK] Все строки зашифрованы')

# 3. Проверка что код парсится
print('\n[Синтаксическая валидность]')
sys.path.insert(0, os.getcwd())
try:
    from obfuscator.lexer import Lexer
    from obfuscator.parser import Parser
    tokens = Lexer(content).tokenize()
    ast = Parser(tokens).parse()
    print('  [OK] Обфусцированный код парсится обратно')
except Exception as e:
    print(f'  [FAIL] Ошибка: {e}')

# 4. Декриптор
print('\n[Декриптор]')
if 'bit32.bxor' in content or 'bxor' in content:
    print('  [OK] Декриптор с bxor найден')
else:
    print('  [!] Декриптор не найден!')

# 5. Проверка что стандартные Roblox идентификаторы не тронуты
print('\n[Roblox globals]')
must_have = ['game', 'workspace', 'task', 'pairs', 'ipairs', 'print', 'string', 'table']
missing = [g for g in must_have if g not in content]
if missing:
    print(f'  [!] Пропали Roblox globals: {missing}')
else:
    print('  [OK] Все стандартные globals на месте')

print()
print('=' * 60)
