from __future__ import annotations

import random
from typing import Any, Dict, List, Optional

from .opcodes import (
    BytecodeEncoder,
    ConstantType,
    Opcode,
    OpcodeMap,
    Proto,
)
from ..ast_unparser import escape_lua_string
from ..utils.crypto import bytes_to_py_string, gen_random_key, rc4_encrypt
from ..utils.random_gen import NameGenerator, make_rng


class VMNames:
    def __init__(self, name_gen: NameGenerator):
        self.create_vm = name_gen.generate()
        self.decode_str = name_gen.generate()
        self.decode_bc = name_gen.generate()
        self.execute = name_gen.generate()

        self.proto_tbl = name_gen.generate()
        self.const_tbl = name_gen.generate()
        self.code_tbl = name_gen.generate()
        self.regs = name_gen.generate()
        self.pc = name_gen.generate()
        self.upvals = name_gen.generate()
        self.protos = name_gen.generate()
        self.env = name_gen.generate()
        self.args_tbl = name_gen.generate()
        self.vararg_tbl = name_gen.generate()

        self.instr = name_gen.generate()
        self.op = name_gen.generate()
        self.a = name_gen.generate()
        self.b = name_gen.generate()
        self.c = name_gen.generate()
        self.k = name_gen.generate()

        self.bytecode_str = name_gen.generate()
        self.key = name_gen.generate()
        self.i = name_gen.generate()

        self.str_byte = name_gen.generate()
        self.str_sub = name_gen.generate()
        self.str_char = name_gen.generate()
        self.tbl_insert = name_gen.generate()
        self.tbl_unpack = name_gen.generate()
        self.bxor = name_gen.generate()

        self.tmp1 = name_gen.generate()
        self.tmp2 = name_gen.generate()
        self.tmp3 = name_gen.generate()
        self.result = name_gen.generate()
        self.n = name_gen.generate()
        self.cnt = name_gen.generate()


class BytecodeSerializer:
    def __init__(self, opcode_map: OpcodeMap, rng: random.Random):
        self.op_map = opcode_map
        self.encoder = BytecodeEncoder(opcode_map)
        self.rng = rng

    def serialize_proto(self, proto: Proto, key: bytes) -> str:
        raw = self.encoder.encode_proto(proto)
        encrypted = rc4_encrypt(raw, key)
        py_str = bytes_to_py_string(encrypted)
        return escape_lua_string(py_str)

    def serialize_key(self, key: bytes) -> str:
        return escape_lua_string(bytes_to_py_string(key))


class RuntimeGenerator:
    def __init__(
        self,
        seed: Optional[int] = None,
        shuffle_dispatch: bool = True,
        add_junk_ops: bool = True,
    ):
        if seed is None:
            seed = random.randint(0, 2**32 - 1)

        self.seed = seed
        self.rng = make_rng(seed)
        self.name_gen = NameGenerator(rng=self.rng, style='hex')
        self.names = VMNames(self.name_gen)

        self.op_map = OpcodeMap(seed=self.rng.randint(1, 2**31))
        self.serializer = BytecodeSerializer(self.op_map, self.rng)

        self.shuffle_dispatch = shuffle_dispatch
        self.add_junk_ops = add_junk_ops

    def generate_vm_wrapper(
        self,
        proto: Proto,
        fn_name: str = 'protectedFn',
    ) -> str:
        key = gen_random_key(16, rng=self.rng)

        bc_lit = self.serializer.serialize_proto(proto, key)
        key_lit = self.serializer.serialize_key(key)

        runtime_code = self._generate_runtime()
        wrapper = self._generate_wrapper(fn_name, bc_lit, key_lit)

        return runtime_code + '\n\n' + wrapper

    def _generate_runtime(self) -> str:
        n = self.names
        lines: List[str] = []

        lines.append(f'-- NZL VM Runtime (build {self.seed:08x})')
        lines.append(f'local {n.str_byte} = string.byte')
        lines.append(f'local {n.str_sub} = string.sub')
        lines.append(f'local {n.str_char} = string.char')
        lines.append(f'local {n.tbl_insert} = table.insert')
        lines.append(f'local {n.tbl_unpack} = table.unpack or unpack')
        lines.append(f'local {n.bxor} = bit32.bxor')

        lines.append('')
        lines.append(self._gen_rc4_decrypt())

        lines.append('')
        lines.append(self._gen_bytecode_decoder())

        lines.append('')
        lines.append(self._gen_execute_function())

        lines.append('')
        lines.append(self._gen_create_vm())

        return '\n'.join(lines)

    def _gen_rc4_decrypt(self) -> str:
        n = self.names
        s = self.name_gen.generate()
        j = self.name_gen.generate()
        i = self.name_gen.generate()
        data = self.name_gen.generate()
        key = self.name_gen.generate()
        out = self.name_gen.generate()
        tmp = self.name_gen.generate()
        idx = self.name_gen.generate()
        k_len = self.name_gen.generate()

        code = f'''local function {n.decode_str}({data}, {key})
    local {s} = {{}}
    for {i} = 0, 255 do {s}[{i}] = {i} end
    local {j} = 0
    local {k_len} = #{key}
    for {i} = 0, 255 do
        {j} = ({j} + {s}[{i}] + {n.str_byte}({key}, ({i} % {k_len}) + 1)) % 256
        {s}[{i}], {s}[{j}] = {s}[{j}], {s}[{i}]
    end
    local {out} = {{}}
    local {i}2 = 0
    local {j}2 = 0
    for {idx} = 1, #{data} do
        {i}2 = ({i}2 + 1) % 256
        {j}2 = ({j}2 + {s}[{i}2]) % 256
        {s}[{i}2], {s}[{j}2] = {s}[{j}2], {s}[{i}2]
        local {tmp} = {s}[({s}[{i}2] + {s}[{j}2]) % 256]
        {out}[{idx}] = {n.str_char}({n.bxor}({n.str_byte}({data}, {idx}), {tmp}))
    end
    return table.concat({out})
end'''
        return code

    def _gen_bytecode_decoder(self) -> str:
        n = self.names
        data = self.name_gen.generate()
        pos = self.name_gen.generate()
        proto = self.name_gen.generate()
        n_ups = self.name_gen.generate()
        n_cons = self.name_gen.generate()
        n_ins = self.name_gen.generate()
        n_pro = self.name_gen.generate()
        i = self.name_gen.generate()
        t = self.name_gen.generate()
        c = self.name_gen.generate()
        length = self.name_gen.generate()
        b0 = self.name_gen.generate()
        b1 = self.name_gen.generate()
        b2 = self.name_gen.generate()
        b3 = self.name_gen.generate()
        u32v = self.name_gen.generate()
        uv_idx = self.name_gen.generate()
        uv_instack = self.name_gen.generate()

        const_nil = ConstantType.NIL.value
        const_bool = ConstantType.BOOL.value
        const_num = ConstantType.NUMBER.value
        const_str = ConstantType.STRING.value
        const_proto = ConstantType.PROTO.value

        code = f'''local function _nzl_read_u32({data}, {pos})
    local {b0} = {n.str_byte}({data}, {pos})
    local {b1} = {n.str_byte}({data}, {pos} + 1)
    local {b2} = {n.str_byte}({data}, {pos} + 2)
    local {b3} = {n.str_byte}({data}, {pos} + 3)
    return {b0} + {b1} * 256 + {b2} * 65536 + {b3} * 16777216, {pos} + 4
end

local function _nzl_read_i32({data}, {pos})
    local {u32v}, {pos} = _nzl_read_u32({data}, {pos})
    if {u32v} >= 2147483648 then {u32v} = {u32v} - 4294967296 end
    return {u32v}, {pos}
end

local function _nzl_read_double({data}, {pos})
    local {b0} = {n.str_byte}({data}, {pos})
    local {b1} = {n.str_byte}({data}, {pos} + 1)
    local {b2} = {n.str_byte}({data}, {pos} + 2)
    local {b3} = {n.str_byte}({data}, {pos} + 3)
    local b4 = {n.str_byte}({data}, {pos} + 4)
    local b5 = {n.str_byte}({data}, {pos} + 5)
    local b6 = {n.str_byte}({data}, {pos} + 6)
    local b7 = {n.str_byte}({data}, {pos} + 7)
    local sign = 1
    if b7 >= 128 then sign = -1; b7 = b7 - 128 end
    local exp = b7 * 16 + math.floor(b6 / 16)
    local mant = (b6 % 16) * 281474976710656 + b5 * 1099511627776 + b4 * 4294967296
        + {b3} * 16777216 + {b2} * 65536 + {b1} * 256 + {b0}
    local val
    if exp == 0 then
        if mant == 0 then
            val = 0
        else
            val = sign * mant * 2^(-1074)
        end
    elseif exp == 2047 then
        if mant == 0 then
            val = sign * math.huge
        else
            val = 0/0
        end
    else
        val = sign * (1 + mant / 4503599627370496) * 2^(exp - 1023)
    end
    return val, {pos} + 8
end

local function {n.decode_bc}({data}, {pos})
    {pos} = {pos} or 1
    local {proto} = {{}}

    {proto}.num_params, {pos} = _nzl_read_u32({data}, {pos})
    {proto}.is_vararg = {n.str_byte}({data}, {pos}) ~= 0
    {pos} = {pos} + 1
    {proto}.max_stack, {pos} = _nzl_read_u32({data}, {pos})

    {n_ups}, {pos} = _nzl_read_u32({data}, {pos})
    {proto}.upvalues = {{}}
    for {i} = 1, {n_ups} do
        local {uv_instack} = {n.str_byte}({data}, {pos}) ~= 0
        {pos} = {pos} + 1
        local {uv_idx}
        {uv_idx}, {pos} = _nzl_read_u32({data}, {pos})
        {proto}.upvalues[{i}] = {{instack = {uv_instack}, index = {uv_idx}}}
    end

    {n_cons}, {pos} = _nzl_read_u32({data}, {pos})
    {proto}.constants = {{}}
    for {i} = 1, {n_cons} do
        local {t} = {n.str_byte}({data}, {pos})
        {pos} = {pos} + 1
        if {t} == {const_nil} then
            {proto}.constants[{i}] = nil
        elseif {t} == {const_bool} then
            {proto}.constants[{i}] = ({n.str_byte}({data}, {pos}) ~= 0)
            {pos} = {pos} + 1
        elseif {t} == {const_num} then
            local {c}
            {c}, {pos} = _nzl_read_double({data}, {pos})
            {proto}.constants[{i}] = {c}
        elseif {t} == {const_str} then
            local {length}
            {length}, {pos} = _nzl_read_u32({data}, {pos})
            {proto}.constants[{i}] = {n.str_sub}({data}, {pos}, {pos} + {length} - 1)
            {pos} = {pos} + {length}
        elseif {t} == {const_proto} then
            local {c}
            {c}, {pos} = _nzl_read_u32({data}, {pos})
            {proto}.constants[{i}] = {{__proto_ref = {c}}}
        end
    end

    {n_ins}, {pos} = _nzl_read_u32({data}, {pos})
    {proto}.code = {{}}
    for {i} = 1, {n_ins} do
        local instr = {{}}
        instr.op = {n.str_byte}({data}, {pos})
        instr.a = {n.str_byte}({data}, {pos} + 1)
        instr.b = {n.str_byte}({data}, {pos} + 2)
        instr.c = {n.str_byte}({data}, {pos} + 3)
        instr.k, _ = _nzl_read_i32({data}, {pos} + 4)
        {proto}.code[{i}] = instr
        {pos} = {pos} + 8
    end

    {n_pro}, {pos} = _nzl_read_u32({data}, {pos})
    {proto}.protos = {{}}
    for {i} = 1, {n_pro} do
        {proto}.protos[{i}], {pos} = {n.decode_bc}({data}, {pos})
    end

    return {proto}, {pos}
end'''
        return code

    def _gen_execute_function(self) -> str:
        n = self.names

        proto_var = self.name_gen.generate()
        args_var = self.name_gen.generate()
        upvals_var = self.name_gen.generate()
        r = n.regs
        pc = n.pc
        code = self.name_gen.generate()
        k_tbl = self.name_gen.generate()
        instr = n.instr
        op = n.op
        a = n.a
        b = n.b
        c = n.c
        kop = n.k
        env = n.env
        i = n.i
        tmp = n.tmp1

        dispatch_branches = self._gen_dispatch_branches(
            r, k_tbl, pc, code, env, tmp, a, b, c, kop, proto_var, upvals_var
        )

        if self.add_junk_ops:
            dispatch_branches += self._gen_junk_branches(r)

        if self.shuffle_dispatch:
            self.rng.shuffle(dispatch_branches)

        if not dispatch_branches:
            dispatch_body = '-- no ops'
        else:
            first = dispatch_branches[0]
            rest = dispatch_branches[1:]
            parts = [f'if {first[0]} then\n            do\n{first[1]}\n            end']
            for cond, body in rest:
                parts.append(f'elseif {cond} then\n            do\n{body}\n            end')
            parts.append('        end')
            dispatch_body = '\n        '.join(parts)

        code_str = f'''local function {n.execute}({proto_var}, {args_var}, {upvals_var})
    local {r} = {{}}
    local {code} = {proto_var}.code
    local {k_tbl} = {proto_var}.constants
    local {env} = getfenv and getfenv() or _G
    local {pc} = 1
    local {instr}, {op}, {a}, {b}, {c}, {kop}
    local {tmp}
    local {i}

    if {args_var} then
        for {i} = 1, #{args_var} do
            {r}[{i} - 1] = {args_var}[{i}]
        end
    end

    while true do
        {instr} = {code}[{pc}]
        if not {instr} then break end
        {op} = {instr}.op
        {a} = {instr}.a
        {b} = {instr}.b
        {c} = {instr}.c
        {kop} = {instr}.k
        {pc} = {pc} + 1

        {dispatch_body}
    end
end'''
        return code_str

    def _gen_dispatch_branches(
        self,
        r: str,
        k_tbl: str,
        pc: str,
        code: str,
        env: str,
        tmp: str,
        a: str,
        b: str,
        c: str,
        kop: str,
        proto_var: str,
        upvals_var: str,
    ) -> List[tuple]:
        branches: List[tuple] = []
        m = self.op_map

        def add(opcode: Opcode, body: str):
            num = m.get_num(opcode)
            stripped = body.strip()
            if not stripped or stripped.startswith('--'):
                stripped = 'local _nzl_pad = nil\n            ' + stripped
            branches.append((f'{self.names.op} == {num}', '            ' + stripped))

        add(Opcode.LOADK, f'{r}[{a}] = {k_tbl}[{kop} + 1]')
        add(Opcode.LOADN, f'if {b} >= 128 then {r}[{a}] = {b} - 256 else {r}[{a}] = {b} end')
        add(Opcode.LOADBOOL, f'{r}[{a}] = ({b} ~= 0)')
        add(Opcode.LOADNIL, f'for {tmp}i = {a}, {a} + {b} do {r}[{tmp}i] = nil end')
        add(Opcode.MOVE, f'{r}[{a}] = {r}[{b}]')

        add(Opcode.GETGLOBAL, f'{r}[{a}] = {env}[{k_tbl}[{kop} + 1]]')
        add(Opcode.SETGLOBAL, f'{env}[{k_tbl}[{kop} + 1]] = {r}[{a}]')

        add(Opcode.GETUPVAL, f'''if {upvals_var} and {upvals_var}[{b}] then
                local _uv = {upvals_var}[{b}]
                {r}[{a}] = _uv[1][_uv[2]]
            else
                {r}[{a}] = nil
            end''')

        add(Opcode.SETUPVAL, f'''if {upvals_var} and {upvals_var}[{b}] then
                local _uv = {upvals_var}[{b}]
                _uv[1][_uv[2]] = {r}[{a}]
            end''')

        add(Opcode.NEWTABLE, f'{r}[{a}] = {{}}')
        add(Opcode.GETTABLE, f'{r}[{a}] = {r}[{b}][{r}[{c}]]')
        add(Opcode.SETTABLE, f'{r}[{a}][{r}[{b}]] = {r}[{c}]')

        add(Opcode.GETFIELD, f'{r}[{a}] = {r}[{b}][{k_tbl}[{kop} + 1]]')
        add(Opcode.SETFIELD, f'{r}[{a}][{k_tbl}[{kop} + 1]] = {r}[{b}]')
        add(Opcode.SETLIST, f'for {tmp}i = 1, {b} do {r}[{a}][{c} + {tmp}i] = {r}[{a} + {tmp}i] end')

        add(Opcode.ADD, f'{r}[{a}] = {r}[{b}] + {r}[{c}]')
        add(Opcode.SUB, f'{r}[{a}] = {r}[{b}] - {r}[{c}]')
        add(Opcode.MUL, f'{r}[{a}] = {r}[{b}] * {r}[{c}]')
        add(Opcode.DIV, f'{r}[{a}] = {r}[{b}] / {r}[{c}]')
        add(Opcode.MOD, f'{r}[{a}] = {r}[{b}] % {r}[{c}]')
        add(Opcode.POW, f'{r}[{a}] = {r}[{b}] ^ {r}[{c}]')
        add(Opcode.IDIV, f'{r}[{a}] = math.floor({r}[{b}] / {r}[{c}])')
        add(Opcode.UNM, f'{r}[{a}] = -{r}[{b}]')
        add(Opcode.NOT, f'{r}[{a}] = not {r}[{b}]')
        add(Opcode.LEN, f'{r}[{a}] = #{r}[{b}]')

        add(Opcode.CONCAT, f'''local {tmp}s = ""
            for {tmp}i = {b}, {c} do {tmp}s = {tmp}s .. tostring({r}[{tmp}i]) end
            {r}[{a}] = {tmp}s''')

        add(Opcode.EQ, f'{r}[{a}] = ({r}[{b}] == {r}[{c}])')
        add(Opcode.NEQ, f'{r}[{a}] = ({r}[{b}] ~= {r}[{c}])')
        add(Opcode.LT, f'{r}[{a}] = ({r}[{b}] < {r}[{c}])')
        add(Opcode.LE, f'{r}[{a}] = ({r}[{b}] <= {r}[{c}])')
        add(Opcode.GT, f'{r}[{a}] = ({r}[{b}] > {r}[{c}])')
        add(Opcode.GE, f'{r}[{a}] = ({r}[{b}] >= {r}[{c}])')

        add(Opcode.AND, f'{r}[{a}] = {r}[{b}] and {r}[{c}]')
        add(Opcode.OR, f'{r}[{a}] = {r}[{b}] or {r}[{c}]')

        add(Opcode.JMP, f'{pc} = {pc} + {kop}')
        add(Opcode.JMPIF, f'if {r}[{a}] then {pc} = {pc} + {kop} end')
        add(Opcode.JMPIFNOT, f'if not {r}[{a}] then {pc} = {pc} + {kop} end')

        add(Opcode.CLOSURE, f'''local _pref = {k_tbl}[{kop} + 1]
            if type(_pref) == "table" and _pref.__proto_ref then
                local _p = {proto_var}.protos[_pref.__proto_ref + 1]
                local _captured_R = {r}
                local _parent_upvals = {upvals_var}
                local _child_upvals = {{}}

                if _p.upvalues then
                    for _uvi = 1, #_p.upvalues do
                        local _uvm = _p.upvalues[_uvi]
                        local _slot = _uvi - 1
                        if _uvm.instack then
                            _child_upvals[_slot] = {{_captured_R, _uvm.index}}
                        else
                            if _parent_upvals then
                                _child_upvals[_slot] = _parent_upvals[_uvm.index]
                            else
                                _child_upvals[_slot] = nil
                            end
                        end
                    end
                end

                {r}[{a}] = function(...)
                    return {self.names.execute}(_p, {{...}}, _child_upvals)
                end
            end''')

        add(Opcode.CALL, f'''local _args = {{}}
            for _i = 1, {b} - 1 do _args[_i] = {r}[{a} + _i] end
            local _fn = {r}[{a}]
            local _rets = {{_fn({self.names.tbl_unpack}(_args, 1, {b} - 1))}}
            local _need = {c} - 1
            if _need == -1 then _need = #_rets end
            for _i = 1, _need do {r}[{a} + _i - 1] = _rets[_i] end''')

        add(Opcode.TAILCALL, f'''local _args = {{}}
            for _i = 1, {b} - 1 do _args[_i] = {r}[{a} + _i] end
            return {r}[{a}]({self.names.tbl_unpack}(_args, 1, {b} - 1))''')

        add(Opcode.RETURN, f'''if {b} == 0 then return end
            local _rets = {{}}
            for _i = 1, {b} do _rets[_i] = {r}[{a} + _i - 1] end
            return {self.names.tbl_unpack}(_rets, 1, {b})''')

        add(Opcode.VARARG, f'{r}[{a}] = nil')

        add(Opcode.SELF, f'''{r}[{a} + 1] = {r}[{b}]
            {r}[{a}] = {r}[{b}][{r}[{c}]]''')

        add(Opcode.FORPREP, f'''{r}[{a}] = {r}[{a}] - {r}[{a} + 2]
            {pc} = {pc} + {kop}''')

        add(Opcode.FORLOOP, f'''{r}[{a}] = {r}[{a}] + {r}[{a} + 2]
            local _step = {r}[{a} + 2]
            local _cont
            if _step > 0 then _cont = ({r}[{a}] <= {r}[{a} + 1]) else _cont = ({r}[{a}] >= {r}[{a} + 1]) end
            if _cont then
                {r}[{a} + 3] = {r}[{a}]
                {pc} = {pc} + {kop}
            end''')

        add(Opcode.TFORCALL, f'''local _rets = {{{r}[{a}]({r}[{a} + 1], {r}[{a} + 2])}}
            for _i = 1, {b} do {r}[{a} + 2 + _i] = _rets[_i] end''')

        add(Opcode.TFORLOOP, f'''if {r}[{a} + 3] ~= nil then
                {r}[{a} + 2] = {r}[{a} + 3]
                {pc} = {pc} + {kop}
            end''')

        add(Opcode.CLOSE, 'local _nzl_close = nil')
        add(Opcode.NOP, 'local _nzl_nop = nil')
        add(Opcode.CHECKSUM, 'local _nzl_checksum = nil')
        add(Opcode.TRAP, 'while true do end')

        return branches

    def _gen_junk_branches(self, r: str) -> List[tuple]:
        junk_branches = []
        used_nums = {self.op_map.get_num(op) for op in Opcode}
        candidates = [n for n in range(1, 256) if n not in used_nums]
        if not candidates:
            return junk_branches

        n_junk = min(self.rng.randint(3, 8), len(candidates))
        for num in self.rng.sample(candidates, n_junk):
            junk_body = f'            local _junk_{num} = {r}[0]'
            junk_branches.append((f'{self.names.op} == {num}', junk_body))
        return junk_branches

    def _gen_create_vm(self) -> str:
        n = self.names
        bc = self.name_gen.generate()
        k = self.name_gen.generate()
        dec = self.name_gen.generate()
        p = self.name_gen.generate()

        code = f'''local function {n.create_vm}({bc}, {k})
    local {dec} = {n.decode_str}({bc}, {k})
    local {p} = {n.decode_bc}({dec})
    return function(...)
        return {n.execute}({p}, {{...}}, nil)
    end
end'''
        return code

    def _generate_wrapper(self, fn_name: str, bytecode_lit: str, key_lit: str) -> str:
        n = self.names
        return f'''-- VM-protected function
local {fn_name} = {n.create_vm}(
    {bytecode_lit},
    {key_lit}
)'''

    def stats(self) -> Dict[str, Any]:
        return {
            'seed': self.seed,
            'opcode_map_seed': self.op_map.seed,
            'num_opcodes': len(list(Opcode)),
        }


def generate_vm_code(
    proto: Proto,
    fn_name: str = 'protectedFn',
    seed: Optional[int] = None,
) -> str:
    gen = RuntimeGenerator(seed=seed)
    return gen.generate_vm_wrapper(proto, fn_name=fn_name)


def _test():
    import os
    import sys

    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if root not in sys.path:
        sys.path.insert(0, root)

    from obfuscator.lexer import Lexer
    from obfuscator.parser import Parser
    from obfuscator.vm.compiler import compile_function

    def parse_func(params: str, body: str):
        code = f'local function __fn__({params}) {body} end'
        ast = Parser(Lexer(code).tokenize()).parse()
        return ast.body.statements[0].func

    passed = 0
    failed = 0

    def ok(label):
        nonlocal passed
        passed += 1
        print(f'  ✅ {label}')

    def fail(label, detail=''):
        nonlocal failed
        failed += 1
        print(f'  ❌ {label}' + (f' — {detail}' if detail else ''))

    def check(label, cond, detail=''):
        if cond:
            ok(label)
        else:
            fail(label, detail)

    print('\n' + '═' * 56)
    print('  NZL VM Runtime Generator — Tests')
    print('═' * 56)

    print('\n[1] Basic function')
    fn = parse_func('a, b', 'return a + b')
    proto = compile_function(fn, 'add')
    gen = RuntimeGenerator(seed=1)
    code = gen.generate_vm_wrapper(proto, 'myAdd')
    check('generated code exists', isinstance(code, str) and len(code) > 500)
    check('contains myAdd', 'myAdd' in code)
    check('contains bit32.bxor', 'bit32.bxor' in code)

    print('\n[2] Escaped bytecode')
    check('bytecode uses \\ddd', '\\1' in code or '\\2' in code or '\\0' in code)

    print('\n[3] Non-empty dispatch branches')
    lines = code.split('\n')
    empty_branches = 0
    for idx, line in enumerate(lines):
        s = line.strip()
        if s.endswith('then') and idx + 1 < len(lines):
            nxt = lines[idx + 1].strip()
            if nxt.startswith('elseif') or nxt == 'end':
                empty_branches += 1
    check('no empty branches', empty_branches == 0, str(empty_branches))

    print('\n[4] Upvalue-aware recursion factory')
    fn2 = parse_func('', '''
local function fn(n)
    if n <= 1 then return 1 end
    return n * fn(n - 1)
end
return fn
''')
    try:
        proto2 = compile_function(fn2, 'factory')
        code2 = gen.generate_vm_wrapper(proto2, 'factFactory')
        check('factory code generated', len(code2) > 800)
        check('closure uses proto.upvalues', '.upvalues' in code2)
    except Exception as e:
        fail('factory code generated', str(e))

    print('\n[5] Polymorphism')
    gen1 = RuntimeGenerator(seed=100)
    gen2 = RuntimeGenerator(seed=200)
    c1 = gen1.generate_vm_wrapper(proto, 'fn')
    c2 = gen2.generate_vm_wrapper(proto, 'fn')
    check('different seeds -> different code', c1 != c2)

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