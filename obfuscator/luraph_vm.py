"""
NZL Studio Obfuscator — Luraph-style VM Obfuscator

Полностью переписанная VM-защита в стиле Luraph:
- Все имена v0, v1, v2...
- Зашифрованный байткод в строке
- Декодер, чтение примитивов, десериализатор, VM-интерпретатор
- Сплющенное управление (while true do ... if vX==N then)
- Мусорные условия, мёртвые ветки
"""

from __future__ import annotations

import random
import struct
from typing import Dict, List, Optional, Tuple, Any

from .vm.compiler import compile_function, CompileError
from .vm.opcodes import Proto, Opcode
from .ast_nodes import FunctionExpr, Block
from .utils.random_gen import make_rng
from .utils.crypto import rc4_encrypt, gen_random_key


class LuraphVMObfuscator:
    """
    Генератор VM-обфускации в стиле Luraph.
    
    Вход: AST функции
    Выход: самодостаточный Lua-код с VM-интерпретатором
    """
    
    def __init__(self, seed: Optional[int] = None):
        if seed is None:
            seed = random.randint(0, 2**32 - 1)
        self.seed = seed
        self.rng = make_rng(seed)
        self.var_counter = 0
        self.opcode_map = self._generate_opcode_map()
        
    def _next_var(self) -> str:
        """Генерирует следующее имя переменной v0, v1, v2..."""
        name = f"v{self.var_counter}"
        self.var_counter += 1
        return name
    
    def _generate_opcode_map(self) -> Dict[int, int]:
        """Генерирует маппинг opcode -> obfuscated_opcode"""
        opcodes = list(range(len(Opcode)))
        shuffled = opcodes.copy()
        self.rng.shuffle(shuffled)
        return {opcodes[i]: shuffled[i] for i in range(len(opcodes))}
    
    def _obfuscate_number(self, n: int) -> str:
        """Обфусцирует число через арифметические выражения"""
        choice = self.rng.randint(0, 3)
        if choice == 0:
            # Простое число
            return str(n)
        elif choice == 1:
            # a + b = n
            a = self.rng.randint(0, n if n > 0 else 100)
            b = n - a
            return f"({a} + {b})"
        elif choice == 2:
            # a - b = n
            a = self.rng.randint(n, n + 1000)
            b = a - n
            return f"({a} - {b})"
        else:
            # bit32.bxor(a, b) = n
            a = self.rng.randint(0, 255)
            b = n ^ a
            return f"bit32.bxor({a}, {b})"
    
    def _generate_prelude(self) -> Tuple[str, Dict[str, str]]:
        """
        Генерирует прелюдию с локальными переменными.
        Возвращает (код, маппинг имя_функции -> имя_переменной)
        """
        lines = []
        name_map = {}
        
        # Базовые функции
        funcs = [
            ("tonumber", "tonumber"),
            ("string_byte", "string.byte"),
            ("string_char", "string.char"),
            ("string_sub", "string.sub"),
            ("string_gsub", "string.gsub"),
            ("string_rep", "string.rep"),
            ("string_len", "string.len"),
            ("math_ldexp", "math.ldexp"),
            ("math_floor", "math.floor"),
            ("bit32_bxor", "bit32.bxor"),
            ("bit32_band", "bit32.band"),
            ("bit32_bor", "bit32.bor"),
            ("bit32_lshift", "bit32.lshift"),
            ("bit32_rshift", "bit32.rshift"),
            ("table_unpack", "(table.unpack or unpack)"),
            ("setmetatable", "setmetatable"),
            ("getmetatable", "getmetatable"),
            ("pcall", "pcall"),
            ("select", "select"),
            ("type", "type"),
            ("tostring", "tostring"),
            ("error", "error"),
            ("rawget", "rawget"),
            ("rawset", "rawset"),
        ]
        
        for func_name, func_value in funcs:
            var_name = self._next_var()
            lines.append(f"local {var_name}={func_value};")
            name_map[func_name] = var_name
        
        return "\n".join(lines), name_map
    
    def _encode_proto(self, proto: Proto) -> bytes:
        """Кодирует Proto в бинарный формат"""
        data = bytearray()
        
        # Header
        data.extend(struct.pack("<I", proto.num_params))
        data.extend(struct.pack("<B", 1 if proto.is_vararg else 0))
        data.extend(struct.pack("<I", proto.max_stack))
        data.extend(struct.pack("<I", len(proto.upvalues)))
        
        # Upvalues
        for uv in proto.upvalues:
            if isinstance(uv, (tuple, list)) and len(uv) >= 2:
                instack, index = bool(uv[0]), int(uv[1])
            elif isinstance(uv, dict):
                instack = bool(uv.get('instack', False))
                index = int(uv.get('index', 0))
            else:
                instack, index = False, 0
            data.extend(struct.pack("<B", 1 if instack else 0))
            data.extend(struct.pack("<I", index))
        
        # Constants
        data.extend(struct.pack("<I", len(proto.constants)))
        for const in proto.constants:
            from .vm.opcodes import ConstantType
            if const.type == ConstantType.NIL:
                data.extend(b"\x00")
            elif const.type == ConstantType.BOOL:
                data.extend(b"\x01")
                data.extend(struct.pack("<B", 1 if const.value else 0))
            elif const.type == ConstantType.NUMBER:
                data.extend(b"\x02")
                data.extend(struct.pack("<d", float(const.value)))
            elif const.type == ConstantType.STRING:
                data.extend(b"\x03")
                encoded = str(const.value).encode("utf-8")
                data.extend(struct.pack("<I", len(encoded)))
                data.extend(encoded)
            elif const.type == ConstantType.PROTO:
                data.extend(b"\x04")
                data.extend(struct.pack("<I", int(const.value)))
            else:
                data.extend(b"\x00")
        
        # Code (instructions)
        data.extend(struct.pack("<I", len(proto.code)))
        for instr in proto.code:
            obf_op = self.opcode_map.get(int(instr.op), int(instr.op))
            data.extend(struct.pack("<B", obf_op))
            data.extend(struct.pack("<B", instr.a & 0xFF))
            data.extend(struct.pack("<B", instr.b & 0xFF))
            data.extend(struct.pack("<B", instr.c & 0xFF))
            k = instr.k
            if k < 0:
                k += 2**32
            data.extend(struct.pack("<I", k & 0xFFFFFFFF))
        
        # Protos (рекурсивно)
        data.extend(struct.pack("<I", len(proto.protos)))
        for sub_proto in proto.protos:
            sub_data = self._encode_proto(sub_proto)
            data.extend(struct.pack("<I", len(sub_data)))
            data.extend(sub_data)
        
        return bytes(data)
    
    def _encrypt_bytecode(self, data: bytes) -> Tuple[str, str]:
        """Шифрует байткод RC4 и возвращает (encoded_string, key)"""
        # Используем self.rng для детерминированной генерации ключа
        key = bytes([self.rng.randint(0, 255) for _ in range(16)])
        encrypted = rc4_encrypt(data, key)
        
        # Кодируем как строку с escape-последовательностями
        encoded = ""
        for byte in encrypted:
            encoded += f"\\{byte}"
        
        # Кодируем ключ
        key_encoded = ""
        for byte in key:
            key_encoded += f"\\{byte}"
        
        return encoded, key_encoded
    
    def _generate_decoder(self, names: Dict[str, str]) -> Tuple[str, str]:
        """
        Генерирует декодер строки (RC4).
        Возвращает (код, имя_функции)
        """
        func_name = self._next_var()
        s_var = self._next_var()
        k_var = self._next_var()
        i_var = self._next_var()
        j_var = self._next_var()
        t_var = self._next_var()
        result_var = self._next_var()
        
        k_local = self._next_var()
        
        code = f"""local function {func_name}({s_var}, {k_var})
    local {i_var}, {j_var}, {t_var} = 0, 0, {{}}
    for {i_var} = 0, 255 do {t_var}[{i_var}] = {i_var} end
    {i_var} = 0
    for {i_var} = 0, 255 do
        {j_var} = ({j_var} + {t_var}[{i_var}] + {names['string_byte']}({k_var}, ({i_var} % {names['string_len']}({k_var})) + 1)) % 256
        {t_var}[{i_var}], {t_var}[{j_var}] = {t_var}[{j_var}], {t_var}[{i_var}]
    end
    {i_var}, {j_var} = 0, 0
    local {result_var} = {{}}
    for {i_var} = 1, {names['string_len']}({s_var}) do
        {j_var} = ({j_var} + 1) % 256
        local {k_local} = ({t_var}[{j_var}] + {names['string_byte']}({s_var}, {i_var})) % 256
        {result_var}[{i_var}] = {names['string_char']}({names['bit32_bxor']}({names['string_byte']}({s_var}, {i_var}), {t_var}[({t_var}[{j_var}] + {k_local}) % 256]))
    end
    return {names['table_unpack']}({result_var})
end"""
        
        return code, func_name
    
    def _generate_readers(self, names: Dict[str, str]) -> Tuple[str, Dict[str, str]]:
        """
        Генерирует функции чтения примитивов.
        Возвращает (код, маппинг имя_функции -> имя_переменной)
        """
        lines = []
        reader_map = {}
        
        # read_byte
        func_name = self._next_var()
        s_var = self._next_var()
        i_var = self._next_var()
        lines.append(f"""local function {func_name}({s_var}, {i_var})
    return {names['string_byte']}({s_var}, {i_var}), {i_var} + {self._obfuscate_number(1)}
end""")
        reader_map["read_byte"] = func_name
        
        # read_uint16
        func_name = self._next_var()
        s_var = self._next_var()
        i_var = self._next_var()
        b1_var = self._next_var()
        b2_var = self._next_var()
        lines.append(f"""local function {func_name}({s_var}, {i_var})
    local {b1_var}, {b2_var} = {names['string_byte']}({s_var}, {i_var}), {names['string_byte']}({s_var}, {i_var} + {self._obfuscate_number(1)})
    return {b1_var} + {b2_var} * {self._obfuscate_number(256)}, {i_var} + {self._obfuscate_number(2)}
end""")
        reader_map["read_uint16"] = func_name
        
        # read_uint32
        func_name = self._next_var()
        s_var = self._next_var()
        i_var = self._next_var()
        b1_var = self._next_var()
        b2_var = self._next_var()
        b3_var = self._next_var()
        b4_var = self._next_var()
        lines.append(f"""local function {func_name}({s_var}, {i_var})
    local {b1_var}, {b2_var}, {b3_var}, {b4_var} = {names['string_byte']}({s_var}, {i_var}), {names['string_byte']}({s_var}, {i_var} + {self._obfuscate_number(1)}), {names['string_byte']}({s_var}, {i_var} + {self._obfuscate_number(2)}), {names['string_byte']}({s_var}, {i_var} + {self._obfuscate_number(3)})
    return {b1_var} + {b2_var} * {self._obfuscate_number(256)} + {b3_var} * {self._obfuscate_number(65536)} + {b4_var} * {self._obfuscate_number(16777216)}, {i_var} + {self._obfuscate_number(4)}
end""")
        reader_map["read_uint32"] = func_name
        
        # read_double
        func_name = self._next_var()
        s_var = self._next_var()
        i_var = self._next_var()
        bytes_var = self._next_var()
        sign_var = self._next_var()
        exp_var = self._next_var()
        mant_var = self._next_var()
        j_var = self._next_var()
        
        lines.append(f"""local function {func_name}({s_var}, {i_var})
    local {bytes_var} = {{}}
    for {j_var} = 0, 7 do {bytes_var}[{j_var}] = {names['string_byte']}({s_var}, {i_var} + {j_var}) end
    local {sign_var} = {names['bit32_band']}({bytes_var}[7], 128) > 0 and -1 or 1
    local {exp_var} = {names['bit32_band']}({bytes_var}[7], 127) * 16 + {names['bit32_rshift']}({bytes_var}[6], 4)
    local {mant_var} = ({bytes_var}[0] + {bytes_var}[1] * 256 + {bytes_var}[2] * 65536 + {bytes_var}[3] * 16777216 + {bytes_var}[4] * 4294967296 + {names['bit32_band']}({bytes_var}[5], 15) * 1099511627776) / 4503599627370496
    if {exp_var} == 0 then return {sign_var} * {mant_var} * 2^-1022, {i_var} + 8 end
    if {exp_var} == 2047 then return {mant_var} == 0 and ({sign_var} / 0) or (0/0), {i_var} + 8 end
    return {sign_var} * (1 + {mant_var}) * 2^({exp_var} - 1023), {i_var} + 8
end""")
        reader_map["read_double"] = func_name
        
        # read_string
        func_name = self._next_var()
        s_var = self._next_var()
        i_var = self._next_var()
        len_var = self._next_var()
        new_i_var = self._next_var()
        lines.append(f"""local function {func_name}({s_var}, {i_var})
    local {len_var}, {new_i_var} = {reader_map['read_uint32']}({s_var}, {i_var})
    return {names['string_sub']}({s_var}, {new_i_var}, {new_i_var} + {len_var} - 1), {new_i_var} + {len_var}
end""")
        reader_map["read_string"] = func_name
        
        return "\n\n".join(lines), reader_map
    
    def _generate_deserializer(self, names: Dict[str, str], readers: Dict[str, str]) -> Tuple[str, str]:
        """
        Генерирует десериализатор прототипов.
        Возвращает (код, имя_функции)
        """
        func_name = self._next_var()
        data_var = self._next_var()
        i_var = self._next_var()
        proto_var = self._next_var()
        
        # Все имена в десериализаторе — через vXX
        is_vararg_v = self._next_var()
        num_upvalues_v = self._next_var()
        u_v = self._next_var()
        instack_v = self._next_var()
        idx_v = self._next_var()
        num_consts_v = self._next_var()
        c_v = self._next_var()
        ctype_v = self._next_var()
        bval_v = self._next_var()
        val_v = self._next_var()
        num_code_v = self._next_var()
        op_v = self._next_var()
        a_v = self._next_var()
        b_v = self._next_var()
        cc_v = self._next_var()
        k_v = self._next_var()
        num_protos_v = self._next_var()
        len_v = self._next_var()
        sub_data_v = self._next_var()
        
        code = f"""local function {func_name}({data_var})
    local {i_var} = 1
    local {proto_var} = {{constants = {{}}, code = {{}}, protos = {{}}, upvalues = {{}}}}
    {proto_var}.num_params, {i_var} = {readers['read_uint32']}({data_var}, {i_var})
    local {is_vararg_v}
    {is_vararg_v}, {i_var} = {readers['read_byte']}({data_var}, {i_var})
    {proto_var}.is_vararg = ({is_vararg_v} == 1)
    {proto_var}.max_stack, {i_var} = {readers['read_uint32']}({data_var}, {i_var})
    local {num_upvalues_v}
    {num_upvalues_v}, {i_var} = {readers['read_uint32']}({data_var}, {i_var})
    for {u_v} = 1, {num_upvalues_v} do
        local {instack_v}, {idx_v}
        {instack_v}, {i_var} = {readers['read_byte']}({data_var}, {i_var})
        {idx_v}, {i_var} = {readers['read_uint32']}({data_var}, {i_var})
        {proto_var}.upvalues[{u_v}] = {{instack = ({instack_v} == 1), index = {idx_v}}}
    end
    local {num_consts_v}
    {num_consts_v}, {i_var} = {readers['read_uint32']}({data_var}, {i_var})
    for {c_v} = 1, {num_consts_v} do
        local {ctype_v}
        {ctype_v}, {i_var} = {readers['read_byte']}({data_var}, {i_var})
        if {ctype_v} == 0 then
            {proto_var}.constants[{c_v}] = nil
        elseif {ctype_v} == 1 then
            local {bval_v}
            {bval_v}, {i_var} = {readers['read_byte']}({data_var}, {i_var})
            {proto_var}.constants[{c_v}] = ({bval_v} == 1)
        elseif {ctype_v} == 2 then
            local {val_v}
            {val_v}, {i_var} = {readers['read_double']}({data_var}, {i_var})
            {proto_var}.constants[{c_v}] = {val_v}
        elseif {ctype_v} == 3 then
            local {val_v}
            {val_v}, {i_var} = {readers['read_string']}({data_var}, {i_var})
            {proto_var}.constants[{c_v}] = {val_v}
        elseif {ctype_v} == 4 then
            local {val_v}
            {val_v}, {i_var} = {readers['read_uint32']}({data_var}, {i_var})
            {proto_var}.constants[{c_v}] = {val_v}
        end
    end
    local {num_code_v}
    {num_code_v}, {i_var} = {readers['read_uint32']}({data_var}, {i_var})
    for {c_v} = 1, {num_code_v} do
        local {op_v}, {a_v}, {b_v}, {cc_v}, {k_v}
        {op_v}, {i_var} = {readers['read_byte']}({data_var}, {i_var})
        {a_v}, {i_var} = {readers['read_byte']}({data_var}, {i_var})
        {b_v}, {i_var} = {readers['read_byte']}({data_var}, {i_var})
        {cc_v}, {i_var} = {readers['read_byte']}({data_var}, {i_var})
        {k_v}, {i_var} = {readers['read_uint32']}({data_var}, {i_var})
        if {k_v} >= 2147483648 then {k_v} = {k_v} - 4294967296 end
        {proto_var}.code[{c_v}] = {{{op_v}, {a_v}, {b_v}, {cc_v}, {k_v}}}
    end
    local {num_protos_v}
    {num_protos_v}, {i_var} = {readers['read_uint32']}({data_var}, {i_var})
    for {c_v} = 1, {num_protos_v} do
        local {len_v}
        {len_v}, {i_var} = {readers['read_uint32']}({data_var}, {i_var})
        local {sub_data_v} = {names['string_sub']}({data_var}, {i_var}, {i_var} + {len_v} - 1)
        {proto_var}.protos[{c_v}] = {func_name}({sub_data_v})
        {i_var} = {i_var} + {len_v}
    end
    return {proto_var}
end"""
        
        return code, func_name
    
    def _generate_vm_interpreter(self, names: Dict[str, str], deserializer_name: str) -> Tuple[str, str]:
        """
        Генерирует VM-интерпретатор со сплющенным управлением.
        Возвращает (код, имя_функции)
        """
        func_name = self._next_var()
        proto_var = self._next_var()
        args_var = self._next_var()
        env_var = self._next_var()
        pc_var = self._next_var()
        regs_var = self._next_var()
        
        # Имена переменных для инструкций (используются и в диспетчере, и в основном цикле)
        instr_var = self._next_var()
        op_var = self._next_var()
        a_var = self._next_var()
        b_var = self._next_var()
        c_var = self._next_var()
        k_var = self._next_var()
        state_var = self._next_var()
        results_var = self._next_var()
        loop_i = self._next_var()
        
        # Генерируем opcode -> obfuscated opcode mapping
        opcode_checks = []
        for orig_op, obf_op in sorted(self.opcode_map.items()):
            op_name = Opcode(orig_op).name
            opcode_checks.append((obf_op, orig_op, op_name))
        
        # Сортируем по obfuscated opcode для лучшего obfuscation
        opcode_checks.sort(key=lambda x: x[0])
        
        # Генерируем ветки диспетчера
        dispatch_branches = []
        for obf_op, orig_op, op_name in opcode_checks:
            branch_code = self._generate_opcode_handler(orig_op, op_name, names, regs_var, pc_var, proto_var, env_var, args_var, deserializer_name, func_name, a_var, b_var, c_var, k_var)
            obf_op_expr = self._obfuscate_number(obf_op)
            dispatch_branches.append(f"        if {state_var} == {obf_op_expr} then\n{branch_code}\n        end")
        
        # Добавляем мусорные ветки
        junk_branches = self._generate_junk_branches(regs_var, state_var)
        all_branches = dispatch_branches + junk_branches
        self.rng.shuffle(all_branches)
        
        # Собираем диспетчер
        dispatch_code = "\n".join(all_branches)
        
        code = f"""local function {func_name}({proto_var}, {args_var}, {env_var})
    local {pc_var} = 1
    local {regs_var} = {{}}
    for {loop_i} = 1, {proto_var}.num_params do
        {regs_var}[{loop_i} - 1] = {args_var}[{loop_i}]
    end
    while true do
        local {instr_var} = {proto_var}.code[{pc_var}]
        if not {instr_var} then break end
        local {op_var}, {a_var}, {b_var}, {c_var}, {k_var} = {instr_var}[1], {instr_var}[2], {instr_var}[3], {instr_var}[4], {instr_var}[5]
        local {state_var} = {op_var}
        while true do
{dispatch_code}
            break
        end
        {pc_var} = {pc_var} + 1
        if {op_var} == {self._obfuscate_number(self.opcode_map[Opcode.RETURN])} then
            local {results_var} = {{}}
            for {loop_i} = {a_var}, {b_var} > 0 and ({a_var} + {b_var} - 2) or #{regs_var} do
                {results_var}[#{results_var} + 1] = {regs_var}[{loop_i}]
            end
            return {names['table_unpack']}({results_var})
        end
    end
end"""
        
        return code, func_name
    
    def _generate_opcode_handler(self, opcode: int, op_name: str, names: Dict[str, str], 
                                 regs: str, pc: str, proto: str, env: str, args: str,
                                 deserializer: str, vm_name: str, 
                                 a_var: str, b_var: str, c_var: str, k_var: str) -> str:
        """Генерирует обработчик одного опкода"""
        
        a, b, c, k = a_var, b_var, c_var, k_var
        
        if op_name == "LOADK":
            return f"            {regs}[{a}] = {proto}.constants[{b} + 1]"
        elif op_name == "LOADN":
            return f"            {regs}[{a}] = {b}"
        elif op_name == "LOADBOOL":
            return f"            {regs}[{a}] = ({b} == 1)"
        elif op_name == "LOADNIL":
            return f"            {regs}[{a}] = nil"
        elif op_name == "MOVE":
            return f"            {regs}[{a}] = {regs}[{b}]"
        elif op_name == "GETGLOBAL":
            return f"            {regs}[{a}] = {env}[{proto}.constants[{b} + 1]]"
        elif op_name == "SETGLOBAL":
            return f"            {env}[{proto}.constants[{b} + 1]] = {regs}[{a}]"
        elif op_name == "GETUPVAL":
            return f"            {regs}[{a}] = {env}_upvalues[{b} + 1]"
        elif op_name == "SETUPVAL":
            return f"            {env}_upvalues[{b} + 1] = {regs}[{a}]"
        elif op_name == "NEWTABLE":
            return f"            {regs}[{a}] = {{}}"
        elif op_name == "GETTABLE":
            return f"            {regs}[{a}] = {regs}[{b}][{regs}[{c}]]"
        elif op_name == "SETTABLE":
            return f"            {regs}[{b}][{regs}[{c}]] = {regs}[{a}]"
        elif op_name == "GETFIELD":
            return f"            {regs}[{a}] = {regs}[{b}][{proto}.constants[{c} + 1]]"
        elif op_name == "SETFIELD":
            return f"            {regs}[{a}][{proto}.constants[{c} + 1]] = {regs}[{b}]"
        elif op_name == "ADD":
            return f"            {regs}[{a}] = {regs}[{b}] + {regs}[{c}]"
        elif op_name == "SUB":
            return f"            {regs}[{a}] = {regs}[{b}] - {regs}[{c}]"
        elif op_name == "MUL":
            return f"            {regs}[{a}] = {regs}[{b}] * {regs}[{c}]"
        elif op_name == "DIV":
            return f"            {regs}[{a}] = {regs}[{b}] / {regs}[{c}]"
        elif op_name == "MOD":
            return f"            {regs}[{a}] = {regs}[{b}] % {regs}[{c}]"
        elif op_name == "POW":
            return f"            {regs}[{a}] = {regs}[{b}] ^ {regs}[{c}]"
        elif op_name == "UNM":
            return f"            {regs}[{a}] = -{regs}[{b}]"
        elif op_name == "NOT":
            return f"            {regs}[{a}] = not {regs}[{b}]"
        elif op_name == "LEN":
            return f"            {regs}[{a}] = #{regs}[{b}]"
        elif op_name == "CONCAT":
            res = self._next_var()
            ci = self._next_var()
            return f"""            local {res} = {regs}[{b}]
            for {ci} = {b} + 1, {c} do {res} = {res} .. {regs}[{ci}] end
            {regs}[{a}] = {res}"""
        elif op_name == "EQ":
            return f"            if ({regs}[{b}] == {regs}[{c}]) == ({a} == 1) then {pc} = {pc} + 1 end"
        elif op_name == "NEQ":
            return f"            if ({regs}[{b}] ~= {regs}[{c}]) == ({a} == 1) then {pc} = {pc} + 1 end"
        elif op_name == "LT":
            return f"            if ({regs}[{b}] < {regs}[{c}]) == ({a} == 1) then {pc} = {pc} + 1 end"
        elif op_name == "LE":
            return f"            if ({regs}[{b}] <= {regs}[{c}]) == ({a} == 1) then {pc} = {pc} + 1 end"
        elif op_name == "GT":
            return f"            if ({regs}[{b}] > {regs}[{c}]) == ({a} == 1) then {pc} = {pc} + 1 end"
        elif op_name == "GE":
            return f"            if ({regs}[{b}] >= {regs}[{c}]) == ({a} == 1) then {pc} = {pc} + 1 end"
        elif op_name == "AND":
            return f"            {regs}[{a}] = {regs}[{b}] and {regs}[{c}]"
        elif op_name == "OR":
            return f"            {regs}[{a}] = {regs}[{b}] or {regs}[{c}]"
        elif op_name == "JMP":
            return f"            {pc} = {pc} + {b} - 1"
        elif op_name == "JMPIF":
            return f"            if {regs}[{a}] then {pc} = {pc} + {b} - 1 end"
        elif op_name == "JMPIFNOT":
            return f"            if not {regs}[{a}] then {pc} = {pc} + {b} - 1 end"
        elif op_name == "CLOSURE":
            sub_p = self._next_var()
            cl_env = self._next_var()
            ci = self._next_var()
            ck = self._next_var()
            cv = self._next_var()
            uv = self._next_var()
            return f"""            local {sub_p} = {proto}.protos[{b} + 1]
            local {cl_env} = {{}}
            for {ck}, {cv} in pairs({env}) do {cl_env}[{ck}] = {cv} end
            {cl_env}._upvalues = {{}}
            for {ci}, {uv} in ipairs({sub_p}.upvalues) do
                if {uv}.instack then {cl_env}._upvalues[{ci}] = {regs}[{uv}.index]
                else {cl_env}._upvalues[{ci}] = {env}_upvalues[{uv}.index + 1] end
            end
            {regs}[{a}] = function(...) return {vm_name}({sub_p}, {{...}}, {cl_env}) end"""
        elif op_name == "CALL":
            func_v = self._next_var()
            call_args_v = self._next_var()
            results_v = self._next_var()
            ci = self._next_var()
            return f"""            local {func_v} = {regs}[{a}]
            local {call_args_v} = {{}}
            for {ci} = {a} + 1, {b} > 0 and ({a} + {b} - 1) or #{regs} do {call_args_v}[#{call_args_v} + 1] = {regs}[{ci}] end
            local {results_v} = {{{func_v}({names['table_unpack']}({call_args_v}))}}
            for {ci} = 1, {c} > 0 and ({c} - 1) or #{results_v} do {regs}[{a} + {ci} - 1] = {results_v}[{ci}] end"""
        elif op_name == "TAILCALL":
            func_v = self._next_var()
            call_args_v = self._next_var()
            ci = self._next_var()
            return f"""            local {func_v} = {regs}[{a}]
            local {call_args_v} = {{}}
            for {ci} = {a} + 1, {b} > 0 and ({a} + {b} - 1) or #{regs} do {call_args_v}[#{call_args_v} + 1] = {regs}[{ci}] end
            return {func_v}({names['table_unpack']}({call_args_v}))"""
        elif op_name == "RETURN":
            return "            "
        elif op_name == "FORPREP":
            return f"""            {regs}[{a}] = {regs}[{a}] - {regs}[{a} + 2]
            {pc} = {pc} + {b} - 1"""
        elif op_name == "FORLOOP":
            step_v = self._next_var()
            cont_v = self._next_var()
            return f"""            {regs}[{a}] = {regs}[{a}] + {regs}[{a} + 2]
            local {step_v} = {regs}[{a} + 2]
            local {cont_v} = ({step_v} > 0) and ({regs}[{a}] <= {regs}[{a} + 1]) or ({regs}[{a}] >= {regs}[{a} + 1])
            if {cont_v} then
                {regs}[{a} + 3] = {regs}[{a}]
                {pc} = {pc} + {b} - 1
            end"""
        elif op_name == "SELF":
            return f"""            {regs}[{a} + 1] = {regs}[{b}]
            {regs}[{a}] = {regs}[{b}][{regs}[{c}]]"""
        elif op_name == "VARARG":
            ci = self._next_var()
            return f"""            for {ci} = 0, {b} - 2 do {regs}[{a} + {ci}] = {args}[{ci} + 1] end"""
        elif op_name == "TRAP":
            return "            while true do end"
        else:
            return "            "
    
    def _generate_junk_branches(self, regs: str, state_var: str) -> List[str]:
        """Генерирует мусорные ветки для obfuscation"""
        branches = []
        num_junk = self.rng.randint(5, 15)
        
        for i in range(num_junk):
            junk_val = self.rng.randint(200, 255)
            
            # Разные типы мусорных операций
            choice = self.rng.randint(0, 3)
            if choice == 0:
                body = f"            local _ = {regs}[0]"
            elif choice == 1:
                body = f"            local _ = {self._obfuscate_number(self.rng.randint(0, 1000))}"
            elif choice == 2:
                body = f"            local _ = bit32.bxor({self.rng.randint(0, 255)}, {self.rng.randint(0, 255)})"
            else:
                junk_str = ''.join(self.rng.choices('abcdefghijklmnopqrstuvwxyz', k=5))
                body = f'            local _ = #"{junk_str}"'
            
            branches.append(f"        if {state_var} == {self._obfuscate_number(junk_val)} then\n{body}\n        end")
        
        return branches
    
    def obfuscate(self, func: FunctionExpr, func_name: str = "protected") -> str:
        """
        Главная функция: обфусцирует функцию в Luraph-стиль.
        
        Args:
            func: AST функции
            func_name: имя для результирующей функции
            
        Returns:
            Полный Lua-код с VM-интерпретатором
        """
        # Компилируем функцию в байткод
        proto = compile_function(func, func_name)
        
        # Кодируем байткод
        bytecode_data = self._encode_proto(proto)
        encrypted_bc, key = self._encrypt_bytecode(bytecode_data)
        
        # Генерируем все части кода
        prelude, names = self._generate_prelude()
        decoder_code, decoder_name = self._generate_decoder(names)
        readers_code, reader_map = self._generate_readers(names)
        deserializer_code, deserializer_name = self._generate_deserializer(names, reader_map)
        
        # Генерируем VM с передачей имени десериализатора
        vm_code, vm_name = self._generate_vm_interpreter(names, deserializer_name)
        
        # Финальная сборка
        bytecode_var = self._next_var()
        key_var = self._next_var()
        decoded_var = self._next_var()
        proto_var = self._next_var()
        result_func = self._next_var()
        
        code = f"""{prelude}

local {bytecode_var}="{encrypted_bc}";
local {key_var}="{key}";

{decoder_code}

{readers_code}

{deserializer_code}

{vm_code}

local {result_func} = function(...)
    local {decoded_var} = {decoder_name}({bytecode_var}, {key_var})
    local {proto_var} = {deserializer_name}({decoded_var})
    return {vm_name}({proto_var}, {{...}}, getfenv and getfenv() or _ENV)
end

return {result_func}"""
        
        return code


def obfuscate_function(func: FunctionExpr, func_name: str = "protected", 
                       seed: Optional[int] = None) -> str:
    """
    Удобная обёртка для обфускации одной функции.
    """
    obfuscator = LuraphVMObfuscator(seed=seed)
    return obfuscator.obfuscate(func, func_name)


def obfuscate_script(source: str, seed: Optional[int] = None) -> str:
    """
    Обфусцирует целый Lua-скрипт в Luraph-стиль.
    
    Оборачивает весь скрипт в одну функцию и компилирует в VM.
    
    Args:
        source: исходный Lua-код
        seed: seed для генератора
        
    Returns:
        Обфусцированный Lua-код
    """
    from .lexer import Lexer
    from .parser import Parser
    from .ast_nodes import FunctionExpr, Block
    
    # Парсим скрипт
    ast = Parser(Lexer(source).tokenize()).parse()
    
    # Создаём обёртку: function(...) <script body> end
    wrapper_func = FunctionExpr(
        params=[],
        is_vararg=True,
        body=ast.body,
    )
    
    # Обфусцируем
    obfuscator = LuraphVMObfuscator(seed=seed)
    vm_code = obfuscator.obfuscate(wrapper_func, "main")
    
    # Заменяем финальный 'return vX' на вызов 'vX(...)'
    # чтобы скрипт выполнился при загрузке
    stripped = vm_code.rstrip()
    last_return_idx = stripped.rfind('\nreturn ')
    if last_return_idx >= 0:
        func_name = stripped[last_return_idx + len('\nreturn '):].strip()
        vm_code = stripped[:last_return_idx] + f'\n{func_name}(...)'
    
    # Добавляем брендинг NZL Studio
    branding = "-- NZL Studio Obfuscator | discord.gg/c3kBtN9vXb"
    vm_code = f"{branding}\n{vm_code}\n{branding}"
    
    return vm_code
