"""
NZL Studio Obfuscator - Cryptographic Primitives
Provides encryption utilities used across the obfuscator.

All functions are pure Python — no external dependencies.
All algorithms have matching Lua implementations.

FIX v4:
    - bytes_to_lua_string больше НЕ возвращает готовые Lua-escape'ы
    - вместо этого возвращается RawByteString: Python str с байт-мэппингом 0..255
    - AST unparser сам решает, как правильно сериализовать это в Lua
    - это убирает двойное экранирование вида \\221
"""

import os
import random
import struct
from typing import List, Tuple, Union, Optional


# ==================== RAW BYTE STRING ====================

class RawByteString(str):
    """
    Специальная строка для хранения сырых байтов 0..255 внутри AST.

    Важно:
    - каждый Python-символ == один байт
    - используется latin-1 mapping: байт 221 -> chr(221)
    - обычные пользовательские строки НЕ должны создаваться этим классом
    """

    __slots__ = ()

    @classmethod
    def from_bytes(cls, data: bytes) -> "RawByteString":
        return cls(data.decode('latin-1'))

    def to_bytes(self) -> bytes:
        return self.encode('latin-1')


def bytes_to_py_string(data: bytes) -> RawByteString:
    """
    Превращает bytes -> RawByteString с 1:1 mapping байтов 0..255.
    """
    return RawByteString.from_bytes(data)


def py_string_to_bytes(text: str) -> bytes:
    """
    Обратное преобразование для RawByteString / latin-1-compatible строки.
    """
    if isinstance(text, RawByteString):
        return text.to_bytes()
    return text.encode('latin-1')


def bytes_to_lua_string(data: bytes) -> RawByteString:
    """
    Backward-compatible alias.

    Раньше функция возвращала уже escape'нутую Lua-строку, что и ломало проект.
    Теперь она возвращает RawByteString, который должен попасть в StringLit.value,
    а дальше ast_unparser сам сериализует его в корректный Lua literal.
    """
    return bytes_to_py_string(data)


# ==================== RC4 STREAM CIPHER ====================

class RC4:
    def __init__(self, key: Union[bytes, str]):
        if isinstance(key, str):
            key = key.encode('utf-8')
        if len(key) == 0:
            raise ValueError("RC4 key cannot be empty")
        if len(key) > 256:
            key = key[:256]

        self.S = list(range(256))
        j = 0
        for i in range(256):
            j = (j + self.S[i] + key[i % len(key)]) & 0xFF
            self.S[i], self.S[j] = self.S[j], self.S[i]

        self.i = 0
        self.j = 0

    def encrypt(self, data: Union[bytes, str]) -> bytes:
        if isinstance(data, str):
            data = data.encode('utf-8')

        result = bytearray()
        S = self.S.copy()
        i, j = 0, 0

        for byte in data:
            i = (i + 1) & 0xFF
            j = (j + S[i]) & 0xFF
            S[i], S[j] = S[j], S[i]
            k = S[(S[i] + S[j]) & 0xFF]
            result.append(byte ^ k)

        return bytes(result)


def rc4_encrypt(data: Union[bytes, str], key: Union[bytes, str]) -> bytes:
    return RC4(key).encrypt(data)


# ==================== XOR CIPHERS ====================

def xor_single(data: Union[bytes, str], key_byte: int) -> bytes:
    if isinstance(data, str):
        data = data.encode('utf-8')
    key_byte &= 0xFF
    return bytes(b ^ key_byte for b in data)


def xor_multi(data: Union[bytes, str], key: Union[bytes, str]) -> bytes:
    if isinstance(data, str):
        data = data.encode('utf-8')
    if isinstance(key, str):
        key = key.encode('utf-8')
    if len(key) == 0:
        raise ValueError("XOR key cannot be empty")

    return bytes(b ^ key[i % len(key)] for i, b in enumerate(data))


def xor_rotating(data: Union[bytes, str], key_start: int, rotation: int = 7) -> bytes:
    if isinstance(data, str):
        data = data.encode('utf-8')

    key = key_start & 0xFF
    rotation &= 0xFF
    result = bytearray()

    for byte in data:
        result.append(byte ^ key)
        key = (key + rotation) & 0xFF

    return bytes(result)


# ==================== CUSTOM BASE85 ====================

BASE85_ALPHABET = (
    "0123456789"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "abcdefghijklmnopqrstuvwxyz"
    "!#$%&()*+-;<=>?@^_`{|}~"
)
assert len(BASE85_ALPHABET) == 85, f"Alphabet length must be 85, got {len(BASE85_ALPHABET)}"

_BASE85_DECODE_TABLE = {c: i for i, c in enumerate(BASE85_ALPHABET)}


def base85_encode(data: Union[bytes, str]) -> str:
    if isinstance(data, str):
        data = data.encode('utf-8')

    padding = (4 - len(data) % 4) % 4
    data += b'\0' * padding

    result = []
    for i in range(0, len(data), 4):
        chunk = data[i:i + 4]
        num = struct.unpack('>I', chunk)[0]
        encoded = []
        for _ in range(5):
            encoded.append(BASE85_ALPHABET[num % 85])
            num //= 85
        result.append(''.join(reversed(encoded)))

    encoded_str = ''.join(result)

    if padding > 0:
        encoded_str = encoded_str[:-padding]

    return encoded_str


def base85_decode(text: str) -> bytes:
    if not text:
        return b''

    remainder = len(text) % 5
    if remainder == 0:
        padding = 0
    else:
        padding = 5 - remainder
        text += BASE85_ALPHABET[0] * padding

    result = bytearray()
    for i in range(0, len(text), 5):
        chunk = text[i:i + 5]
        num = 0
        for c in chunk:
            if c not in _BASE85_DECODE_TABLE:
                raise ValueError(f"Invalid character in Base85: {c!r}")
            num = num * 85 + _BASE85_DECODE_TABLE[c]
        result.extend(struct.pack('>I', num & 0xFFFFFFFF))

    if padding > 0:
        result = result[:-padding]

    return bytes(result)


# ==================== CHUNK SPLITTING ====================

class EncryptedChunk:
    __slots__ = ('data', 'key', 'algorithm')

    def __init__(self, data: bytes, key: bytes, algorithm: str):
        self.data = data
        self.key = key
        self.algorithm = algorithm

    def __repr__(self):
        return f"Chunk({self.algorithm}, {len(self.data)}b)"


def split_and_encrypt(
    data: Union[bytes, str],
    chunk_size: int = 32,
    algorithm: str = 'rc4'
) -> List[EncryptedChunk]:
    if isinstance(data, str):
        data = data.encode('utf-8')

    if algorithm not in ('rc4', 'xor'):
        raise ValueError(f"Unknown algorithm: {algorithm}")

    chunks = []
    for i in range(0, len(data), chunk_size):
        chunk_data = data[i:i + chunk_size]

        if algorithm == 'rc4':
            key = os.urandom(4)
            encrypted = rc4_encrypt(chunk_data, key)
        else:
            key_len = random.randint(2, 4)
            key = os.urandom(key_len)
            encrypted = xor_multi(chunk_data, key)

        chunks.append(EncryptedChunk(encrypted, key, algorithm))

    return chunks


def merge_chunks(chunks: List[EncryptedChunk]) -> bytes:
    result = bytearray()
    for chunk in chunks:
        if chunk.algorithm == 'rc4':
            result.extend(rc4_encrypt(chunk.data, chunk.key))
        else:
            result.extend(xor_multi(chunk.data, chunk.key))
    return bytes(result)


# ==================== CHECKSUMS ====================

def crc32(data: Union[bytes, str]) -> int:
    if isinstance(data, str):
        data = data.encode('utf-8')

    crc = 0xFFFFFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xEDB88320
            else:
                crc >>= 1
    return crc ^ 0xFFFFFFFF


def fnv1a_hash(data: Union[bytes, str]) -> int:
    if isinstance(data, str):
        data = data.encode('utf-8')

    h = 0x811C9DC5
    for byte in data:
        h ^= byte
        h = (h * 0x01000193) & 0xFFFFFFFF
    return h


def fnv1a_seeded(data: Union[bytes, str], seed: int) -> int:
    if isinstance(data, str):
        data = data.encode('utf-8')

    h = seed & 0xFFFFFFFF
    for byte in data:
        h ^= byte
        h = (h * 0x01000193) & 0xFFFFFFFF
    return h


# ==================== LUA HELPERS ====================

def bytes_to_lua_hex(data: bytes) -> str:
    return data.hex()


def lua_string_from_hex(hex_str: str) -> str:
    return f'string.char(unpack({{ {", ".join("0x" + hex_str[i:i+2] for i in range(0, len(hex_str), 2))} }}))'


# ==================== KEY GENERATORS ====================

def gen_random_key(length: int, rng: Optional[random.Random] = None) -> bytes:
    if rng is None:
        return os.urandom(length)
    return bytes(rng.randint(0, 255) for _ in range(length))


def gen_seeded_key(seed: int, length: int) -> bytes:
    rng = random.Random(seed)
    return bytes(rng.randint(0, 255) for _ in range(length))


def derive_key(master_key: bytes, chunk_index: int) -> bytes:
    combined = master_key + struct.pack('>I', chunk_index)
    h1 = fnv1a_seeded(combined, 0x12345678)
    h2 = fnv1a_seeded(combined, 0x87654321)
    return struct.pack('>II', h1, h2)


# ==================== TESTING ====================

def _self_test():
    print("=" * 60)
    print("NZL Crypto Self-Test v4 (raw-byte string fix)")
    print("=" * 60)

    # RC4
    print("\n[1] RC4:")
    key = b"secret_key_123"
    plain = b"Hello, World! This is a test message."
    encrypted = rc4_encrypt(plain, key)
    decrypted = rc4_encrypt(encrypted, key)
    assert plain == decrypted, "RC4 self-test failed!"
    print("  ✓ RC4 OK")

    # XOR multi
    print("\n[2] XOR (multi-byte):")
    key = b"abc"
    encrypted = xor_multi(plain, key)
    decrypted = xor_multi(encrypted, key)
    assert plain == decrypted, "XOR multi self-test failed!"
    print("  ✓ XOR multi OK")

    # XOR rotating
    print("\n[3] XOR (rotating):")
    encrypted = xor_rotating(plain, key_start=0x42, rotation=7)
    decrypted = xor_rotating(encrypted, key_start=0x42, rotation=7)
    assert plain == decrypted, "XOR rotating self-test failed!"
    print("  ✓ XOR rotating OK")

    # Base85
    print("\n[4] Base85:")
    for test_data in [b"", b"a", b"ab", b"abc", b"abcd", b"abcde", b"Hello!", plain]:
        encoded = base85_encode(test_data)
        decoded = base85_decode(encoded)
        assert test_data == decoded, f"Base85 failed for {test_data!r}: got {decoded!r}"
    print("  ✓ Base85 OK")

    # Chunks
    print("\n[5] Chunk splitting:")
    chunks = split_and_encrypt(plain, chunk_size=8, algorithm='rc4')
    reconstructed = merge_chunks(chunks)
    assert plain == reconstructed, "Chunk reconstruction failed!"
    print("  ✓ Chunk splitting OK")

    # CRC32
    print("\n[6] CRC32:")
    assert crc32(b"123456789") == 0xCBF43926
    print("  ✓ CRC32 OK")

    # FNV-1a
    print("\n[7] FNV-1a:")
    assert fnv1a_hash(b"") == 0x811C9DC5
    print("  ✓ FNV-1a OK")

    # Raw byte packing
    print("\n[8] Raw byte-string packing:")
    all_bytes = bytes(range(256))
    packed = bytes_to_py_string(all_bytes)
    assert isinstance(packed, RawByteString), "bytes_to_py_string must return RawByteString"
    assert len(packed) == 256, "Length mismatch in RawByteString packing"
    assert py_string_to_bytes(packed) == all_bytes, "Round-trip bytes <-> RawByteString failed"
    print("  ✓ RawByteString preserves all 256 byte values")

    # End-to-end through ast_unparser.escape_lua_string
    print("\n[9] End-to-end Lua escaping:")
    from obfuscator.ast_unparser import escape_lua_string

    def simulate_lua_string_parse(lua_inner: str) -> bytes:
        result = bytearray()
        i = 0
        while i < len(lua_inner):
            c = lua_inner[i]
            if c != '\\':
                result.append(ord(c))
                i += 1
                continue

            i += 1
            if i >= len(lua_inner):
                raise ValueError("trailing backslash")

            nc = lua_inner[i]

            if nc == '\\':
                result.append(92)
                i += 1
            elif nc == '"':
                result.append(34)
                i += 1
            elif nc == "'":
                result.append(39)
                i += 1
            elif nc == 'n':
                result.append(10)
                i += 1
            elif nc == 'r':
                result.append(13)
                i += 1
            elif nc == 't':
                result.append(9)
                i += 1
            elif nc == 'a':
                result.append(7)
                i += 1
            elif nc == 'b':
                result.append(8)
                i += 1
            elif nc == 'f':
                result.append(12)
                i += 1
            elif nc == 'v':
                result.append(11)
                i += 1
            elif nc.isdigit():
                digits = ''
                while i < len(lua_inner) and lua_inner[i].isdigit() and len(digits) < 3:
                    digits += lua_inner[i]
                    i += 1
                value = int(digits)
                if value > 255:
                    raise ValueError(f"decimal escape too large: {digits}")
                result.append(value)
            else:
                raise ValueError(f"unknown escape: \\{nc}")

        return bytes(result)

    critical = bytes([221, 203, 216, 227])
    critical_lit = escape_lua_string(bytes_to_py_string(critical))
    assert critical_lit[0] in ('"', "'") and critical_lit[-1] == critical_lit[0]
    critical_inner = critical_lit[1:-1]
    assert '\\\\221' not in critical_inner, f"Double slash bug still present: {critical_inner!r}"
    assert simulate_lua_string_parse(critical_inner) == critical
    print("  ✓ No double-slash on critical payload")

    glue_case = bytes([224, ord('0'), ord('1'), ord('k')])
    glue_lit = escape_lua_string(bytes_to_py_string(glue_case))
    glue_inner = glue_lit[1:-1]
    assert '\\2240' not in glue_inner, f"Digit-glue bug still present: {glue_inner!r}"
    assert simulate_lua_string_parse(glue_inner) == glue_case
    print("  ✓ No digit-glue after decimal escapes")

    rng_test = random.Random(42)
    for trial in range(50):
        length = rng_test.randint(1, 100)
        original = bytes(rng_test.randint(0, 255) for _ in range(length))
        packed = bytes_to_py_string(original)
        lua_lit = escape_lua_string(packed)
        assert lua_lit[0] in ('"', "'") and lua_lit[-1] == lua_lit[0]
        decoded = simulate_lua_string_parse(lua_lit[1:-1])
        assert decoded == original, (
            f"Trial {trial}: mismatch!\n"
            f"  Original: {original!r}\n"
            f"  Literal:  {lua_lit!r}\n"
            f"  Decoded:  {decoded!r}"
        )
    print("  ✓ 50 random round-trips through unparser escape")

    print("\n" + "=" * 60)
    print("✅ ALL TESTS PASSED (v4)")
    print("=" * 60)


if __name__ == "__main__":
    _self_test()