"""
NZL STUDIO - Sprint 4b: devirtualizer собственного VM
====================================================
opmap_recovery  — восстановление op-map по тексту runtime (скелеты веток)
proto_decode    — байты (RC4-бLOB) -> Proto
lifter          — Proto -> Lua AST (структурный контрол-поток)
"""

from .opmap_recovery import recover_op_map, SEMANTIC_EQ
from .proto_decode import BlobDecodeError, decode_blob, decode_proto
from .lifter import LiftError, Lifter, lift_proto

__all__ = [
    'recover_op_map', 'SEMANTIC_EQ',
    'BlobDecodeError', 'decode_blob', 'decode_proto',
    'LiftError', 'Lifter', 'lift_proto',
]
