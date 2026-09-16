# obfuscator/transformers/vm_protection.py
"""
NZL Studio Obfuscator — VM Protection Transformer (v3)

Ищет функции с маркером -- @vm и компилирует их в VM bytecode.

Как это работает:
1. Препроцессинг исходника (regex): -- @vm перед функцией
   → вставляется валидный вызов-маркер _NZL_VM_MARK_()
2. Парсер сохраняет вызов-маркер как CallStat
3. Трансформер ищет CallStat с именем _NZL_VM_MARK_ и помечает СЛЕДУЮЩИЙ стейтмент
4. Помеченные функции компилируются в VM через factory wrapper
5. Маркеры удаляются

Пример использования:
    local function myFn(x) -- @vm
        return x * 2
    end
"""

from __future__ import annotations

import re
import sys
import os
import random
import traceback
from typing import List, Optional, Tuple, Set, Dict

root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if root not in sys.path:
    sys.path.insert(0, root)

from obfuscator.ast_nodes import (
    Node, Chunk, Block, Stat, Expr,
    LocalFunctionStat, FunctionDeclStat, LocalAssignStat, AssignStat,
    FunctionExpr, NameExpr, CallExpr, IndexExpr,
    NumberLit, StringLit, NilLit, BoolLit,
    ReturnStat, CallStat,
)
from obfuscator.ast_unparser import unparse
from obfuscator.lexer import Lexer
from obfuscator.parser import Parser
from obfuscator.utils.random_gen import make_rng, NameGenerator
from obfuscator.vm.compiler import Compiler, can_compile
from obfuscator.vm.runtime_lua import RuntimeGenerator


# ══════════════════════════════════════════════════════════════════
#  МАРКЕР
# ══════════════════════════════════════════════════════════════════

VM_MARKER_COMMENT = '@vm'
VM_MARKER_CALL_NAME = '_NZL_VM_MARK_'

_DEBUG = False


# ══════════════════════════════════════════════════════════════════
#  ПРЕПРОЦЕССИНГ ИСХОДНИКА
# ══════════════════════════════════════════════════════════════════

# Ищем строки, содержащие -- @vm
# и вставляем ПЕРЕД ними _NZL_VM_MARK_()
# Комментарий -- @vm может быть:
#   1. На отдельной строке
#   2. В конце строки с функцией (inline)
#
# Regex подход:
# - inline:  "local function foo(...) -- @vm"
#   → вставляем маркер ПЕРЕД этой строкой
# - standalone: "-- @vm\nlocal function foo"
#   → заменяем "-- @vm" на "_NZL_VM_MARK_()"

_RE_INLINE_MARKER = re.compile(
    r'^([ \t]*)(local\s+function|function)\b(.*?)(--[ \t]*@vm.*)$',
    re.MULTILINE,
)

_RE_STANDALONE_MARKER = re.compile(
    r'^([ \t]*)--[ \t]*@vm[^\n]*$',
    re.MULTILINE,
)


def preprocess_source(source: str) -> str:
    """
    Вставляет _NZL_VM_MARK_() перед функциями с маркером @vm.
    """
    # Шаг 1: inline маркеры → вставляем маркер ПЕРЕД строкой
    def _inline_repl(m: re.Match) -> str:
        indent = m.group(1)
        fn_keyword = m.group(2)
        fn_rest = m.group(3)
        # Убираем комментарий с той же строки
        return f'{indent}{VM_MARKER_CALL_NAME}()\n{indent}{fn_keyword}{fn_rest}'

    source = _RE_INLINE_MARKER.sub(_inline_repl, source)

    # Шаг 2: standalone маркеры → заменяем на вызов
    def _standalone_repl(m: re.Match) -> str:
        indent = m.group(1)
        return f'{indent}{VM_MARKER_CALL_NAME}()'

    source = _RE_STANDALONE_MARKER.sub(_standalone_repl, source)

    return source


# ══════════════════════════════════════════════════════════════════
#  ПРОВЕРКА МАРКЕРА В AST
# ══════════════════════════════════════════════════════════════════

def _is_vm_marker_stat(stat: Stat) -> bool:
    """
    Проверяет, является ли стейтмент вызовом _NZL_VM_MARK_().
    Может быть CallStat или ExprStat/иначе — зависит от парсера.
    """
    if isinstance(stat, CallStat):
        call = stat.call if hasattr(stat, 'call') else stat
        # CallStat.call — CallExpr
        expr = getattr(stat, 'call', None) or getattr(stat, 'expr', None)
        if expr is None:
            # Возможно, CallStat напрямую содержит func/args
            func = getattr(stat, 'func', None)
        else:
            func = getattr(expr, 'func', None)

        if isinstance(func, NameExpr) and func.name == VM_MARKER_CALL_NAME:
            return True

    # Универсальный обход
    if hasattr(stat, '__dataclass_fields__'):
        for fname in stat.__dataclass_fields__:
            val = getattr(stat, fname, None)
            if isinstance(val, CallExpr):
                if isinstance(val.func, NameExpr) and val.func.name == VM_MARKER_CALL_NAME:
                    return True

    return False


# ══════════════════════════════════════════════════════════════════
#  ИМЕНА / ТЕЛА ФУНКЦИЙ
# ══════════════════════════════════════════════════════════════════

def _get_func_name(stat: Stat) -> Optional[str]:
    if isinstance(stat, LocalFunctionStat):
        return stat.name
    if isinstance(stat, FunctionDeclStat):
        target = stat.target
        if isinstance(target, str):
            return target
        if isinstance(target, NameExpr):
            return target.name
        return None
    return None


def _get_func_expr(stat: Stat) -> Optional[FunctionExpr]:
    if isinstance(stat, (LocalFunctionStat, FunctionDeclStat)):
        return stat.func
    return None


# ══════════════════════════════════════════════════════════════════
#  FACTORY WRAPPER
# ══════════════════════════════════════════════════════════════════

def _wrap_in_factory_source(fn_name: str, func_expr: FunctionExpr) -> str:
    tmp_stat = LocalFunctionStat(
        name=fn_name,
        func=func_expr,
        line=getattr(func_expr, 'line', 0),
    )
    tmp_block = Block(statements=[tmp_stat], return_stat=None, line=0)
    tmp_chunk = Chunk(body=tmp_block, line=0)

    inner_src = unparse(tmp_chunk, minified=False)

    return (
        f"local function __nzl_tmp_factory__()\n"
        f"{inner_src}\n"
        f"return {fn_name}\n"
        f"end\n"
    )


# ══════════════════════════════════════════════════════════════════
#  КОМПИЛЯЦИЯ
# ══════════════════════════════════════════════════════════════════

def _compile_function_to_vm(
    fn_name: str,
    func_expr: FunctionExpr,
    factory_lua_name: str,
    rng: random.Random,
) -> Tuple[Optional[str], str]:
    try:
        factory_src = _wrap_in_factory_source(fn_name, func_expr)
        tokens = Lexer(factory_src).tokenize()
        factory_ast = Parser(tokens).parse()

        if not factory_ast.body.statements:
            return None, "empty factory AST"

        factory_stat = factory_ast.body.statements[0]
        if not isinstance(factory_stat, LocalFunctionStat):
            return None, f"factory not LocalFunctionStat: {type(factory_stat).__name__}"

        factory_func = factory_stat.func

        can_ok, can_reason = can_compile(factory_func)
        if not can_ok:
            return None, f"can_compile=False: {can_reason}"

        compiler = Compiler()
        proto = compiler.compile_function(factory_func, name=factory_lua_name)

        rt_gen = RuntimeGenerator(seed=rng.randint(0, 0xFFFFFFFF))
        vm_code = rt_gen.generate_vm_wrapper(proto, fn_name=factory_lua_name)

        return vm_code, ''

    except Exception as e:
        err = f"{type(e).__name__}: {e}"
        if _DEBUG:
            traceback.print_exc()
        return None, err


# ══════════════════════════════════════════════════════════════════
#  ТРАНСФОРМЕР
# ══════════════════════════════════════════════════════════════════

class VMProtectionTransformer:
    """
    Заменяет функции, помеченные _NZL_VM_MARK_() (после препроцессинга),
    на VM-защищённые версии.
    """

    def __init__(self, seed: Optional[int] = None, debug: bool = False):
        global _DEBUG
        if seed is None:
            seed = random.randint(0, 0xFFFFFFFF)
        self.seed = seed
        self.rng = make_rng(seed)
        self._name_gen = NameGenerator(rng=self.rng, style='hex')
        self._counter = 0
        self._stats = {
            'functions_protected': 0,
            'functions_failed': 0,
            'functions_skipped': 0,
        }
        self._errors: List[str] = []
        _DEBUG = debug

    def _next_factory_name(self) -> str:
        self._counter += 1
        suffix = self._name_gen.generate()
        return f'__nzlvm_{suffix}_{self._counter}__'

    def transform(self, ast: Chunk) -> Tuple[str, Chunk]:
        """
        Возвращает (prelude_lua_code, new_ast).
        """
        factories: List[str] = []

        self._process_block(ast.body, factories)
        self._walk_block(ast.body, factories)

        prelude = '\n\n'.join(factories) if factories else ''
        return prelude, ast

    def _process_block(self, block: Block, factories: List[str]) -> None:
        """
        Ищет пары: [маркер] [функция] → заменяет на VM.
        """
        stmts = block.statements
        i = 0
        new_stmts: List[Stat] = []
        marked_indices: Set[int] = set()

        # Собираем индексы маркированных функций
        while i < len(stmts):
            stat = stmts[i]
            if _is_vm_marker_stat(stat):
                # Следующий стейтмент — целевая функция
                if i + 1 < len(stmts):
                    marked_indices.add(i + 1)
                # Индекс маркера тоже надо удалить
                marked_indices.add(-1000 - i)  # sentinel — будем игнорировать позднее
            i += 1

        # Обрабатываем стейтменты
        i = 0
        while i < len(stmts):
            stat = stmts[i]

            # Пропускаем маркер
            if _is_vm_marker_stat(stat):
                i += 1
                continue

            # Проверяем: помечен ли этот стейтмент как цель
            if i in marked_indices:
                if isinstance(stat, (LocalFunctionStat, FunctionDeclStat)):
                    replacement = self._try_protect(stat, factories)
                    if replacement is not None:
                        new_stmts.append(replacement)
                        i += 1
                        continue
                    else:
                        # Не удалось — оставляем как есть
                        new_stmts.append(stat)
                        i += 1
                        continue
                else:
                    self._stats['functions_skipped'] += 1
                    self._errors.append(
                        f"marker before non-function: {type(stat).__name__}"
                    )
                    new_stmts.append(stat)
                    i += 1
                    continue

            new_stmts.append(stat)
            i += 1

        block.statements = new_stmts

    def _try_protect(
        self,
        stat: Stat,
        factories: List[str],
    ) -> Optional[Stat]:
        fn_name = _get_func_name(stat)
        func_expr = _get_func_expr(stat)

        if fn_name is None or func_expr is None:
            self._stats['functions_skipped'] += 1
            self._errors.append(
                f"cannot extract name/func from {type(stat).__name__}"
            )
            return None

        factory_lua_name = self._next_factory_name()

        factory_code, err = _compile_function_to_vm(
            fn_name=fn_name,
            func_expr=func_expr,
            factory_lua_name=factory_lua_name,
            rng=self.rng,
        )

        if factory_code is None:
            self._stats['functions_failed'] += 1
            self._errors.append(f"fail '{fn_name}': {err}")
            return None

        factories.append(factory_code)

        line = getattr(stat, 'line', 0)
        call_expr = CallExpr(
            func=NameExpr(name=factory_lua_name, line=line),
            args=[],
            line=line,
        )

        if isinstance(stat, LocalFunctionStat):
            replacement = LocalAssignStat(
                names=[fn_name],
                values=[call_expr],
                attribs=[None],
                line=line,
            )
        else:
            replacement = AssignStat(
                targets=[NameExpr(name=fn_name, line=line)],
                values=[call_expr],
                line=line,
            )

        self._stats['functions_protected'] += 1
        return replacement

    def _walk_block(self, block: Block, factories: List[str]) -> None:
        for stat in block.statements:
            self._walk_stat(stat, factories)

    def _walk_stat(self, stat, factories: List[str]) -> None:
        if not hasattr(stat, '__dataclass_fields__'):
            return

        for fname in stat.__dataclass_fields__:
            val = getattr(stat, fname, None)
            if isinstance(val, FunctionExpr):
                if val.body:
                    self._process_block(val.body, factories)
                    self._walk_block(val.body, factories)
            elif isinstance(val, Block):
                self._process_block(val, factories)
                self._walk_block(val, factories)
            elif isinstance(val, Node):
                self._walk_stat(val, factories)
            elif isinstance(val, list):
                for item in val:
                    if isinstance(item, FunctionExpr):
                        if item.body:
                            self._process_block(item.body, factories)
                            self._walk_block(item.body, factories)
                    elif isinstance(item, Block):
                        self._process_block(item, factories)
                        self._walk_block(item, factories)
                    elif isinstance(item, Node):
                        self._walk_stat(item, factories)
                    elif isinstance(item, tuple):
                        for sub in item:
                            if isinstance(sub, (Block, Node)):
                                self._walk_stat(sub, factories)

    @property
    def stats(self) -> dict:
        return dict(self._stats)

    @property
    def errors(self) -> List[str]:
        return list(self._errors)


# ══════════════════════════════════════════════════════════════════
#  CONVENIENCE
# ══════════════════════════════════════════════════════════════════

def apply_vm_protection(
    ast: Chunk,
    seed: Optional[int] = None,
    debug: bool = False,
) -> Tuple[str, Chunk]:
    transformer = VMProtectionTransformer(seed=seed, debug=debug)
    return transformer.transform(ast)


# ══════════════════════════════════════════════════════════════════
#  SELF-TEST
# ══════════════════════════════════════════════════════════════════

def _test():
    print('=' * 60)
    print('🧪 ТЕСТЫ: vm_protection.py (v3 — preprocessing)')
    print('=' * 60)

    passed = 0
    failed = 0

    def check(label: str, cond: bool, detail: str = ''):
        nonlocal passed, failed
        if cond:
            print(f'  ✅ {label}')
            passed += 1
        else:
            print(f'  ❌ {label}' + (f' — {detail}' if detail else ''))
            failed += 1

    def parse(code: str) -> Chunk:
        return Parser(Lexer(code).tokenize()).parse()

    def parse_with_marker(code: str) -> Chunk:
        """Полный pipeline: preprocess → parse."""
        return parse(preprocess_source(code))

    # ── Test 1: препроцессор ─────────────────────────────────────
    print('\n[1] Препроцессор находит @vm')

    src1 = 'local function add(a, b) -- @vm\n    return a + b\nend\n'
    pre1 = preprocess_source(src1)
    check('inline @vm → маркер добавлен',
          VM_MARKER_CALL_NAME in pre1,
          f'pre={pre1!r}')

    src2 = '-- @vm\nlocal function mul(a, b)\n    return a * b\nend\n'
    pre2 = preprocess_source(src2)
    check('standalone @vm → маркер добавлен',
          VM_MARKER_CALL_NAME in pre2,
          f'pre={pre2!r}')

    src3 = 'local function noVm(a, b)\n    return a + b\nend\n'
    pre3 = preprocess_source(src3)
    check('без @vm → без маркера',
          VM_MARKER_CALL_NAME not in pre3)

    # ── Test 2: после препроцессинга валидный Lua ────────────────
    print('\n[2] После препроцессинга — валидный Lua')
    try:
        ast1 = parse(pre1)
        check('inline preprocessed парсится', ast1 is not None)
    except Exception as e:
        check('inline preprocessed парсится', False, str(e)[:80])

    try:
        ast2 = parse(pre2)
        check('standalone preprocessed парсится', ast2 is not None)
    except Exception as e:
        check('standalone preprocessed парсится', False, str(e)[:80])

    # ── Test 3: маркер не найден → функция не тронута ────────────
    print('\n[3] Нет маркера → функция не тронута')
    code = 'local function add(a, b) return a + b end\n'
    ast = parse_with_marker(code)
    transformer = VMProtectionTransformer(seed=42, debug=True)
    prelude, new_ast = transformer.transform(ast)
    check('prelude пустой', prelude == '')
    check('0 protected', transformer.stats['functions_protected'] == 0)

    # ── Test 4: маркер inline → функция защищена ─────────────────
    print('\n[4] Inline @vm → функция защищена')
    code2 = 'local function mul(a, b) -- @vm\n    return a * b\nend\n'
    ast2 = parse_with_marker(code2)
    transformer2 = VMProtectionTransformer(seed=42, debug=True)
    prelude2, new_ast2 = transformer2.transform(ast2)

    if transformer2.errors:
        print('  📋 errors:')
        for e in transformer2.errors:
            print(f'      → {e}')

    check(f'stats: 1 protected (got {transformer2.stats})',
          transformer2.stats['functions_protected'] == 1)
    check('prelude не пустой', len(prelude2) > 0)

    # Проверяем: маркер удалён, функция заменена
    stat_types = [type(s).__name__ for s in new_ast2.body.statements]
    check(f'нет лишних маркеров (statements={stat_types})',
          not any('_NZL_VM_MARK_' in unparse(Chunk(body=Block(statements=[s], return_stat=None, line=0), line=0))
                  for s in new_ast2.body.statements))

    # ── Test 5: standalone @vm перед функцией ────────────────────
    print('\n[5] Standalone @vm → функция защищена')
    code3 = '-- @vm\nlocal function sub(a, b)\n    return a - b\nend\n'
    ast3 = parse_with_marker(code3)
    transformer3 = VMProtectionTransformer(seed=100, debug=True)
    prelude3, new_ast3 = transformer3.transform(ast3)

    if transformer3.errors:
        print('  📋 errors:')
        for e in transformer3.errors:
            print(f'      → {e}')

    check(f'standalone: 1 protected (got {transformer3.stats})',
          transformer3.stats['functions_protected'] == 1)

    # ── Test 6: рекурсия factorial ───────────────────────────────
    print('\n[6] Рекурсия factorial')
    code4 = '''local function factorial(n) -- @vm
    if n <= 1 then return 1 end
    return n * factorial(n - 1)
end
'''
    ast4 = parse_with_marker(code4)
    transformer4 = VMProtectionTransformer(seed=200, debug=True)
    prelude4, new_ast4 = transformer4.transform(ast4)

    if transformer4.errors:
        print('  📋 errors:')
        for e in transformer4.errors:
            print(f'      → {e}')

    check(f'factorial protected (stats={transformer4.stats})',
          transformer4.stats['functions_protected'] == 1)

    # ── Test 7: несколько функций разом ──────────────────────────
    print('\n[7] Несколько @vm функций')
    code5 = '''local function f1(a) -- @vm
    return a + 1
end

local function f2(a) -- @vm
    return a * 2
end

local function f3(a)
    return a - 1
end
'''
    ast5 = parse_with_marker(code5)
    transformer5 = VMProtectionTransformer(seed=300, debug=True)
    prelude5, new_ast5 = transformer5.transform(ast5)

    if transformer5.errors:
        print('  📋 errors:')
        for e in transformer5.errors:
            print(f'      → {e}')

    check(f'2 protected, 1 не тронута (got {transformer5.stats})',
          transformer5.stats['functions_protected'] == 2)

    # ── Test 8: FunctionDeclStat ─────────────────────────────────
    print('\n[8] FunctionDeclStat с @vm')
    code6 = 'function greet(name) -- @vm\n    return "Hi " .. name\nend\n'
    ast6 = parse_with_marker(code6)
    transformer6 = VMProtectionTransformer(seed=999, debug=True)
    prelude6, new_ast6 = transformer6.transform(ast6)

    if transformer6.errors:
        print('  📋 errors:')
        for e in transformer6.errors:
            print(f'      → {e}')

    check(f'FunctionDecl protected (stats={transformer6.stats})',
          transformer6.stats['functions_protected'] == 1)

    # ── Итог ─────────────────────────────────────────────────────
    total = passed + failed
    print()
    print('=' * 60)
    print(f'📊 Результат: {passed}/{total} тестов прошло')
    if failed == 0:
        print('🎉 vm_protection.py v3 РАБОТАЕТ!')
    else:
        print(f'⚠️  Провалено: {failed}')
    print('=' * 60)

    return failed == 0


if __name__ == '__main__':
    success = _test()
    sys.exit(0 if success else 1)