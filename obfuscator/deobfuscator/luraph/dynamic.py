"""
NZL STUDIO - Sprint 5 (slice 2): динамическое извлечение payload Luraph v14.x
============================================================================
Стратегия: запустить обфусцированный чанк в нашей LuaSandbox с ПОДМЕНЁННЫМИ
`load`/`loadstring`. Luraph расшифровывает тело программы и в конце вызывает
`load(decrypted_src)` (в образце v14.6 — через слот k[16](w)). Записывающая
заглушка перехватывает РАСШИФРОВАННЫЙ ИСХОДНИК до того, как VM попытается
его вызвать.

Результат: DynamicExtractResult.captured — список перехваченных строк
(обычно 1 элемент = полный исходник payload). Дальше payload можно
распарсить нашим парсером и прогнать через обычный конвейер деобфускации.

Ограничения (честно):
- скорость: интерпретатор Python делает ~0.4 млн шагов/с; реальный образец
  требует сотни миллионов шагов (минуты, не миллисекунды);
- семантика: LuaSandbox покрывает не 100% Luau; если VM упрётся
  в нереализованную операцию — extract вернёт error и то, что успел
  перехватить;
- это ИЗВЛЕЧЕНИЕ, а не девиртуализация: если payload сам содержит VM-ядро
  (многоуровневый Luraph), потребуется повторный прогон (Sprint 6+).

CLI:
    py -m obfuscator.deobfuscator.luraph.dynamic <file.lua> \
        [--max-steps N] [--out payload.lua] [--progress-every N]
"""
from __future__ import annotations

import argparse
import os
import sys
import time

__all__ = ['DynamicExtractResult', 'extract_payload', '_self_test']


class DynamicExtractResult:
    """Итог динамического прогона."""

    def __init__(self, captured=None, error=None, steps=0, elapsed=0.0):
        self.captured = captured or []   # list[str] — перехваченные load()
        self.error = error               # str | None — чем кончился прогон
        self.steps = steps               # сколько шагов VM выполнено
        self.elapsed = elapsed           # секунд

    @property
    def ok(self) -> bool:
        return bool(self.captured)

    @property
    def payload(self):
        """Крупнейший перехваченный источник (обычно он один)."""
        if not self.captured:
            return None
        return max(self.captured, key=len)

    def __repr__(self):
        return ('DynamicExtractResult(captured=%d, error=%r, steps=%d, '
                'elapsed=%.1fs)' % (len(self.captured), self.error,
                                    self.steps, self.elapsed))


class _ProgressSandbox:
    """Обёртка: LuaSandbox + периодический прогресс в stdout (для длинных
    фоновых прогонов)."""

    def __init__(self, progress_every: int = 0):
        from obfuscator.deobfuscator.core.lua_sandbox import LuaSandbox
        self.sb = LuaSandbox()
        self.progress_every = progress_every
        if progress_every:
            outer = self

            class _SB(type(self.sb)):
                def _step(inner_self):
                    super()._step()
                    if (inner_self._steps % outer.progress_every) == 0:
                        sys.stdout.write('  ... %d steps (%.0fs)\n'
                                         % (inner_self._steps,
                                            time.time() - outer.t0))
                        sys.stdout.flush()
            self.sb = _SB()
        self.t0 = time.time()


def extract_payload(source: str, max_steps: int = 1_500_000_000,
                    progress_every: int = 0,
                    compile_mode: bool = False) -> DynamicExtractResult:
    """Прогнать Luraph-чанк в песочнице, перехватив load/loadstring.

    compile_mode=False (по умолчанию): заглушка load() возвращает nil —
    VM упадёт сразу ПОСЛЕ перехвата (payload уже у нас).
    compile_mode=True: load() реально исполняет перехваченный код в новой
    песочнице — нужно для МНОГОУРОВНЕВОГО Luraph (вложенные load), но
    медленнее и рискованнее.
    """
    holder = _ProgressSandbox(progress_every)
    sb = holder.sb
    sb.MAX_STEPS = max_steps
    holder.t0 = time.time()

    captured: list = []

    def _rec_load(args):
        a = args[0] if isinstance(args, (list, tuple)) and args else args
        if isinstance(a, str):
            captured.append(a)
            sys.stdout.write('[!!] load() captured %d chars\n' % len(a))
            sys.stdout.flush()
        if not compile_mode:
            return None
        # compile_mode: исполнить payload в свежей песочнице, вернуть
        # функцию-обёртку результата
        try:
            from obfuscator.deobfuscator.core.lua_sandbox import LuaSandbox
            inner = LuaSandbox()
            inner.MAX_STEPS = max(1_000_000, max_steps // 10)
            env2 = inner.execute(a, env={'load': _rec_load,
                                         'loadstring': _rec_load})
            ret = env2.get('__return__')
            if callable(ret):
                return ret
            return lambda _a: ret
        except Exception as e:  # noqa: BLE001
            sys.stdout.write('[!!] inner exec failed: %s\n' % e)
            return None

    error = None
    t0 = time.time()
    try:
        sb.execute(source, env={'load': _rec_load, 'loadstring': _rec_load})
    except Exception as e:  # noqa: BLE001
        error = '%s: %s' % (type(e).__name__, e)
    return DynamicExtractResult(captured=captured, error=error,
                                steps=getattr(sb, '_steps', 0),
                                elapsed=time.time() - t0)


# ---------------------------------------------------------------------------
# self-test: синтетическая проверка механизма (быстро, без реального образца)
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

    # T1: синтетический чанк, шифрующий тело и вызывающий load()
    src1 = ('local enc = "return 40 + 2"\n'
            'local f = load(enc)\n'
            'return f and f() or 0\n')
    r1 = extract_payload(src1, max_steps=100_000)
    check('T1 capture', r1.ok and r1.payload == 'return 40 + 2',
          'captured=%r' % (r1.captured,))

    # T2: loadstring тоже перехватывается
    src2 = 'local f = loadstring("return 7*7")\nreturn f and f() or 0\n'
    r2 = extract_payload(src2, max_steps=100_000)
    check('T2 loadstring', r2.ok and r2.payload == 'return 7*7')

    # T3: без load() — ничего не перехвачено, ошибки нет
    r3 = extract_payload('return 1 + 1\n', max_steps=10_000)
    check('T3 no-load', not r3.ok and r3.error is None)

    # T4: compile_mode — вложенный load исполняется
    src4 = ('local f = load("return load(\\"return 1+2\\")()")\n'
            'return f and f() or 0\n')
    r4 = extract_payload(src4, max_steps=100_000, compile_mode=True)
    check('T4 compile_mode nested', len(r4.captured) == 2,
          'captured=%d' % len(r4.captured))

    print('\nResult: %d/%d' % (passed, passed + failed))
    print('[OK] ALL PASSED' if failed == 0 else '[XX] FAILURES: %d' % failed)
    return 0 if failed == 0 else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog='py -m obfuscator.deobfuscator.luraph.dynamic',
        description='Dynamic payload extraction for Luraph v14.x samples')
    ap.add_argument('file', nargs='?', help='обфусцированный .lua файл')
    ap.add_argument('--max-steps', type=int, default=1_500_000_000)
    ap.add_argument('--out', help='куда сохранить перехваченный payload')
    ap.add_argument('--progress-every', type=int, default=25_000_000,
                    help='печатать прогресс каждые N шагов (0 = выкл)')
    ap.add_argument('--compile', action='store_true',
                    help='compile_mode: исполнять перехваченные load()')
    ap.add_argument('--test', action='store_true', help='синтетический self-test')
    a = ap.parse_args(argv)

    if a.test or not a.file:
        return _self_test()

    with open(a.file, encoding='utf-8', errors='replace') as f:
        src = f.read()
    print('extracting payload from %s (%d bytes)' % (a.file, len(src)))
    print('max_steps=%d progress_every=%d compile=%s'
          % (a.max_steps, a.progress_every, a.compile))
    r = extract_payload(src, max_steps=a.max_steps,
                        progress_every=a.progress_every,
                        compile_mode=a.compile)
    print('steps=%d elapsed=%.1fs captured=%d error=%s'
          % (r.steps, r.elapsed, len(r.captured), r.error))
    if r.payload:
        p = r.payload
        print('payload: %d bytes, first 200 chars:' % len(p))
        print(p[:200])
        if a.out:
            out_dir = os.path.dirname(os.path.abspath(a.out))
            if out_dir and not os.path.isdir(out_dir):
                os.makedirs(out_dir, exist_ok=True)
            with open(a.out, 'w', encoding='utf-8', newline='\n') as f:
                f.write(p)
            print('saved -> %s' % a.out)
        return 0
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
