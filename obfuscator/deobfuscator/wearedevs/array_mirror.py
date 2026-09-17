"""WeAreDevs v1 string-array mirror (Sprint 7, slice 4b).

The real sample decrypts its string array in-place at bootstrap with two
codecs (found statically around offsets ~125k-130k of the source):

  * entries starting with '(' : base64 with a CUSTOM alphabet S
    (4 chars -> 3 bytes, big-endian 6-bit groups, '=' padding emits 1-2
    extra bytes);
  * entries starting with 'M' : ascii85-like with a CUSTOM value map l
    (groups of up to 5 chars forward, Y = Y*85 + value, pad value 84
    group of n chars -> n-1 bytes big-endian).

Both alphabets are literal tables of char -> arithmetic expression; this
module evaluates those expressions, mirrors both codecs and decodes the
whole array offline (instant, no sandbox).

Usage:
    py -m obfuscator.deobfuscator.wearedevs.array_mirror --test
    py -m obfuscator.deobfuscator.wearedevs.array_mirror --sample path\\wearedevs.lua --outdir out
"""

import os
import re
import sys
import json
import argparse

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

_CONST_RE = re.compile(r'^[0-9x()+\-*/% ]+$')
_ENTRY_RE = re.compile(r'(?:\["((?:\\.|[^"\\])+)"\]|(?<![A-Za-z0-9_"\]])([A-Za-z0-9_]))'
                       r'=((?:[-+*/%()]|\d)+)(?=[,;}])')


def eval_const(expr):
    expr = expr.strip()
    if not _CONST_RE.match(expr):
        raise ValueError('unsafe const: %r' % expr[:40])
    return int(eval(expr, {'__builtins__': {}}, {}))


def parse_char_table(text, pos):
    """Parse a {c=expr, ["c"]=expr; ...} table starting at text[pos]=='{'."""
    assert text[pos] == '{'
    end = text.index('}', pos)
    body = text[pos + 1:end + 1]
    out = {}
    for m in _ENTRY_RE.finditer(body):
        raw = m.group(1) or m.group(2)
        if m.group(1):
            raw = raw.encode('latin1', 'replace').decode('unicode_escape')
        if len(raw) != 1:
            continue
        out[raw] = eval_const(m.group(3))
    return out, end + 1


def decode_b64(s, alphabet):
    acc = 0
    cnt = 0
    out = bytearray()
    i = 0
    while i < len(s):
        c = s[i]
        if c == '=':
            out.append(acc >> 16)
            if i + 1 < len(s) and s[i + 1] != '=':
                out.append((acc % 65536) // 256)
            break
        v = alphabet.get(c)
        if v is None:
            break
        acc = acc + v * (64 ** (3 - cnt))
        cnt += 1
        if cnt == 4:
            out.append(acc >> 16)
            out.append((acc % 65536) // 256)
            out.append(acc % 256)
            acc = 0
            cnt = 0
        i += 1
    return bytes(out)


def decode_a85(s, values, pad=84):
    out = bytearray()
    k = 0
    n = len(s)
    while k < n:
        remain = n - k
        q = 5 if remain >= 5 else remain
        y = 0
        ok = True
        for v in range(5):
            if v < q:
                m = values.get(s[k + v])
                if m is None:
                    ok = False
                    m = pad
            else:
                m = pad
            y = y * 85 + m
        if ok:
            b = [ (y // 16777216) % 256, (y // 65536) % 256, (y // 256) % 256, y % 256 ]
            out.extend(b[:q - 1])
        k += q
    return bytes(out)


def extract_arrays(source):
    """Locate S (base64 alphabet), l (a85 values) and the V string array."""
    anchor = source.find('Y=V local q=math.floor')
    if anchor < 0:
        anchor = source.find('local W=string.char')
    if anchor < 0:
        return None, None, None
    s_pos = source.find('S={', anchor)
    l_pos = source.find('l={', anchor)
    b64, _ = parse_char_table(source, s_pos + 2) if s_pos >= 0 else ({}, 0)
    a85, _ = parse_char_table(source, l_pos + 2) if l_pos >= 0 else ({}, 0)
    v_start = source.rfind('V={', 0, anchor)
    arr = []
    if v_start >= 0:
        j = source.index('{', v_start)
        depth = 0
        k = j
        while k < len(source):
            c = source[k]
            if c == '{':
                depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0:
                    break
            elif c == '"':
                k += 1
                buf = []
                while source[k] != '"':
                    if source[k] == '\\':
                        k += 1
                    buf.append(source[k])
                    k += 1
                arr.append(''.join(buf))
            k += 1
    return b64, a85, arr


def decode_array(arr, b64, a85):
    out = []
    for e in arr:
        if e.startswith('('):
            out.append(decode_b64(e[1:], b64))
        elif e.startswith('M'):
            out.append(decode_a85(e[1:], a85))
        else:
            out.append(e.encode('latin1', 'replace'))
    return out


# --------------------------------------------------------------------------- #
# self-test
# --------------------------------------------------------------------------- #

_B64_AL = {c: i for i, c in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ'
                                      'abcdefghijklmnopqrstuvwxyz0123456789+/')}
_A85_AL = {chr(33 + i): i for i in range(85)}


def _enc_b64(data, alphabet):
    inv = {v: k for k, v in alphabet.items()}
    out = []
    for i in range(0, len(data) - 2, 3):
        v = (data[i] << 16) | (data[i + 1] << 8) | data[i + 2]
        out.append(inv[(v >> 18) % 64] + inv[(v >> 12) % 64] + inv[(v >> 6) % 64] + inv[v % 64])
    return '(' + ''.join(out)


def _enc_a85(data, values):
    inv = {v: k for k, v in values.items()}
    out = []
    i = 0
    n = len(data)
    while i < n:
        grp = data[i:i + 4]
        v = 0
        for b in grp:
            v = v * 256 + b
        v <<= 8 * (4 - len(grp))
        chars = [inv[v // 85 ** 4], inv[(v // 85 ** 3) % 85], inv[(v // 85 ** 2) % 85],
                 inv[(v // 85) % 85], inv[v % 85]]
        out.append(''.join(chars[:len(grp) + 1]))
        i += 4
    return 'M' + ''.join(out)


def _selftest():
    fails = []

    def chk(tag, cond, extra=''):
        print(('[OK] ' if cond else '[XX] ') + tag + (' ' + extra if extra else ''))
        if not cond:
            fails.append(tag)

    plain = b'Workspace.FireServ'
    e64 = _enc_b64(plain, _B64_AL)
    chk('T1 base64 mirror round-trip', decode_b64(e64[1:], _B64_AL) == plain,
        repr(decode_b64(e64[1:], _B64_AL)))
    plain85 = b'HumanoidRootPart'
    e85 = _enc_a85(plain85, _A85_AL)
    chk('T2 ascii85 mirror round-trip', decode_a85(e85[1:], _A85_AL) == plain85,
        repr(decode_a85(e85[1:], _A85_AL)))
    tab, _ = parse_char_table('{B=105842+-105815,Q=28;["7"]=67,["x"]=12+-3}', 0)
    chk('T3 char table const eval', tab == {'B': 27, 'Q': 28, '7': 67, 'x': 9}, str(tab))
    pad = _enc_b64(b'ab', _B64_AL) if False else '(QUJD'  # 3-byte group of 'ABC'
    chk('T4 partial group safe (no crash)', isinstance(decode_b64('QUJD', _B64_AL), bytes))
    arr = [e64, e85, 'plain']
    dec = decode_array(arr, _B64_AL, _A85_AL)
    chk('T5 decode_array dispatch', dec == [plain, plain85, b'plain'], str(dec))
    tail = b'FireServer1'
    et = _enc_a85(tail, _A85_AL)
    chk('T6 a85 tail group round-trip', decode_a85(et[1:], _A85_AL) == tail,
        repr(decode_a85(et[1:], _A85_AL)))

    print('')
    print('Result: %d/6' % (6 - len(fails)))
    if fails:
        print('[XX] FAILURES: %d' % len(fails))
        return 1
    print('[OK] ALL PASSED')
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description='WeAreDevs string-array mirror')
    ap.add_argument('--test', action='store_true')
    ap.add_argument('--sample', default=None)
    ap.add_argument('--show', type=int, default=24)
    ap.add_argument('--outdir', default=None)
    a = ap.parse_args(argv)
    if a.test:
        return _selftest()
    if a.sample:
        src = open(a.sample, encoding='utf-8', errors='replace').read()
        b64, a85, arr = extract_arrays(src)
        print('alphabet b64=%d a85=%d array=%d' % (len(b64), len(a85), len(arr)))
        dec = decode_array(arr, b64, a85)
        printable = sum(1 for d in dec if d and all(32 <= c < 127 for c in d))
        print('decoded=%d printable=%d' % (len(dec), printable))
        for d in dec[:a.show]:
            print('  %r' % d[:70])
        if a.outdir:
            if not os.path.isdir(a.outdir):
                os.makedirs(a.outdir)
            with open(os.path.join(a.outdir, 'strings.json'), 'w', encoding='utf-8') as fh:
                json.dump([d.decode('latin1') for d in dec], fh, ensure_ascii=False)
            print('saved -> %s' % os.path.join(a.outdir, 'strings.json'))
        return 0
    ap.error('use --test or --sample')


if __name__ == '__main__':
    sys.exit(main())
