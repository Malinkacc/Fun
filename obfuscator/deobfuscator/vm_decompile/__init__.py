"""
NZL STUDIO - Sprint 4b: devirtualizer собственного VM
====================================================
opmap_recovery  — восстановление op-map по тексту runtime (скелеты веток)
proto_decode    — байты (RC4-блоб) -> Proto
lifter          — Proto -> Lua AST (структурный контрол-поток)

Импорты ленивые (PEP 562): `python -m obfuscator.deobfuscator.vm_decompile.X`
не должен печатать runpy RuntimeWarning про sys.modules.
"""

_LAZY = {
    'recover_op_map': '.opmap_recovery',
    'SEMANTIC_EQ': '.opmap_recovery',
    'BlobDecodeError': '.proto_decode',
    'decode_blob': '.proto_decode',
    'decode_proto': '.proto_decode',
    'LiftError': '.lifter',
    'Lifter': '.lifter',
    'lift_proto': '.lifter',
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
