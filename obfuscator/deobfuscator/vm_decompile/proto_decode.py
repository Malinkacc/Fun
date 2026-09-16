"""
NZL STUDIO - Sprint 4b: декодер VM-байткода (Python-сторона)
============================================================
Зеркально повторяет формат BytecodeEncoder.encode_proto и Lua-декодер
runtime (_gen_bytecode_decoder):

    proto   : num_params u32LE | is_vararg u8 | max_stack u32LE
              | n_upvalues u32LE | [instack u8, index u32LE]*
              | n_consts u32LE | const*
              | n_code u32LE | instr(8B)*
              | n_protos u32LE | proto*
    const   : tag u8 (0 NIL, 1 BOOL+u8, 2 NUMBER+<d, 3 STRING+u32+utf8,
              4 PROTO+u32)
    instr   : op u8 | a u8 | b u8 | c u8 | k s32LE

Номера опкодов подаются восстановленной картой num -> Opcode
(см. opmap_recovery).
"""

from __future__ import annotations

import struct
from typing import Dict, List, Tuple

from obfuscator.vm.opcodes import (
    Constant, ConstantPool, ConstantType, Instruction, Opcode, Proto,
)


class BlobDecodeError(ValueError):
    """Блоб не является валидным VM-байткодом NZL."""


def _u32(data: bytes, pos: int) -> Tuple[int, int]:
    if pos + 4 > len(data):
        raise BlobDecodeError('truncated u32')
    return int.from_bytes(data[pos:pos + 4], 'little'), pos + 4


def _u8(data: bytes, pos: int) -> Tuple[int, int]:
    if pos + 1 > len(data):
        raise BlobDecodeError('truncated u8')
    return data[pos], pos + 1


def _decode_constant(data: bytes, pos: int) -> Tuple[Constant, int]:
    tag, pos = _u8(data, pos)
    if tag == ConstantType.NIL:
        return Constant(type=ConstantType.NIL, value=None), pos
    if tag == ConstantType.BOOL:
        v, pos = _u8(data, pos)
        return Constant(type=ConstantType.BOOL, value=bool(v)), pos
    if tag == ConstantType.NUMBER:
        if pos + 8 > len(data):
            raise BlobDecodeError('truncated number const')
        v = struct.unpack_from('<d', data, pos)[0]
        return Constant(type=ConstantType.NUMBER, value=v), pos + 8
    if tag == ConstantType.STRING:
        ln, pos = _u32(data, pos)
        if pos + ln > len(data):
            raise BlobDecodeError('truncated string const')
        s = data[pos:pos + ln].decode('utf-8', errors='replace')
        return Constant(type=ConstantType.STRING, value=s), pos + ln
    if tag == ConstantType.PROTO:
        idx, pos = _u32(data, pos)
        return Constant(type=ConstantType.PROTO, value=idx), pos
    raise BlobDecodeError(f'unknown const tag {tag}')


def decode_proto(data: bytes, pos: int,
                 num2op: Dict[int, Opcode]) -> Tuple[Proto, int]:
    num_params, pos = _u32(data, pos)
    is_vararg, pos = _u8(data, pos)
    max_stack, pos = _u32(data, pos)

    n_uv, pos = _u32(data, pos)
    upvalues: List[Tuple[bool, int]] = []
    for _ in range(n_uv):
        instack, pos = _u8(data, pos)
        index, pos = _u32(data, pos)
        upvalues.append((bool(instack), index))

    n_c, pos = _u32(data, pos)
    pool = ConstantPool()
    for _ in range(n_c):
        const, pos = _decode_constant(data, pos)
        pool.add(const)

    n_code, pos = _u32(data, pos)
    code: List[Instruction] = []
    for _ in range(n_code):
        if pos + 8 > len(data):
            raise BlobDecodeError('truncated instruction')
        op_num = data[pos]
        a, b, c = data[pos + 1], data[pos + 2], data[pos + 3]
        k = int.from_bytes(data[pos + 4:pos + 8], 'little')
        if k >= 2 ** 31:
            k -= 2 ** 32
        op = num2op.get(op_num)
        if op is None:
            raise BlobDecodeError(f'unknown opcode num {op_num}')
        code.append(Instruction(op=op, a=a, b=b, c=c, k=k))
        pos += 8

    n_p, pos = _u32(data, pos)
    protos: List[Proto] = []
    for _ in range(n_p):
        sub, pos = decode_proto(data, pos, num2op)
        protos.append(sub)

    proto = Proto(
        name='<devirt>',
        num_params=num_params,
        is_vararg=bool(is_vararg),
        max_stack=max_stack,
        code=code,
        constants=pool,
        protos=protos,
        upvalues=upvalues,
    )
    return proto, pos


def decode_blob(data: bytes, num2op: Dict[int, Opcode]) -> Proto:
    """Полный блоб -> Proto (проверяет, что съедены все байты)."""
    proto, pos = decode_proto(data, 0, num2op)
    if pos != len(data):
        raise BlobDecodeError(
            f'trailing bytes: consumed {pos} of {len(data)}')
    return proto


def _test() -> None:
    import os
    import random
    import sys
    root = os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))))
    if root not in sys.path:
        sys.path.insert(0, root)

    from obfuscator.lexer import Lexer
    from obfuscator.parser import Parser
    from obfuscator.vm.compiler import compile_function
    from obfuscator.vm.opcodes import BytecodeEncoder, OpcodeMap
    from obfuscator.vm.runtime_lua import RuntimeGenerator
    from obfuscator.utils.crypto import rc4_encrypt

    passed = failed = 0

    def check(label: str, ok: bool, extra: str = '') -> None:
        nonlocal passed, failed
        if ok:
            passed += 1
            print(f'  [OK] {label}' + (f'  {extra}' if extra else ''))
        else:
            failed += 1
            print(f'  [XX] {label}' + (f'  {extra}' if extra else ''))

    print('=' * 60)
    print('  vm_decompile.proto_decode — tests')
    print('=' * 60)

    samples = [
        'local function f(a, b) local x = a + b * 2 return x - 1 end',
        'local function g(n) if n <= 1 then return 1 end '
        'return n * g(n - 1) end',
        'local function c(...) local t = {...} return #t end',
        'local function h(t) local s = 0 for i, v in ipairs(t) do '
        's = s + v end return s end',
    ]

    for si, src in enumerate(samples):
        ast = Parser(Lexer(src).tokenize()).parse()
        func = ast.body.statements[0].func
        proto = compile_function(func, name='f')

        op_map = OpcodeMap(seed=1000 + si)
        enc = BytecodeEncoder(op_map)
        raw = enc.encode_proto(proto)
        key = bytes(random.Random(si).randrange(256) for _ in range(16))
        blob = rc4_encrypt(raw, key)

        num2op = {n: op for n, op in op_map._num_to_op.items()}
        try:
            dec = decode_blob(rc4_encrypt(blob, key), num2op)
            ok = (
                len(dec.code) == len(proto.code)
                and all(i.op == j.op and i.a == j.a and i.b == j.b
                        and i.c == j.c and i.k == j.k
                        for i, j in zip(dec.code, proto.code))
                and len(dec.protos) == len(proto.protos)
                and dec.num_params == proto.num_params
            )
            check(f'sample {si}: blob round-trip byte-exact', ok,
                  f'ins={len(dec.code)}, protos={len(dec.protos)}')
        except BlobDecodeError as e:
            check(f'sample {si}: blob round-trip byte-exact', False, str(e))

    # литерал из serialize_proto -> unescape через Lexer -> decode
    gen = RuntimeGenerator(seed=42)
    ast = Parser(Lexer(samples[0]).tokenize()).parse()
    proto = compile_function(ast.body.statements[0].func, name='f')
    key = b'0123456789abcdef'
    lit = gen.serializer.serialize_proto(proto, key)
    toks = Lexer('local s = ' + lit).tokenize()
    val = [t for t in toks if type(t).__name__ == 'Token'
           and getattr(t, 'type', None) is not None]
    str_tok = None
    for t in toks:
        if 'STRING' in str(getattr(t, 'type', '')):
            str_tok = t
            break
    check('literal tokenized', str_tok is not None)
    if str_tok is not None:
        raw2 = str_tok.value.encode('latin-1')
        dec2 = rc4_encrypt(raw2, key)
        num2op = {n: op for n, op in gen.op_map._num_to_op.items()}
        try:
            p2 = decode_blob(dec2, num2op)
            check('serialize_proto literal -> decode', len(p2.code) == len(proto.code))
        except BlobDecodeError as e:
            check('serialize_proto literal -> decode', False, str(e))

    # битый блоб -> ошибка, не падение
    try:
        decode_blob(b'\x01\x02\x03', num2op)
        check('garbage blob raises BlobDecodeError', False)
    except BlobDecodeError:
        check('garbage blob raises BlobDecodeError', True)

    total = passed + failed
    print('=' * 60)
    print(f'  Result: {passed}/{total}')
    if failed:
        sys.exit(1)
    print('  [OK] ALL PASSED')


if __name__ == '__main__':
    _test()
