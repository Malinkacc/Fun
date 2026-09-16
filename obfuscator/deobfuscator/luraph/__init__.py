"""
NZL STUDIO - Sprint 5: парсер/декодеры формата Luraph v14.x
==========================================================
parser        — структурная карта образца: handlers/aliases/dispatcher
(decoders/luraph_decoder использует карту для deep-проходов;
 девиртуализация VM Luraph — Sprint 6+.)
"""

from .parser import LuraphReport, detect_source, parse_chunk, parse_source

__all__ = ['LuraphReport', 'detect_source', 'parse_chunk', 'parse_source']
