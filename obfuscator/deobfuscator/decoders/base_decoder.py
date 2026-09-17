"""
NZL Deobfuscator - Base Decoder
================================
Общий интерфейс для всех декодеров.

Декодер = NodeTransformer, который умеет:
- name           — короткое имя ("string.char folding")
- run(chunk)     — прогнать по AST, вернуть (new_chunk, stats)
- stats          — сколько узлов заменено
"""

from dataclasses import dataclass, field
from obfuscator.deobfuscator.core.base import NodeTransformer, Chunk


@dataclass
class DecoderStats:
    """Статистика прогона декодера."""
    name: str = ""
    replaced: int = 0
    scanned: int = 0
    errors: int = 0
    details: list[str] = field(default_factory=list)
    
    def __repr__(self):
        return f"[{self.name}] replaced={self.replaced}/{self.scanned}, errors={self.errors}"
    
    def summary(self) -> str:
        lines = [f"┌─ {self.name}"]
        lines.append(f"│  scanned : {self.scanned}")
        lines.append(f"│  replaced: {self.replaced}")
        lines.append(f"│  errors  : {self.errors}")
        if self.details:
            lines.append(f"│  details :")
            for d in self.details[:5]:
                lines.append(f"│    • {d}")
            if len(self.details) > 5:
                lines.append(f"│    ... +{len(self.details)-5} more")
        lines.append(f"└─")
        return "\n".join(lines)


class BaseDecoder(NodeTransformer):
    """
    Базовый класс всех декодеров.
    
    Наследник должен:
      1) Задать class-attr `NAME`
      2) Переопределить нужные `visit_*` — вернуть новый узел (или тот же)
      3) Инкрементить self.stats.scanned / .replaced при обработке
    """
    
    NAME = "base"
    
    def __init__(self):
        super().__init__()
        self.stats = DecoderStats(name=self.NAME)
    
    def run(self, chunk: Chunk) -> tuple[Chunk, DecoderStats]:
        """Запустить декодер. Возвращает (изменённый chunk, статистика)."""
        self.stats = DecoderStats(name=self.NAME)
        new_chunk = self.visit(chunk)
        return new_chunk, self.stats