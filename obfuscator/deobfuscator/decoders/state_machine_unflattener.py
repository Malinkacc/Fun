"""
NZL Deobfuscator - State Machine Unflattener (Sprint 3, deobf side)
===================================================================
Распознаёт dispatch-автомат NZL (и похожие линейные цепочки) и
возвращает линейный код:

    local state = 48211               local a = 1
    while true do                     local b = a + 1
      if state == 48211 then          print(b)
        local a = 1
        state = 90110         ->
      elseif ...
      else break end
    end

Паттерн (строгий, иначе SKIP — чужой код не ломаем):
  [local X = <int>]  сразу за ним  [while true do <if-chain> end]
  - все ветки if: `X == <int-литерал>` (уникальные id);
  - тело ветки: исходные инструкции + последняя `X = <int>` (переход)
    ИЛИ `break` (терминатор);
  - else-блок: ровно [break];
  - имя X не встречается больше нигде в блоке и внутри тел веток
    (кроме условия/перехода).

Цепочка восстанавливается обходом переходов от entry-id; защиты:
циклы, битые переходы, next=0 => конец (else break).

Порядок в pipeline: ПОСЛЕ number expr fold (id могут быть зашифрованы
как 0X.../bit32... — fold вернёт литералы).
"""

from dataclasses import fields, is_dataclass

from obfuscator.deobfuscator.core.base import (
    NumberLit, BoolLit, NameExpr, BinaryOp,
    AssignStat, LocalAssignStat, WhileStat, IfStat, BreakStat, Block,
)
from .base_decoder import BaseDecoder


def _iter_children(node):
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


class StateMachineUnflattener(BaseDecoder):
    NAME = "state machine unflatten"

    # ------------------------------------------------------------
    # pattern helpers
    # ------------------------------------------------------------

    @staticmethod
    def _is_entry(stat):
        return (
            isinstance(stat, LocalAssignStat)
            and len(stat.names) == 1
            and len(stat.values) == 1
            and isinstance(stat.values[0], NumberLit)
            and isinstance(stat.values[0].value, int)
        )

    @staticmethod
    def _is_true_while(stat):
        return (
            isinstance(stat, WhileStat)
            and isinstance(stat.cond, BoolLit)
            and stat.cond.value is True
        )

    def _parse_dispatch(self, while_stat, name: str):
        """
        Возвращает {id: (stmts, next_id|None)} или None, если не паттерн.
        next_id=None означает терминатор (break в конце ветки).
        """
        body = while_stat.body
        if not isinstance(body, Block) or len(body.statements or []) != 1:
            return None
        if getattr(body, 'return_stat', None) is not None:
            return None
        if_stat = body.statements[0]
        if not isinstance(if_stat, IfStat):
            return None
        if if_stat.else_block is None:
            return None
        else_stmts = if_stat.else_block.statements or []
        if len(else_stmts) != 1 or not isinstance(else_stmts[0], BreakStat):
            return None
        if getattr(if_stat.else_block, 'return_stat', None) is not None:
            return None

        arms = {}
        for cond, block in if_stat.branches:
            if not (
                isinstance(cond, BinaryOp)
                and cond.op == '=='
                and isinstance(cond.left, NameExpr)
                and cond.left.name == name
                and isinstance(cond.right, NumberLit)
                and isinstance(cond.right.value, int)
            ):
                return None
            sid = int(cond.right.value)
            if sid in arms:
                return None
            if not isinstance(block, Block) or getattr(block, 'return_stat', None) is not None:
                return None
            stmts = list(block.statements or [])
            if not stmts:
                return None
            last = stmts[-1]
            if (
                isinstance(last, AssignStat)
                and len(last.targets) == 1
                and isinstance(last.targets[0], NameExpr)
                and last.targets[0].name == name
                and len(last.values) == 1
                and isinstance(last.values[0], NumberLit)
            ):
                nxt = int(last.values[0].value)
                core = stmts[:-1]
            elif isinstance(last, BreakStat):
                nxt = None
                core = stmts[:-1]
            else:
                return None
            # имя X не должно светиться внутри тела ветки
            for st in core:
                if self._name_used(st, name):
                    return None
            arms[sid] = (core, nxt)
        return arms

    @staticmethod
    def _name_used(node, name: str) -> bool:
        if isinstance(node, NameExpr):
            return node.name == name
        for _f, child in _iter_children(node):
            if StateMachineUnflattener._name_used(child, name):
                return True
        return False

    # ------------------------------------------------------------
    # chain walk
    # ------------------------------------------------------------

    def _collect_chain(self, arms, entry):
        out = []
        cur = entry
        seen = set()
        while cur is not None and cur != 0:
            if cur in seen or cur not in arms:
                return None
            seen.add(cur)
            core, nxt = arms[cur]
            out.extend(core)
            cur = nxt
        return out

    # ------------------------------------------------------------
    # one block
    # ------------------------------------------------------------

    @staticmethod
    def _is_bare_local(stat):
        """`local a, b` без значений — hoist-объявление обфускатора."""
        return isinstance(stat, LocalAssignStat) and not stat.values

    def _relocalize(self, chain, declared):
        """
        Первое присваивание каждому hoisted-имени превращаем обратно
        в local (иначе переменные стали бы глобальными).
        """
        if not declared:
            return chain
        localized = set()
        out = []
        for st in chain:
            if (
                isinstance(st, AssignStat)
                and st.targets
                and all(
                    isinstance(t, NameExpr) and t.name in declared and t.name not in localized
                    for t in st.targets
                )
            ):
                for t in st.targets:
                    localized.add(t.name)
                out.append(LocalAssignStat(
                    line=getattr(st, 'line', 0),
                    names=[t.name for t in st.targets],
                    values=list(st.values),
                    attribs=[None] * len(st.targets),
                ))
            else:
                out.append(st)
        return out

    def _unflatten_block(self, block: Block) -> int:
        stmts = block.statements or []
        i = 0
        done = 0
        while i < len(stmts) - 1:
            entry_stat, while_stat = stmts[i], stmts[i + 1]
            if not (self._is_entry(entry_stat) and self._is_true_while(while_stat)):
                i += 1
                continue
            name = entry_stat.names[0]
            arms = self._parse_dispatch(while_stat, name)
            chain = self._collect_chain(arms, int(entry_stat.values[0].value)) if arms else None
            ok = chain is not None
            # поглощаем hoist-объявления (`local a, b`) перед парой
            start = i
            declared = []
            while start > 0 and self._is_bare_local(stmts[start - 1]):
                declared = list(stmts[start - 1].names) + declared
                start -= 1
            if ok:
                # имя не должно использоваться вне пары (entry, while) и hoist'ов
                rest = stmts[:start] + stmts[i + 2:]
                for st in rest:
                    if self._name_used(st, name):
                        ok = False
                        break
                rt = getattr(block, 'return_stat', None)
                if ok and rt is not None and self._name_used(rt, name):
                    ok = False
            if not ok:
                i += 1
                continue
            self.stats.scanned += 1
            chain = self._relocalize(chain, declared)
            stmts = stmts[:start] + chain + stmts[i + 2:]
            block.statements = stmts
            self.stats.replaced += 1
            self.stats.details.append(f"unflattened '{name}' ({len(chain)} stmts)")
            done += 1
            # не двигаем i: на этом месте теперь линейный код,
            # внутри которого может лежать ещё одна обёртка
        return done

    # ------------------------------------------------------------
    # entry
    # ------------------------------------------------------------

    def run(self, chunk):
        from .base_decoder import DecoderStats
        self.stats = DecoderStats(name=self.NAME)

        def walk(node):
            if isinstance(node, Block):
                self._unflatten_block(node)
            for _f, child in list(_iter_children(node)):
                walk(child)

        walk(chunk)
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
        'local state = 300\n'
        'while true do\n'
        '  if state == 300 then\n'
        '    local a = 1\n'
        '    state = 100\n'
        '  elseif state == 100 then\n'
        '    local b = a + 1\n'
        '    state = 200\n'
        '  elseif state == 200 then\n'
        '    print(b)\n'
        '    state = 0\n'
        '  else\n'
        '    break\n'
        '  end\n'
        'end\n'
    )
    chunk = parse_code(src)
    _c, stats = StateMachineUnflattener().run(chunk)
    out = ast_to_code(chunk)
    check("linear restored", out.strip().startswith("local a = 1"),
          out.replace("\n", " | ")[:70])
    check("order correct", out.index("local a = 1") < out.index("local b = a + 1") < out.index("print(b)"))
    check("dispatch gone", "while true" not in out and "state" not in out)
    check("stats", stats.replaced == 1, f"replaced={stats.replaced}")

    # чужой while true (не dispatch) не трогаем
    src2 = (
        'local i = 0\n'
        'while true do\n'
        '  i = i + 1\n'
        '  if i > 5 then break end\n'
        'end\n'
        'print(i)\n'
    )
    chunk2 = parse_code(src2)
    _c2, stats2 = StateMachineUnflattener().run(chunk2)
    out2 = ast_to_code(chunk2)
    check("plain while untouched", "while true do" in out2 and stats2.replaced == 0)

    print()
    print(f"StateMachineUnflattener tests: {passed}/{passed + failed}")
    if failed:
        raise SystemExit(1)
    print("All state machine unflattener tests passed!")
