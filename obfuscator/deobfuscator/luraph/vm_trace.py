"""
NZL STUDIO - Sprint 6 (slice 3): трейсер VM Luraph v14.x
========================================================
Образец v14.6 — интерактивный Roblox-скрипт: он НЕ завершается и НЕ
вызывает load() (проверено: 1.5 млрд шагов, captured=0). Поэтому вместо
«дождаться конца» снимаем ТРЕЙС работы VM:

- каждый вызов функции внутри песочницы метится ИМЕНЕМ ОБРАБОТЧИКА из
  структурного парсера (идентификация по id(body) AST-узла — LuaFunction
  в песочнице хранит тот же Block-узел, что и FunctionExpr обработчика);
- пишется гистограмма «обработчик -> число вызовов» (горячие обработчики
  = часто исполняемые опкоды VM — основа карты опкодов для лифтера);
- пишется ограниченная лента событий (шаг песочницы, обработчик,
  числовые аргументы) — порядок исполнения.

Результат анализа (этот модуль): сопоставление «горячих» обработчиков с
их телами из parser.py даёт семантику опкодов (slice 4: карта опкодов,
slice 5: лифтер байткода в Lua AST).

CLI:
    py -m obfuscator.deobfuscator.luraph.vm_trace <file.lua> \
        [--max-steps N] [--max-records N] [--out trace.json]
"""
from __future__ import annotations

import time

__all__ = ['TraceResult', 'trace_vm', 'build_handler_body_map', '_self_test']


def build_handler_body_map_from_chunk(chunk, banner_version=None):
    """{id(body_node): handler_name} по УЖЕ распарсенному chunk (тот же AST,
    который исполняет песочница, — иначе id не совпадут)."""
    from obfuscator.deobfuscator.luraph.parser import parse_chunk
    rep = parse_chunk(chunk, banner_version)
    if not rep.detected:
        return {}
    out = {}
    for name, fn in rep.handlers.items():
        body = getattr(fn, 'body', None)
        if body is not None:
            out[id(body)] = name
    return out


def build_handler_body_map(source: str):
    """Вариант для внешнего использования (парсит заново)."""
    from obfuscator.lexer import Lexer
    from obfuscator.parser import Parser
    from obfuscator.deobfuscator.luraph.parser import detect_source
    try:
        chunk = Parser(Lexer(source).tokenize()).parse()
    except Exception:  # noqa: BLE001
        return {}
    return build_handler_body_map_from_chunk(chunk, detect_source(source))


class TraceResult:
    def __init__(self):
        self.histogram = {}      # handler_name -> calls
        self.records = []        # [(steps, handler, [numeric args])]
        self.anon_calls = 0      # вызовы не из таблицы обработчиков
        self.total_calls = 0
        self.steps = 0
        self.elapsed = 0.0
        self.error = None

    def top(self, n=15):
        return sorted(self.histogram.items(), key=lambda kv: -kv[1])[:n]

    def summary(self) -> str:
        lines = ['calls=%d (anon=%d) steps=%d elapsed=%.1fs' % (
            self.total_calls, self.anon_calls, self.steps, self.elapsed)]
        for name, cnt in self.top():
            lines.append('  %-10s %d' % (name, cnt))
        if self.error:
            lines.append('error: %s' % self.error)
        return '\n'.join(lines)

    def to_json_obj(self):
        return {
            'histogram': self.histogram,
            'anon_calls': self.anon_calls,
            'total_calls': self.total_calls,
            'steps': self.steps,
            'elapsed': round(self.elapsed, 1),
            'error': self.error,
            'records': self.records[:2000],
        }


def trace_vm(source: str, max_steps: int = 200_000_000,
             max_records: int = 20_000,
             progress_every: int = 0) -> TraceResult:
    """Прогнать образец в песочнице, собирая трейс вызовов обработчиков."""
    import sys
    from obfuscator.lexer import Lexer
    from obfuscator.parser import Parser
    from obfuscator.deobfuscator.core.lua_sandbox import (
        LuaSandbox, LuaFunction)
    from obfuscator.deobfuscator.core import lua_sandbox as _ls
    from obfuscator.deobfuscator.luraph.parser import detect_source

    res = TraceResult()
    t0 = time.time()

    # ОДИН парс: и карта обработчиков, и исполнение — по одному AST,
    # иначе id(body) не совпадут
    try:
        chunk = Parser(Lexer(source).tokenize()).parse()
    except Exception as e:  # noqa: BLE001
        res.error = 'ParseError: %s' % str(e)[:120]
        res.elapsed = time.time() - t0
        return res
    body_map = build_handler_body_map_from_chunk(chunk, detect_source(source))

    class _TraceSB(LuaSandbox):
        def _call_function(inner, fn, args, env=None):
            res.total_calls += 1
            if isinstance(fn, LuaFunction):
                name = body_map.get(id(fn.body))
                if name is not None:
                    res.histogram[name] = res.histogram.get(name, 0) + 1
                    if len(res.records) < max_records:
                        nums = [a for a in args
                                if isinstance(a, (int, float))
                                and not isinstance(a, bool)]
                        res.records.append(
                            (inner._steps, name, [str(x)[:14] for x in nums[:5]]))
                else:
                    res.anon_calls += 1
            else:
                res.anon_calls += 1
            return super()._call_function(fn, args, env)

        if progress_every:
            def _step(inner):
                super()._step()
                if inner._steps % progress_every == 0:
                    sys.stdout.write('  ... %d steps, %d calls (%.0fs)\n'
                                     % (inner._steps, res.total_calls,
                                        time.time() - t0))
                    sys.stdout.flush()

    sb = _TraceSB()
    sb.MAX_STEPS = max_steps
    sb._steps = 0
    sb._depth = 0
    env = dict(sb._globals)
    env['_G'] = _ls._EnvTable(env)
    try:
        sb._exec_chunk(chunk, env)
    except _ls.LuaReturn:
        pass  # штатный возврат чанка
    except Exception as e:  # noqa: BLE001
        res.error = '%s: %s' % (type(e).__name__, str(e)[:160])
    res.steps = getattr(sb, '_steps', 0)
    res.elapsed = time.time() - t0
    return res


# ---------------------------------------------------------------------------
# self-test: синтетическая «мини-VM» той же формы (мега-таблица + вызовы
# обработчиков), трейс должен опознать обработчики по именам.
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

    # мини-Luraph: баннер + return({...}):S() форма
    mini = (
        '-- This file was protected using Luraph Obfuscator v14.6\n'
        'return({\n'
        '  S = function(L) local i = {} i[1] = 0\n'
        '    for n = 1, 5 do i[1] = L:ADD(i[1], n) i[1] = L:MUL(i[1], 2) end\n'
        '    return i[1] end,\n'
        '  ADD = function(L, a, b) return a + b end,\n'
        '  MUL = function(L, a, b) return a * b end\n'
        '}):S()()\n'
    )
    r = trace_vm(mini, max_steps=200_000, max_records=500)
    check('T1 mini trace runs', r.total_calls > 0 and r.error is None,
          'calls=%d err=%r' % (r.total_calls, r.error))
    hist = r.histogram
    check('T2 handlers recognized by name',
          hist.get('ADD') == 5 and hist.get('MUL') == 5,
          repr(hist))
    check('T3 records captured with args',
          len(r.records) >= 10 and r.records[0][1] in ('ADD', 'MUL', 'S'),
          'records=%d first=%r' % (len(r.records), r.records[0] if r.records else None))

    # отрицательный: не-Luraph источник — пустая карта, трейс всё равно идёт
    r2 = trace_vm('local x = 1 + 1\nreturn x\n', max_steps=50_000)
    check('T4 non-luraph: no handlers, no crash',
          r2.histogram == {} and r2.error is None,
          'anon=%d' % r2.anon_calls)

    print('\nResult: %d/%d' % (passed, passed + failed))
    print('[OK] ALL PASSED' if failed == 0 else '[XX] FAILURES: %d' % failed)
    return 0 if failed == 0 else 1


def main(argv=None) -> int:
    import argparse
    import json
    ap = argparse.ArgumentParser(
        prog='py -m obfuscator.deobfuscator.luraph.vm_trace')
    ap.add_argument('file', nargs='?')
    ap.add_argument('--max-steps', type=int, default=200_000_000)
    ap.add_argument('--max-records', type=int, default=20_000)
    ap.add_argument('--progress-every', type=int, default=0)
    ap.add_argument('--out', help='сохранить трейс в JSON')
    ap.add_argument('--test', action='store_true')
    a = ap.parse_args(argv)

    if a.test or not a.file:
        return _self_test()

    with open(a.file, encoding='utf-8', errors='replace') as f:
        src = f.read()
    print('tracing %s (max_steps=%d)' % (a.file, a.max_steps))
    r = trace_vm(src, max_steps=a.max_steps, max_records=a.max_records,
                 progress_every=a.progress_every or 25_000_000)
    print(r.summary())
    if a.out:
        import os
        d = os.path.dirname(os.path.abspath(a.out))
        if d and not os.path.isdir(d):
            os.makedirs(d, exist_ok=True)
        with open(a.out, 'w', encoding='utf-8') as f:
            json.dump(r.to_json_obj(), f, ensure_ascii=False, indent=1)
        print('saved -> %s' % a.out)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
