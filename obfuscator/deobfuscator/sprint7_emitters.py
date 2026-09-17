"""Sprint 7 synthetic emitters (slice 5, part 1).

Adversarial-development rule: every obfuscator family we decode must also be
EMITTABLE, so decoders can be round-trip tested on ground truth.  Three
emitters mimic the shapes observed in the real samples:

  * emit_moonsec(inner)  - env/getfenv grab, PRNG-flavour counter loop, then
    loadstring(inner) reached through the env table: dynamic_decrypt must
    capture `inner` by identity.
  * emit_moonveil(prog)  - state table with H register file, a.a decoder
    closure (repeat-based), opcode closures of the SUB / DIV / CALL-G shapes
    and an executor loop over prog = [(op, b, c, d), ...].
  * emit_wearedevs(strs, rotations) - 'M'-prefixed cipher array, head/tail
    rotation loop, then a decode pass writing plaintext into a new table:
    array_trace must capture every plaintext string.
"""

import os
import sys

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)


def _lua_str(s):
    out = []
    for ch in s:
        o = ord(ch)
        if ch == '\\':
            out.append('\\\\')
        elif ch == '"':
            out.append('\\"')
        elif ch == '\n':
            out.append('\\n')
        elif 32 <= o < 127:
            out.append(ch)
        else:
            out.append('\\%03d' % o)
    return '"' + ''.join(out) + '"'


def emit_moonsec(inner):
    return (
        "local env = getfenv and getfenv() or _ENV\n"
        "local n = 0\n"
        "local c1 = function() n = n + 1 return n end\n"
        "local c2 = function(k) return k + n end\n"
        "while n < 40 do c2(c1()) end\n"
        "local f = env.loadstring or loadstring\n"
        "return f(%s)\n" % _lua_str(inner)
    )


_MV_OPS = {
    1: ("M[1] = function(a, b, c, d) a.H[d] = a.a(b, 100) - a.a(c, 50) "
        "return a.H[d] end\n"),
    2: ("M[2] = function(a, b, c, d) a.H[d] = a.a(b, 70) / a.a(c, 20) "
        "return a.H[d] end\n"),
    3: ("M[3] = function(a, b, c, d) a.H[d] = a.g(a.a(b, 7), a.a(c, 3)) "
        "return a.H[d] end\n"),
}


def emit_moonveil(prog):
    parts = [
        "local M = {}\n",
        "M.H = {}\n",
        "M.a = function(x, k)\n",
        "  local i = 0\n",
        "  local z = 41\n",
        "  repeat i = i + 1 until i > 2\n",
        "  z = z + x\n",
        "  return x - k\n",
        "end\n",
        "M.g = function(x, y) return x * y end\n",
    ]
    for op in sorted(set(p[0] for p in prog)):
        parts.append(_MV_OPS[op])
    parts.append("local P = {\n")
    for p in prog:
        parts.append("  {%d, %d, %d, %d},\n" % tuple(p))
    parts.append("}\n")
    parts.append("local acc = 0\n")
    parts.append("for i = 1, #P do\n")
    parts.append("  local p = P[i]\n")
    parts.append("  acc = acc + M[p[1]](M, p[2], p[3], p[4])\n")
    parts.append("end\n")
    parts.append("return acc\n")
    return ''.join(parts)


def _rev(s):
    return s[::-1]


def emit_wearedevs(strs, rotations):
    parts = ["local V = {\n"]
    for s in strs:
        parts.append("  %s,\n" % _lua_str('M' + _rev(s)))
    parts.append("}\n")
    parts.append("local n = #V\n")
    parts.append("local a, b = 1, n\n")
    parts.append("local j = 0\n")
    parts.append("while j < %d do\n" % rotations)
    parts.append("  local t = V[a]\n")
    parts.append("  V[a] = V[b]\n")
    parts.append("  V[b] = t\n")
    parts.append("  a = a % n + 1\n")
    parts.append("  b = (b + n - 2) % n + 1\n")
    parts.append("  j = j + 1\n")
    parts.append("end\n")
    parts.append("local P = {}\n")
    parts.append("for i = 1, n do\n")
    parts.append("  local s = V[i]\n")
    parts.append("  P[i] = s:sub(2):reverse()\n")
    parts.append("end\n")
    parts.append("return #P\n")
    return ''.join(parts)
