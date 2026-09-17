"""
NZL STUDIO - Sprint 6 (slice 5): лифтер VM Luraph v14.x
=======================================================
Превращает ДАМП VM-фрейма (массивы инструкций, снятые песочницей в момент
первой диспетчеризации каждой VM-функции) в читаемый Lua-псевдокод.

Фрейм Luraph (образец v14.6):
    t[E]  — опкод инструкции E (1-based)
    l,h,V — числовые операнды (регистры / адреса / счётчики)
    g,w,_ — операнды-значения (числа / строки / константы)
    D     — регистровый файл, U — upvalue, n — аргументы, b — глобалы

Два уровня лифта:
1. РУЧНАЯ ТАБЛИЦА (OPSEM) для 43 динамически подтверждённых опкодов —
   точный pretty-print: r{N} вместо D[N], константы инлайнятся, JMP-цели
   становятся метками L{n};
2. ОБЩИЙ FALLBACK для остальных опкодов: текст статического листа
   (vm_opcodes.extract_opcode_leaves) с механической подстановкой операндов
   l[E]/h[E]/V[E]/g[E]/w[E]/_[E] -> значения фрейма. Работает для любого
   листа без ручного разбора.

Восстановленная семантика (slice 4): 32/156=JMP V, 83=JMP h, 4=JMPF,
100/109=branch-if-<=, 31/17=FORPREP/FORLOOP, 16=frame init, 39=varargs,
55=SELF, 142=MOV, 92=LOADK, 10=NOT, 57=SUB, 37=DIV(w), 34=MUL(g), 72=ADD,
40=MOD(g), 104=GETUPVAL, 56=GETGLOBAL(b[g]), 91/45/64/22=GETTABLE,
46/67/133/135=SETTABLE, 101=NEWTABLE, 113/117/102=CALL 0/1/2,
28=CALLV, 136=CALLM (мультивызов, nresults=V-1), 81/121/108=void-звонки,
13/74/88=RETURN (протокол (bool, base, count)), 119=CLOSURE+капчеры.

CLI:
    py -m obfuscator.deobfuscator.luraph.vm_lift --test
    py -m obfuscator.deobfuscator.luraph.vm_lift --demo [--out lifted.txt]
    py -m obfuscator.deobfuscator.luraph.vm_lift --frames frames.json \
        [--static sample.lua] [--max N] [--out lifted.txt]
"""
from __future__ import annotations

import json
import os

__all__ = ['OPSEM', 'lift_frame', 'lift_frames', 'load_static_texts',
           'demo_lift', '_self_test']

if __package__ in (None, ''):  # запуск файлом: py obfuscator\...\vm_lift.py
    import sys as _sys
    _sys.path.insert(0, os.path.abspath(os.path.join(
        os.path.dirname(__file__), '..', '..', '..')))

# метки опкодов (мнемоника для аннотаций)
MNEMONIC = {
    32: 'JMP', 156: 'JMP', 83: 'JMP', 4: 'JMPF', 100: 'BRLE', 109: 'BRLE',
    17: 'FORLOOP', 31: 'FORPREP', 16: 'FRAMEINIT', 39: 'VARARGS', 55: 'SELF',
    10: 'NOT', 57: 'SUB', 37: 'DIV', 34: 'MUL', 72: 'ADD', 40: 'MOD',
    142: 'MOV', 92: 'LOADK', 104: 'GETUPVAL', 56: 'GETGLOBAL',
    91: 'GETTABLE', 45: 'GETTABLE', 64: 'GETTABLE', 22: 'GETTABLE',
    46: 'SETTABLE', 67: 'SETTABLE', 133: 'SETTABLE', 135: 'SETTABLE',
    101: 'NEWTABLE', 113: 'CALL0', 117: 'CALL1', 102: 'CALL2',
    28: 'CALLV', 136: 'CALLM', 121: 'VCALL1', 108: 'VCALL2', 81: 'VCALL0',
    13: 'RET', 74: 'RET2', 88: 'RET0', 119: 'CLOSURE',
}

# цели переходов по опкодам: (опкод -> имя массива-операнда цели)
JUMP_SRC = {32: 'V', 156: 'V', 83: 'h', 4: 'h', 100: 'l', 109: 'l',
            31: 'l', 17: 'l'}


def _iv(x):
    """Значение операнда -> int (фрейм хранит float-ы) или None."""
    if isinstance(x, bool) or x is None:
        return None
    if isinstance(x, (int, float)):
        return int(x)
    return None


def _const(x):
    """Рендер константы операнда в Lua-литерал."""
    if x is None:
        return 'nil'
    if isinstance(x, bool):
        return 'true' if x else 'false'
    if isinstance(x, float):
        return repr(int(x)) if x == int(x) else repr(x)
    if isinstance(x, int):
        return str(x)
    if isinstance(x, str):
        if x == 'TBL':
            return '{...}'
        if x == 'FN':
            return '<fn>'
        out = []
        for ch in x:
            o = ord(ch)
            if ch == '\\':
                out.append('\\\\')
            elif ch == '"':
                out.append('\\"')
            elif ch == '\n':
                out.append('\\n')
            elif ch == '\r':
                out.append('\\r')
            elif ch == '\t':
                out.append('\\t')
            elif o < 32 or o > 126:
                out.append('\\%d' % o)
            else:
                out.append(ch)
        return '"%s"' % ''.join(out)
    return str(x)


def _reg(x):
    v = _iv(x)
    return 'r%d' % v if v is not None else 'r?'


def _arrays(fr):
    """Единый доступ к массивам фрейма (две схемы: arrays{} или плоская)."""
    a = fr.get('arrays')
    if not isinstance(a, dict):
        a = fr
    return a


def _op(a, name, E):
    """Операнд name[E] (E 1-based) или None."""
    arr = a.get(name)
    if not isinstance(arr, list):
        return None
    i = E - 1
    if 0 <= i < len(arr):
        return arr[i]
    return None


class _LiftCtx:
    def __init__(self, fr, static_texts=None):
        self.a = _arrays(fr)
        self.fr = fr
        self.static = static_texts or {}
        t = self.a.get('t') or []
        self.n = len(t)

    def opcode(self, E):
        return _iv(_op(self.a, 't', E))

    def L(self, E):
        return _op(self.a, 'l', E)

    def H(self, E):
        return _op(self.a, 'h', E)

    def V(self, E):
        return _op(self.a, 'V', E)

    def G(self, E):
        return _op(self.a, 'g', E)

    def W(self, E):
        return _op(self.a, 'w', E)

    def S(self, E):  # '_' — константа инструкции
        return _op(self.a, '_', E)

    def U(self, i):
        arr = self.a.get('U') or []
        v = _iv(i)
        if v is not None and 0 <= v - 1 < len(arr):
            return arr[v - 1]
        return None

    def B_(self, i):  # b — таблица глобалов
        arr = self.a.get('b') or []
        v = _iv(i)
        if v is not None and 0 <= v - 1 < len(arr):
            return arr[v - 1]
        return None


def _render_op(ctx, q, E):
    """Точный pretty-print известного опкода или None."""
    L, H, V = ctx.L(E), ctx.H(E), ctx.V(E)
    G, W, S = ctx.G(E), ctx.W(E), ctx.S(E)
    li, hi, vi = _iv(L), _iv(H), _iv(V)

    if q in (32, 156):                       # E = V[E]
        return 'goto L%d' % (vi or 0)
    if q == 83:                              # E = h[E]
        return 'goto L%d' % (hi or 0)
    if q == 4:                               # if not D[l] then E = h
        return 'if not %s then goto L%d end' % (_reg(L), hi or 0)
    if q == 100:                             # if not (g < D[h]) then E = l
        return 'if %s <= %s then goto L%d end' % (_reg(H), _const(G), li or 0)
    if q == 109:                             # if not (D[h] < D[V]) then E=l
        return 'if %s <= %s then goto L%d end' % (_reg(V), _reg(H), li or 0)
    if q == 142:                             # D[V] = D[h]
        return '%s = %s' % (_reg(V), _reg(H))
    if q == 92:                              # D[V] = _[E]
        return '%s = %s' % (_reg(V), _const(S))
    if q == 10:                              # D[l] = not D[V]
        return '%s = not %s' % (_reg(L), _reg(V))
    if q == 57:                              # D[V] = D[l] - D[h]
        return '%s = %s - %s' % (_reg(V), _reg(L), _reg(H))
    if q == 37:                              # D[V] = D[h] / w[E]
        return '%s = %s / %s' % (_reg(V), _reg(H), _const(W))
    if q == 34:                              # D[l] = D[h] * g[E]
        return '%s = %s * %s' % (_reg(L), _reg(H), _const(G))
    if q == 72:                              # D[h] = D[V] + D[l]
        return '%s = %s + %s' % (_reg(H), _reg(V), _reg(L))
    if q == 40:                              # D[l] = D[h] % g[E]
        return '%s = %s %% %s' % (_reg(L), _reg(H), _const(G))
    if q == 101:                             # D[V] = {}
        return '%s = {}' % _reg(V)
    if q == 56:                              # D[l] = b[g[E]]
        gname = ctx.B_(G)
        return '%s = _ENV[%s]' % (_reg(L),
                                  _const(gname) if gname is not None
                                  else ('b[%s]' % _const(G)))
    if q == 104:                             # D[V] = U[h[E]]
        uv = ctx.U(H)
        return '%s = %s' % (_reg(V),
                            _const(uv) if uv is not None and not
                            isinstance(uv, (dict, list)) else 'up[%s]' % _const(H))
    if q == 45:                              # D[V] = U[l][_[E]]
        base = ctx.U(L)
        bs = _const(base) if isinstance(base, str) else 'up[%s]' % _const(L)
        return '%s = %s[%s]' % (_reg(V), bs, _const(S))
    if q == 91:                              # D[h] = U[l][D[V]]
        base = ctx.U(L)
        bs = _const(base) if isinstance(base, str) else 'up[%s]' % _const(L)
        return '%s = %s[%s]' % (_reg(H), bs, _reg(V))
    if q == 64:                              # D[V] = D[h][w[E]]
        return '%s = %s[%s]' % (_reg(V), _reg(H), _const(W))
    if q == 22:                              # D[V] = D[l][D[h]]
        return '%s = %s[%s]' % (_reg(V), _reg(L), _reg(H))
    if q == 46:                              # D[V][D[l]] = D[h]
        return '%s[%s] = %s' % (_reg(V), _reg(L), _reg(H))
    if q == 67:                              # D[V][D[h]] = w[E]
        return '%s[%s] = %s' % (_reg(V), _reg(H), _const(W))
    if q == 133:                             # D[V][w[E]] = _[E]
        return '%s[%s] = %s' % (_reg(V), _const(W), _const(S))
    if q == 135:                             # D[V][_[E]] = D[l]
        return '%s[%s] = %s' % (_reg(V), _const(S), _reg(L))
    if q == 113:                             # B=h; D[B] = D[B]()
        return '%s = %s()' % (_reg(H), _reg(H))
    if q == 117:                             # j=V; D[j] = D[j](D[j+1])
        return '%s = %s(%s)' % (_reg(V), _reg(V),
                                'r%d' % (vi + 1) if vi is not None else 'r?')
    if q == 102:                             # D[j] = D[j](D[j+1], D[j+2])
        if vi is None:
            return '%s = %s(?, ?)' % (_reg(V), _reg(V))
        return '%s = %s(r%d, r%d)' % (_reg(V), _reg(V), vi + 1, vi + 2)
    if q == 28:                              # D[j]=D[j](unpack(D,j+1,B))
        return '%s = %s(...)  -- args r%d..top' % (
            _reg(L), _reg(L), (li or 0) + 1)
    if q == 136:                             # CALLM: A=V[E] nresults=V-1
        nres = 'all' if vi == 0 else (0 if vi == 1 else vi - 1)
        nargs = (hi or 1) - 1
        return '(%s, nres=%s) = %s(args r%d..r%d)' % (
            _reg(L), nres, _reg(L), (li or 0) + 1, (li or 0) + nargs)
    if q == 81:                              # D[l]()
        return '%s()' % _reg(L)
    if q == 121:                             # D[l](D[l+1])
        return '%s(%s)' % (_reg(L),
                           'r%d' % (li + 1) if li is not None else 'r?')
    if q == 108:                             # D[h](D[h+1], D[h+2])
        if hi is None:
            return '%s(?, ?)' % _reg(H)
        return '%s(r%d, r%d)' % (_reg(H), hi + 1, hi + 2)
    if q == 16:                              # for Z=1,h: D[Z] = n[Z]
        return '-- params: r1..r%s = args' % _const(H)
    if q == 39:                              # varargs -> D[h..h+V-1]
        if hi is None:
            return 'r?.. = ...'
        return 'r%d..r%d = ...' % (hi, hi + max(0, (vi or 1) - 1))
    if q == 55:                              # SELF
        return '%s = %s; %s = %s[%s]' % (
            'r%d' % (vi + 1) if vi is not None else 'r?', _reg(L),
            _reg(V), _reg(L), _const(S))
    if q == 31:                              # FORPREP
        if vi is None:
            return 'for ? = ?, ?, ? do goto L%d' % (li or 0)
        return 'for %s = r%d, r%d, r%d do  -- goto L%d' % (
            _reg(V), vi, vi + 1, vi + 2, li or 0)
    if q == 17:                              # FORLOOP
        return 'FORLOOP var %s -> goto L%d' % (
            'r%d' % (hi + 3) if hi is not None else 'r?', li or 0)
    if q == 88:                              # return
        return 'return'
    if q == 74:                              # return D[V], D[V+1]
        if vi is None:
            return 'return ?, ?'
        return 'return %s, r%d' % (_reg(V), vi + 1)
    if q == 13:                              # return D[h] (протокол (false,j,j))
        return 'return %s' % _reg(H)
    if q == 119:                             # CLOSURE
        return '%s = closure(proto g[%s])  -- captures from U/D/pending' % (
            _reg(H), _const(G))
    return None


def _fallback(ctx, q, E):
    """Общий lift неизвестного опкода: текст листа + подстановка операндов."""
    txt = ctx.static.get(q)
    if not txt:
        return '--[[op %s]] (no static text)' % q
    subs = {
        'l[E]': _const(ctx.L(E)), 'h[E]': _const(ctx.H(E)),
        'V[E]': _const(ctx.V(E)), 'g[E]': _const(ctx.G(E)),
        'w[E]': _const(ctx.W(E)), '_[E]': _const(ctx.S(E)),
    }
    out = txt
    for k, v in subs.items():
        out = out.replace(k, v)
    if len(out) > 400:
        out = out[:400] + ' ...'
    return '--[[op %s]] %s' % (q, out)


def lift_frame(fr, static_texts=None, name=None):
    """Один фрейм -> список строк Lua-псевдокода."""
    ctx = _LiftCtx(fr, static_texts)
    a = ctx.a
    lines = []
    dlen = len(a.get('D') or [])
    header = '-- VM function %s: %d instrs, %d regs' % (
        name or '?', ctx.n, dlen)
    sc = fr.get('scalars') or {}
    if sc:
        header += ' (dump @step %s)' % sc.get('step', fr.get('step', '?'))
    lines.append(header)
    lines.append('function %s(...)' % (name or 'vmfn'))

    # метки: цели всех переходов
    targets = set()
    for E in range(1, ctx.n + 1):
        q = ctx.opcode(E)
        srcname = JUMP_SRC.get(q)
        if srcname:
            tv = _iv(_op(a, srcname, E))
            if tv is not None and 1 <= tv <= ctx.n:
                targets.add(tv)

    for E in range(1, ctx.n + 1):
        if E in targets:
            lines.append('L%d:' % E)
        q = ctx.opcode(E)
        mn = MNEMONIC.get(q, 'OP%s' % q)
        body = _render_op(ctx, q, E)
        if body is None:
            body = _fallback(ctx, q, E)
        lines.append('  %s  --[[#%d %s]]' % (body, E, mn))
    lines.append('end')
    return lines


def lift_frames(frames_obj, static_texts=None, max_frames=None,
                name_prefix='vmfn'):
    """Список фреймов -> полный текст."""
    if isinstance(frames_obj, dict) and 'frames' in frames_obj:
        frames = frames_obj['frames']
    elif isinstance(frames_obj, list):
        frames = frames_obj
    else:
        frames = [frames_obj]
    out = []
    for i, fr in enumerate(frames):
        if max_frames is not None and i >= max_frames:
            out.append('-- (%d more frames omitted)' % (len(frames) - i))
            break
        out += lift_frame(fr, static_texts, name='%s%d' % (name_prefix, i + 1))
        out.append('')
    return '\n'.join(out)


def load_static_texts(sample_path):
    """{q: текст листа} из статической карты vm_opcodes (мгновенно)."""
    try:
        from obfuscator.deobfuscator.luraph.vm_opcodes import static_opcode_map
        with open(sample_path, encoding='utf-8', errors='replace') as f:
            src = f.read()
        dc = static_opcode_map(src)
        out = {}
        for lf in dc.leaves:
            lo, hi = lf['iv']
            txt = lf.get('text') or ''
            if hi - lo > 400:
                hi = lo  # «бесконечный» лист — только для lo
            for q in range(lo, min(hi, lo + 400) + 1):
                out.setdefault(q, txt)
        return out
    except Exception:  # noqa: BLE001
        return {}


def _demo_paths():
    here = os.path.dirname(os.path.abspath(__file__))
    sdir = os.path.join(here, '..', 'samples', 'luraph')
    return (os.path.normpath(os.path.join(sdir, 'v14.6_frames.json')),
            os.path.normpath(os.path.join(sdir, 'v14.6_sample1.lua')))


def demo_lift(max_frames=3):
    """Лифт встроенного дампа фреймов реального образца (мгновенно)."""
    frames_path, sample_path = _demo_paths()
    with open(frames_path, encoding='utf-8') as f:
        frames_obj = json.load(f)
    static = load_static_texts(sample_path)
    return lift_frames(frames_obj, static, max_frames=max_frames)


# ---------------------------------------------------------------------------
# self-test
# ---------------------------------------------------------------------------

def _self_test() -> int:
    passed = failed = 0

    def check(name, cond, extra=''):
        nonlocal passed, failed
        if cond:
            passed += 1
            print('[OK] %s %s' % (name, extra))
        else:
            failed += 1
            print('[XX] %s %s' % (name, extra))

    N = 8
    fr = {'step': 1, 'scalars': {'E': 1}, 'arrays': {
        #  1   2    3    4   5    6   7    8
        't': [16, 92, 142, 72, 133, 32, 88, 77],
        'l': [2, 0, 0, 2, 0, 7, 0, 3],
        'h': [2, 0, 2, 3, 0, 0, 0, 0],
        'V': [0, 1, 3, 1, 2, 7, 0, 0],
        'g': [None] * N,
        'w': [None, None, None, None, 'name', None, None, None],
        '_': [None, 5, None, None, 'val', None, None, None],
        'U': [], 'D': [None] * 6, 'n': [],
    }}
    text = '\n'.join(lift_frame(fr, {77: 'D[V[E]] = weird(l[E], h[E])'},
                                name='tfn'))
    check('T1 header + function wrapper',
          'function tfn(...)' in text and '8 instrs' in text, '')
    check('T2 FRAMEINIT + LOADK inlined',
          'params: r1..r2 = args' in text and 'r1 = 5' in text, '')
    check('T3 MOV / ADD registers',
          'r3 = r2' in text and 'r3 = r1 + r2' in text, '')
    check('T4 SETTABLE const operands',
          'r2["name"] = "val"' in text, '')
    check('T5 JMP + label L7 + RET',
          'goto L7' in text and '\nL7:' in text and '\n  return ' in text, '')
    check('T6 unknown opcode fallback with substitution',
          'weird(3, 0)' in text and 'op 77' in text, '')
    check('T7 no float register names', 'r3.0' not in text and 'r1.0' not in text, '')

    # lift_frames: пакет + ограничение
    multi = lift_frames({'frames': [fr, fr]}, {77: 'x'}, max_frames=1)
    check('T8 lift_frames max_frames',
          'vmfn2' not in multi and '1 more frames omitted' in multi
          and 'function vmfn1(...)' in multi, '')

    # демо на встроенном дампе реального образца (если есть)
    frames_path, _sample = _demo_paths()
    if os.path.isfile(frames_path):
        try:
            demo = demo_lift(max_frames=2)
            ok = 'function vmfn1(...)' in demo and len(demo) > 200
            check('T9 demo lift of real frames', ok,
                  'len=%d' % len(demo))
        except Exception as e:  # noqa: BLE001
            check('T9 demo lift of real frames', False, str(e)[:80])
    else:
        print('[!!] T9 skipped: bundled frames dump absent (%s)' % frames_path)
        passed += 1

    print('\nResult: %d/%d' % (passed, passed + failed))
    print('[OK] ALL PASSED' if failed == 0 else '[XX] FAILURES: %d' % failed)
    return 0 if failed == 0 else 1


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(
        prog='py -m obfuscator.deobfuscator.luraph.vm_lift')
    ap.add_argument('--frames', help='JSON с дампом фреймов (harvest)')
    ap.add_argument('--static', help='sample.lua для fallback-текстов опкодов')
    ap.add_argument('--max', type=int, default=None)
    ap.add_argument('--out', help='сохранить lifted-код в файл')
    ap.add_argument('--demo', action='store_true',
                    help='лифт встроенного дампа реального образца')
    ap.add_argument('--test', action='store_true')
    a = ap.parse_args(argv)

    if a.test or not (a.frames or a.demo):
        return _self_test()

    if a.demo:
        text = demo_lift(max_frames=a.max or 3)
    else:
        with open(a.frames, encoding='utf-8') as f:
            frames_obj = json.load(f)
        static = load_static_texts(a.static) if a.static else {}
        text = lift_frames(frames_obj, static, max_frames=a.max)

    if a.out:
        d = os.path.dirname(os.path.abspath(a.out))
        if d and not os.path.isdir(d):
            os.makedirs(d, exist_ok=True)
        with open(a.out, 'w', encoding='utf-8') as f:
            f.write(text)
        print('lifted -> %s (%d chars)' % (a.out, len(text)))
    head = text.splitlines()[:40]
    print('\n'.join(head))
    if len(text.splitlines()) > 40:
        print('... (%d lines total)' % len(text.splitlines()))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
