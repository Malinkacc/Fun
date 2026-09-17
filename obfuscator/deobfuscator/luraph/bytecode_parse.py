"""
NZL STUDIO - Sprint 6 (slice 2): разбор байткода VM Luraph v14.x
================================================================
Вход: байткод из bytecode_extract (ASCII85-блоб без 'LPH~').

Формат (реверс по реальному образцу v14.6, честно помечаем границы
изученного):
    AF EF           магический заголовок
    02 00           версия формата (u16 LE)
    далее СЕКЦИИ констант в TLV-грамматике:
        8a <len:u8> <bytes>   строка
        4c <val:i64 LE>       целое
        61 <val:f64 LE>       double
        81 <val:u8>           bool/nil-маркер
        17 <id:u8>            разделитель секций (идёт перед очередной
                              группой констант; id = 00, 01, ...)
    после секций констант (~20% файла) идёт область ИНСТРУКЦИЙ
    (~80%) — её формат в этом срезе НЕ разбирается, а честно картируется
    как RAW-остатки секций (slice 3: карта опкодов + лифтер).

Что уже даёт: полная таблица констант VM (имена API: GetService, UDim2,
NextNumber, bit32, coroutine... + числа) — справочник для лифтера и
быстрый «отпечаток» образца (какие API использует защищаемый скрипт).

CLI:
    py -m obfuscator.deobfuscator.luraph.bytecode_parse <file.bin|.lua> \
        [--json out.json] [--strings] [--test]
"""
from __future__ import annotations

import struct

__all__ = ['Const', 'Section', 'BytecodeParseResult', 'parse_bytecode',
           'MAGIC', '_self_test']

MAGIC = b'\xaf\xef'

TAG_STR = 0x8A
TAG_INT = 0x4C
TAG_DBL = 0x61
TAG_BLN = 0x81
TAG_SECTION = 0x17


class Const:
    __slots__ = ('kind', 'value', 'offset')

    def __init__(self, kind, value, offset):
        self.kind = kind      # 'str' | 'int' | 'dbl' | 'bln'
        self.value = value
        self.offset = offset

    def __repr__(self):
        return 'Const(%s, %r, @%#x)' % (self.kind, self.value, self.offset)


class Section:
    __slots__ = ('index', 'start', 'consts_end', 'end', 'consts')

    def __init__(self, index, start):
        self.index = index        # id из маркера 17 <id> (у первой — None)
        self.start = start        # начало TLV-области
        self.consts_end = start   # конец распознанных констант
        self.end = start          # конец секции (начало следующей)
        self.consts = []          # list[Const]

    @property
    def raw_size(self):
        return self.end - self.consts_end

    def __repr__(self):
        return ('Section(id=%r, %#x-%#x, consts=%d, raw=%d)'
                % (self.index, self.start, self.end, len(self.consts),
                   self.raw_size))


class BytecodeParseResult:
    def __init__(self, ok=False, error=None):
        self.ok = ok
        self.error = error
        self.version = None
        self.sections = []        # list[Section]

    @property
    def constants(self):
        out = []
        for s in self.sections:
            out.extend(s.consts)
        return out

    @property
    def strings(self):
        return [c.value for c in self.constants if c.kind == 'str']

    def stats(self):
        from collections import Counter
        cnt = Counter(c.kind for c in self.constants)
        return dict(cnt)

    def __repr__(self):
        return ('BytecodeParseResult(ok=%s, ver=%r, sections=%d, '
                'constants=%d, stats=%r, error=%r)'
                % (self.ok, self.version, len(self.sections),
                   len(self.constants), self.stats(), self.error))


def _try_const(data, off):
    """Распознать одну TLV-константу. Возвращает (Const, new_off) или None."""
    if off >= len(data):
        return None
    tag = data[off]
    if tag == TAG_STR:
        if off + 2 > len(data):
            return None
        ln = data[off + 1]
        if off + 2 + ln > len(data):
            return None
        raw = data[off + 2:off + 2 + ln]
        try:
            val = raw.decode('utf-8')
        except UnicodeDecodeError:
            return None
        # строки VM — печатаемые; байтовый мусор отбрасываем
        if any(b < 9 or (13 < b < 32) for b in raw):
            return None
        return Const('str', val, off), off + 2 + ln
    if tag in (TAG_INT, TAG_DBL):
        if off + 9 > len(data):
            return None
        raw = data[off + 1:off + 9]
        if tag == TAG_INT:
            val = struct.unpack('<q', raw)[0]
            # правдоподобие: маленькие целые или 32-битные без знака
            if not (-2**40 <= val <= 2**40) and not (0 <= val <= 0xFFFFFFFF):
                return None
            return Const('int', val, off), off + 9
        val = struct.unpack('<d', raw)[0]
        # правдоподобие: не nan/inf, порядок вменяемый
        if val != val or val in (float('inf'), float('-inf')):
            return None
        if val != 0.0 and not (1e-12 < abs(val) < 1e15):
            return None
        return Const('dbl', val, off), off + 9
    if tag == TAG_BLN:
        if off + 2 > len(data):
            return None
        return Const('bln', data[off + 1], off), off + 2
    return None


def _looks_like_tlv_run(data, off, min_run=2):
    """С позиции off начинается серия из >= min_run валидных констант?"""
    n = 0
    cur = off
    while n < min_run:
        r = _try_const(data, cur)
        if r is None:
            return False
        _, cur = r
        n += 1
    return True


def _at_section(data, off):
    """С позиции off начинается разделитель секций 17 <id:u8> и сразу за
    ним — валидная TLV-константа, id правдоподобен (0..15)."""
    return (off + 2 < len(data) and data[off] == TAG_SECTION
            and data[off + 1] <= 15
            and _try_const(data, off + 2) is not None)


def parse_bytecode(data: bytes) -> BytecodeParseResult:
    res = BytecodeParseResult()
    if len(data) < 8:
        res.error = 'too short (%d bytes)' % len(data)
        return res
    if data[:2] != MAGIC:
        res.error = 'bad magic %s (want af ef)' % data[:2].hex()
        return res
    res.version = struct.unpack('<H', data[2:4])[0]

    off = 4
    section = Section(None, off)
    res.sections.append(section)

    while off < len(data):
        # разделитель секций: 17 <id>, за ним должна идти TLV-константа
        if _at_section(data, off):
            section.end = off
            section = Section(data[off + 1], off + 2)
            res.sections.append(section)
            off += 2
            continue
        r = _try_const(data, off)
        if r is not None:
            c, off2 = r
            section.consts.append(c)
            off = off2
            section.consts_end = off
            continue
        # нераспознанный байт: RAW-область (инструкции). Сканируем вперёд
        # до ближайшего достоверного возобновления TLV.
        off += 1
        while off < len(data):
            if _at_section(data, off):
                break
            if _looks_like_tlv_run(data, off, 4):
                break
            off += 1
    section.end = len(data)
    res.ok = True
    return res


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

    # T1: синтетический байткод полной грамматики
    blob = bytearray()
    blob += MAGIC + struct.pack('<H', 2)
    blob += bytes([TAG_STR, 3]) + b'abc'
    blob += bytes([TAG_INT]) + struct.pack('<q', 7)
    blob += bytes([TAG_DBL]) + struct.pack('<d', 1.5)
    blob += bytes([TAG_BLN, 1])
    blob += bytes([TAG_SECTION, 0])
    blob += bytes([TAG_STR, 1]) + b'x'
    blob += bytes([TAG_SECTION, 1])
    blob += bytes([TAG_STR, 2]) + b'yz'
    blob += bytes([0x04, 0xAC, 0x04, 0x04, 0x40])  # RAW-хвост (инструкции)
    r1 = parse_bytecode(bytes(blob))
    check('T1 synthetic ok', r1.ok and r1.version == 2)
    check('T1 strings', r1.strings == ['abc', 'x', 'yz'], repr(r1.strings))
    check('T1 sections=3 + raw tail',
          len(r1.sections) == 3 and r1.sections[-1].raw_size == 5,
          repr(r1.sections))

    # T2: плохая магия — честная ошибка
    r2 = parse_bytecode(b'\x00\x00\x02\x00' + b'\x00' * 20)
    check('T2 bad magic', (not r2.ok) and 'magic' in (r2.error or ''))

    # T3: реальный образец
    here = os.path.dirname(os.path.abspath(__file__))
    sample = os.path.join(here, '..', 'samples', 'luraph',
                          'v14.6_sample1.lua')
    if not os.path.exists(sample):
        print('[!!] T3 SKIP - sample not found')
    else:
        from obfuscator.deobfuscator.luraph.bytecode_extract import (
            extract_bytecode)
        with open(sample, encoding='utf-8', errors='replace') as f:
            src = f.read()
        bc = extract_bytecode(src).bytecode
        r3 = parse_bytecode(bc)
        check('T3 parse ok', r3.ok, repr(r3))
        strs = set(r3.strings)
        check('T3 version=2', r3.version == 2)
        check('T3 sections >= 3', len(r3.sections) >= 3,
              'n=%d' % len(r3.sections))
        check('T3 constants >= 400', len(r3.constants) >= 400,
              'n=%d %r' % (len(r3.constants), r3.stats()))
        check('T3 known API names present',
              {'GetService', 'UDim2', 'NextNumber', 'string', 'bit32'}
              <= strs,
              'total strings=%d' % len(strs))
        raw_total = sum(s.raw_size for s in r3.sections)
        check('T3 raw (instructions) area mapped',
              raw_total > len(bc) * 0.25,
              'raw=%d of %d (%.0f%%)' % (raw_total, len(bc),
                                         100 * raw_total / len(bc)))
    print('\nResult: %d/%d' % (passed, passed + failed))
    print('[OK] ALL PASSED' if failed == 0 else '[XX] FAILURES: %d' % failed)
    return 0 if failed == 0 else 1


def main(argv=None) -> int:
    import argparse
    import json
    import os
    ap = argparse.ArgumentParser(
        prog='py -m obfuscator.deobfuscator.luraph.bytecode_parse')
    ap.add_argument('file', nargs='?',
                    help='.bin (байткод) или .lua (извлечём сами)')
    ap.add_argument('--json', help='сохранить константы в JSON')
    ap.add_argument('--strings', action='store_true',
                    help='напечатать все строковые константы')
    ap.add_argument('--test', action='store_true')
    a = ap.parse_args(argv)

    if a.test or not a.file:
        return _self_test()

    if a.file.lower().endswith('.lua'):
        from obfuscator.deobfuscator.luraph.bytecode_extract import (
            extract_bytecode)
        with open(a.file, encoding='utf-8', errors='replace') as f:
            src = f.read()
        r0 = extract_bytecode(src)
        if not r0.ok:
            print('[XX] bytecode extraction failed: %s' % r0.error)
            return 1
        data = r0.bytecode
        print('extracted bytecode: %d bytes (handler=%r)'
              % (len(data), r0.blob_handler))
    else:
        with open(a.file, 'rb') as f:
            data = f.read()

    r = parse_bytecode(data)
    if not r.ok:
        print('[XX] parse failed: %s' % r.error)
        return 1
    print('[OK] version=%r sections=%d constants=%d stats=%r'
          % (r.version, len(r.sections), len(r.constants), r.stats()))
    for s in r.sections:
        print('  %r' % s)
    if a.strings:
        print('strings (%d):' % len(r.strings))
        for sv in r.strings:
            print('  %r' % sv)
    if a.json:
        out = {
            'version': r.version,
            'sections': [
                {'id': s.index, 'start': s.start, 'consts_end': s.consts_end,
                 'end': s.end, 'raw_size': s.raw_size}
                for s in r.sections],
            'constants': [
                {'kind': c.kind, 'value': c.value, 'offset': c.offset}
                for c in r.constants],
        }
        jdir = os.path.dirname(os.path.abspath(a.json))
        if jdir and not os.path.isdir(jdir):
            os.makedirs(jdir, exist_ok=True)
        with open(a.json, 'w', encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
        print('saved -> %s' % a.json)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
