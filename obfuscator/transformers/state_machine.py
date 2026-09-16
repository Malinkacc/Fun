"""
NZL Studio Obfuscator - State Machine Dispatch (Sprint 3, obf side)
===================================================================
Превращает линейный блок инструкций в dispatch-автомат как у Luraph:

    local a = 1                     local state = 48211
    local b = a + 1         ->      while true do
    print(b)                          if state == 48211 then
                                        local a = 1
                                        state = 90110
                                      elseif state == 90110 then
                                        ...
                                      else
                                        break
                                      end
                                    end

Правила безопасности v1 (блок НЕ трогаем, если):
  - инструкций меньше min_stmts;
  - среди прямых инструкций блока есть Break/Continue/Goto
    (они принадлежат ВНЕШНЕМУ циклу, перенос сломает семантику);
  - блок уже является dispatch-обёрткой (повторный прогон).

Вложенные составные инструкции (if/for/while/functions) переносятся
ЦЕЛИКОМ — это безопасно. Тела функций обрабатываются рекурсивно
(config.flatten_functions).

Порядок обхода: state_machine ставится ДО number_obfuscator, чтобы
number-обфускатор зашифровал id состояний (0X..., bit32...) —
деобфускатор сначала свернёт их обратно (number expr fold),
и только потом StateMachineUnflattener увидит литералы.

Adversarial-пара: decoders/state_machine_unflattener.py.
"""

import random
from dataclasses import dataclass
from typing import Optional

from ..ast_nodes import (
    Node, NodeTransformer,
    Chunk, Block,
    BoolLit, NumberLit, StringLit, NameExpr, BinaryOp, IndexExpr, NilLit,
    AssignStat, LocalAssignStat, WhileStat, IfStat, BreakStat, TableExpr,
    ContinueStat, GotoStat, ReturnStat, FunctionExpr, LocalFunctionStat,
    FunctionDeclStat,
)
from ..utils.random_gen import make_rng


# ==================== КОНФИГ ====================

@dataclass
class StateMachineConfig:
    probability: float = 1.0
    min_stmts: int = 3
    flatten_functions: bool = True
    state_name: Optional[str] = None     # None -> выбрать из пула ниже
    id_min: int = 1024
    id_max: int = 0xFFFF

    @classmethod
    def balanced(cls):
        return cls()

    @classmethod
    def aggressive(cls):
        return cls(min_stmts=2, id_min=0x10000, id_max=0xFFFFFF)


@dataclass
class StateMachineStats:
    blocks_seen: int = 0
    blocks_flattened: int = 0
    statements_dispatched: int = 0
    blocks_skipped: int = 0

    def report(self) -> str:
        return (f"  Blocks seen:      {self.blocks_seen}\n"
                f"  Blocks flattened: {self.blocks_flattened}\n"
                f"  Statements disp.: {self.statements_dispatched}")


# имена в стиле Luraph (короткие/служебные), детектор compare их видит
_NAME_POOL = ("state", "q", "st", "sm", "_sm")

_HOMO = "Il1O0"


class StateMachineTransformer:
    def __init__(self, rng: random.Random, config: Optional[StateMachineConfig] = None):
        self.rng = rng
        self.config = config or StateMachineConfig()
        self.stats = StateMachineStats()

    # ------------------------------------------------------------
    # eligibility
    # ------------------------------------------------------------

    @staticmethod
    def _is_dispatch_wrapper(block: Block) -> bool:
        """Уже обёрнуто нами: [local hoisted..., local X = N, while true do if X == ... ]"""
        stmts = block.statements or []
        if len(stmts) < 2:
            return False
        first, second = stmts[-2], stmts[-1]
        for pre in stmts[:-2]:
            if not (isinstance(pre, LocalAssignStat) and not pre.values):
                return False
        return (
            isinstance(first, LocalAssignStat)
            and len(first.names) == 1
            and isinstance(second, WhileStat)
            and isinstance(second.cond, BoolLit)
            and second.cond.value is True
        )

    @staticmethod
    def _top_local_names(stmts) -> list:
        """Имена top-level local'ов блока (порядок объявления)."""
        names = []
        for st in stmts:
            if isinstance(st, LocalAssignStat):
                names.extend(st.names)
        return names

    def _eligible(self, block: Block) -> bool:
        stmts = block.statements or []
        self.stats.blocks_seen += 1
        if len(stmts) < self.config.min_stmts:
            return False
        for st in stmts:
            if isinstance(st, (BreakStat, ContinueStat, GotoStat, ReturnStat)):
                return False
        if self._is_dispatch_wrapper(block):
            return False
        # повторное объявление того же local = другая переменная в Lua:
        # hoist склеит их и сломает замыкания — не трогаем такой блок
        names = self._top_local_names(stmts)
        if len(names) != len(set(names)):
            return False
        return True

    # ------------------------------------------------------------
    # flatten one block
    # ------------------------------------------------------------

    def _flatten(self, block: Block) -> None:
        stmts = list(block.statements)
        # PIN: `local X = {...}` (string array / любые таблицы-данные)
        # остаётся ЛИНЕЙНЫМ перед автоматом — иначе hoist превратит его
        # в `X = {...}` внутри ветки и сломает string-array детектор/декодер
        pinned = []
        if (
            stmts
            and isinstance(stmts[0], LocalAssignStat)
            and len(stmts[0].values) == 1
            and isinstance(stmts[0].values[0], TableExpr)
        ):
            pinned.append(stmts.pop(0))
        if len(stmts) < self.config.min_stmts:
            block.statements = pinned + stmts
            return
        n = len(stmts)

        ids = []
        while len(ids) < n:
            cand = self.rng.randint(self.config.id_min, self.config.id_max)
            if cand not in ids:
                ids.append(cand)

        order = list(range(n))
        self.rng.shuffle(order)

        # HOIST: local'ы веток видимы только в своей ветке — объявляем их
        # ДО while, а в ветках оставляем присваивания (семантика линейного кода)
        hoisted = []
        arm_stmts_map = {}
        for idx, st in enumerate(stmts):
            if isinstance(st, LocalAssignStat):
                for nm in st.names:
                    if nm not in hoisted:
                        hoisted.append(nm)
                values = list(st.values) if st.values else []
                targets = [
                    NameExpr(line=getattr(st, 'line', 0), name=nm) for nm in st.names
                ]
                while len(values) < len(targets):
                    values.append(NilLit(line=getattr(st, 'line', 0)))
                arm_stmts_map[idx] = AssignStat(
                    line=getattr(st, 'line', 0), targets=targets, values=values
                )
            else:
                arm_stmts_map[idx] = st

        name = self.config.state_name or self.rng.choice(_NAME_POOL)
        if name == "_sm":
            name = "_" + "".join(self.rng.choice(_HOMO) for _ in range(4))

        branches = []
        for pos, idx in enumerate(order):
            # ВАЖНО: переходы идут в ИСХОДНОМ порядке инструкций (idx -> idx+1),
            # shuffle меняет только ТЕКСТОВЫЙ порядок веток и значения id
            nxt = ids[idx + 1] if idx + 1 < n else 0
            arm_stmts = [
                arm_stmts_map[idx],
                AssignStat(
                    line=getattr(stmts[idx], 'line', 0),
                    targets=[NameExpr(line=getattr(stmts[idx], 'line', 0), name=name)],
                    values=[NumberLit(line=getattr(stmts[idx], 'line', 0), value=nxt)],
                ),
            ]
            cond = BinaryOp(
                line=getattr(stmts[idx], 'line', 0),
                left=NameExpr(line=getattr(stmts[idx], 'line', 0), name=name),
                op='==',
                right=NumberLit(line=getattr(stmts[idx], 'line', 0), value=ids[idx]),
            )
            branches.append((cond, Block(line=getattr(stmts[idx], 'line', 0),
                                         statements=arm_stmts)))

        if_stat = IfStat(
            line=1,
            branches=branches,
            else_block=Block(line=1, statements=[BreakStat(line=1)]),
        )
        while_stat = WhileStat(
            line=1,
            cond=BoolLit(line=1, value=True),
            body=Block(line=1, statements=[if_stat]),
        )
        entry = LocalAssignStat(
            line=1,
            names=[name],
            values=[NumberLit(line=1, value=ids[0])],   # id ПЕРВОЙ инструкции
            attribs=[None],
        )

        prelude = []
        if hoisted:
            prelude.append(LocalAssignStat(
                line=1, names=list(hoisted), values=[], attribs=[None] * len(hoisted),
            ))
        block.statements = pinned + prelude + [entry, while_stat]
        self.stats.blocks_flattened += 1
        self.stats.statements_dispatched += n

    # ------------------------------------------------------------
    # recursion
    # ------------------------------------------------------------

    def _visit_functions(self, node) -> None:
        """Рекурсивно обработать тела функций ВНУТРИ инструкций блока."""
        if node is None or not hasattr(node, '__dataclass_fields__'):
            return
        from dataclasses import fields as dc_fields
        if isinstance(node, FunctionExpr):
            self._process_block(node.body)
            return
        if isinstance(node, LocalFunctionStat):
            self._process_block(node.func.body)
            return
        if isinstance(node, FunctionDeclStat):
            self._process_block(node.func.body)
            return
        for f in dc_fields(node):
            v = getattr(node, f.name, None)
            if isinstance(v, (list, tuple)):
                for item in v:
                    if isinstance(item, tuple):
                        for sub in item:
                            self._visit_functions(sub)
                    else:
                        self._visit_functions(item)
            elif hasattr(v, '__dataclass_fields__'):
                self._visit_functions(v)

    def _process_block(self, block: Block) -> None:
        if block is None:
            return
        if self.config.flatten_functions:
            for st in list(block.statements or []):
                self._visit_functions(st)
            rt = getattr(block, 'return_stat', None)
            if rt is not None:
                self._visit_functions(rt)
        if self._eligible(block) and self.rng.random() <= self.config.probability:
            self._flatten(block)

    def transform(self, chunk: Chunk) -> Chunk:
        self._process_block(chunk.body)
        return chunk


def obfuscate_state_machine(
    ast_chunk: Chunk,
    rng: Optional[random.Random] = None,
    config: Optional[StateMachineConfig] = None,
) -> tuple:
    """High-level API: (modified_ast, stats)."""
    if rng is None:
        rng = make_rng()
    t = StateMachineTransformer(rng, config)
    return t.transform(ast_chunk), t.stats


# ==================== SELF-TEST ====================

if __name__ == '__main__':
    from ..lexer import Lexer
    from ..parser import Parser
    from ..ast_unparser import unparse

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
        'local a = 1\n'
        'local b = a + 1\n'
        'local c = b * 3\n'
        'print(c)\n'
        'warn("done")\n'
        'for i = 1, 2 do print(i) end\n'
    )
    chunk = Parser(Lexer(src).tokenize()).parse()
    new_chunk, stats = obfuscate_state_machine(chunk, make_rng(seed=5))
    out = unparse(new_chunk)

    check("while true present", "while true do" in out)
    check("dispatch ifs present", out.count("== ") >= 5, f"arms={out.count('== ')}")
    check("break in else", "break" in out)
    check("no original order left", out.index("a = 1") > out.index("while true"))
    check("locals hoisted before while",
          out.index("local a") < out.index("while true"),
          out.splitlines()[0][:40])
    reparse_ok = True
    try:
        Parser(Lexer(out).tokenize()).parse()
    except Exception as e:  # noqa: BLE001
        reparse_ok = False
        print("     reparse:", e)
    check("output reparseable", reparse_ok)
    check("stats", stats.blocks_flattened >= 1 and stats.statements_dispatched >= 6,
          f"flat={stats.blocks_flattened}, disp={stats.statements_dispatched}")

    # блок с break НЕ трогаем
    src2 = (
        'for i = 1, 10 do\n'
        '  if i > 3 then break end\n'
        '  print(i)\n'
        'end\n'
        'local x = 1\n'
        'local y = 2\n'
        'local z = 3\n'
        'print(x + y + z)\n'
    )
    chunk2 = Parser(Lexer(src2).tokenize()).parse()
    _c2, stats2 = obfuscate_state_machine(chunk2, make_rng(seed=6))
    out2 = unparse(_c2)
    check("inner break safe (for body not flattened into outer)",
          "for i = 1, 10 do" in out2)

    print()
    print(f"StateMachineTransformer tests: {passed}/{passed + failed}")
    if failed:
        raise SystemExit(1)
    print("All state machine tests passed!")
