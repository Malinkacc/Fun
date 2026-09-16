from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Dict, List, Optional, Tuple


class Opcode(IntEnum):
    LOADK = 0
    LOADN = 1
    LOADBOOL = 2
    LOADNIL = 3
    MOVE = 4

    GETGLOBAL = 5
    SETGLOBAL = 6
    GETUPVAL = 7
    SETUPVAL = 8

    NEWTABLE = 9
    GETTABLE = 10
    SETTABLE = 11
    GETFIELD = 12
    SETFIELD = 13
    SETLIST = 14

    ADD = 15
    SUB = 16
    MUL = 17
    DIV = 18
    MOD = 19
    POW = 20
    IDIV = 21
    UNM = 22
    NOT = 23
    LEN = 24
    CONCAT = 25

    EQ = 26
    NEQ = 27
    LT = 28
    LE = 29
    GT = 30
    GE = 31

    AND = 32
    OR = 33

    JMP = 34
    JMPIF = 35
    JMPIFNOT = 36

    CLOSURE = 37
    CALL = 38
    TAILCALL = 39
    RETURN = 40
    VARARG = 41
    SELF = 42

    FORPREP = 43
    FORLOOP = 44
    TFORCALL = 45
    TFORLOOP = 46

    CLOSE = 47
    NOP = 48
    CHECKSUM = 49
    TRAP = 50


class InstrFormat(IntEnum):
    NONE = 0
    A = 1
    AB = 2
    ABC = 3
    AK = 4
    ABK = 5
    AX = 6
    X = 7


OPCODE_FORMATS: Dict[Opcode, InstrFormat] = {
    Opcode.LOADK: InstrFormat.AK,
    Opcode.LOADN: InstrFormat.AB,
    Opcode.LOADBOOL: InstrFormat.AB,
    Opcode.LOADNIL: InstrFormat.AB,
    Opcode.MOVE: InstrFormat.AB,

    Opcode.GETGLOBAL: InstrFormat.AK,
    Opcode.SETGLOBAL: InstrFormat.AK,
    Opcode.GETUPVAL: InstrFormat.AB,
    Opcode.SETUPVAL: InstrFormat.AB,

    Opcode.NEWTABLE: InstrFormat.ABC,
    Opcode.GETTABLE: InstrFormat.ABC,
    Opcode.SETTABLE: InstrFormat.ABC,
    Opcode.GETFIELD: InstrFormat.ABK,
    Opcode.SETFIELD: InstrFormat.ABK,
    Opcode.SETLIST: InstrFormat.ABC,

    Opcode.ADD: InstrFormat.ABC,
    Opcode.SUB: InstrFormat.ABC,
    Opcode.MUL: InstrFormat.ABC,
    Opcode.DIV: InstrFormat.ABC,
    Opcode.MOD: InstrFormat.ABC,
    Opcode.POW: InstrFormat.ABC,
    Opcode.IDIV: InstrFormat.ABC,
    Opcode.UNM: InstrFormat.AB,
    Opcode.NOT: InstrFormat.AB,
    Opcode.LEN: InstrFormat.AB,
    Opcode.CONCAT: InstrFormat.ABC,

    Opcode.EQ: InstrFormat.ABC,
    Opcode.NEQ: InstrFormat.ABC,
    Opcode.LT: InstrFormat.ABC,
    Opcode.LE: InstrFormat.ABC,
    Opcode.GT: InstrFormat.ABC,
    Opcode.GE: InstrFormat.ABC,

    Opcode.AND: InstrFormat.ABC,
    Opcode.OR: InstrFormat.ABC,

    Opcode.JMP: InstrFormat.X,
    Opcode.JMPIF: InstrFormat.AX,
    Opcode.JMPIFNOT: InstrFormat.AX,

    Opcode.CLOSURE: InstrFormat.AK,
    Opcode.CALL: InstrFormat.ABC,
    Opcode.TAILCALL: InstrFormat.AB,
    Opcode.RETURN: InstrFormat.AB,
    Opcode.VARARG: InstrFormat.AB,
    Opcode.SELF: InstrFormat.ABC,

    Opcode.FORPREP: InstrFormat.AX,
    Opcode.FORLOOP: InstrFormat.AX,
    Opcode.TFORCALL: InstrFormat.AB,
    Opcode.TFORLOOP: InstrFormat.AX,

    Opcode.CLOSE: InstrFormat.A,
    Opcode.NOP: InstrFormat.NONE,
    Opcode.CHECKSUM: InstrFormat.X,
    Opcode.TRAP: InstrFormat.NONE,
}


@dataclass
class Instruction:
    op: Opcode
    a: int = 0
    b: int = 0
    c: int = 0
    k: int = 0
    line: int = 0

    def format(self) -> InstrFormat:
        return OPCODE_FORMATS.get(self.op, InstrFormat.NONE)

    def __repr__(self) -> str:
        fmt = self.format()
        name = self.op.name
        if fmt == InstrFormat.NONE:
            return f'{name}'
        if fmt == InstrFormat.A:
            return f'{name} A={self.a}'
        if fmt == InstrFormat.AB:
            return f'{name} A={self.a} B={self.b}'
        if fmt == InstrFormat.ABC:
            return f'{name} A={self.a} B={self.b} C={self.c}'
        if fmt == InstrFormat.AK:
            return f'{name} A={self.a} K={self.k}'
        if fmt == InstrFormat.ABK:
            return f'{name} A={self.a} B={self.b} K={self.k}'
        if fmt == InstrFormat.AX:
            return f'{name} A={self.a} X={self.k}'
        if fmt == InstrFormat.X:
            return f'{name} X={self.k}'
        return f'{name}(?)'


class ConstantType(IntEnum):
    NIL = 0
    BOOL = 1
    NUMBER = 2
    STRING = 3
    PROTO = 4


@dataclass
class Constant:
    type: ConstantType
    value: Any = None

    def __repr__(self) -> str:
        if self.type == ConstantType.NIL:
            return 'nil'
        if self.type == ConstantType.BOOL:
            return str(self.value).lower()
        if self.type == ConstantType.STRING:
            v = str(self.value)
            if len(v) > 40:
                v = v[:37] + '...'
            return f'"{v}"'
        return str(self.value)

    def __hash__(self):
        return hash((self.type, self.value))

    def __eq__(self, other):
        return isinstance(other, Constant) and self.type == other.type and self.value == other.value


class ConstantPool:
    def __init__(self):
        self._constants: List[Constant] = []
        self._index: Dict[Constant, int] = {}

    def add(self, const: Constant) -> int:
        if const in self._index:
            return self._index[const]
        idx = len(self._constants)
        self._constants.append(const)
        self._index[const] = idx
        return idx

    def add_nil(self) -> int:
        return self.add(Constant(type=ConstantType.NIL, value=None))

    def add_bool(self, v: bool) -> int:
        return self.add(Constant(type=ConstantType.BOOL, value=v))

    def add_number(self, v: float) -> int:
        return self.add(Constant(type=ConstantType.NUMBER, value=float(v)))

    def add_string(self, v: str) -> int:
        return self.add(Constant(type=ConstantType.STRING, value=str(v)))

    def add_proto(self, proto_idx: int) -> int:
        idx = len(self._constants)
        self._constants.append(Constant(type=ConstantType.PROTO, value=proto_idx))
        return idx

    def __len__(self) -> int:
        return len(self._constants)

    def __iter__(self):
        return iter(self._constants)

    def __getitem__(self, i: int) -> Constant:
        return self._constants[i]


@dataclass
class Proto:
    name: str = '<anonymous>'
    num_params: int = 0
    is_vararg: bool = False
    max_stack: int = 32
    code: List[Instruction] = field(default_factory=list)
    constants: ConstantPool = field(default_factory=ConstantPool)
    protos: List['Proto'] = field(default_factory=list)
    upvalues: List[Tuple[bool, int]] = field(default_factory=list)
    upvalue_names: List[str] = field(default_factory=list)
    line: int = 0

    def emit(self, instr: Instruction) -> int:
        self._auto_line(instr)
        self.code.append(instr)
        return len(self.code) - 1

    def _auto_line(self, instr: Instruction) -> None:
        if instr.line == 0 and self.code:
            instr.line = self.code[-1].line

    def emit_op(
        self,
        op: Opcode,
        a: int = 0,
        b: int = 0,
        c: int = 0,
        k: int = 0,
        line: int = 0,
    ) -> int:
        return self.emit(Instruction(op=op, a=a, b=b, c=c, k=k, line=line))

    def add_proto(self, proto: 'Proto') -> int:
        self.protos.append(proto)
        return len(self.protos) - 1

    def current_pc(self) -> int:
        return len(self.code)

    def patch_jump(self, instr_idx: int, target_pc: int) -> None:
        instr = self.code[instr_idx]
        offset = target_pc - (instr_idx + 1)
        instr.k = offset

    def dump(self) -> str:
        lines = [
            f'-- Proto: {self.name} (params={self.num_params}, '
            f'vararg={self.is_vararg}, stack={self.max_stack})'
        ]

        if self.upvalues:
            lines.append(f'-- Upvalues ({len(self.upvalues)}):')
            for i, (instack, index) in enumerate(self.upvalues):
                uv_name = self.upvalue_names[i] if i < len(self.upvalue_names) else '?'
                lines.append(
                    f'   [{i}] name={uv_name!r} instack={bool(instack)} index={int(index)}'
                )

        lines.append(f'-- Constants ({len(self.constants)}):')
        for i, c in enumerate(self.constants):
            lines.append(f'   [{i}] {c!r}')

        lines.append(f'-- Code ({len(self.code)}):')
        for pc, instr in enumerate(self.code):
            lines.append(f'   {pc:4d}  {instr!r}')

        if self.protos:
            lines.append(f'-- Nested protos ({len(self.protos)}):')
            for i, p in enumerate(self.protos):
                lines.append(f'   [{i}] {p.name}')

        return '\n'.join(lines)


class OpcodeMap:
    def __init__(self, seed: Optional[int] = None):
        if seed is None:
            seed = random.randint(0, 2**32 - 1)
        self.seed = seed
        rng = random.Random(seed)

        all_ops = list(Opcode)
        available_nums = list(range(1, 256))
        rng.shuffle(available_nums)

        if len(available_nums) < len(all_ops):
            raise RuntimeError('Too many opcodes for 8-bit runtime ids')

        self._op_to_num: Dict[Opcode, int] = {}
        self._num_to_op: Dict[int, Opcode] = {}

        for i, op in enumerate(all_ops):
            num = available_nums[i]
            self._op_to_num[op] = num
            self._num_to_op[num] = op

    def get_num(self, op: Opcode) -> int:
        return self._op_to_num[op]

    def get_op(self, num: int) -> Optional[Opcode]:
        return self._num_to_op.get(num)

    def all_pairs(self) -> List[Tuple[Opcode, int]]:
        return list(self._op_to_num.items())

    def dump_lua_map(self) -> str:
        parts = []
        for op, num in sorted(self._op_to_num.items(), key=lambda x: x[0].value):
            parts.append(f'{op.name}={num}')
        return '{' + ','.join(parts) + '}'


class BytecodeEncoder:
    INSTR_SIZE = 8

    def __init__(self, opcode_map: OpcodeMap):
        self.op_map = opcode_map

    def encode_instruction(self, instr: Instruction) -> bytes:
        op_num = self.op_map.get_num(instr.op)
        a = instr.a & 0xFF
        b = instr.b & 0xFF
        c = instr.c & 0xFF
        k = instr.k
        if k < 0:
            k += 2**32
        k &= 0xFFFFFFFF
        return bytes([
            op_num,
            a,
            b,
            c,
            k & 0xFF,
            (k >> 8) & 0xFF,
            (k >> 16) & 0xFF,
            (k >> 24) & 0xFF,
        ])

    def decode_instruction(self, data: bytes, offset: int = 0) -> Instruction:
        op_num = data[offset]
        a = data[offset + 1]
        b = data[offset + 2]
        c = data[offset + 3]
        k = (
            data[offset + 4]
            | (data[offset + 5] << 8)
            | (data[offset + 6] << 16)
            | (data[offset + 7] << 24)
        )
        if k >= 2**31:
            k -= 2**32
        op = self.op_map.get_op(op_num) or Opcode.NOP
        return Instruction(op=op, a=a, b=b, c=c, k=k)

    def encode_constant(self, const: Constant) -> bytes:
        t = const.type
        if t == ConstantType.NIL:
            return bytes([ConstantType.NIL])
        if t == ConstantType.BOOL:
            return bytes([ConstantType.BOOL, 1 if const.value else 0])
        if t == ConstantType.NUMBER:
            import struct
            return bytes([ConstantType.NUMBER]) + struct.pack('<d', float(const.value))
        if t == ConstantType.STRING:
            data = str(const.value).encode('utf-8')
            length = len(data)
            return bytes([ConstantType.STRING]) + length.to_bytes(4, 'little') + data
        if t == ConstantType.PROTO:
            proto_idx = int(const.value)
            return bytes([ConstantType.PROTO]) + proto_idx.to_bytes(4, 'little')
        raise ValueError(f'Unknown const type: {t}')

    def _normalize_upvalue(self, uv: Any) -> Tuple[bool, int]:
        if isinstance(uv, dict):
            return bool(uv.get('instack', False)), int(uv.get('index', 0))

        if isinstance(uv, (tuple, list)) and len(uv) >= 2:
            return bool(uv[0]), int(uv[1])

        raise ValueError(f'Invalid upvalue metadata: {uv!r}')

    def encode_proto(self, proto: Proto) -> bytes:
        parts: List[bytes] = []

        parts.append(proto.num_params.to_bytes(4, 'little'))
        parts.append(bytes([1 if proto.is_vararg else 0]))
        parts.append(proto.max_stack.to_bytes(4, 'little'))

        parts.append(len(proto.upvalues).to_bytes(4, 'little'))
        for uv in proto.upvalues:
            instack, index = self._normalize_upvalue(uv)
            parts.append(bytes([1 if instack else 0]))
            parts.append(int(index).to_bytes(4, 'little'))

        parts.append(len(proto.constants).to_bytes(4, 'little'))
        for c in proto.constants:
            parts.append(self.encode_constant(c))

        parts.append(len(proto.code).to_bytes(4, 'little'))
        for instr in proto.code:
            parts.append(self.encode_instruction(instr))

        parts.append(len(proto.protos).to_bytes(4, 'little'))
        for p in proto.protos:
            parts.append(self.encode_proto(p))

        return b''.join(parts)


def create_polymorphic_vm(seed: Optional[int] = None) -> Tuple[OpcodeMap, BytecodeEncoder]:
    op_map = OpcodeMap(seed=seed)
    encoder = BytecodeEncoder(op_map)
    return op_map, encoder


def count_opcodes(proto: Proto) -> Dict[Opcode, int]:
    counts: Dict[Opcode, int] = {}
    for instr in proto.code:
        counts[instr.op] = counts.get(instr.op, 0) + 1
    for nested in proto.protos:
        for op, n in count_opcodes(nested).items():
            counts[op] = counts.get(op, 0) + n
    return counts


def _test():
    passed = 0
    failed = 0

    def ok(label: str):
        nonlocal passed
        passed += 1
        print(f'  ✅ {label}')

    def fail(label: str, detail: str = ''):
        nonlocal failed
        failed += 1
        print(f'  ❌ {label}' + (f' — {detail}' if detail else ''))

    def check(label: str, cond: bool, detail: str = ''):
        if cond:
            ok(label)
        else:
            fail(label, detail)

    print('\n' + '═' * 56)
    print('  NZL VM Opcodes — Tests')
    print('═' * 56)

    values = [op.value for op in Opcode]
    check('opcode values unique', len(values) == len(set(values)))

    missing = [op for op in Opcode if op not in OPCODE_FORMATS]
    check('all opcodes have formats', len(missing) == 0, str(missing))

    i1 = Instruction(op=Opcode.LOADK, a=5, k=12)
    i2 = Instruction(op=Opcode.ADD, a=1, b=2, c=3)
    check('LOADK repr', 'LOADK' in repr(i1) and 'A=5' in repr(i1), repr(i1))
    check('ADD repr', 'ADD' in repr(i2) and 'C=3' in repr(i2), repr(i2))

    pool = ConstantPool()
    a = pool.add_string('hello')
    b = pool.add_string('hello')
    c = pool.add_string('world')
    check('string dedupe', a == b and a != c)

    proto = Proto(name='test', num_params=1, max_stack=4)
    proto.upvalues.append((True, 3))
    proto.upvalue_names.append('x')
    k0 = proto.constants.add_number(42)
    proto.emit_op(Opcode.LOADK, a=0, k=k0)
    proto.emit_op(Opcode.RETURN, a=0, b=1)

    jproto = Proto(name='jump')
    j = jproto.emit_op(Opcode.JMP, k=0)
    jproto.emit_op(Opcode.LOADN, a=0, b=1)
    jproto.emit_op(Opcode.LOADN, a=1, b=2)
    jproto.patch_jump(j, jproto.current_pc())
    check('patch_jump works', jproto.code[j].k == 2, str(jproto.code[j].k))

    m1 = OpcodeMap(seed=1)
    m2 = OpcodeMap(seed=2)
    m3 = OpcodeMap(seed=1)
    check('different seeds -> different ids', m1.get_num(Opcode.LOADK) != m2.get_num(Opcode.LOADK))
    check('same seeds -> same ids', m1.get_num(Opcode.LOADK) == m3.get_num(Opcode.LOADK))
    check('inverse map works', m1.get_op(m1.get_num(Opcode.ADD)) == Opcode.ADD)

    enc = BytecodeEncoder(m1)
    data = enc.encode_instruction(Instruction(op=Opcode.JMP, k=-100))
    dec = enc.decode_instruction(data)
    check('signed k round-trip', dec.k == -100, str(dec.k))

    pdata = enc.encode_proto(proto)
    check('proto encoded to bytes', isinstance(pdata, bytes) and len(pdata) > 0)
    check('upvalue metadata encoded too', len(pdata) > 4 + 1 + 4 + 4 + 5, str(len(pdata)))

    dump_str = proto.dump()
    check('dump includes upvalues', 'Upvalues' in dump_str and 'instack=True' in dump_str, dump_str)

    parent = Proto(name='parent')
    parent.emit_op(Opcode.LOADK, a=0)
    child = Proto(name='child')
    child.emit_op(Opcode.ADD, a=0, b=1, c=2)
    parent.add_proto(child)
    counts = count_opcodes(parent)
    check('count_opcodes sees nested', counts.get(Opcode.ADD, 0) == 1)

    total = passed + failed
    print('\n' + '═' * 56)
    print(f'  Result: {passed}/{total} passed', end='')
    if failed == 0:
        print(' 🎉')
    else:
        print(f' ({failed} failed) ❌')
    print('═' * 56)

    return failed == 0


if __name__ == '__main__':
    import sys
    success = _test()
    sys.exit(0 if success else 1)