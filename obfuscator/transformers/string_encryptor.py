"""
NZL Studio Obfuscator - String Encryptor Transformer
Replaces string literals in AST with encrypted runtime-decrypted versions.

Strategy:
    - Each string gets its own algorithm and key
    - Available algorithms: RC4, XOR-multi, XOR-rotating
    - Long strings may be chunked
    - Interpolated strings are decomposed:
      text parts encrypted, expression parts kept as-is
    - Decryptor function is polymorphic

FIX:
    - encrypted payloads are now stored as RawByteString (chr-mapped bytes 0..255)
    - ast_unparser is responsible for final Lua escaping
    - this removes the old double-escaping bug (\\221)
"""

import random
from typing import Optional, Tuple, Dict
from dataclasses import dataclass

from ..ast_nodes import (
    NodeTransformer,
    Chunk, Expr,
    StringLit, NumberLit, NameExpr, CallExpr,
    InterpStringLit, BinaryOp,
)
from ..utils import crypto
from ..utils.random_gen import NameGenerator, make_rng, weighted_choice


# ==================== CONSTANTS ====================

MIN_ENCRYPT_LENGTH = 2
CHUNK_THRESHOLD = 100
DEFAULT_CHUNK_SIZE = 32

ALGO_RC4 = 1
ALGO_XOR = 2
ALGO_XOR_ROT = 3

ALGO_WEIGHTS = [
    (ALGO_RC4, 50),
    (ALGO_XOR, 30),
    (ALGO_XOR_ROT, 20),
]


# ==================== STATS ====================

@dataclass
class EncryptionStats:
    total_strings: int = 0
    encrypted_strings: int = 0
    skipped_empty: int = 0
    skipped_short: int = 0
    interp_strings: int = 0
    chunked_strings: int = 0
    total_bytes_encrypted: int = 0
    algo_usage: Dict[int, int] = None

    def __post_init__(self):
        if self.algo_usage is None:
            self.algo_usage = {ALGO_RC4: 0, ALGO_XOR: 0, ALGO_XOR_ROT: 0}

    def report(self) -> str:
        algo_names = {
            ALGO_RC4: 'RC4',
            ALGO_XOR: 'XOR',
            ALGO_XOR_ROT: 'XOR-rot',
        }
        lines = [
            f"  Total strings:      {self.total_strings}",
            f"  Encrypted:          {self.encrypted_strings}",
            f"  Skipped (empty):    {self.skipped_empty}",
            f"  Skipped (short):    {self.skipped_short}",
            f"  Interpolated:       {self.interp_strings}",
            f"  Chunked (long):     {self.chunked_strings}",
            f"  Total bytes hidden: {self.total_bytes_encrypted}",
            f"  Algorithm usage:",
        ]
        for aid, count in self.algo_usage.items():
            lines.append(f"    - {algo_names[aid]:<8}: {count}")
        return '\n'.join(lines)


# ==================== ENCRYPTED PAYLOAD ====================

@dataclass
class EncryptedPayload:
    # RawByteString-compatible values for AST StringLit.value
    data: str
    key: str
    algo_id: int
    original_length: int

    # Real bytes kept for tests/debug verification
    _raw_data: bytes = b''
    _raw_key: bytes = b''

    def to_ast_call(self, decryptor_name: str, line: int = 0) -> CallExpr:
        return CallExpr(
            line=line,
            func=NameExpr(line=line, name=decryptor_name),
            args=[
                StringLit(line=line, value=self.data),
                StringLit(line=line, value=self.key),
                NumberLit(line=line, value=self.algo_id),
            ]
        )


# ==================== ENCRYPTION LOGIC ====================

class StringEncryptor:
    def __init__(self, rng: random.Random):
        self.rng = rng

    def encrypt(self, text: str) -> EncryptedPayload:
        original_length = len(text)
        text_bytes = text.encode('utf-8')

        algo_id = weighted_choice(self.rng, ALGO_WEIGHTS)

        if algo_id == ALGO_RC4:
            encrypted, key_bytes = self._encrypt_rc4(text_bytes)
        elif algo_id == ALGO_XOR:
            encrypted, key_bytes = self._encrypt_xor(text_bytes)
        elif algo_id == ALGO_XOR_ROT:
            encrypted, key_bytes = self._encrypt_xor_rot(text_bytes)
        else:
            raise ValueError(f"Unknown algorithm: {algo_id}")

        data_value = crypto.bytes_to_py_string(encrypted)
        key_value = crypto.bytes_to_py_string(key_bytes)

        return EncryptedPayload(
            data=data_value,
            key=key_value,
            algo_id=algo_id,
            original_length=original_length,
            _raw_data=encrypted,
            _raw_key=key_bytes,
        )

    def _encrypt_rc4(self, data: bytes) -> Tuple[bytes, bytes]:
        key_len = self.rng.randint(4, 8)
        key = bytes(self.rng.randint(1, 255) for _ in range(key_len))
        encrypted = crypto.rc4_encrypt(data, key)
        return encrypted, key

    def _encrypt_xor(self, data: bytes) -> Tuple[bytes, bytes]:
        key_len = self.rng.randint(2, 6)
        key = bytes(self.rng.randint(1, 255) for _ in range(key_len))
        encrypted = crypto.xor_multi(data, key)
        return encrypted, key

    def _encrypt_xor_rot(self, data: bytes) -> Tuple[bytes, bytes]:
        start = self.rng.randint(1, 255)
        rotation = self.rng.randint(1, 255)
        key = bytes([start, rotation])
        encrypted = crypto.xor_rotating(data, key_start=start, rotation=rotation)
        return encrypted, key


# ==================== MAIN TRANSFORMER ====================

class StringEncryptorTransformer(NodeTransformer):
    def __init__(
        self,
        rng: random.Random,
        decryptor_name: str,
        enable_chunking: bool = True
    ):
        self.rng = rng
        self.decryptor_name = decryptor_name
        self.enable_chunking = enable_chunking
        self.encryptor = StringEncryptor(rng)
        self.stats = EncryptionStats()

    def visit_StringLit(self, node: StringLit) -> Expr:
        self.stats.total_strings += 1
        text = node.value

        if len(text) == 0:
            self.stats.skipped_empty += 1
            return node

        if len(text) < MIN_ENCRYPT_LENGTH:
            self.stats.skipped_short += 1
            return node

        if self.enable_chunking and len(text) > CHUNK_THRESHOLD:
            return self._encrypt_chunked(text, node.line)

        return self._encrypt_single(text, node.line)

    def visit_InterpStringLit(self, node: InterpStringLit) -> Expr:
        self.stats.interp_strings += 1

        if not node.parts:
            return StringLit(line=node.line, value="")

        result_parts = []
        for part in node.parts:
            if isinstance(part, str):
                if len(part) == 0:
                    continue
                if len(part) >= MIN_ENCRYPT_LENGTH:
                    result_parts.append(self._encrypt_single(part, node.line))
                else:
                    result_parts.append(StringLit(line=node.line, value=part))
            else:
                visited_expr = self.visit(part)
                result_parts.append(
                    CallExpr(
                        line=node.line,
                        func=NameExpr(line=node.line, name='tostring'),
                        args=[visited_expr],
                    )
                )

        if len(result_parts) == 0:
            return StringLit(line=node.line, value="")
        if len(result_parts) == 1:
            return result_parts[0]

        expr = result_parts[0]
        for right in result_parts[1:]:
            expr = BinaryOp(
                line=node.line,
                op='..',
                left=expr,
                right=right,
            )
        return expr

    def _encrypt_single(self, text: str, line: int) -> CallExpr:
        payload = self.encryptor.encrypt(text)
        self.stats.encrypted_strings += 1
        self.stats.total_bytes_encrypted += len(text.encode('utf-8'))
        self.stats.algo_usage[payload.algo_id] += 1
        return payload.to_ast_call(self.decryptor_name, line)

    def _encrypt_chunked(self, text: str, line: int) -> Expr:
        self.stats.chunked_strings += 1

        num_chunks = self.rng.randint(2, 4)
        chunk_size = max(1, len(text) // num_chunks)

        chunks = []
        for i in range(0, len(text), chunk_size):
            chunks.append(text[i:i + chunk_size])

        encrypted_calls = [self._encrypt_single(chunk, line) for chunk in chunks]

        expr = encrypted_calls[0]
        for right in encrypted_calls[1:]:
            expr = BinaryOp(
                line=line,
                op='..',
                left=expr,
                right=right,
            )
        return expr


# ==================== RUNTIME LUA GENERATOR ====================

class DecryptorRuntimeGenerator:
    def __init__(self, rng: random.Random, name_gen: NameGenerator):
        self.rng = rng
        self.name_gen = name_gen

    def generate(self, decryptor_name: str) -> str:
        v_data = self.name_gen.generate()
        v_key = self.name_gen.generate()
        v_algo = self.name_gen.generate()
        v_result = self.name_gen.generate()
        v_i = self.name_gen.generate()
        v_j = self.name_gen.generate()
        v_S = self.name_gen.generate()
        v_temp = self.name_gen.generate()
        v_kbyte = self.name_gen.generate()
        v_klen = self.name_gen.generate()
        v_out = self.name_gen.generate()
        v_start = self.name_gen.generate()
        v_rot = self.name_gen.generate()

        rc4_code = self._gen_rc4(v_data, v_key, v_result, v_i, v_j, v_S, v_temp)
        xor_code = self._gen_xor_multi(v_data, v_key, v_out, v_i, v_kbyte, v_klen)
        xor_rot_code = self._gen_xor_rot(v_data, v_key, v_out, v_i, v_kbyte, v_start, v_rot)

        branches = [
            (ALGO_RC4, rc4_code),
            (ALGO_XOR, xor_code),
            (ALGO_XOR_ROT, xor_rot_code),
        ]
        self.rng.shuffle(branches)

        dispatch_lines = []
        first = True
        for algo_id, body in branches:
            keyword = 'if' if first else 'elseif'
            dispatch_lines.append(f"    {keyword} {v_algo} == {algo_id} then")
            for line in body.split('\n'):
                if line.strip():
                    dispatch_lines.append(f"        {line}")
            first = False
        dispatch_lines.append("    end")

        dispatch = '\n'.join(dispatch_lines)

        code = f"""local function {decryptor_name}({v_data}, {v_key}, {v_algo})
{dispatch}
end
"""
        return code

    def _gen_rc4(self, v_data, v_key, v_result, v_i, v_j, v_S, v_temp) -> str:
        return f"""local {v_S} = {{}}
for {v_i} = 0, 255 do {v_S}[{v_i}] = {v_i} end
local {v_j} = 0
for {v_i} = 0, 255 do
    {v_j} = ({v_j} + {v_S}[{v_i}] + string.byte({v_key}, ({v_i} % #{v_key}) + 1)) % 256
    {v_S}[{v_i}], {v_S}[{v_j}] = {v_S}[{v_j}], {v_S}[{v_i}]
end
local {v_result} = {{}}
{v_i} = 0
{v_j} = 0
for {v_temp} = 1, #{v_data} do
    {v_i} = ({v_i} + 1) % 256
    {v_j} = ({v_j} + {v_S}[{v_i}]) % 256
    {v_S}[{v_i}], {v_S}[{v_j}] = {v_S}[{v_j}], {v_S}[{v_i}]
    local k = {v_S}[({v_S}[{v_i}] + {v_S}[{v_j}]) % 256]
    {v_result}[{v_temp}] = string.char(bit32.bxor(string.byte({v_data}, {v_temp}), k))
end
return table.concat({v_result})"""

    def _gen_xor_multi(self, v_data, v_key, v_out, v_i, v_kbyte, v_klen) -> str:
        return f"""local {v_out} = {{}}
local {v_klen} = #{v_key}
for {v_i} = 1, #{v_data} do
    local {v_kbyte} = string.byte({v_key}, (({v_i} - 1) % {v_klen}) + 1)
    {v_out}[{v_i}] = string.char(bit32.bxor(string.byte({v_data}, {v_i}), {v_kbyte}))
end
return table.concat({v_out})"""

    def _gen_xor_rot(self, v_data, v_key, v_out, v_i, v_kbyte, v_start, v_rot) -> str:
        return f"""local {v_out} = {{}}
local {v_start} = string.byte({v_key}, 1)
local {v_rot} = string.byte({v_key}, 2)
local {v_kbyte} = {v_start}
for {v_i} = 1, #{v_data} do
    {v_out}[{v_i}] = string.char(bit32.bxor(string.byte({v_data}, {v_i}), {v_kbyte}))
    {v_kbyte} = ({v_kbyte} + {v_rot}) % 256
end
return table.concat({v_out})"""


# ==================== HIGH-LEVEL API ====================

def encrypt_strings_in_chunk(
    ast_chunk: Chunk,
    rng: Optional[random.Random] = None,
    name_gen: Optional[NameGenerator] = None,
    enable_chunking: bool = True,
) -> Tuple[Chunk, str, EncryptionStats]:
    if rng is None:
        rng = make_rng()
    if name_gen is None:
        name_gen = NameGenerator(rng=rng)

    decryptor_name = name_gen.generate()

    transformer = StringEncryptorTransformer(
        rng=rng,
        decryptor_name=decryptor_name,
        enable_chunking=enable_chunking,
    )
    modified_ast = transformer.visit(ast_chunk)

    runtime_gen = DecryptorRuntimeGenerator(rng=rng, name_gen=name_gen)
    decryptor_code = runtime_gen.generate(decryptor_name)

    return modified_ast, decryptor_code, transformer.stats


# ==================== SELF-TEST ====================

def _self_test():
    print("=" * 60)
    print("NZL String Encryptor Self-Test")
    print("=" * 60)

    # Test 1: round-trip using raw bytes
    print("\n[1] Round-trip encryption test:")
    rng = make_rng(seed=12345)
    encryptor = StringEncryptor(rng)

    test_strings = [
        "Hello, World!",
        "a",
        "The quick brown fox jumps over the lazy dog",
        "Special chars: \\n\\t\"'",
        "Unicode: привет мир",
        "Very long string " * 20,
        "\x00\x01\x02\xff\xfe",
    ]

    for text in test_strings:
        if len(text) == 0:
            continue

        for _ in range(5):
            payload = encryptor.encrypt(text)
            enc_bytes = payload._raw_data
            key_bytes = payload._raw_key

            assert isinstance(payload.data, crypto.RawByteString)
            assert isinstance(payload.key, crypto.RawByteString)
            assert crypto.py_string_to_bytes(payload.data) == enc_bytes
            assert crypto.py_string_to_bytes(payload.key) == key_bytes

            if payload.algo_id == ALGO_RC4:
                decrypted = crypto.rc4_encrypt(enc_bytes, key_bytes)
            elif payload.algo_id == ALGO_XOR:
                decrypted = crypto.xor_multi(enc_bytes, key_bytes)
            elif payload.algo_id == ALGO_XOR_ROT:
                decrypted = crypto.xor_rotating(enc_bytes, key_bytes[0], key_bytes[1])
            else:
                raise AssertionError(f"Unexpected algo_id: {payload.algo_id}")

            decrypted_str = decrypted.decode('utf-8')
            assert decrypted_str == text, (
                f"Mismatch! Algo={payload.algo_id}\n"
                f"Expected: {text!r}\n"
                f"Got:      {decrypted_str!r}"
            )

    print("  ✓ All 3 algorithms round-trip correctly")

    # Test 2: raw byte-string packing
    print("\n[2] Raw byte-string packing verification:")
    rnd = random.Random(999)
    for _ in range(10):
        random_bytes = bytes(rnd.randint(0, 255) for _ in range(50))
        packed = crypto.bytes_to_py_string(random_bytes)
        assert isinstance(packed, crypto.RawByteString)
        assert crypto.py_string_to_bytes(packed) == random_bytes
    print("  ✓ RawByteString preserves byte payloads exactly")

    # Test 3: full AST transformation
    print("\n[3] AST transformation:")
    from ..parser import parse

    src = '''
local msg = "Hello, World!"
local greeting = "Welcome"
print(msg)
print(greeting)
local empty = ""
local x = "a"
'''
    ast = parse(src)

    rng = make_rng(seed=999)
    modified_ast, decryptor_code, stats = encrypt_strings_in_chunk(ast, rng=rng)

    print("  Stats:")
    print(stats.report())

    print("\n  Generated decryptor (first 15 lines):")
    for line in decryptor_code.split('\n')[:15]:
        print(f"    {line}")

    # Test 4: interpolation
    print("\n[4] Interpolated string handling:")
    src_interp = '''
local name = "World"
local greeting = `Hello, ${name}!`
print(greeting)
'''
    ast_interp = parse(src_interp)
    rng = make_rng(seed=42)
    modified, decryptor, stats = encrypt_strings_in_chunk(ast_interp, rng=rng)
    print(f"  Interp strings processed: {stats.interp_strings}")
    print(f"  Text parts encrypted:     {stats.encrypted_strings}")
    assert stats.interp_strings > 0
    print("  ✓ Interpolation handled")

    # Test 5: chunking
    print("\n[5] Chunking test:")
    long_text = "x" * 200
    src_long = f'local big = "{long_text}"'
    ast_long = parse(src_long)
    rng = make_rng(seed=1)
    modified, decryptor, stats = encrypt_strings_in_chunk(ast_long, rng=rng)
    assert stats.chunked_strings == 1
    print(f"  ✓ Long string ({len(long_text)} chars) was chunked")

    # Test 6: polymorphism
    print("\n[6] Polymorphism test:")
    src_poly = 'local x = "test string"'
    outputs = set()
    for seed in [1, 2, 3, 4, 5]:
        ast_p = parse(src_poly)
        _, decryptor_p, _ = encrypt_strings_in_chunk(ast_p, rng=make_rng(seed=seed))
        outputs.add(decryptor_p)
    print(f"  5 different seeds -> {len(outputs)} different decryptors")
    assert len(outputs) == 5, "Polymorphism failed!"
    print("  ✓ Every build produces unique output")

    # Test 7: stress
    print("\n[7] Stress test (100 different strings):")
    stress_code = '\n'.join(
        f'local v{i} = "String number {i} with random data {random.random()}"'
        for i in range(100)
    )
    ast_stress = parse(stress_code)
    rng = make_rng(seed=777)
    modified, decryptor, stats = encrypt_strings_in_chunk(ast_stress, rng=rng)
    print(f"  Encrypted {stats.encrypted_strings}/100 strings")
    assert stats.encrypted_strings == 100
    print("  ✓ Stress test passed")

    print("\n" + "=" * 60)
    print("✅ ALL TESTS PASSED!")
    print("=" * 60)


if __name__ == "__main__":
    _self_test()