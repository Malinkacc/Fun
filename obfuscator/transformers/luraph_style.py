"""
NZL STUDIO - Sprint 5: Luraph-style mimic (obfuscator-фича)
==========================================================
Adversarial-пара к decoders/luraph_decoder.py: заворачивает чанк в
форму Luraph v14.x, чтобы декодер можно было гонять round-trip:

    return({
        S  = function(L) <исходный код> end,     -- dispatcher-имя S
        dA = function(L,L) return L; end,       -- junk-хендлеры
        ...
        X = string, z = table, G = bit32, k = unpack, Q = nil,
    }):S(...);

Плюс restyle чисел в 0X/0B-литералы с подчёркиваниями (стиль v14,
lexer/unparser это поддерживают через NumberLit.raw).

Фича ВЫКЛЮЧЕНА по умолчанию (вызывается напрямую из тестов) — ноль
риска регрессий для medium/hard/insane.
"""

from __future__ import annotations

import random
from typing import List, Optional, Tuple

from obfuscator.ast_nodes import (
    Block, CallExpr, Chunk, FunctionExpr, IndexExpr, MethodCallExpr,
    NameExpr, NilLit, NumberLit, ParenExpr, ReturnStat, StringLit,
    TableExpr, TableField, VarargLit,
)

_JUNK_BODIES = [
    'return L;',
    'if i then return P, L; end; return L, i;',
    'L = 1; return L;',
    'return i % 8;',
    'local P; P = L; return P, i;',
    'return nil, L;',
    'if L ~= 0 then return i, L; end; return nil;',
    'return L, i, P;',
]

_ALIASES = [
    ('X', 'string'), ('z', 'table'), ('G', 'bit32'), ('k', 'unpack'),
    ('M', 'type'), ('E', 'pcall'), ('Q', None),
]


class LuraphStyleTransformer:
    """Заворачивает chunk в Luraph-подобную mega-таблицу."""

    def __init__(self, seed: Optional[int] = None,
                 junk_handlers: int = 8,
                 restyle_numbers: bool = True):
        self.rng = random.Random(seed)
        self.junk_handlers = junk_handlers
        self.restyle_numbers = restyle_numbers

    # ── number restyle ─────────────────────────────────────────
    def _restyle(self, node) -> None:
        fields = getattr(node, '__dataclass_fields__', None)
        if fields is None:
            return
        for fname in list(fields):
            fv = getattr(node, fname, None)
            if isinstance(fv, NumberLit):
                self._restyle_num(fv)
            elif isinstance(fv, list):
                for item in fv:
                    self._restyle(item)
            elif hasattr(fv, '__dataclass_fields__'):
                self._restyle(fv)

    def _restyle_num(self, node: NumberLit) -> None:
        v = node.value
        if not (isinstance(v, int) and 0 <= v <= 0xFFFFFF):
            return
        if self.rng.random() < 0.5:
            return
        if self.rng.random() < 0.5:
            digits = format(v, 'X')
            raw = '0X' + self._underscores(digits)
        else:
            digits = format(v, 'b')
            raw = '0B' + self._underscores(digits)
        node.raw = raw

    @staticmethod
    def _underscores(digits: str) -> str:
        if len(digits) < 4:
            return digits
        pos = len(digits) // 2
        return digits[:pos] + '_' + digits[pos:]

    # ── transform ──────────────────────────────────────────────
    def transform(self, chunk: Chunk) -> Chunk:
        body = chunk.body or Block(statements=[])
        orig_block = Block(statements=list(body.statements),
                           return_stat=body.return_stat)

        if self.restyle_numbers:
            self._restyle(orig_block)

        fields: List[TableField] = []

        # dispatcher S с исходным кодом внутри
        fields.append(TableField(
            key=StringLit(value='S'),
            value=FunctionExpr(params=['L'], is_vararg=False,
                               body=orig_block),
            is_name=True))

        # junk-хендлеры в стиле Luraph (короткие имена, мёртвые ветки)
        from obfuscator.lexer import Lexer
        from obfuscator.parser import Parser
        names = ['dA', 'XW', 'gW', 'iA', 'aA', 'eA', 'wW', 'qA',
                 'SW', 'ZW', 'KW', 'OW']
        for q in range(self.junk_handlers):
            src = ('local function h(L,i,P)' + _JUNK_BODIES[q %
                   len(_JUNK_BODIES)] + ' end')
            fn = Parser(Lexer(src).tokenize()).parse()
            func = fn.body.statements[0].func
            fields.append(TableField(key=StringLit(value=names[q]),
                                     value=func, is_name=True))

        # алиасы библиотек
        for nm, lib in _ALIASES:
            val = NameExpr(name=lib) if lib else NilLit()
            fields.append(TableField(key=StringLit(value=nm), value=val,
                                     is_name=True))

        tbl = TableExpr(fields=fields)
        method = MethodCallExpr(obj=ParenExpr(inner=tbl), method='S',
                                args=[])
        outer = CallExpr(func=method, args=[VarargLit()])
        new_body = Block(statements=[],
                         return_stat=ReturnStat(values=[outer]))
        return Chunk(line=chunk.line, body=new_body)
