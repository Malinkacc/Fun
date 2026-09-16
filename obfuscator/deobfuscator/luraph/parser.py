"""
NZL STUDIO - Sprint 5: структурный парсер Luraph v14.x
======================================================
Формат образца samples/luraph/v14.6_sample1.lua:

    -- This file was protected using Luraph Obfuscator v14.6 [https://lura.ph/]
    return({
        dA=function(L,L)return L;end,          -- handler'ы (colon-вызовы)
        XW=function(L,i,P,k,m,U)...end,
        v=bit32.rrotate,                        -- алиасы библиотек (dot-вызовы)
        X=string, z=table, G=bit32, k=unpack, Q=nil,
        S=function(L) ... диспетчер ... end
    }):S()(...);

Парсер НЕ девиртуализирует VM Luraph (это Sprint 6+); он даёт карту:
  * handlers  — именованные function-элементы таблицы;
  * aliases   — элементы-значения (библиотечные алиасы, nil, таблицы);
  * dispatcher — имя метода, которым вызывают таблицу (обычно 'S');
  * outer_args — аргументы внешнего вызова (обычно (...));
Эта карта кормит deep-декодеры (luraph_decoder: alias-inline) и бота.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from obfuscator.ast_nodes import (
    Block, CallExpr, Chunk, Expr, FunctionExpr, IndexExpr, MethodCallExpr,
    NameExpr, Node, ParenExpr, ReturnStat, Stat, StringLit, TableExpr,
    TableField, VarargLit,
)


def _unparen(e: Expr) -> Expr:
    while isinstance(e, ParenExpr):
        e = e.inner
    return e

BANNER_RE = re.compile(
    r'protected using Luraph Obfuscator v(\d+(?:\.\d+)*)', re.IGNORECASE)


@dataclass
class LuraphReport:
    detected: bool = False
    banner_version: Optional[str] = None
    dispatcher: Optional[str] = None
    outer_args: List[Expr] = field(default_factory=list)
    handlers: Dict[str, FunctionExpr] = field(default_factory=dict)
    aliases: Dict[str, Expr] = field(default_factory=dict)
    table_field_order: List[str] = field(default_factory=list)

    def summary(self) -> str:
        return (f'detected={self.detected} ver={self.banner_version} '
                f'dispatcher={self.dispatcher} '
                f'handlers={len(self.handlers)} aliases={len(self.aliases)}')


def detect_source(source: str) -> Optional[str]:
    """Версия из баннера, если он есть."""
    m = BANNER_RE.search(source)
    return m.group(1) if m else None


def _unwrap_entry_table(chunk: Chunk) -> Optional[Tuple[TableExpr, str,
                                                        List[Expr]]]:
    """
    Ищем форму  return( { ... } ):NAME( ...outer... )
    Возвращает (таблица, имя диспетчера, аргументы внешнего вызова).
    """
    if chunk.body is None:
        return None
    # Luraph-файл = ровно один return всей таблицы (statements пусты,
    # return живёт в Block.return_stat)
    if chunk.body.statements:
        return None
    st = chunk.body.return_stat
    if not isinstance(st, ReturnStat) or len(st.values) != 1:
        return None
    outer = st.values[0]
    if not isinstance(outer, CallExpr):
        return None
    inner = outer.func
    if isinstance(inner, MethodCallExpr):
        tbl, name = _unparen(inner.obj), inner.method
        if inner.args:
            return None
    elif isinstance(inner, CallExpr):
        if not isinstance(inner.func, IndexExpr):
            return None
        idx = inner.func.index
        if not (inner.func.is_dot and isinstance(idx, StringLit)):
            return None
        tbl, name = _unparen(inner.func.obj), str(idx.value)
        if inner.args:
            return None
    else:
        return None
    if not isinstance(tbl, TableExpr):
        return None
    return tbl, name, list(outer.args)


def parse_chunk(chunk: Chunk,
                banner_version: Optional[str] = None) -> LuraphReport:
    rep = LuraphReport(banner_version=banner_version)
    found = _unwrap_entry_table(chunk)
    if found is None:
        return rep
    tbl, name, outer_args = found
    rep.dispatcher = name
    rep.outer_args = outer_args
    for f in tbl.fields:
        key = f.key
        if isinstance(key, StringLit):
            nm = str(key.value)
        elif isinstance(key, NameExpr):
            nm = key.name
        else:
            continue
        rep.table_field_order.append(nm)
        if isinstance(f.value, FunctionExpr):
            rep.handlers[nm] = f.value
        else:
            rep.aliases[nm] = f.value
    # форма Luraph: диспетчер вызывается методом таблицы и внешний
    # вызов пропускает varargs; handlers используют self-таблицу
    rep.detected = bool(rep.handlers) and (
        banner_version is not None
        or any(isinstance(a, VarargLit) for a in outer_args)
        or len(rep.handlers) >= 8)
    return rep


def parse_source(source: str) -> LuraphReport:
    from obfuscator.deobfuscator.core.base import parse_code
    chunk = parse_code(source)
    return parse_chunk(chunk, detect_source(source))


def _test() -> None:
    import os
    import sys
    root = os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))))
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
    print('  luraph.parser — tests')
    print('=' * 60)

    here = os.path.dirname(os.path.abspath(__file__))
    sample = os.path.join(here, '..', 'samples', 'luraph',
                          'v14.6_sample1.lua')

    # T1: реальный образец
    if os.path.exists(sample):
        src = open(sample, encoding='utf-8', errors='replace').read()
        rep = parse_source(src)
        check('T1 real v14.6 sample detected', rep.detected,
              rep.summary())
        check('T1 banner version = 14.6', rep.banner_version == '14.6',
              str(rep.banner_version))
        check('T1 dispatcher = S', rep.dispatcher == 'S',
              str(rep.dispatcher))
        check('T1 handlers >= 50', len(rep.handlers) >= 50,
              f'n={len(rep.handlers)}')
        check('T1 aliases include bit32/string/table',
              any('bit32' in _src_of(v) for v in rep.aliases.values())
              and any('string' in _src_of(v)
                      for v in rep.aliases.values()),
              f'n={len(rep.aliases)}')
        check('T1 outer call passes varargs',
              any(isinstance(a, VarargLit) for a in rep.outer_args))
        check('T1 dispatcher is a handler',
              rep.dispatcher in rep.handlers)
    else:
        check('T1 real sample exists', False, sample)

    # T2: не-Luraph код не детектится
    from obfuscator.deobfuscator.core.base import parse_code
    plain = parse_code('local x = 1\nprint(x)\n')
    rep2 = parse_chunk(plain, None)
    check('T2 plain code not detected', not rep2.detected)
    tbl_only = parse_code('return({a = function() end}):a()\n')
    rep3 = parse_chunk(tbl_only, None)
    check('T2 tiny table not detected as Luraph', not rep3.detected,
          rep3.summary())

    total = passed + failed
    print('=' * 60)
    print(f'  Result: {passed}/{total}')
    if failed:
        sys.exit(1)
    print('  [OK] ALL PASSED')


def _src_of(expr: Expr) -> str:
    from obfuscator.ast_unparser import unparse
    try:
        return unparse(expr)
    except Exception:  # noqa: BLE001
        return ''


if __name__ == '__main__':
    _test()
