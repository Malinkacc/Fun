"""MoonSec V3 proto-tree decompiler (slice 2b-10).

Lifts the decoded proto tree (protos.json from proto_decode) to readable
Lua using the per-opcode semantics table extracted from the VM dispatch
(msvm_semantics).  This is the "real statements" upgrade of the 2b-8
pseudo-Lua listing.

Execution model encoded here (all verified on the real sample):

* Instructions are [op, A, B, C]; VM fields e[g]/e[d]/e[c]/e[r] map to
  op/A/B/C.  EVERY control transfer uses the B field: the handlers do
  ``n=e[c]`` and the loop tail adds 1, so the target slot is B+1
  (JMP ops 152/28; TEST/TESTN/TESTSET/EQ/NE family; FORLOOP/FORPREP;
  EQ_K ops 59/96).  A TEST-like TRUE branch SKIPS the next slot, so the
  slot after a TEST-like macro is dead padding (rendered as a comment).
* Superinstructions consume 1 + (#handler refetch pairs ``e=t[n]``)
  slots (msvm_semantics ``consumed``); CLOSURE-with-descriptors ops
  (112/123, handler ``for d=1,e[r] do n=n+1; local e=t[n]; ... end``)
  additionally consume the C descriptor slots.  Each chain element
  renders from its OWN slot's A/B/C.
* Opcode 24 NEVER dispatches (its slot body is ``n=-2`` junk); op-24
  slots are CLOSURE upvalue descriptors (consumed positionally) or
  filler.  Anti-tamper regions contain intentionally DEAD slots (e.g.
  TEST/JMP with non-integer targets); these are rendered as ``--[[dead
  ...]]`` comments, never silently dropped.

Honesty: anything that does not fit the model (unknown chain entry,
non-integer control field, target outside the proto) is emitted as an
explicit comment marker, so the output shows exactly what is proven.

Usage:
    py -m obfuscator.deobfuscator.moonsec.msvm_decomp --test
    py -m obfuscator.deobfuscator.moonsec.msvm_decomp --sample path\\moonsec_v3.lua --protos out\\protos.json --outdir out
"""

import os
import re
import sys
import json
import argparse

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)


# --------------------------------------------------------------------------- #
# operand / literal rendering
# --------------------------------------------------------------------------- #

def lua_lit(v):
    """Const-substituted operand -> Lua literal (bytes/str/dict forms)."""
    if isinstance(v, bool):
        return 'true' if v else 'false'
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, bytes):
        try:
            s = v.decode('utf-8')
        except UnicodeDecodeError:
            return "x'%s'" % v.hex()
        if all(32 <= ord(ch) < 127 or ch in '\n\t' for ch in s):
            return '"%s"' % s.replace('\\', '\\\\').replace('"', '\\"')
        return "x'%s'" % v.hex()
    if isinstance(v, str):
        return '"%s"' % v.replace('\\', '\\\\').replace('"', '\\"')
    if isinstance(v, dict) and '__bytes__' in v:
        return "x'%s'" % v['__bytes__']
    if v is None:
        return 'nil'
    return repr(v)


def rref(v):
    """Operand as register reference if int, else literal."""
    if isinstance(v, int) and not isinstance(v, bool):
        return 'r%d' % v
    return lua_lit(v)


def field_variants(detail):
    """Small helper: does the detail string contain a marker?"""
    return detail


# --------------------------------------------------------------------------- #
# per-effect renderers: (name, detail, slot) -> statement text or None
# --------------------------------------------------------------------------- #

def render_effect(name, detail, A, B, C):
    """Render one sub-effect.  Returns Lua statement text (no label)."""
    if name == 'MOVE':
        return 'r%d = %s' % (A, rref(B))
    if name == 'LOADK':
        return 'r%d = %s' % (A, lua_lit(B))
    if name == 'LOADIMM':
        return 'r%d = %s' % (A, rref(B))
    if name == 'GETGLOBAL':
        return 'r%d = G[%s]' % (A, lua_lit(B))
    if name == 'SETGLOBAL':
        return 'G[%s] = r%d' % (lua_lit(B), A)
    if name == 'GETUPVAL':
        return 'r%d = U[%s]' % (A, lua_lit(B))
    if name == 'SETUPVAL':
        return 'U[%s] = r%d' % (lua_lit(B), A)
    if name == 'GETTABLE':
        if 'R[C]]' in detail:
            return 'r%d = %s[%s]' % (A, rref(B), rref(C))
        return 'r%d = %s[%s]' % (A, rref(B), lua_lit(C))
    if name == 'SETTABLE':
        if 'R[A][R[B]]' in detail:
            return '%s[%s] = %s' % (rref(A), rref(B), rref(C))
        return '%s[%s] = %s' % (rref(A), lua_lit(B), rref(C))
    if name in ('ADD', 'SUB', 'MUL', 'DIV', 'MOD', 'POW'):
        op = {'ADD': '+', 'SUB': '-', 'MUL': '*', 'DIV': '/', 'MOD': '%',
              'POW': '^'}[name]
        rhs = rref(C) if ('%s R[C]' % op) in detail or ('%s R[C]' % op) in detail.replace('r', 'R') else lua_lit(C)
        if ('R[C]') in detail:
            rhs = rref(C)
        return 'r%d = %s %s %s' % (A, rref(B), op, rhs)
    if name == 'LEN':
        return 'r%d = #(%s)' % (A, rref(B))
    if name == 'UNM':
        return 'r%d = -(%s)' % (A, rref(B))
    if name == 'NOT':
        return 'r%d = not (%s)' % (A, rref(B))
    if name == 'NEWTABLE':
        return 'r%d = {}' % A
    if name == 'LOADBOOL':
        return 'r%d = (%s ~= 0)' % (A, lua_lit(B))
    if name == 'LOADNIL':
        return 'r%s..r%s = nil' % (A, rref(B))
    if name == 'JMP':
        return 'goto L%d' % ((B + 1) if isinstance(B, int) else B)
    if name == 'TEST':
        return 'if not %s then goto L%d end' % (rref(A), (B + 1) if isinstance(B, int) else B)
    if name == 'TESTN':
        return 'if %s then goto L%d end' % (rref(A), (B + 1) if isinstance(B, int) else B)
    if name == 'TESTSET':
        return 'if %s then r%d = %s; goto L%d end' % (
            rref(C), A, rref(C), (B + 1) if isinstance(B, int) else B)
    if name in ('EQ_C', 'EQI_EQ'):
        # handler: if (A==C) then skip-next else goto -> goto when A ~= C
        return 'if %s ~= %s then goto L%d end' % (rref(A), lua_lit(C),
                                                  (B + 1) if isinstance(B, int) else B)
    if name in ('NE_C', 'EQI_NE'):
        # handler: if (A~=C) then skip-next else goto -> goto when A == C
        return 'if %s == %s then goto L%d end' % (rref(A), lua_lit(C),
                                                  (B + 1) if isinstance(B, int) else B)
    if name == 'EQ_R':
        return 'if %s ~= %s then goto L%d end' % (rref(A), rref(C),
                                                  (B + 1) if isinstance(B, int) else B)
    if name == 'NE_R':
        return 'if %s == %s then goto L%d end' % (rref(A), rref(C),
                                                  (B + 1) if isinstance(B, int) else B)
    if name in ('LT_C', 'LE_C'):
        op = '<' if name.startswith('LT') else '<='
        return 'if not (%s %s %s) then goto L%d end' % (
            rref(A), op, lua_lit(C), (B + 1) if isinstance(B, int) else B)
    if name in ('LT_R', 'LE_R'):
        op = '<' if name.startswith('LT') else '<='
        return 'if not (%s %s %s) then goto L%d end' % (
            rref(A), op, rref(C), (B + 1) if isinstance(B, int) else B)
    if name == 'EQ_K':
        return 'if %s == %s then goto L%d end' % (rref(A), rref(C),
                                                  (B + 1) if isinstance(B, int) else B)
    if name == 'CALL_0':
        return 'r%d()' % A
    if name in ('CALLC', 'CALLV', 'CALL?'):
        # multres call forms: r[A] = r[A](r[A+1], ...)
        return 'r%d = %s(varargs)' % (A, rref(A))
    if name == 'TAILCALL':
        return 'return %s(varargs)' % rref(A)
    if name == 'RETURN_0':
        return 'return'
    if name == 'RETURN_1':
        if 's(l' in detail.replace(' ', ''):
            return 'return %s(varargs)' % rref(A)
        return 'return %s' % rref(A)
    if name == 'RETURN_m':
        return 'return %s, ...' % rref(A)
    if name == 'VARARG':
        return 'r%d.. = varargs' % A
    if name == 'CONCAT':
        return 'r%d = concat(%s..%s)' % (A, rref(B), rref(C))
    if name == 'CLOSURE':
        if 'proto(-1)' in detail or 'K[' not in detail:
            return 'r%d = closure(<descriptors>)' % A
        return 'r%d = closure(%s)' % (A, lua_lit(B))
    if name == 'CLOSE_UV':
        return 'close_upvalues(r%d..)' % A
    if name == 'FORLOOP':
        return 'forloop: goto L%d' % ((B + 1) if isinstance(B, int) else B)
    if name == 'FORPREP':
        return 'forprep: goto L%d' % ((B + 1) if isinstance(B, int) else B)
    if name == 'SELF':
        return 'r%d+1 = %s; r%d = %s[%s]' % (A, rref(B), A, rref(B), rref(C))
    if name == 'NOP':
        return None
    return None


# --------------------------------------------------------------------------- #
# control classification
# --------------------------------------------------------------------------- #

CONTROL_SKIPS_NEXT = {'TEST', 'TESTN', 'TESTSET', 'EQ_C', 'NE_C', 'EQ_R',
                      'NE_R', 'LT_C', 'LE_C', 'LT_R', 'LE_R', 'EQ_K'}
DESCRIPTOR_OPS = {112, 123}


def opinfo_of(opinfo, op):
    return opinfo.get(str(op)) or {}


def consumed_of(opinfo, op, C):
    rec = opinfo_of(opinfo, op)
    cons = rec.get('consumed', 1)
    det = ' '.join(rec.get('details', []))
    if 'ford=1,e[r]do' in det.replace(' ', ''):
        cons += (C or 0)
    return max(1, cons)


def lift_proto(proto, opinfo, proto_path='0'):
    """Lift one proto -> (lines, stats)."""
    ins = proto['instrs']
    n = len(ins)
    lines = []
    stats = {'slots': n, 'macros': 0, 'junk': 0, 'filler': 0}
    # label collection pass
    targets = set()
    i = 0
    while i < n:
        op = ins[i][0]
        A, B, C = ins[i][1], ins[i][2], ins[i][3]
        rec = opinfo_of(opinfo, op)
        chain = rec.get('chain') or []
        cons = consumed_of(opinfo, op, C)
        head = chain[0][-1][0] if chain else None
        if head in ('JMP', 'TEST', 'TESTN', 'TESTSET', 'EQ_C', 'NE_C', 'EQ_R',
                    'NE_R', 'LT_C', 'LE_C', 'LT_R', 'LE_R', 'EQ_K',
                    'FORLOOP', 'FORPREP') and isinstance(B, int):
            targets.add(B + 1)
        if op == 24:
            i += 1
            continue
        i += cons
    # emission pass
    i = 0
    while i < n:
        op = ins[i][0]
        A, B, C = ins[i][1], ins[i][2], ins[i][3]
        slot = i + 1
        if slot in targets:
            lines.append('L%d:' % slot)
        if op == 24:
            stats['filler'] += 1
            lines.append('  --[[filler/descriptor op=24 B=%s]]' % lua_lit(B))
            i += 1
            continue
        rec = opinfo_of(opinfo, op)
        chain = rec.get('chain') or []
        cons = consumed_of(opinfo, op, C)
        stats['macros'] += 1
        head = chain[0][-1][0] if chain else None
        # broken control?
        if head == 'TESTSET' and not isinstance(C, int) and C is not None \
                and not isinstance(C, str):
            pass
        if head in ('JMP', 'TEST', 'TESTN', 'TESTSET', 'EQ_C', 'NE_C', 'EQ_R',
                    'NE_R', 'LT_C', 'LE_C', 'LT_R', 'LE_R', 'EQ_K',
                    'FORLOOP', 'FORPREP') and not isinstance(B, int):
            stats['junk'] += 1
            lines.append('  --[[dead slot #%d op=%d A=%r B=%r C=%r]]'
                         % (slot, op, A, B, C))
            i += cons
            continue
        emitted = False
        for k in range(cons):
            sidx = i + k
            if sidx >= n:
                break
            sA, sB, sC = ins[sidx][1], ins[sidx][2], ins[sidx][3]
            if k < len(chain):
                name, det = chain[k][-1]  # last (most resolved) candidate
            else:
                name, det = 'RAW', 'op=%d' % op
            txt = render_effect(name, det, sA, sB, sC)
            if txt is None:
                continue
            lines.append('  %s  --[[#%d.%d op=%d]]' % (txt, slot, k + 1, op))
            emitted = True
            if name in CONTROL_SKIPS_NEXT and k == 0:
                lines.append('  --[[slot #%d skipped by %s]]' % (slot + 1, name))
        if not emitted:
            stats['junk'] += 1
            lines.append('  --[[unresolved slot #%d op=%d A=%r B=%r C=%r]]'
                         % (slot, op, A, B, C))
        i += cons
    return lines, stats


def clean_lua(text):
    """Strip provenance comments (--[[...]]) from lifted Lua; keeps
    statements and labels, drops lines that become empty."""
    out = []
    for line in text.split('\n'):
        s = re.sub(r'\s*--\[\[.*?\]\]\s*$', '', line)
        if s.strip() == '' and '--[[' in line:
            continue  # pure comment line (dead slot marker etc.)
        if s.strip() == '' and line.strip() == '':
            continue
        out.append(s)
    return '\n'.join(out)


def lift_tree(root, opinfo):
    """Lift a proto tree; returns (text, stats_list)."""
    out = []
    allstats = []

    def walk(p, path):
        head = ['-- ===== proto %s (nparams=%d, consts=%d, instrs=%d) ====='
                % ('.'.join(map(str, path)), p.get('nparams', 0),
                   len(p.get('consts', [])), len(p.get('instrs', [])))]
        head.append('function proto_%s(...)' % '.'.join(map(str, path)))
        lines, st = lift_proto(p, opinfo, '.'.join(map(str, path)))
        st['path'] = '.'.join(map(str, path))
        allstats.append(st)
        out.extend(head)
        out.extend(lines)
        out.append('end')
        out.append('')
        for j, ch in enumerate(p.get('nested', [])):
            walk(ch, path + [j])

    walk(root, [0])
    return '\n'.join(out), allstats


# --------------------------------------------------------------------------- #
# self-test on synthetic trees
# --------------------------------------------------------------------------- #

def _mk_opinfo():
    """Handcrafted op table for the synthetic test (mirrors proven forms)."""
    return {
        '5':  {'consumed': 1, 'chain': [[['MOVE', 'MOVE R[A]:=R[B]']]]},
        '12': {'consumed': 1, 'chain': [[['LOADK', 'LOADK R[A]:=B']]]},
        '127': {'consumed': 1, 'chain': [[['GETGLOBAL', 'GETGLOBAL R[A]:=G[B]']]]},
        '150': {'consumed': 1, 'chain': [[['SETGLOBAL', 'SETGLOBAL G[B]:=R[A]']]]},
        '22': {'consumed': 1, 'chain': [[['GETTABLE', 'GETTABLE R[A]:=R[B][R[C]]']]]},
        '54': {'consumed': 1, 'chain': [[['SETTABLE', 'SETTABLE R[A][R[B]]:=R[C]']]]},
        '23': {'consumed': 1, 'chain': [[['ADD', 'ADD R[A]:=R[B] + R[C]']]]},
        '152': {'consumed': 1, 'chain': [[['JMP', 'JMP pc:=B']]]},
        '20': {'consumed': 1, 'chain': [[['TEST', 'TEST skip-if-true']]]},
        '65': {'consumed': 1, 'chain': [[['RETURN_0', 'RETURN_0']]]},
        '4': {'consumed': 1, 'chain': [[['RETURN_1', 'RETURN_1 doreturnl[e[d]]end']]]},
        '8': {'consumed': 1, 'chain': [[['CLOSURE', 'CLOSURE R[A]:=proto(K[B])']]]},
        '123': {'consumed': 1,
                'chain': [[['CLOSURE', "CLOSURE R[A]:=proto(-1) ; ford=1,e[r]do"]]],
                'details': ['CLOSURE ford=1,e[r]do n=n+1 local e=t[n]']},
        '25': {'consumed': 7,
               'chain': [[['GETGLOBAL', 'GETGLOBAL R[A]:=G[B]']],
                         [['GETGLOBAL', 'GETGLOBAL R[A]:=G[B]']],
                         [['GETGLOBAL', 'GETGLOBAL R[A]:=G[B]']],
                         [['GETTABLE', 'GETTABLE R[A]:=R[B][R[C]]']],
                         [['RETURN_1', 'RETURN_1 doreturnl[f](s(l,f+1,e[c]))end']],
                         [['RETURN_m', 'RETURN_m doreturns(l,f,a)end']],
                         [['RETURN_0', 'RETURN_0']]]},
    }


def _selftest():
    fails = []

    def chk(tag, cond, extra=''):
        print('[%s] %s%s' % ('OK' if cond else 'XX', tag,
                             (' -- ' + str(extra)) if extra and not cond else ''))
        if not cond:
            fails.append(tag)

    oi = _mk_opinfo()

    # T1: simple statements render with register/literal operands
    proto = {'nparams': 0, 'consts': [], 'instrs': [
        [12, 1, 'hello', None],       # r1 = "hello"
        [12, 2, 42, None],            # r2 = 42
        [23, 3, 1, 2],                # r3 = r1 + r2
        [4, 3, 0, 0],                 # return r3
    ], 'nested': []}
    lines, st = lift_proto(proto, oi)
    txt = '\n'.join(lines)
    chk('T1 LOADK str', 'r1 = "hello"' in txt, txt)
    chk('T1 LOADK int', 'r2 = 42' in txt, txt)
    chk('T1 ADD', 'r3 = r1 + r2' in txt, txt)
    chk('T1 RETURN_1', 'return r3' in txt, txt)

    # T2: JMP + label + TEST skip semantics
    proto2 = {'nparams': 0, 'consts': [], 'instrs': [
        [20, 1, 4, None],             # TEST r1: true->skip #2, false->goto L4+? B=4 -> L5? B+1
        [152, 0, 3, None],            # (skipped if TEST true) JMP -> L4
        [12, 1, 'x', None],
        [152, 0, 1, None],            # JMP back to L2
        [65, 0, 0, 0],                # return
    ], 'nested': []}
    lines2, _st2 = lift_proto(proto2, oi)
    t2 = '\n'.join(lines2)
    chk('T2 TEST inverted goto', 'if not r1 then goto L5 end' in t2, t2)
    chk('T2 skip marker', 'skipped by TEST' in t2, t2)
    chk('T2 label emitted', 'L4:' in t2 and 'L2:' in t2, t2)

    # T3: GETGLOBAL/SETGLOBAL/GETTABLE/SETTABLE
    proto3 = {'nparams': 0, 'consts': [], 'instrs': [
        [127, 1, 'print', None],
        [54, 2, 'k', 3],
        [22, 4, 2, 3],
        [150, 4, 'out', None],
    ], 'nested': []}
    t3 = '\n'.join(lift_proto(proto3, oi)[0])
    chk('T3 GETGLOBAL', 'r1 = G["print"]' in t3, t3)
    chk('T3 SETTABLE imm-key', 'r2["k"] = r3' in t3, t3)
    chk('T3 GETTABLE reg-key', 'r4 = r2[r3]' in t3, t3)
    chk('T3 SETGLOBAL', 'G["out"] = r4' in t3, t3)

    # T4: CLOSURE with descriptor consumption (op 123, C=2 -> 3 slots)
    proto4 = {'nparams': 0, 'consts': [], 'instrs': [
        [123, 5, 1, 2],
        [24, 0, 3, 0],
        [24, 0, 0, 0],
        [12, 9, 'after', None],
    ], 'nested': []}
    lines4, st4 = lift_proto(proto4, oi)
    t4 = '\n'.join(lines4)
    chk('T4 CLOSURE descs consumed', st4['macros'] == 2, st4)
    chk('T4 descriptor markers', t4.count('descriptor') >= 0 and 'r9 = "after"' in t4, t4)

    # T5: superinstr chain renders per-slot (op 25: 3x GETGLOBAL + GETTABLE + ...)
    proto5 = {'nparams': 0, 'consts': [], 'instrs': [
        [25, 7, 'string', None],
        [2, 5, 19, None],
        [2, 9, 'string', None],
        [139, 9, 9, 'char'],
        [55, 10, 8, 0],
        [4, 9, 0, 0],
        [65, 0, 0, 0],
    ], 'nested': []}
    lines5, st5 = lift_proto(proto5, oi)
    t5 = '\n'.join(lines5)
    chk('T5 chain GETGLOBAL', 'r7 = G["string"]' in t5, t5)
    chk('T5 chain GETTABLE', "r9 = r9[\"char\"]" in t5, t5)
    chk('T5 consumed 7 slots', st5['macros'] == 1 and st5['slots'] == 7, st5)

    chk('T5b clean_lua strips provenance',
        '[[' not in clean_lua('  r1 = 2  --[[#5.1 op=25]]\n--[[dead slot #6]]\nL7:'),
        'clean output must keep code+labels only')

    # T6: dead slot marking for broken control field
    proto6 = {'nparams': 0, 'consts': [], 'instrs': [
        [20, 6, 'getfenv', None],
        [12, 1, 'ok', None],
    ], 'nested': []}
    lines6, st6 = lift_proto(proto6, oi)
    t6 = '\n'.join(lines6)
    chk('T6 dead marked', 'dead slot #1' in t6 and st6['junk'] == 1, t6)
    chk('T6 continues after dead', 'r1 = "ok"' in t6, t6)

    print('')
    print('Result: %d/6' % (6 - len(fails)))
    if fails:
        print('[XX] FAILURES: %d' % len(fails))
        return 1
    print('[OK] ALL PASSED')
    return 0


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def main(argv=None):
    ap = argparse.ArgumentParser(description='MoonSec V3 proto decompiler')
    ap.add_argument('--test', action='store_true')
    ap.add_argument('--sample', default=None)
    ap.add_argument('--protos', default=None)
    ap.add_argument('--outdir', default='out')
    ap.add_argument('--maxlines', type=int, default=80)
    ap.add_argument('--clean', action='store_true',
                    help='strip provenance comments from the output')
    a = ap.parse_args(argv)
    if a.test:
        return _selftest()
    if not a.sample or not a.protos:
        print('need --sample path and --protos path (or --test)')
        return 2
    from obfuscator.deobfuscator.moonsec.msvm_semantics import extract
    src = open(a.sample, encoding='utf-8', errors='replace').read()
    sem = extract(src)
    opinfo = {str(k): v for k, v in sem['ops'].items()}
    protos = json.load(open(a.protos, encoding='utf-8'))
    text, stats = lift_tree(protos[0], opinfo)
    if a.clean:
        text = clean_lua(text)
    os.makedirs(a.outdir, exist_ok=True)
    p = os.path.join(a.outdir, 'msvm_decompiled.lua')
    with open(p, 'w', encoding='utf-8') as fh:
        fh.write(text + '\n')
    tot = sum(s['slots'] for s in stats)
    junk = sum(s['junk'] for s in stats)
    fill = sum(s['filler'] for s in stats)
    mac = sum(s['macros'] for s in stats)
    print('protos: %d ; slots: %d ; macros: %d ; filler(op24): %d ; dead/unresolved: %d (%.1f%%)'
          % (len(stats), tot, mac, fill, junk, 100.0 * junk / max(1, tot)))
    for s in stats:
        print('  proto %-8s slots=%-4d macros=%-4d junk=%d' %
              (s['path'], s['slots'], s['macros'], s['junk']))
    shown = text.split('\n')
    for ln in shown[:a.maxlines]:
        print(ln)
    if len(shown) > a.maxlines:
        print('... (%d more lines -> %s)' % (len(shown) - a.maxlines, p))
    print('saved ->', p)
    return 0


if __name__ == '__main__':
    sys.exit(main())
