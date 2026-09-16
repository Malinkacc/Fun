"""
NZL STUDIO - Sprint 4b: восстановление op-map VM из исходника runtime
====================================================================
Обфускатор перемешивает dispatch-ветки (shuffle_dispatch=True), поэтому
номер опкода нельзя получить из порядка веток. Но ТЕЛА веток генерируются
из фиксированных шаблонов runtime_lua.py: после нормализации случайных
имён (роли R/K/PC/A/B/C/...) скелет тела однозначно определяет семантику.

Алгоритм:
  1. из исходника цели извлекаем execute-функцию и её dispatch-ветки
     (num -> body);
  2. генерируем ЭТАЛОННЫЙ runtime (shuffle/junk выкл), извлекаем его ветки
     в порядке enum Opcode -> скелет -> Opcode;
  3. нормализуем тела цели теми же ролями и сопоставляем скелеты.

Ветки, не совпавшие ни с одним эталоном (junk-опкоды), помечаются JUNK —
компилятор их никогда не эмитирует, для девиртуализации они не нужны.
"""

from __future__ import annotations

import re
from typing import Dict, Optional, Tuple

from obfuscator.vm.opcodes import Opcode
from obfuscator.vm.runtime_lua import RuntimeGenerator

# execute-шапка: proto, args, upvals, r, code, k_tbl, env, pc,
#                instr, op, a, b, c, k, tmp, i
_EXECUTE_HDR = re.compile(
    r'local function (\w+)\((\w+), (\w+), (\w+)\)\n'
    r'    local (\w+) = \{\}\n'
    r'    local (\w+) = \2\.code\n'
    r'    local (\w+) = \2\.constants\n'
    r'    local (\w+) = getfenv and getfenv\(\) or _G\n'
    r'    local (\w+) = 1\n'
    r'    local (\w+), (\w+), (\w+), (\w+), (\w+), (\w+)\n'
    r'    local (\w+)\n'
    r'    local (\w+)\n'
)

# ветка dispatch: if/elseif <op> == N then do <body> end (end ветки = 12 пробелов)
_BRANCH = re.compile(
    r'(?:if|elseif) (\w+) == (\d+) then\n            do\n(.*?)\n            end\n',
    re.DOTALL,
)

_ROLES = (
    'execute', 'proto', 'args', 'upvals', 'r', 'code', 'k_tbl', 'env', 'pc',
    'instr', 'op', 'a', 'b', 'c', 'kop', 'tmp', 'i',
)

# prelude-локали (aliased builtins), которые встречаются в телах веток
_PRELUDE_ROLES = (
    ('tbl_unpack', r'local (\w+) = table\.unpack or unpack'),
    ('bxor', r'local (\w+) = bit32\.bxor'),
    ('str_byte', r'local (\w+) = string\.byte'),
    ('str_sub', r'local (\w+) = string\.sub'),
    ('str_char', r'local (\w+) = string\.char'),
    ('tbl_insert', r'local (\w+) = table\.insert'),
)

# опкоды с семантически идентичными телами — для девиртуализации взаимозаменяемы
SEMANTIC_EQ = [
    {Opcode.MOVE, Opcode.DUP},
    {Opcode.GETTABLE, Opcode.RAWGET},
    {Opcode.SETTABLE, Opcode.RAWSET},
    {Opcode.LEN, Opcode.STRLEN},
    {Opcode.GETFIELD, Opcode.GETTABLE_K},
    {Opcode.SETFIELD, Opcode.SETTABLE_K},
    {Opcode.SELECT, Opcode.YIELDK},
]


def extract_execute_names(src: str) -> Optional[Dict[str, str]]:
    """Достаёт имена локалей execute-функции по роли."""
    src = src.replace('\r\n', '\n')
    m = _EXECUTE_HDR.search(src)
    if not m:
        return None
    names = dict(zip(_ROLES, m.groups()))
    varargs_re = re.compile(
        r'\n    local (\w+) = \{\}\n    if ' + re.escape(names['args']) + r' then\n'
    )
    mv = varargs_re.search(src[m.end():])
    names['varargs'] = mv.group(1) if mv else ''
    for role, pat in _PRELUDE_ROLES:
        mp = re.search(pat, src)
        names[role] = mp.group(1) if mp else ''
    return names


def extract_branches(src: str) -> Dict[int, str]:
    """num -> тело ветки dispatch (без do/end обёртки)."""
    src = src.replace('\r\n', '\n')
    out: Dict[int, str] = {}
    for _opvar, num, body in _BRANCH.findall(src):
        out[int(num)] = body
    return out


def normalize_body(body: str, names: Dict[str, str]) -> str:
    """Заменяет случайные имена execute/prelude-локалей на роли."""
    items = [(role, names.get(role, '')) for role in _ROLES]
    items += [(role, names.get(role, '')) for role, _ in _PRELUDE_ROLES]
    items.append(('varargs', names.get('varargs', '')))
    items = [(role, n) for role, n in items if n]
    # tmp порождает идентификаторы с суффиксами ({tmp}i, {tmp}s, ...)
    items.sort(key=lambda kv: len(kv[1]), reverse=True)
    for role, n in items:
        if role == 'tmp':
            body = re.sub(r'\b' + re.escape(n) + r'\w*', 'TMP', body)
        else:
            body = re.sub(r'\b' + re.escape(n) + r'\b', role.upper(), body)
    return body


def reference_skeletons() -> Dict[str, Opcode]:
    """Скелет тела -> Opcode (эталон, порядок enum)."""
    gen = RuntimeGenerator(seed=0x5A4B0001, shuffle_dispatch=False,
                           add_junk_ops=False)
    ref_src = gen._generate_runtime()
    ref_names = extract_execute_names(ref_src)
    if ref_names is None:
        raise RuntimeError('reference runtime header not parsed')
    skels: Dict[str, Opcode] = {}
    for num, body in extract_branches(ref_src).items():
        op = gen.op_map.get_op(num)
        if op is None:
            continue
        skels[normalize_body(body, ref_names)] = op
    return skels


_REF_CACHE: Optional[Dict[str, Opcode]] = None


def recover_op_map(runtime_src: str) -> Tuple[Dict[int, Opcode], Dict[int, str]]:
    """
    Возвращает (num -> Opcode, num -> причина_если_не_распознано).
    """
    global _REF_CACHE
    if _REF_CACHE is None:
        _REF_CACHE = reference_skeletons()

    names = extract_execute_names(runtime_src)
    if names is None:
        return {}, {'__header__': 'execute header not found'}

    known: Dict[int, Opcode] = {}
    unknown: Dict[int, str] = {}
    for num, body in extract_branches(runtime_src).items():
        skel = normalize_body(body, names)
        op = _REF_CACHE.get(skel)
        if op is None:
            unknown[num] = 'unmatched skeleton (junk or new opcode)'
        else:
            known[num] = op
    return known, unknown


def _test() -> None:
    import os
    import sys
    root = os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))))
    if root not in sys.path:
        sys.path.insert(0, root)

    passed = failed = 0

    def check(label: str, ok: bool, extra: str = '') -> None:
        nonlocal passed, failed
        if ok:
            passed += 1
            print(f'  [OK] {label}' + (f'  {extra}' if extra else ''))
        else:
            failed += 1
            print(f'  [XX] {label}' + (f'  {extra}' if extra else ''))

    print('=' * 60)
    print('  vm_decompile.opmap_recovery — tests')
    print('=' * 60)

    def sem_ok(true_op: Opcode, got_op: Opcode) -> bool:
        if true_op == got_op:
            return True
        return any(true_op in grp and got_op in grp for grp in SEMANTIC_EQ)

    n_ops = len(list(Opcode))
    for seed in (1, 42, 7):
        gen = RuntimeGenerator(seed=seed)
        src = gen._generate_runtime()
        known, unknown = recover_op_map(src)
        bad = {n: (gen.op_map.get_op(n).name, op.name)
               for n, op in known.items()
               if not sem_ok(gen.op_map.get_op(n), op)}
        missed = [n for n in gen.op_map._num_to_op if n not in known]
        check(f'seed={seed}: all real branches recovered (semantically)',
              not bad and not missed and len(known) + len(missed) >= n_ops,
              f'known={len(known)}, missed={missed[:4]}, bad={list(bad)[:3]}')
        check(f'seed={seed}: unknown are junk only',
              all(gen.op_map.get_op(n) is None for n in unknown),
              f'unknown={sorted(unknown)[:4]}')

    # чужой/битый исходник -> пустая карта, без исключений
    known, unknown = recover_op_map('local x = 1\n')
    check('garbage source -> empty map', not known and unknown)

    total = passed + failed
    print('=' * 60)
    print(f'  Result: {passed}/{total}')
    if failed:
        sys.exit(1)
    print('  [OK] ALL PASSED')


if __name__ == '__main__':
    _test()
