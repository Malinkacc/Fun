"""
NZL STUDIO - Sprint 7 (slice 1): универсальный динамический дешифратор
======================================================================
Обфускаторы без статически читаемых строк (MoonSec V3, MoonVeil, WeAreDevs
и подобные) расшифровывают payload ВО ВРЕМЯ исполнения и отдают его в
loadstring/load (прямо или через динамический индекс table[m(...)]).
Статические декодеры их не берут — берём динамикой:

1. образец исполняется в LuaSandbox;
2. неизвестные Roblox-глобалы (game, workspace, Instance, task, ...)
   предзаполнены AutoMock-таблицами: любое поле/вызов возвращает новый
   мок (метатабличные __index/__call) — расшифровка не падает на GUI-коде;
3. loadstring/load/loadfile/dofile перехватываются ПО ИДЕНТИЧНОСТИ функции
   (не по имени!) — любой алиас и table[m(...)] ловятся;
4. захваченный payload рекурсивно прогоняется снова (глубина настраивается)
   — снимаются все слои обфускации;
5. результат: список слоёв (depth, via, текст) — дальше их можно гонять
   через обычный pipeline engine.

CLI:
    py -m obfuscator.deobfuscator.dynamic_decrypt --test
    py -m obfuscator.deobfuscator.dynamic_decrypt file.lua \
        [--max-steps N] [--depth K] [--outdir DIR]
"""
from __future__ import annotations

import json
import os
import time

__all__ = ['CaptureResult', 'capture_layers', 'make_mock', '_self_test']

if __package__ in (None, ''):  # запуск файлом
    import sys as _sys
    _sys.path.insert(0, os.path.abspath(os.path.join(
        os.path.dirname(__file__), '..', '..')))

# глобалы Roblox-окружения, которые мокируются автоматически
ROBLOX_GLOBALS = (
    'game', 'workspace', 'script', 'Instance', 'task', 'spawn', 'wait',
    'delay', 'require', 'players', 'Players', 'Enum', 'Vector2', 'Vector3',
    'CFrame', 'Color3', 'UDim', 'UDim2', 'TweenInfo', 'Ray', 'Region3',
    'Rect', 'NumberRange', 'NumberSequence', 'ColorSequence', 'BrickColor',
    'Faces', 'Axes', 'os', 'tick', 'elapsedTime', 'time', 'typeof',
    'warn', 'print', 'shared', 'settings', 'UserSettings', 'plugin',
    'debug', 'coroutine', 'bit32', 'utf8',
)


class CaptureResult:
    def __init__(self):
        self.layers = []        # [{'depth': int, 'via': str, 'text': str}]
        self.steps = 0
        self.elapsed = 0.0
        self.error = None       # ошибка ВЕРХНЕГО прогона
        self.depth_errors = {}  # depth -> ошибка прогона слоя

    def summary(self) -> str:
        lines = ['layers=%d steps=%d elapsed=%.1fs error=%s' % (
            len(self.layers), self.steps, self.elapsed, self.error)]
        for ly in self.layers[:20]:
            lines.append('  depth=%d via=%s len=%d head=%r' % (
                ly['depth'], ly['via'], len(ly['text']), ly['text'][:60]))
        return '\n'.join(lines)


def make_mock(sb, name='mock', _cache=None):
    """AutoMock-таблица: любое поле и вызов возвращают новый мок."""
    from obfuscator.deobfuscator.core.lua_sandbox import LuaTable
    t = LuaTable()
    mt = LuaTable()
    t.metatable = mt

    def _idx(args):
        tbl, key = args[0], args[1]
        if not isinstance(tbl, LuaTable):
            return None
        v = tbl.rawget(key)
        if v is None:
            v = make_mock(sb, '%s.%s' % (name, key))
            tbl.rawset(key, v)
        return v

    def _call(args):
        return make_mock(sb, name + '()')

    mt.rawset('__index', _idx)
    mt.rawset('__call', _call)
    mt.rawset('__tostring', lambda a: name)
    return t


def _run_one(sb_factory, source, captured, depth, via, max_steps):
    """Один прогон: исполняет source, пишет пойманные payload в captured."""
    from obfuscator.lexer import Lexer
    from obfuscator.parser import Parser
    from obfuscator.deobfuscator.core import lua_sandbox as _ls

    chunk = Parser(Lexer(source).tokenize()).parse()
    sb = sb_factory()
    sb.MAX_STEPS = max_steps

    # перехват load-семейства ПО ИДЕНТИЧНОСТИ
    for lname in ('loadstring', 'load', 'loadfile', 'dofile'):
        orig = sb._globals.get(lname)
        if orig is None or not callable(orig):
            continue

        def wrap(o=orig, n=lname):
            def f(args):
                a0 = args[0] if args else None
                if isinstance(a0, str):
                    captured.append({'depth': depth, 'via': n, 'text': a0})
                return o(args)
            return f

        sb._globals[lname] = wrap()

    env = dict(sb._globals)
    env['_G'] = _ls._EnvTable(env)
    for g in ROBLOX_GLOBALS:
        if g not in env or env[g] is None:
            env[g] = make_mock(sb, g)
    try:
        sb._exec_chunk(chunk, env)
    except _ls.LuaReturn:
        pass
    except Exception as e:  # noqa: BLE001
        return '%s: %s' % (type(e).__name__, str(e)[:140]), sb
    return None, sb


def capture_layers(source: str, max_steps: int = 30_000_000,
                   max_depth: int = 3, progress=False) -> CaptureResult:
    """Исполнить образец и снять все слои loadstring-ayload'ов."""
    from obfuscator.deobfuscator.core.lua_sandbox import LuaSandbox
    from obfuscator.lexer import Lexer
    from obfuscator.parser import Parser

    res = CaptureResult()
    t0 = time.time()

    def sb_factory():
        return LuaSandbox()

    captured = []
    err, sb = _run_one(sb_factory, source, captured, 1, 'top', max_steps)
    res.error = err
    res.steps = getattr(sb, '_steps', 0)

    # рекурсия по захваченным payload
    depth = 1
    seen = {source}
    while depth < max_depth:
        next_batch = [c for c in captured if c['depth'] == depth
                      and c['text'] not in seen]
        if not next_batch:
            break
        depth += 1
        for ly in next_batch:
            seen.add(ly['text'])
            try:
                Parser(Lexer(ly['text']).tokenize()).parse()
            except Exception:  # noqa: BLE001
                continue  # не Lua-код — не гоняем
            e2, sb2 = _run_one(sb_factory, ly['text'], captured, depth,
                               'layer%d' % depth, max_steps)
            if e2:
                res.depth_errors[depth] = e2
            res.steps += getattr(sb2, '_steps', 0)
            if progress:
                print('  depth %d via %s: %d chars, err=%s' % (
                    depth, ly['via'], len(ly['text']), e2), flush=True)

    res.layers = captured
    res.elapsed = time.time() - t0
    return res


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

    # T1: payload через string.char + loadstring
    s1 = ('local s = string.char(114,101,116,117,114,110,32,52,50)'
          ' return loadstring(s)()')
    r1 = capture_layers(s1, max_steps=2_000_000, max_depth=1)
    check('T1 loadstring captured by identity',
          len(r1.layers) == 1 and r1.layers[0]['text'] == 'return 42',
          'layers=%r err=%r' % ([l['text'] for l in r1.layers], r1.error))

    # T2: mock-окружение Roblox + вызов-цепочка + capture
    s2 = ('local x = game:GetService("X"):WaitForChild("Y") '
          'local f = loadstring("return 1") return f()')
    r2 = capture_layers(s2, max_steps=2_000_000, max_depth=1)
    check('T2 Roblox mock env survives chains',
          r2.error is None and len(r2.layers) == 1
          and r2.layers[0]['text'] == 'return 1',
          'err=%r layers=%d' % (r2.error, len(r2.layers)))

    # T3: metatable __call на таблице исполняется
    s3 = ('local t = setmetatable({}, {__call = function(s, a) '
          'return a * 2 end}) return t(21)')
    r3 = capture_layers(s3, max_steps=2_000_000, max_depth=1)
    check('T3 table __call metamethod works', r3.error is None,
          'err=%r' % r3.error)

    # T4: два слоя (payload внутри payload)
    inner = 'return loadstring("return 7")()'
    enc = ','.join(str(b) for b in inner.encode())
    s4 = 'return loadstring(string.char(%s))()' % enc
    r4 = capture_layers(s4, max_steps=4_000_000, max_depth=3)
    texts = [l['text'] for l in r4.layers]
    check('T4 recursive depth-2 capture',
          len(r4.layers) == 2 and 'return 7' in texts,
          'texts=%r err=%r' % (texts, r4.error))

    # T5: без loadstring — пусто, без ошибки
    s5 = 'local a = 1 + 1 return a'
    r5 = capture_layers(s5, max_steps=2_000_000, max_depth=1)
    check('T5 no-capture source clean',
          r5.layers == [] and r5.error is None, 'err=%r' % r5.error)

    print('\nResult: %d/%d' % (passed, passed + failed))
    print('[OK] ALL PASSED' if failed == 0 else '[XX] FAILURES: %d' % failed)
    return 0 if failed == 0 else 1


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(
        prog='py -m obfuscator.deobfuscator.dynamic_decrypt')
    ap.add_argument('file', nargs='?')
    ap.add_argument('--max-steps', type=int, default=30_000_000)
    ap.add_argument('--depth', type=int, default=3)
    ap.add_argument('--outdir', help='сохранить слои в каталог')
    ap.add_argument('--test', action='store_true')
    a = ap.parse_args(argv)

    if a.test or not a.file:
        return _self_test()

    with open(a.file, encoding='utf-8', errors='replace') as f:
        src = f.read()
    print('dynamic decrypt: %s (max_steps=%d depth=%d)' % (
        a.file, a.max_steps, a.depth))
    r = capture_layers(src, max_steps=a.max_steps, max_depth=a.depth,
                       progress=True)
    print(r.summary())
    if a.outdir:
        os.makedirs(a.outdir, exist_ok=True)
        for i, ly in enumerate(r.layers):
            p = os.path.join(a.outdir, 'layer_d%d_%d.lua' % (ly['depth'], i))
            with open(p, 'w', encoding='utf-8') as f:
                f.write(ly['text'])
        with open(os.path.join(a.outdir, 'summary.json'), 'w',
                  encoding='utf-8') as f:
            json.dump({'layers': [{k: v for k, v in ly.items()
                                   if k != 'text'} for ly in r.layers],
                       'steps': r.steps, 'error': r.error,
                       'depth_errors': r.depth_errors}, f, indent=1)
        print('saved %d layers -> %s' % (len(r.layers), a.outdir))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
