"""MoonSec V3 structured decompiler (slice 2b-12).

Upgrades the 2b-10 goto-form Lua to STRUCTURED control flow where the
CFG proves it; every non-matching site falls back to the proven goto
form, so the output can only gain structure, never lose correctness.

Patterns (semantics from the 2b-9 handler table, verified on the real
sample's CFG):

* repeat-until: a TEST-family macro whose FALSE branch targets BACKWARD
  (T <= slot): handler TRUE exits (falls through), FALSE repeats.
  Renders ``repeat <body T..S> until <cond>``.
* if-then / if-else / if-return: TEST-family macro with FORWARD target
  T.  Scan the then-region for its terminator:
  - ``goto J`` with J > T  -> if-else (else = T..J-1)
  - RETURN                 -> if-then ending in return
  - fall-through into T    -> if-then (join = T)
* Safety: no jump target may land STRICTLY INSIDE a structured region
  (checked against the proto's full target set), else fallback.
* EQ_K (ops 59/96, inverted polarity) and TESTSET stay in goto form on
  purpose; FORLOOP/FORPREP stay as numeric-for markers (the loop
  control-variable register writes live inside alias-unrolled handlers
  and are not extracted yet -- documented gap, no guessing).
* Labels are emitted only for targets still referenced by a remaining
  goto; structured regions drop their own labels.

Usage:
    py -m obfuscator.deobfuscator.moonsec.msvm_struct --test
    py -m obfuscator.deobfuscator.moonsec.msvm_struct --sample path\\moonsec_v3.lua --protos out\\protos.json --outdir out
"""

import os
import re
import sys
import json
import argparse

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from obfuscator.deobfuscator.moonsec.msvm_decomp import (
    lua_lit, rref, render_effect, consumed_of, opinfo_of,
)

TESTF = {'TEST', 'TESTN', 'TESTSET', 'EQ_C', 'NE_C', 'EQ_R', 'NE_R',
         'LT_C', 'LE_C', 'LT_R', 'LE_R', 'EQ_K'}
RETF = {'RETURN_0', 'RETURN_1', 'RETURN_m', 'TAILCALL', 'CALLC'}
STRUCT_TESTF = TESTF - {'EQ_K', 'TESTSET'}


def chain_head(opinfo, op):
    ch = opinfo_of(opinfo, op).get('chain')
    if not ch:
        return None
    return ch[0][-1][0]


def test_cond(r):
    """Condition of a TEST-family macro; TRUE branch EXITS (falls
    through), FALSE branch goes to target.  None if not renderable."""
    h, A, C = r['head'], r['A'], r['C']
    ra = rref(A)
    if h == 'TEST':
        return ra
    if h == 'TESTN':
        return 'not %s' % ra
    if h == 'EQ_C':
        return '%s == %s' % (ra, lua_lit(C))
    if h == 'NE_C':
        return '%s ~= %s' % (ra, lua_lit(C))
    if h == 'LT_C':
        return '%s < %s' % (ra, lua_lit(C))
    if h == 'LE_C':
        return '%s <= %s' % (ra, lua_lit(C))
    if h == 'EQ_R':
        return '%s == %s' % (ra, rref(C))
    if h == 'NE_R':
        return '%s ~= %s' % (ra, rref(C))
    if h == 'LT_R':
        return '%s < %s' % (ra, rref(C))
    if h == 'LE_R':
        return '%s <= %s' % (ra, rref(C))
    return None


def build_recs(proto, opinfo):
    """One record per macro start.  kind in
    test/jmp/forloop/forprep/ret/linear/filler/dead."""
    ins = proto['instrs']
    n = len(ins)
    recs = []
    i = 0
    while i < n:
        op = ins[i][0]
        A, B, C = ins[i][1], ins[i][2], ins[i][3]
        slot = i + 1
        head = chain_head(opinfo, op)
        cons = consumed_of(opinfo, op, C)
        r = {'slot': slot, 'op': op, 'A': A, 'B': B, 'C': C, 'cons': cons,
             'head': head, 'kind': 'linear', 'target': None, 'cond': None,
             'lines': []}
        if op == 24:
            r['kind'] = 'filler'
            r['lines'] = ['--[[filler/descriptor op=24 B=%s]]' % lua_lit(B)]
            recs.append(r)
            i += 1
            continue
        if head in (TESTF | {'JMP', 'FORLOOP', 'FORPREP'}) \
                and not isinstance(B, int):
            r['kind'] = 'dead'
            r['lines'] = ['--[[dead slot #%d op=%d A=%r B=%r C=%r]]'
                          % (slot, op, A, B, C)]
            recs.append(r)
            i += cons
            continue
        tgt = (B + 1) if isinstance(B, int) else None
        if head == 'JMP':
            r['kind'] = 'jmp'
            r['target'] = tgt
        elif head == 'FORLOOP':
            r['kind'] = 'forloop'
            r['target'] = tgt
            r['lines'] = ['forloop: goto L%d  --[[numeric-for marker]]' % (tgt or 0)]
        elif head == 'FORPREP':
            r['kind'] = 'forprep'
            r['target'] = tgt
            r['lines'] = ['forprep: goto L%d  --[[numeric-for marker]]' % (tgt or 0)]
        elif head in TESTF:
            r['kind'] = 'test'
            r['target'] = tgt
            r['cond'] = test_cond(r)
        elif head in RETF:
            r['kind'] = 'ret'
        # linear sub-slot statements (skip the control head effect)
        chain = opinfo_of(opinfo, op).get('chain') or []
        out = []
        for k in range(cons):
            sidx = i + k
            if sidx >= n:
                break
            sA, sB, sC = ins[sidx][1], ins[sidx][2], ins[sidx][3]
            if k < len(chain):
                name, det = chain[k][-1]
            else:
                name, det = 'RAW', 'op=%d' % op
            if r['kind'] in ('test', 'jmp', 'forloop', 'forprep') and k == 0:
                continue  # control effect handled structurally
            txt = render_effect(name, det, sA, sB, sC)
            if txt is not None:
                out.append(txt)
        if r['kind'] == 'linear' and not out and r['head'] != 'NOP':
            out.append('--[[unresolved slot #%d op=%d]]' % (slot, op))
        r['lines'] = r['lines'] + out
        recs.append(r)
        i += cons
    return recs


class Structurer(object):
    def __init__(self, recs):
        self.recs = recs
        self.by_slot = {r['slot']: k for k, r in enumerate(recs)}
        self.targets = set()
        for r in recs:
            if r['target']:
                self.targets.add(r['target'])
        self.stats = {'if': 0, 'ifelse': 0, 'ifret': 0, 'repeat': 0,
                      'goto': 0, 'dead': 0, 'filler': 0, 'for': 0,
                      'linear': 0, 'ret': 0}
        self.gotos_used = set()

    def interior(self, a, b):
        """Jump targets strictly inside slot range (a, b) exclusive."""
        return [t for t in self.targets if a < t < b]

    def range(self, k0, k1, ind):
        """Render records[k0:k1] at indent; returns list of (slot, text)."""
        out = []
        i = k0
        while i < k1:
            r = self.recs[i]
            pad = '  ' * ind
            if r['kind'] == 'dead':
                out.append((r['slot'], pad + r['lines'][0]))
                self.stats['dead'] += 1
                i += 1
                continue
            if r['kind'] == 'filler':
                out.append((r['slot'], pad + r['lines'][0]))
                self.stats['filler'] += 1
                i += 1
                continue
            if r['kind'] == 'forloop' or r['kind'] == 'forprep':
                out.append((r['slot'], pad + r['lines'][0]))
                self.stats['for'] += 1
                self.gotos_used.add(r['target'])
                i += 1
                continue
            if r['kind'] == 'jmp':
                if r['target']:
                    out.append((r['slot'], pad + 'goto L%d' % r['target']))
                    self.gotos_used.add(r['target'])
                self.stats['goto'] += 1
                i += 1
                continue
            if r['kind'] == 'ret':
                for tx in r['lines']:
                    out.append((r['slot'], pad + tx))
                self.stats['ret'] += 1
                i += 1
                continue
            if r['kind'] == 'linear':
                for tx in r['lines']:
                    out.append((r['slot'], pad + tx))
                self.stats['linear'] += 1
                i += 1
                continue
            if r['kind'] == 'test':
                T = r['target']
                S = r['slot']
                pad_i = i + 1  # rec index of the TRUE-skip padding slot (S+1)
                has_pad = pad_i < k1 and self.recs[pad_i]['slot'] == S + 1
                # ---- repeat-until (backward target) ----
                # arbitrary gotos INSIDE the loop body are legal (they stay
                # inside the repeat), so no interior check here; targets that
                # are not macro starts (anti-tamper mid-superinstr entries)
                # simply never reach this branch (T not in by_slot).
                if (T is not None and r['cond'] and T in self.by_slot
                        and self.by_slot[T] < i
                        and self.by_slot[T] >= k0):
                    k_body = self.by_slot[T]
                    out.append((S, pad + 'repeat'))
                    out.extend(self.range(k_body, i, ind + 1))
                    out.append((S, pad + 'until %s' % r['cond']))
                    self.stats['repeat'] += 1
                    i += 1
                    # the TRUE branch skips slot S+1; render it after the
                    # loop (it may still be a jump target from elsewhere)
                    if has_pad:
                        pr = self.recs[pad_i]
                        for tx in (pr['lines'] if pr['kind'] in
                                   ('linear', 'ret', 'dead', 'filler')
                                   else []):
                            out.append((pr['slot'], pad + tx))
                        if pr['kind'] in ('dead', 'filler'):
                            self.stats['dead'] += 1
                        i += 1
                    continue
                # ---- if (forward target, T >= S+2) ----
                if (T is not None and r['cond'] and T in self.by_slot
                        and self.by_slot[T] > i + 1
                        and self.by_slot[T] <= k1
                        and not self.interior(S, T)):
                    k_t = self.by_slot[T]
                    # then-region starts AFTER the skipped padding slot
                    j0 = i + 2 if has_pad else i + 1
                    term = None
                    # then-terminator: RETURN directly inside the then
                    j = j0
                    while j < k_t:
                        if self.recs[j]['kind'] == 'ret':
                            term = ('ret', j)
                            break
                        j += 1
                    # else-terminator: goto J > T inside the else region
                    if term is None:
                        j = k_t
                        while j < k1:
                            rj = self.recs[j]
                            if rj['kind'] == 'jmp' and rj['target'] \
                                    and rj['target'] > T \
                                    and not self.interior(T, rj['target']):
                                term = ('else', j)
                                break
                            j += 1
                    if term is None:
                        term = ('then', None)
                    if term is not None:
                        kind_t, jx = term
                        out.append((S, pad + 'if %s then' % r['cond']))
                        # then-region: [j0, k_t) for then/else joins,
                        # [j0, jx] INCLUDES the return for if-ret
                        then_end = jx + 1 if kind_t == 'ret' else k_t
                        out.extend(self.range(j0, then_end, ind + 1))
                        if kind_t == 'else':
                            out.append((S, pad + 'else'))
                            out.extend(self.range(k_t, jx, ind + 1))
                            # (goto terminator jx is consumed by the shape)
                            out.append((S, pad + 'end'))
                            self.stats['ifelse'] += 1
                            # skipped padding slot (still may be jump target)
                            if has_pad:
                                pr = self.recs[pad_i]
                                for tx in pr['lines']:
                                    out.append((pr['slot'], pad + '--[[pad]] ' + tx))
                            i = jx + 1
                            continue
                        if kind_t == 'ret':
                            out.append((S, pad + 'end'))
                            self.stats['ifret'] += 1
                            if has_pad:
                                pr = self.recs[pad_i]
                                for tx in pr['lines']:
                                    out.append((pr['slot'], pad + '--[[pad]] ' + tx))
                            i = jx + 1
                            continue
                        out.append((S, pad + 'end'))
                        self.stats['if'] += 1
                        if has_pad:
                            pr = self.recs[pad_i]
                            for tx in pr['lines']:
                                out.append((pr['slot'], pad + '--[[pad]] ' + tx))
                        i = k_t
                        continue
                # fallback: goto form for the test
                if r['target']:
                    out.append((S, pad + 'if not (%s) then goto L%d end  --[[fallback]]'
                                % (r['cond'], r['target'])))
                    self.gotos_used.add(r['target'])
                else:
                    for tx in r['lines']:
                        out.append((S, pad + tx))
                self.stats['goto'] += 1
                i += 1
                continue
            # unknown kind
            i += 1
        return out


def lift_proto_struct(proto, opinfo):
    recs = build_recs(proto, opinfo)
    st = Structurer(recs)
    pairs = st.range(0, len(recs), 1)
    lines = []
    labeled = set()
    for slot, text in pairs:
        if slot in st.gotos_used and slot not in labeled:
            lines.append('L%d:' % slot)
            labeled.add(slot)
        lines.append(text)
    return lines, st.stats


def lift_tree_struct(root, opinfo):
    out = []
    allstats = []

    def walk(p, path):
        out.append('-- ===== proto %s (nparams=%d, consts=%d, instrs=%d) ====='
                   % ('.'.join(map(str, path)), p.get('nparams', 0),
                      len(p.get('consts', [])), len(p.get('instrs', []))))
        out.append('function proto_%s(...)' % '.'.join(map(str, path)))
        lines, st = lift_proto_struct(p, opinfo)
        st['path'] = '.'.join(map(str, path))
        allstats.append(st)
        out.extend(lines)
        out.append('end')
        out.append('')
        for j, ch in enumerate(p.get('nested', [])):
            walk(ch, path + [j])

    walk(root, [0])
    return '\n'.join(out), allstats


def _mk_opinfo():
    return {
        '5': {'consumed': 1, 'chain': [[['MOVE', 'MOVE R[A]:=R[B]']]]},
        '12': {'consumed': 1, 'chain': [[['LOADK', 'LOADK R[A]:=B']]]},
        '20': {'consumed': 1, 'chain': [[['TEST', 'TEST skip-if-true']]]},
        '152': {'consumed': 1, 'chain': [[['JMP', 'JMP pc:=B']]]},
        '65': {'consumed': 1, 'chain': [[['RETURN_0', 'RETURN_0']]]},
        '4': {'consumed': 1, 'chain': [[['RETURN_1', 'RETURN_1 doreturnl[e[d]]end']]]},
    }


def _selftest():
    fails = []

    def chk(tag, cond, extra=''):
        print('[%s] %s%s' % ('OK' if cond else 'XX', tag,
                             (' -- ' + str(extra)) if extra and not cond else ''))
        if not cond:
            fails.append(tag)

    oi = _mk_opinfo()

    # T1: repeat-until (TEST backward to body start; pad slot after latch)
    p1 = {'nparams': 0, 'consts': [], 'nested': [], 'instrs': [
        [5, 1, 2, None],          # 1: body
        [20, 3, 0, None],         # 2: latch: TEST r3, false -> 1
        [12, 9, 'p', None],       # 3: skipped by TRUE (pad)
        [65, 0, 0, 0],            # 4: after loop
    ]}
    lines1, st1 = lift_proto_struct(p1, oi)
    t1 = '\n'.join(lines1)
    chk('T1 repeat', 'repeat' in t1 and 'until r3' in t1, t1)
    chk('T1 no goto', 'goto' not in t1, t1)

    # T2: if-then (TRUE skips pad #2, then = slot 3, join = 4)
    p2 = {'nparams': 0, 'consts': [], 'nested': [], 'instrs': [
        [20, 1, 3, None],         # 1: TEST r1, false -> 4
        [12, 9, 'p', None],       # 2: pad (skipped by TRUE)
        [12, 2, 'x', None],       # 3: then
        [65, 0, 0, 0],            # 4: join/return
    ]}
    lines2, st2 = lift_proto_struct(p2, oi)
    t2 = '\n'.join(lines2)
    chk('T2 if-then', 'if r1 then' in t2 and 'end' in t2, t2)
    chk('T2 then body', 'r2 = "x"' in t2, t2)
    chk('T2 pad kept', 'r9 = "p"' in t2, t2)

    # T3: if-else (then 3..3; else = 4..5-1; goto 6 consumed; join = 6)
    p3 = {'nparams': 0, 'consts': [], 'nested': [], 'instrs': [
        [20, 1, 3, None],         # 1: TEST r1, false -> 4 (else)
        [12, 9, 'p', None],       # 2: pad
        [12, 2, 'x', None],       # 3: then
        [12, 5, 'e', None],       # 4: else
        [152, 0, 5, None],        # 5: goto 6 (join, past else)
        [65, 0, 0, 0],            # 6: join/return
    ]}
    lines3, st3 = lift_proto_struct(p3, oi)
    t3 = '\n'.join(lines3)
    chk('T3 if-else shape', 'if r1 then' in t3 and 'else' in t3, t3)
    chk('T3 branches', 'r2 = "x"' in t3 and 'r5 = "e"' in t3, t3)
    chk('T3 then/else order',
        t3.find('r2 = "x"') < t3.find('else') < t3.find('r5 = "e"'), t3)

    # T4: if-return (then ends with RETURN)
    p4 = {'nparams': 0, 'consts': [], 'nested': [], 'instrs': [
        [20, 1, 4, None],         # 1: TEST r1, false -> 5
        [12, 9, 'p', None],       # 2: pad
        [12, 2, 'x', None],       # 3: then
        [4, 2, 0, 0],             # 4: return r2
        [12, 3, 'after', None],   # 5: false-path continues
        [65, 0, 0, 0],            # 6: return
    ]}
    lines4, st4 = lift_proto_struct(p4, oi)
    t4 = '\n'.join(lines4)
    chk('T4 if-ret', 'if r1 then' in t4 and 'return r2' in t4, t4)
    chk('T4 continues', 'r3 = "after"' in t4, t4)

    # T5: if nested inside repeat (join = latch slot)
    p5 = {'nparams': 0, 'consts': [], 'nested': [], 'instrs': [
        [5, 1, 2, None],          # 1: body
        [20, 3, 4, None],         # 2: if r3, false -> 5 (latch)
        [12, 9, 'p', None],       # 3: pad
        [12, 2, 'x', None],       # 4: then
        [20, 4, 0, None],         # 5: latch: TEST r4, false -> 1
        [12, 9, 'p', None],       # 6: pad (after latch)
        [65, 0, 0, 0],            # 7: after loop
    ]}
    lines5, st5 = lift_proto_struct(p5, oi)
    t5 = '\n'.join(lines5)
    chk('T5 nested', 'repeat' in t5 and 'if r3 then' in t5 and 'until r4' in t5, t5)
    chk('T5 then inside', t5.find('if r3 then') < t5.find('until r4'), t5)

    # T6: safety fallback (jump INTO the then-region)
    p6 = {'nparams': 0, 'consts': [], 'nested': [], 'instrs': [
        [20, 1, 3, None],         # 1: TEST r1, false -> 4
        [12, 9, 'p', None],       # 2: pad
        [12, 2, 'x', None],       # 3: then
        [152, 0, 2, None],        # 4: goto 3 -- INTO the then region!
        [65, 0, 0, 0],            # 5
    ]}
    lines6, st6 = lift_proto_struct(p6, oi)
    t6 = '\n'.join(lines6)
    chk('T6 fallback on interior jump', 'if r1 then' not in t6, t6)
    chk('T6 goto kept', 'goto L4' in t6 and 'L3:' in t6, t6)

    print('')
    print('Result: %d/6' % (6 - len(fails)))
    if fails:
        print('[XX] FAILURES: %d' % len(fails))
        return 1
    print('[OK] ALL PASSED')
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description='MoonSec V3 structured decompiler')
    ap.add_argument('--test', action='store_true')
    ap.add_argument('--sample', default=None)
    ap.add_argument('--protos', default=None)
    ap.add_argument('--outdir', default='out')
    ap.add_argument('--maxlines', type=int, default=60)
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
    text, stats = lift_tree_struct(protos[0], opinfo)
    os.makedirs(a.outdir, exist_ok=True)
    p = os.path.join(a.outdir, 'msvm_structured.lua')
    with open(p, 'w', encoding='utf-8') as fh:
        fh.write(text + '\n')
    tot = {'if': 0, 'ifelse': 0, 'ifret': 0, 'repeat': 0, 'goto': 0,
           'dead': 0, 'filler': 0, 'for': 0, 'linear': 0, 'ret': 0}
    for s in stats:
        for k, v in s.items():
            if k in tot:
                tot[k] += v
    print('protos: %d ; structured: if=%d ifelse=%d ifret=%d repeat=%d ; '
          'fallback gotos=%d ; for-markers=%d ; dead=%d'
          % (len(stats), tot['if'], tot['ifelse'], tot['ifret'],
             tot['repeat'], tot['goto'], tot['for'], tot['dead']))
    for s in stats:
        print('  proto %-8s if=%-3d ifelse=%-3d repeat=%-3d goto=%-3d'
              % (s['path'], s['if'], s['ifelse'], s['repeat'], s['goto']))
    shown = text.split('\n')
    for ln in shown[:a.maxlines]:
        print(ln)
    if len(shown) > a.maxlines:
        print('... (%d more lines -> %s)' % (len(shown) - a.maxlines, p))
    print('saved ->', p)
    return 0


if __name__ == '__main__':
    sys.exit(main())
