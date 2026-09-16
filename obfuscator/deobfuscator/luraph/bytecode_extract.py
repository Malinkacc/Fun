"""
NZL STUDIO - Sprint 6 (slice 1): извлечение байткода VM Luraph v14.x
====================================================================
Реальный образец v14.6 НЕ вызывает load() (проверено динамически:
1.5 млрд шагов песочницы, captured=0) — он исполняет байткод напрямую.
Зато байткод лежит в исходнике: обработчик-«хранитель» содержит giant
строковый литерал (~69 КБ) с заголовком ``LPH~``, закодированный
в ASCII85 (base-85, offset 33='!', 'z' = группа нулей).

Схема, прочитанная из AST образца (обработчик RA):
    U = gsub(blob, "z", "!!!!!")          -- раскрытие z-групп
    table __index: для каждой 5-символьной группы n:
        p,w,t,l,g = string.byte(n, 1, 5)
        h = (g-33) + (l-33)*85 + (t-33)*85^2 + (w-33)*85^3 + (p-33)*85^4
    -- т.е. классический ASCII85 -> big-endian uint32

Мы делаем то же самое нативно в Python: ~0.5 с вместо ~1 часа
интерпретации VM песочницей.

Результат: байткод (uint32-выровненный) + список печатаемых строк
(имена API/констант VM — материал для Sprint 6 slice 2: карта опкодов
и лифтер байткода в Lua AST).

CLI:
    py -m obfuscator.deobfuscator.luraph.bytecode_extract <file.lua> \
        [--out bytecode.bin] [--strings] [--test]
"""
from __future__ import annotations

import base64
import binascii
import re
import sys

__all__ = ['BytecodeExtractResult', 'extract_bytecode', 'find_blob',
           'decode_blob', 'extract_strings', '_self_test']

MAGIC = 'LPH~'


class BytecodeExtractResult:
    def __init__(self, blob=None, blob_handler=None, bytecode=None,
                 error=None):
        self.blob = blob              # str | None — giant-литерал из AST
        self.blob_handler = blob_handler  # имя обработчика, где лежит блоб
        self.bytecode = bytecode      # bytes | None — расшифрованный байткод
        self.error = error            # str | None

    @property
    def ok(self) -> bool:
        return self.bytecode is not None

    def __repr__(self):
        return ('BytecodeExtractResult(blob=%s, bytecode=%s, handler=%r, '
                'error=%r)' % (
                    len(self.blob) if self.blob else None,
                    len(self.bytecode) if self.bytecode else None,
                    self.blob_handler, self.error))


def _walk(n):
    """Обход AST без рекурсивного спуска в не-Node объекты."""
    from obfuscator.ast_nodes import Node
    stack = [n]
    while stack:
        cur = stack.pop()
        if not isinstance(cur, Node):
            continue
        yield cur
        for v in vars(cur).values():
            if isinstance(v, Node):
                stack.append(v)
            elif isinstance(v, list):
                for x in v:
                    if isinstance(x, Node):
                        stack.append(x)


def find_blob(source: str):
    """(handler_name, blob_str) — обработчик с наибольшим StringLit.

    Возвращает (None, None), если образец не Luraph или блоба нет.
    """
    from obfuscator.deobfuscator.luraph.parser import parse_source
    from obfuscator.ast_nodes import StringLit

    try:
        rep = parse_source(source)
    except Exception:  # noqa: BLE001
        return None, None
    if not rep.detected:
        return None, None

    best_name, best_val = None, ''
    for name, fn in rep.handlers.items():
        for node in _walk(fn):
            if isinstance(node, StringLit):
                v = getattr(node, 'value', '') or ''
                if len(v) > len(best_val):
                    best_val, best_name = v, name
    if not best_val:
        return None, None
    return best_name, best_val


def decode_blob(blob: str):
    """ASCII85-декодирование блоба Luraph: 'LPH~' скипается, 'z' -> '!!!!!'.

    Возвращает bytes или бросает ValueError с честной причиной.
    """
    s = blob
    if s.startswith(MAGIC):
        s = s[len(MAGIC):]
    elif MAGIC in s[:16]:
        s = s[s.index(MAGIC) + len(MAGIC):]
    s = s.replace('z', '!!!!!')
    try:
        data = base64.a85decode(s.encode('latin-1'), adobe=False,
                                ignorechars=b' \t\n\r')
    except (ValueError, binascii.Error) as e:
        raise ValueError('ascii85 decode failed: %s' % e) from e
    if len(data) % 4 != 0:
        raise ValueError('bytecode not uint32-aligned: %d bytes' % len(data))
    return data


_STRING_RE = re.compile(rb'[ -~]{3,}')


def extract_strings(bytecode: bytes, limit: int = 400):
    """Печатаемые ASCII-последовательности >= 3 символов из байткода
    (имена API, строковые константы VM)."""
    out = []
    for m in _STRING_RE.finditer(bytecode):
        out.append(m.group(0).decode('ascii'))
        if len(out) >= limit:
            break
    return out


def extract_bytecode(source: str) -> BytecodeExtractResult:
    """Полный цикл: detection -> поиск блоба -> ASCII85 -> байткод."""
    name, blob = find_blob(source)
    if blob is None:
        return BytecodeExtractResult(error='no blob found (not Luraph v14.x '
                                           'or no giant string literal)')
    try:
        data = decode_blob(blob)
    except ValueError as e:
        return BytecodeExtractResult(blob=blob, blob_handler=name,
                                     error=str(e))
    return BytecodeExtractResult(blob=blob, blob_handler=name,
                                 bytecode=data)


# ---------------------------------------------------------------------------
# self-test
# ---------------------------------------------------------------------------

def _self_test() -> int:
    import os
    passed = failed = 0

    def check(name, cond, extra=''):
        nonlocal passed, failed
        if cond:
            passed += 1
            print('[OK] %s %s' % (name, extra))
        else:
            failed += 1
            print('[XX] %s %s' % (name, extra))

    # T1: синтетика — корректный ASCII85 c z-группой и заголовком LPH~
    raw = bytes(range(64)) + b'\x00\x00\x00\x00'
    enc = base64.a85encode(raw, adobe=False).decode('ascii')
    enc_z = enc.replace('!!!!!', 'z')
    blob1 = MAGIC + enc_z
    dec1 = decode_blob(blob1)
    check('T1 synthetic a85 round-trip', dec1 == raw,
          '%d bytes' % len(dec1))

    # T2: битый блоб — честная ошибка, не исключение наружу
    r2 = extract_bytecode('return 1 + 1\n')
    check('T2 non-luraph -> no blob', (not r2.ok) and 'no blob' in (r2.error or ''))

    # T3: реальный образец v14.6
    here = os.path.dirname(os.path.abspath(__file__))
    sample = os.path.join(here, '..', 'samples', 'luraph',
                          'v14.6_sample1.lua')
    if not os.path.exists(sample):
        print('[!!] T3 SKIP - sample not found: %s' % sample)
    else:
        with open(sample, encoding='utf-8', errors='replace') as f:
            src = f.read()
        r3 = extract_bytecode(src)
        check('T3 real sample decode ok', r3.ok, repr(r3))
        if r3.ok:
            bc = r3.bytecode
            check('T3 handler found', r3.blob_handler is not None,
                  'handler=%r blob=%d' % (r3.blob_handler, len(r3.blob or '')))
            check('T3 size sane', 10_000 < len(bc) < 500_000,
                  '%d bytes (mod4=%d)' % (len(bc), len(bc) % 4))
            strs = extract_strings(bc)
            joined = '|'.join(strs[:120])
            check('T3 strings look like VM API', len(strs) >= 20,
                  'n=%d sample=%r' % (len(strs), joined[:70]))
    print('\nResult: %d/%d' % (passed, passed + failed))
    print('[OK] ALL PASSED' if failed == 0 else '[XX] FAILURES: %d' % failed)
    return 0 if failed == 0 else 1


def main(argv=None) -> int:
    import argparse
    import os
    ap = argparse.ArgumentParser(
        prog='py -m obfuscator.deobfuscator.luraph.bytecode_extract')
    ap.add_argument('file', nargs='?', help='обфусцированный .lua')
    ap.add_argument('--out', help='куда сохранить байткод (.bin)')
    ap.add_argument('--strings', action='store_true',
                    help='напечатать строки из байткода')
    ap.add_argument('--test', action='store_true', help='self-test')
    a = ap.parse_args(argv)

    if a.test or not a.file:
        return _self_test()

    with open(a.file, encoding='utf-8', errors='replace') as f:
        src = f.read()
    r = extract_bytecode(src)
    if not r.ok:
        print('[XX] extraction failed: %s' % r.error)
        return 1
    print('[OK] handler=%r blob=%d chars -> bytecode=%d bytes'
          % (r.blob_handler, len(r.blob or ''), len(r.bytecode)))
    print('head hex: %s' % r.bytecode[:32].hex())
    if a.strings:
        strs = extract_strings(r.bytecode)
        print('strings (%d):' % len(strs))
        for s in strs[:60]:
            print('  %r' % s)
    if a.out:
        out_dir = os.path.dirname(os.path.abspath(a.out))
        if out_dir and not os.path.isdir(out_dir):
            os.makedirs(out_dir, exist_ok=True)
        with open(a.out, 'wb') as f:
            f.write(r.bytecode)
        print('saved -> %s' % a.out)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
