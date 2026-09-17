"""
NZL STUDIO - Sprint 4b: VM-devirtualizer для собственного VM
============================================================
Откатывает VMProtectionTransformer (insane-уровень):

  1. находит wrapper'ы  local F = create_vm(<blob>, <key16>)  —
     структурно: CallExpr от двух StringLit, key ровно 16 байт;
  2. восстанавливает op-map ПО ТЕКСТУ runtime (opmap_recovery —
     скелетная классификация веток dispatch, seed не нужен);
  3. RC4-расшифровывает блоб (rc4 симметричен) и декодирует Proto
     (proto_decode — зеркало BytecodeEncoder.encode_proto);
  4. поднимает Proto в Lua AST (lifter — обратная к vm/compiler.py:
     структурный if/while/repeat/for, материализация регистров циклов,
     and/or short-circuit, CLOSURE c upvalue-подстановкой);
  5. заменяет call-site'ы  F(captures...)  на вызов поднятой фабрики;
  6. вычищает мёртвый runtime (dead locals в зоне prelude).

Честность: любой сбой (не наш формат, неизвестный опкод, неструктурный
байткод) -> функция остаётся виртуализированной, ошибка в stats.

ВАЖНО: декодеру нужен ИСХОДНЫЙ текст чанка (op-map восстанавливается
регулярками по сгенерированному runtime, unparse-переформатирование их
ломает). engine проставляет chunk.raw_source после парсинга.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from obfuscator.ast_nodes import (
    CallExpr, Chunk, FunctionExpr, IndexExpr, LocalAssignStat,
    LocalFunctionStat, NameExpr, Node, Stat, StringLit,
)
from obfuscator.utils.crypto import rc4_encrypt

from .base_decoder import BaseDecoder, DecoderStats


def _iter_fields(node):
    for fname in getattr(node, '__dataclass_fields__', {}):
        yield fname, getattr(node, fname, None)


class VMDevirtualizerDecoder(BaseDecoder):
    """Убирает собственный NZL VM: блоб -> поднятая Lua-функция."""

    NAME = 'vm_devirtualizer'

    KEY_LEN = 16
    MIN_BLOB_LEN = 64

    def run(self, chunk: Chunk) -> Tuple[Chunk, DecoderStats]:
        self.stats = DecoderStats(name=self.NAME)

        wrappers = self._find_wrappers(chunk)
        self.stats.scanned = len(wrappers)
        if not wrappers:
            return chunk, self.stats

        raw = getattr(chunk, 'raw_source', None)
        if not raw:
            self.stats.errors += 1
            self.stats.details.append('no raw_source on chunk (engine too old)')
            return chunk, self.stats

        from obfuscator.deobfuscator.vm_decompile.opmap_recovery import (
            recover_op_map,
        )
        known, _unknown = recover_op_map(raw)
        if not known:
            self.stats.errors += 1
            self.stats.details.append('op-map recovery failed on runtime')
            return chunk, self.stats

        from obfuscator.deobfuscator.vm_decompile.lifter import (
            LiftError, lift_proto,
        )
        from obfuscator.deobfuscator.vm_decompile.proto_decode import (
            BlobDecodeError, decode_blob,
        )

        lifted: Dict[str, FunctionExpr] = {}
        for fname, blob_lit, key_lit, _idx in wrappers:
            try:
                blob = blob_lit.value.encode('latin-1')
                key = key_lit.value.encode('latin-1')
                if len(key) != self.KEY_LEN:
                    raise BlobDecodeError(f'key len {len(key)} != 16')
                data = rc4_encrypt(blob, key)
                proto = decode_blob(data, known)
                lifted[fname] = lift_proto(proto)
            except (BlobDecodeError, LiftError, UnicodeEncodeError) as e:
                self.stats.errors += 1
                self.stats.details.append(
                    f"'{fname}' left virtualized: "
                    f"{type(e).__name__}: {str(e)[:60]}")
            except Exception as e:  # noqa: BLE001
                self.stats.errors += 1
                self.stats.details.append(
                    f"'{fname}' left virtualized: "
                    f"{type(e).__name__}: {str(e)[:60]}")

        if not lifted:
            return chunk, self.stats

        self.stats.replaced = self._replace_calls(chunk, lifted)

        zone = max(idx for _f, _b, _k, idx in wrappers
                   if _f in lifted) if lifted else -1
        removed = self._remove_dead_locals(chunk, zone)
        self.stats.details.append(
            f'devirtualized {len(lifted)}/{len(wrappers)} factories, '
            f'removed {removed} dead runtime statements')
        return chunk, self.stats

    # ── поиск wrapper'ов ───────────────────────────────────────
    def _find_wrappers(self, chunk: Chunk) -> List[Tuple[str, StringLit,
                                                         StringLit, int]]:
        out: List[Tuple[str, StringLit, StringLit, int]] = []
        top = chunk.body.statements if chunk.body else []
        for idx, st in enumerate(top):
            hit = self._match_wrapper(st)
            if hit is not None:
                out.append((hit[0], hit[1], hit[2], idx))
        return out

    def _match_wrapper(self, st: Stat):
        if not isinstance(st, LocalAssignStat):
            return None
        if len(st.names) != 1 or len(st.values) != 1:
            return None
        val = st.values[0]
        if not isinstance(val, CallExpr):
            return None
        if not isinstance(val.func, NameExpr):
            return None
        if len(val.args) != 2:
            return None
        blob, key = val.args
        if not (isinstance(blob, StringLit) and isinstance(key, StringLit)):
            return None
        if len(key.value) != self.KEY_LEN:
            return None
        if len(blob.value) < self.MIN_BLOB_LEN:
            return None
        return st.names[0], blob, key

    # ── замена call-site'ов ────────────────────────────────────
    def _fix_call(self, call: CallExpr,
                  lifted: Dict[str, FunctionExpr]) -> None:
        if isinstance(call.func, NameExpr) and call.func.name in lifted:
            call.func = lifted[call.func.name]
            self._n_replaced += 1

    def _replace_calls(self, node, lifted: Dict[str, FunctionExpr]) -> int:
        self._n_replaced = 0
        self._walk_calls(node, lifted)
        return self._n_replaced

    def _walk_calls(self, node, lifted: Dict[str, FunctionExpr]) -> None:
        fields = getattr(node, '__dataclass_fields__', None)
        if fields is None:
            return
        for _fname, fv in _iter_fields(node):
            if isinstance(fv, CallExpr):
                self._fix_call(fv, lifted)
                self._walk_calls(fv, lifted)
            elif isinstance(fv, Node):
                self._walk_calls(fv, lifted)
            elif isinstance(fv, list):
                for item in fv:
                    if isinstance(item, CallExpr):
                        self._fix_call(item, lifted)
                        self._walk_calls(item, lifted)
                    elif isinstance(item, Node):
                        self._walk_calls(item, lifted)
                    elif isinstance(item, tuple):
                        for sub in item:
                            if isinstance(sub, CallExpr):
                                self._fix_call(sub, lifted)
                                self._walk_calls(sub, lifted)
                            elif isinstance(sub, Node):
                                self._walk_calls(sub, lifted)

    # ── вычистка мёртвого runtime ──────────────────────────────
    def _remove_dead_locals(self, chunk: Chunk, zone_end: int) -> int:
        if zone_end < 0 or chunk.body is None:
            return 0
        stmts = chunk.body.statements
        removed = 0
        changed = True
        while changed:
            changed = False
            limit = min(zone_end, len(stmts) - 1)
            for i in range(limit + 1):
                st = stmts[i]
                names = self._defined_names(st)
                if not names:
                    continue
                if not self._values_removable(st):
                    continue
                refs = set()
                for st2 in stmts[i + 1:]:
                    self._collect_names(st2, refs)
                if refs & names:
                    continue
                stmts.pop(i)
                zone_end -= 1
                removed += 1
                changed = True
                break
        return removed

    @staticmethod
    def _defined_names(st: Stat) -> set:
        if isinstance(st, LocalFunctionStat):
            return {st.name}
        if isinstance(st, LocalAssignStat):
            return set(st.names)
        return set()

    @staticmethod
    def _values_removable(st: Stat) -> bool:
        """Удалять можно только «чистые» определения: функция, имя,
        литерал или вызов локальной фабрики (create_vm не имеет
        побочных эффектов кроме создания замыкания)."""
        if isinstance(st, LocalFunctionStat):
            return True
        if isinstance(st, LocalAssignStat):
            for v in st.values:
                if isinstance(v, (FunctionExpr, NameExpr, StringLit,
                                  CallExpr, IndexExpr)):
                    continue
                from obfuscator.ast_nodes import BoolLit, NilLit, NumberLit
                if isinstance(v, (BoolLit, NilLit, NumberLit)):
                    continue
                return False
            return True
        return False

    def _collect_names(self, node, acc: set) -> None:
        fields = getattr(node, '__dataclass_fields__', None)
        if fields is None:
            return
        for _fname, fv in _iter_fields(node):
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
            elif isinstance(fv, str):
                # LocalFunctionStat.name / LocalAssignStat.names —
                # определения, не ссылки; но строковые поля имён
                # параметров/полей тоже не NameExpr — игнорируем
                pass
