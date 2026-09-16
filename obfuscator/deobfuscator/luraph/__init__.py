"""
NZL STUDIO - Sprint 5: парсер/декодеры формата Luraph v14.x
==========================================================
parser        — структурная карта образца: handlers/aliases/dispatcher
(decoders/luraph_decoder использует карту для deep-проходов;
 девиртуализация VM Luraph — Sprint 6+.)

Импорты ленивые (PEP 562): `py -m ...luraph.parser` не должен печатать
runpy RuntimeWarning.
"""

_LAZY = {
    'LuraphReport': '.parser',
    'detect_source': '.parser',
    'parse_chunk': '.parser',
    'parse_source': '.parser',
}

__all__ = list(_LAZY)


def __getattr__(name):
    mod_name = _LAZY.get(name)
    if mod_name is None:
        raise AttributeError(f'module {__name__!r} has no attribute {name!r}')
    import importlib
    mod = importlib.import_module(mod_name, __name__)
    return getattr(mod, name)


def __dir__():
    return sorted(__all__)
