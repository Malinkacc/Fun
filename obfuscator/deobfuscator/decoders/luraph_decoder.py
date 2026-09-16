"""
NZL STUDIO - Sprint 5: Luraph deep-decoder
==========================================
Работает по карте из deobfuscator/luraph/parser.py (Luraph v14.x):

  Pass A — UNWRAP: если dispatcher-метод таблицы (:S) не использует
           собственные параметры (наш mimic / простые обёртки), чанк
           разворачивается обратно в тело диспетчера.
  Pass B — ALIAS INLINE: dot-вызовы алиасов среды (`L.fW(a, b)`, где
           fW = bit32.lrotate в таблице) заменяются на прямые
           библиотечные вызовы. Колон-вызовы хендлеров (L:ZW(...))
           не трогаются — это VM-диспетч, его девиртуализация это
           Sprint 6+.

Честность: не-Luraph код -> no-op; реальный VM Luraph остаётся на
месте (только алиасы), ошибки в stats.
"""

from __future__ import annotations

import copy
from typing import Dict, Optional

from obfuscator.ast_nodes import (
    Block, CallExpr, Chunk, Expr, FunctionExpr, IndexExpr, NameExpr,
    Node, StringLit,
)

from .base_decoder import BaseDecoder, DecoderStats

_SAFE_LIBS = {'string', 'table', 'bit32', 'math', 'coroutine', 'utf8'}


def _is_safe_alias_target(e: Expr) -> bool:
    if isinstance(e, NameExpr):
        return e.name in _SAFE_LIBS
    if isinstance(e, IndexExpr) and e.is_dot:
        return isinstance(e.obj, NameExpr) and e.obj.name in _SAFE_LIBS
    return False


class LuraphDecoder(BaseDecoder):
    """Deep-проходы по Luraph-форме: unwrap + alias inline."""

    NAME = 'luraph_decoder'

    def run(self, chunk: Chunk):
        self.stats = DecoderStats(name=self.NAME)

        from obfuscator.deobfuscator.luraph.parser import parse_chunk
        rep = parse_chunk(chunk)
        if not rep.detected:
            return chunk, self.stats
        self.stats.scanned = 1

        disp = rep.handlers.get(rep.dispatcher or '')
        if disp is not None and self._params_unused(disp):
            chunk.body = Block(
                statements=list(disp.body.statements or []),
                return_stat=disp.body.return_stat)
            self.stats.replaced += 1
            self.stats.details.append(
                f'unwrapped straight-line dispatcher '
                f'{rep.dispatcher!r}')
            return chunk, self.stats

        n = self._inline_aliases(chunk, rep.aliases)
        self.stats.replaced += n
        if n:
            self.stats.details.append(f'inlined {n} alias calls')
        return chunk, self.stats

    # ── Pass A ─────────────────────────────────────────────────
    def _params_unused(self, fn: FunctionExpr) -> bool:
        used = set()
        self._collect_names(fn.body, used)
        return not (set(fn.params or []) & used)

    def _collect_names(self, node, acc: set) -> None:
        fields = getattr(node, '__dataclass_fields__', None)
        if fields is None:
            return
        for fname in fields:
            fv = getattr(node, fname, None)
            if isinstance(fv, NameExpr):
                acc.add(fv.name)
            elif isinstance(fv, Node):
                self._collect_names(fv, acc)
            elif isinstance(fv, list):
                for item in fv:
                    if isinstance(item, Node):
                        self._collect_names(item, acc)
                    elif isinstance(item, tuple):
                        for sub in item:
                            if isinstance(sub, Node):
                                self._collect_names(sub, acc)

    # ── Pass B ─────────────────────────────────────────────────
    def _inline_aliases(self, node, aliases: Dict[str, Expr]) -> int:
        n = 0
        safe = {k: v for k, v in aliases.items()
                if _is_safe_alias_target(v)}
        if not safe:
            return 0
        n += self._walk_inline(node, safe)
        return n

    def _walk_inline(self, node, safe: Dict[str, Expr]) -> int:
        n = 0
        fields = getattr(node, '__dataclass_fields__', None)
        if fields is None:
            return 0
        for fname in fields:
            fv = getattr(node, fname, None)
            if isinstance(fv, CallExpr):
                if self._try_inline(fv, safe):
                    n += 1
                n += self._walk_inline(fv, safe)
            elif isinstance(fv, Node):
                n += self._walk_inline(fv, safe)
            elif isinstance(fv, list):
                for item in fv:
                    if isinstance(item, CallExpr):
                        if self._try_inline(item, safe):
                            n += 1
                        n += self._walk_inline(item, safe)
                    elif isinstance(item, Node):
                        n += self._walk_inline(item, safe)
                    elif isinstance(item, tuple):
                        for sub in item:
                            if isinstance(sub, CallExpr):
                                if self._try_inline(sub, safe):
                                    n += 1
                                n += self._walk_inline(sub, safe)
                            elif isinstance(sub, Node):
                                n += self._walk_inline(sub, safe)
        return n

    @staticmethod
    def _try_inline(call: CallExpr, safe: Dict[str, Expr]) -> bool:
        f = call.func
        if not (isinstance(f, IndexExpr) and f.is_dot
                and isinstance(f.index, StringLit)):
            return False
        alias = safe.get(str(f.index.value))
        if alias is None:
            return False
        if not isinstance(f.obj, NameExpr):
            return False
        call.func = copy.deepcopy(alias)
        return True
