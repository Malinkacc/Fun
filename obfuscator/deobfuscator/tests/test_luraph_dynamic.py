"""
NZL STUDIO - Sprint 5 (slice 2): dynamic Luraph payload extraction tests
=========================================================================
T1  synthetic load-container round-trip (extract -> parse -> execute)
T2  computed source container (table.concat) - Luraph-like
T3  real sample fixture gate (samples/luraph/v14.6_payload1.lua, skip if absent)

Run:  py -m obfuscator.deobfuscator.tests.test_luraph_dynamic   (from repo root)
"""
from __future__ import annotations

import os
import sys

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

FIXTURE = os.path.join(_REPO, 'obfuscator', 'deobfuscator', 'samples',
                       'luraph', 'v14.6_payload1.lua')


def _extract(src, max_steps=200_000, compile_mode=False):
    from obfuscator.deobfuscator.luraph.dynamic import extract_payload
    return extract_payload(src, max_steps=max_steps, compile_mode=compile_mode)


def t1_synthetic_roundtrip() -> bool:
    """original -> load-container -> dynamic extract -> payload == original
    -> parse -> unparse -> execute -> same result."""
    from obfuscator.lexer import Lexer
    from obfuscator.parser import Parser
    from obfuscator.ast_unparser import ASTUnparser
    from obfuscator.deobfuscator.core.lua_sandbox import LuaSandbox

    ok = True
    original = 'local a = 6 * 7\nreturn a + 1\n'

    # контейнер в стиле Luraph: источник спрятан, восстанавливается и
    # передаётся в load()
    container = (
        'local k = {}\n'
        'k[1] = "local a = 6 * 7"\n'
        'k[2] = "\\nreturn a + 1\\n"\n'
        'local w = k[1] .. k[2]\n'
        'local f = load(w)\n'
        'return f and f() or -1\n'
    )

    r = _extract(container)
    cond = r.ok and r.payload == original
    print('[%s] T1a capture == original (%r)' % ('OK' if cond else 'XX', r.payload))
    ok = ok and cond

    if not cond:
        return False

    # payload -> parse -> unparse -> execute
    try:
        chunk = Parser(Lexer(r.payload).tokenize()).parse()
        unparsed = ASTUnparser().unparse(chunk)
        env = LuaSandbox().execute(unparsed)
        cond = env.get('__return__') == 43
    except Exception as e:  # noqa: BLE001
        cond = False
        print('[XX] T1b exception: %s' % e)
    print('[%s] T1b parse+exec payload == 43' % ('OK' if cond else 'XX'))
    return ok and cond


def t2_computed_source() -> bool:
    """source is COMPUTED at runtime (table.concat over fragments) -
    exactly what Luraph's decryptor does before calling load()."""
    container = (
        'local t = {}\n'
        'for i = 1, 3 do t[i] = ({"ret", "urn ", "7*7"})[i] end\n'
        'local f = load(table.concat(t))\n'
        'return f and f() or 0\n'
    )
    r = _extract(container)
    cond = r.ok and r.payload == 'return 7*7'
    print('[%s] T2 computed-source capture (%r)' % ('OK' if cond else 'XX', r.payload))
    return cond


def t3_real_fixture() -> bool:
    """Gate test on the REAL extracted payload (fixture produced by a long
    background run of luraph.dynamic on samples/luraph/v14.6_sample1.lua).
    Skipped when the fixture is not present in the working tree."""
    if not os.path.exists(FIXTURE):
        print('[!!] T3 SKIP - fixture not found: %s' % FIXTURE)
        return True
    from obfuscator.lexer import Lexer
    from obfuscator.parser import Parser

    with open(FIXTURE, encoding='utf-8', errors='replace') as f:
        payload = f.read()
    checks = [('size', len(payload) > 500)]
    try:
        chunk = Parser(Lexer(payload).tokenize()).parse()
        checks.append(('parses', chunk is not None))
    except Exception as e:  # noqa: BLE001
        checks.append(('parses', False))
        print('    parse error: %s' % e)
    low = payload.lower()
    checks.append(('has-return', 'return' in low))
    ok = all(c for _, c in checks)
    for name, c in checks:
        print('[%s] T3 %s (%d bytes)' % ('OK' if c else 'XX', name, len(payload)))
    return ok


def main() -> int:
    tests = [
        ('T1 synthetic roundtrip', t1_synthetic_roundtrip),
        ('T2 computed source', t2_computed_source),
        ('T3 real fixture gate', t3_real_fixture),
    ]
    passed = failed = 0
    for name, fn in tests:
        print('\n=== %s ===' % name)
        try:
            if fn():
                passed += 1
            else:
                failed += 1
        except Exception as e:  # noqa: BLE001
            failed += 1
            print('[XX] EXCEPTION: %s: %s' % (type(e).__name__, e))
    print('\n' + '=' * 60)
    print('  Result: %d/%d' % (passed, passed + failed))
    print('  [OK] ALL PASSED' if failed == 0 else '  [XX] FAILURES: %d' % failed)
    print('=' * 60)
    return 0 if failed == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
