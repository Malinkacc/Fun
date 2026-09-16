"""
NZL Studio Obfuscator - String Array Indexing (Sprint 2, obf side)
==================================================================
Выносит строковые литералы в chunk-массив и заменяет использования
на индексацию — фича, которую имеет Luraph v14+:

    print("Hello")                 local _Il1I0O = {"Hello", "World"}
    warn("World")          ->      print(_Il1I0O[1])
                                   warn(_Il1I0O[2])

Детали:
  - дубликаты строк схлопываются в один элемент (как у Luraph);
  - порядок элементов shuffle'ится rng'ом (читаемость вниз);
  - НЕ трогаем:
      * t.field          (IndexExpr.is_dot — индекс это имя поля);
      * {x = 1}          (TableField.is_name — ключ-идентификатор);
      * части InterpStringLit (это сырые str, не StringLit-узлы);
  - массив вставляется ПЕРВЫМ statement'ом chunk'а, поэтому виден
    всем функциям ниже (upvalue);
  - стадия ставится ДО string_encryptor: тот зашифрует УЖЕ вынесенные
    строки прямо в таблице — получаем обе фичи сразу.

Adversarial-пара: decoders/string_array_decoder.py инлайнит обратно.
"""

import random
from dataclasses import dataclass, field
from typing import Optional

from ..ast_nodes import (
    Node, NodeTransformer, NodeVisitor,
    Chunk, Block,
    StringLit, NameExpr, IndexExpr, TableExpr, TableField,
    LocalAssignStat,
)
from ..utils.random_gen import make_rng


# ==================== КОНФИГ ====================

@dataclass
class StringArrayConfig:
    probability: float = 0.85      # шанс вынести конкретную строку
    min_len: int = 2               # короче — не трогаем ("" / " ")
    max_len: int = 200             # длиннее — не трогаем (blobs)
    max_strings: int = 250         # потолок уникальных (Luau 200 locals не при чём, но таблицу не раздуваем)
    shuffle: bool = True
    array_name: Optional[str] = None

    @classmethod
    def conservative(cls):
        return cls(probability=0.5, shuffle=False)

    @classmethod
    def balanced(cls):
        return cls(probability=0.85)

    @classmethod
    def aggressive(cls):
        return cls(probability=1.0, min_len=1, max_len=500, max_strings=500)


@dataclass
class StringArrayStats:
    total_strings: int = 0
    unique: int = 0
    hoisted: int = 0
    replaced_uses: int = 0
    skipped_short: int = 0
    skipped_long: int = 0
    skipped_prob: int = 0
    bytes_added: int = 0

    def report(self) -> str:
        return (f"  Strings found:   {self.total_strings}\n"
                f"  Unique:          {self.unique}\n"
                f"  Hoisted:         {self.hoisted}\n"
                f"  Uses replaced:   {self.replaced_uses}\n"
                f"  Bytes added:     {self.bytes_added}")


# ==================== COLLECTOR ====================

class _StringCollector(NodeVisitor):
    """Собирает значения StringLit, пропуская небезопасные позиции."""

    def __init__(self):
        self.values = []          # порядок первого появления
        self.total = 0

    def visit_StringLit(self, node):
        self.total += 1
        if node.value not in self.values:
            self.values.append(node.value)
        return node

    def visit_IndexExpr(self, node):
        self.visit(node.obj)
        if not node.is_dot:       # t["x"] можно, t.x — НЕТ
            self.visit(node.index)
        return node

    def visit_TableField(self, node):
        if not node.is_name and node.key is not None:
            self.visit(node.key)
        self.visit(node.value)
        return node


class _StringReplacer(NodeTransformer):
    """Заменяет StringLit на NameArray[i] для вынесенных значений."""

    def __init__(self, index: dict, name: str, stats: StringArrayStats):
        super().__init__()
        self.index = index
        self.name = name
        self.stats = stats

    def visit_StringLit(self, node):
        pos = self.index.get(node.value)
        if pos is None:
            return node
        self.stats.replaced_uses += 1
        return IndexExpr(
            line=getattr(node, 'line', 0),
            obj=NameExpr(line=getattr(node, 'line', 0), name=self.name),
            index=_num(node, pos),
            is_dot=False,
        )

    def visit_IndexExpr(self, node):
        node.obj = self.visit(node.obj)
        if not node.is_dot:
            node.index = self.visit(node.index)
        return node

    def visit_TableField(self, node):
        if not node.is_name and node.key is not None:
            node.key = self.visit(node.key)
        node.value = self.visit(node.value)
        return node


def _num(node, pos: int):
    from ..ast_nodes import NumberLit
    return NumberLit(line=getattr(node, 'line', 0), value=pos)


# ==================== TRANSFORMER ====================

_HOMOGLYPHS = "Il1O0"


def _make_array_name(rng: random.Random) -> str:
    return "_" + "".join(rng.choice(_HOMOGLYPHS) for _ in range(6))


class StringArrayTransformer:
    """High-level: collect -> shuffle -> replace -> prepend table."""

    def __init__(self, rng: random.Random, config: Optional[StringArrayConfig] = None):
        self.rng = rng
        self.config = config or StringArrayConfig()
        self.stats = StringArrayStats()

    def transform(self, chunk: Chunk) -> Chunk:
        cfg = self.config

        collector = _StringCollector()
        collector.visit(chunk)
        self.stats.total_strings = collector.total

        candidates = [v for v in collector.values if isinstance(v, str)]
        self.stats.unique = len(candidates)

        hoisted = []
        for v in candidates:
            if len(v) < cfg.min_len:
                self.stats.skipped_short += 1
                continue
            if len(v) > cfg.max_len:
                self.stats.skipped_long += 1
                continue
            if self.rng.random() > cfg.probability:
                self.stats.skipped_prob += 1
                continue
            hoisted.append(v)
            if len(hoisted) >= cfg.max_strings:
                break

        if not hoisted:
            return chunk

        if cfg.shuffle:
            self.rng.shuffle(hoisted)

        name = cfg.array_name or _make_array_name(self.rng)
        index = {v: i + 1 for i, v in enumerate(hoisted)}   # Lua: база 1

        replacer = _StringReplacer(index, name, self.stats)
        chunk = replacer.visit(chunk)

        table = TableExpr(
            line=1,
            fields=[
                TableField(key=None, value=StringLit(line=1, value=v), is_name=False)
                for v in hoisted
            ],
        )
        assign = LocalAssignStat(line=1, names=[name], values=[table], attribs=[None])
        chunk.body.statements.insert(0, assign)

        self.stats.hoisted = len(hoisted)
        self.stats.bytes_added = sum(len(v) + 4 for v in hoisted)
        return chunk


def obfuscate_string_array(
    ast_chunk: Chunk,
    rng: Optional[random.Random] = None,
    config: Optional[StringArrayConfig] = None,
) -> tuple:
    """High-level API: (modified_ast, stats)."""
    if rng is None:
        rng = make_rng()
    transformer = StringArrayTransformer(rng, config)
    return transformer.transform(ast_chunk), transformer.stats


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

    src = '''
local msg = "Hello"
print("Hello")
warn("World")
local t = {["key"] = "value", plain = "skipme"}
print(t.key, t["key"], t.plain)
for i = 1, 3 do print("loop body") end
local f = function() return "inner func string" end
print(f())
'''
    chunk = Parser(Lexer(src).tokenize()).parse()
    rng = make_rng(seed=42)
    new_chunk, stats = obfuscate_string_array(chunk, rng, StringArrayConfig(probability=1.0))
    out = unparse(new_chunk)

    check("array declared first", out.splitlines()[0].startswith("local _"), out.splitlines()[0][:40])
    check("no inline 'Hello' use left", out.count('"Hello"') == 1,
          f"count={out.count('Hello')}")
    check("indexing present", "[1]" in out and "[2]" in out)
    check("dot access untouched", "t.key" in out)
    check("name-key untouched", "plain = " in out)
    check("computed key became index", 't["key"]' not in out)

    reparse_ok = True
    try:
        Parser(Lexer(out).tokenize()).parse()
    except Exception as e:  # noqa: BLE001
        reparse_ok = False
        print(f"     reparse error: {e}")
    check("output reparseable", reparse_ok)
    check("stats sane", stats.hoisted >= 5 and stats.replaced_uses >= 6,
          f"hoisted={stats.hoisted}, uses={stats.replaced_uses}")

    import re as _re
    m = _re.search(r'local\s+(_\w+)\s*=\s*\{', out)
    check("table header parses from output", m is not None, f"name={m.group(1) if m else None}")

    print()
    print(f"StringArrayTransformer tests: {passed}/{passed + failed}")
    if failed:
        raise SystemExit(1)
    print("All string array tests passed!")
