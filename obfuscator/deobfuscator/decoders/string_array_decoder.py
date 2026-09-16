"""
NZL Deobfuscator - String Array Decoder (Sprint 2, deobf side)
==============================================================
Инлайнит обратно вынесенные строковые массивы:

    local _Il1I0O = {"Hello", "World"}     print("Hello")
    print(_Il1I0O[1])              ->      warn("World")
    warn(_Il1I0O[2])

Условия инлайна (консервативно, иначе НЕ трогаем):
  1. `local X = {...}` — один name, одна value, таблица из чисто
     строковых массивных полей (key=None, is_name=False);
  2. ВСЕ использования X в chunk'е — это `X[<целый литерал в диапазоне>]`;
     любое другое использование (X как аргумент, X[i] с переменным i,
     присваивание X = ...) дисквалифицирует кандидата;
  3. после инлайна statement с таблицей удаляется.

Пайплайн крутит passes, поэтому если элементы таблицы ещё зашифрованы
(string.char / decrypt-вызовы), сначала сработают string.char fold и
sandbox decoder, и только потом этот декодер увидит чистые StringLit.
"""

from dataclasses import fields, is_dataclass

from obfuscator.deobfuscator.core.base import (
    NumberLit, StringLit, NameExpr, IndexExpr, TableExpr,
    LocalAssignStat,
)
from .base_decoder import BaseDecoder


def _iter_child_nodes(node):
    """(field_name, child) для всех Node-потомков dataclass-узла."""
    if node is None or not is_dataclass(node):
        return
    for f in fields(node):
        v = getattr(node, f.name, None)
        if isinstance(v, (list, tuple)):
            for item in v:
                if is_dataclass(item):
                    yield f.name, item
        elif is_dataclass(v):
            yield f.name, v


class StringArrayDecoder(BaseDecoder):
    NAME = "string array inline"

    # ------------------------------------------------------------
    # поиск кандидатов
    # ------------------------------------------------------------

    def _find_candidates(self, chunk):
        """Список (block, stmt, name, [str values])."""
        out = []

        def walk(node):
            if isinstance(node, LocalAssignStat) and self._is_array_assign(node):
                table = node.values[0]
                values = [f.value.value for f in table.fields]
                out.append((node, node.names[0], values))
            for _name, child in _iter_child_nodes(node):
                walk(child)

        walk(chunk)
        return out

    @staticmethod
    def _is_array_assign(node: LocalAssignStat) -> bool:
        if len(node.names) != 1 or len(node.values) != 1:
            return False
        table = node.values[0]
        if not isinstance(table, TableExpr) or not table.fields:
            return False
        for f in table.fields:
            if f.key is not None or f.is_name:
                return False
            if not isinstance(f.value, StringLit):
                return False
        return True

    # ------------------------------------------------------------
    # анализ использований
    # ------------------------------------------------------------

    def _scan_uses(self, chunk, name: str, count: int):
        """
        Возвращает (good_nodes, safe).
        good_nodes — IndexExpr вида name[<int 1..count>];
        safe=False, если имя используется как-то ещё.
        """
        good = []
        safe = True

        def walk(node, parent_index_expr=None):
            nonlocal safe
            if isinstance(node, NameExpr):
                if node.name == name:
                    # допустимо ТОЛЬКО как obj у IndexExpr с константным индексом
                    if parent_index_expr is None:
                        safe = False
                    # иначе проверку сделал родитель
                return
            if isinstance(node, IndexExpr):
                const_idx = (
                    isinstance(node.index, NumberLit)
                    and isinstance(node.index.value, int)
                    and not node.is_dot
                    and 1 <= int(node.index.value) <= count
                )
                if isinstance(node.obj, NameExpr) and node.obj.name == name:
                    if const_idx:
                        good.append(node)
                    else:
                        safe = False
                    # детей не обходим (name уже учтён), но index проверим
                    walk(node.index, node)
                    return
                walk(node.obj, node)
                walk(node.index, node)
                return
            for _fname, child in _iter_child_nodes(node):
                walk(child, None)

        walk(chunk)
        return good, safe

    # ------------------------------------------------------------
    # замена
    # ------------------------------------------------------------

    def _replace_uses(self, chunk, name: str, values):
        replaced = 0

        def walk(node):
            nonlocal replaced
            for fname, child in list(_iter_child_nodes(node)):
                if (
                    isinstance(child, IndexExpr)
                    and isinstance(child.obj, NameExpr)
                    and child.obj.name == name
                    and isinstance(child.index, NumberLit)
                    and not child.is_dot
                ):
                    idx = int(child.index.value)
                    if 1 <= idx <= len(values):
                        new_node = StringLit(
                            line=getattr(child, 'line', 0),
                            value=values[idx - 1],
                        )
                        if isinstance(getattr(node, fname, None), list):
                            lst = getattr(node, fname)
                            for pos, item in enumerate(lst):
                                if item is child:
                                    lst[pos] = new_node
                                    break
                        else:
                            setattr(node, fname, new_node)
                        replaced += 1
                        continue
                walk(child)

        walk(chunk)
        return replaced

    @staticmethod
    def _remove_assign(chunk, target_stmt):
        removed = False

        def walk(node):
            nonlocal removed
            for fname, child in list(_iter_child_nodes(node)):
                if child is target_stmt:
                    lst = getattr(node, fname)
                    if isinstance(lst, list):
                        for pos, item in enumerate(lst):
                            if item is child:
                                del lst[pos]
                                removed = True
                                break
                        if removed:
                            continue
                walk(child)

        walk(chunk)
        return removed

    # ------------------------------------------------------------
    # entry
    # ------------------------------------------------------------

    def run(self, chunk):
        from .base_decoder import DecoderStats
        self.stats = DecoderStats(name=self.NAME)

        for _stmt, name, values in self._find_candidates(chunk):
            self.stats.scanned += 1
            good, safe = self._scan_uses(chunk, name, len(values))
            if not safe or not good:
                continue
            replaced = self._replace_uses(chunk, name, values)
            if replaced and self._remove_assign(chunk, _stmt):
                self.stats.replaced += replaced
                self.stats.details.append(f"inlined {name}: {replaced} uses")

        return chunk, self.stats


# ============================================================
# SELF-TEST
# ============================================================

if __name__ == '__main__':
    from obfuscator.deobfuscator.core.base import parse_code, ast_to_code

    passed = failed = 0

    def check(name, cond, extra=""):
        global passed, failed
        if cond:
            passed += 1
            print(f"[OK] {name}" + (f"  {extra}" if extra else ""))
        else:
            failed += 1
            print(f"[XX] {name}" + (f"  {extra}" if extra else ""))

    src = (
        'local _Il1I0O = {"Hello", "World", "loop body"}\n'
        'print(_Il1I0O[1])\n'
        'warn(_Il1I0O[2])\n'
        'for i = 1, 3 do print(_Il1I0O[3]) end\n'
    )
    chunk = parse_code(src)
    dec = StringArrayDecoder()
    new_chunk, stats = dec.run(chunk)
    out = ast_to_code(new_chunk)
    check("strings inlined", '"Hello"' in out and '"World"' in out, out.replace("\n", " | ")[:80])
    check("table removed", "_Il1I0O" not in out)
    check("stats replaced", stats.replaced == 3, f"replaced={stats.replaced}")

    # небезопасный кандидат: имя уходит аргументом
    src2 = (
        'local T = {"aa", "bb"}\n'
        'print(T[1])\n'
        'warn(T)\n'
    )
    chunk2 = parse_code(src2)
    _c2, stats2 = StringArrayDecoder().run(chunk2)
    out2 = ast_to_code(chunk2)
    check("unsafe candidate untouched", 'local T = {"aa", "bb"}' in out2, out2.replace("\n", " | ")[:60])

    # переменный индекс — тоже нет
    src3 = (
        'local T = {"aa", "bb"}\n'
        'local i = 1\n'
        'print(T[i])\n'
    )
    chunk3 = parse_code(src3)
    _c3, stats3 = StringArrayDecoder().run(chunk3)
    out3 = ast_to_code(chunk3)
    check("variable index untouched", "T[i]" in out3)

    print()
    print(f"StringArrayDecoder tests: {passed}/{passed + failed}")
    if failed:
        raise SystemExit(1)
    print("All string array decoder tests passed!")
