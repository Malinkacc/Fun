#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
typeof-fix regression (2e-5).

Bug (found live in the bot, 2026-09-18): lexer mapped 'typeof' to a keyword
token, but the parser only knows the contextual keywords type/export/continue.
Any script calling typeof(...) died with:
    ParserError: Unexpected token: TYPEOF
Fix: demote 'typeof' to a plain NAME in the lexer (typeof is a library
function in both Lua 5.1 and Luau, never a reserved word).

Run either way:
    py obfuscator\\test_typeof.py --test
    py -m obfuscator.test_typeof --test
"""
import os
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from obfuscator.engine import Obfuscator, LEVELS          # noqa: E402
from obfuscator.lexer import Lexer, TokenType             # noqa: E402
from obfuscator.parser import Parser                      # noqa: E402

_FAILS = []


def chk(name, ok, info=''):
    if ok:
        print('[OK] %s' % name)
    else:
        print('[XX] %s  %s' % (name, info))
        _FAILS.append(name)


def _reparse(src):
    Parser(Lexer(src).tokenize()).parse()


def _roundtrip(src, level, tag):
    """obfuscate -> reparse output -> engine-deobfuscate -> reparse result."""
    r = Obfuscator().obfuscate(src, level=level)
    _reparse(r)
    from obfuscator.deobfuscator.engine import DeobfuscatorEngine
    res, _logs = DeobfuscatorEngine().deobfuscate(r)
    out = res if isinstance(res, str) else str(res)
    _reparse(out)
    chk(tag, True)


def main():
    # T1: typeof lexes as a plain NAME
    toks = Lexer('typeof(x)').tokenize()
    chk('T1 lex: typeof = NAME', toks[0].type == TokenType.NAME,
        'got %s' % toks[0].type.name)

    # T2: typeof in every name position + Luau contextual regression
    src = (
        'local plr = game.Players.LocalPlayer\n'
        'if typeof(plr.Character) == nil then print("dead") end\n'
        'local t = typeof(game) .. "_" .. type(plr)\n'
        'local typeof = typeof or type\n'
        'local u = { typeof = 1 }\n'
        'u.typeof = u.typeof + 1\n'
        'local i = 0\n'
        'while i < 3 do i = i + 1 if i == 2 then continue end print(i) end\n'
        'export type Point = { x: number }\n'
        'print(t, u.typeof, typeof(nil))\n'
    )
    try:
        _reparse(src)
        chk('T2 parse: call/field/local-typeof/continue/type-alias', True)
    except Exception as e:
        chk('T2 parse: call/field/local-typeof/continue/type-alias',
            False, '%s: %s' % (type(e).__name__, e))

    # T3: obfuscate at every level, output must re-parse
    for lvl in LEVELS:
        try:
            r = Obfuscator().obfuscate(src, level=lvl)
            _reparse(r)
            chk('T3 %s: obfuscate + reparse (%d bytes)' % (lvl, len(r)), True)
        except Exception as e:
            chk('T3 %s: obfuscate + reparse' % lvl,
                False, '%s: %s' % (type(e).__name__, e))

    # T4: isolated round trips (each shape separately)
    cases = [
        ('local p = 1\nif typeof(p) == nil then print("x") end\n',
         'T4a typeof-in-if'),
        ('local typeof = typeof or type\nprint(typeof(nil))\n',
         'T4b local-typeof'),
        ('local u = { typeof = 1 }\nu.typeof = u.typeof + 1\nprint(u.typeof)\n',
         'T4c field-typeof'),
        ('local i = 0\nwhile i < 3 do i = i + 1 '
         'if i == 2 then continue end print(i) end\n',
         'T4d continue-statement'),
        ('export type Point = { x: number }\nprint(1)\n',
         'T4e type-alias'),
    ]
    for code, tag in cases:
        try:
            _roundtrip(code, 'hard', tag + ': obf+deobf round trip')
        except Exception as e:
            chk(tag + ': obf+deobf round trip', False,
                '%s: %s' % (type(e).__name__, e))

    # T5: alias must not swallow the following statement (parser)
    try:
        chunk = Parser(Lexer(
            'export type Point = { x: number }\nprint(1)\n'
        ).tokenize()).parse()
        stmts = getattr(chunk.body, 'statements', chunk.body)
        first = stmts[0] if stmts else None
        ok = (len(stmts) == 2
              and getattr(first, 'type_expr', '') != ''
              and 'x' in getattr(first, 'type_expr', ''))
        chk('T5 alias keeps next statement + stores type text', ok,
            'body=%d type_expr=%r' % (len(stmts),
                                      getattr(first, 'type_expr', None)))
    except Exception as e:
        chk('T5 alias keeps next statement + stores type text',
            False, '%s: %s' % (type(e).__name__, e))

    # T6: obfuscated output keeps the print call and a valid alias RHS
    try:
        r = Obfuscator().obfuscate(
            'export type Point = { x: number }\nprint(1)\n', level='medium')
        import re
        ok = ('print(' in r
              and re.search(r'type\s+Point\s*=\s*\S', r) is not None
              and re.search(r'type\s+Point\s*=\s*$', r, re.M) is None)
        _reparse(r)
        ok = ok and True
        chk('T6 output: print survives, alias RHS non-empty', ok,
            repr(r[:200]))
    except Exception as e:
        chk('T6 output: print survives, alias RHS non-empty',
            False, '%s: %s' % (type(e).__name__, e))

    print('')
    total = 3 + len(LEVELS) + len(cases) + 2
    print('Result: %d/%d' % (total - len(_FAILS), total))
    if _FAILS:
        print('[XX] FAILURES: %d' % len(_FAILS))
        return 1
    print('[OK] ALL PASSED')
    return 0


if __name__ == '__main__':
    sys.exit(main())
