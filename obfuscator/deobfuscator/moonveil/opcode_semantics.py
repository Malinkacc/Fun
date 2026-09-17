"""MoonVeil 2.x opcode semantics from instruction traces (Sprint 7, slice 3g).

vm_lift.py (slice 3f) cuts the table-I/O trace into VM instructions of the
shape {step, word, operands [[type, value]...], writes [[tid, key, val]...],
tid}.  Analysis of the real sample shows `word` IS the opcode: of 132
distinct words, 123 have exactly one operand/write shape across all their
occurrences (direct table dispatch, one closure per word).

This module classifies every word into an effect class from evidence in the
trace alone (no guessing about unobserved behaviour):

  PROG_LOAD   giant encoded-string operand (>5000 chars) or a bulk burst of
              >1000 operands/writes in one instruction (VM mass-init)
  CONST_EMIT  writes plain strings under ascending integer keys of one table
              (the constant pool: 'CreateWindow', 'Key System', ...)
  NEWFRAME    creates >= 2 fresh tables in one instruction
  FRAME_BIND  zero operands, every write stores a table reference (frame
              root binding; real word 250 writes ['T',0] into one table)
  PC_STEP     zero operands, only write is the pc register (n:1 of pc table)
  ADVANCE     operands present, only write is the pc register (fetch+decode
              cycle; per-instance pc delta is computed from write order)
  FETCH       operands are function/object refs, no writes (word fetchers)
  GUARD       operands present, no writes ever (bind/check closures)
  REG_WRITE   writes sparse non-pc numeric keys (register file stores)
  TICK        zero operands, zero writes (pure state-machine cycles)
  OTHER       anything else, recorded with its full shape signature

Honesty note: classes are EFFECT classes observed in one trace window of the
real sample (steps ~450k+).  They describe what each opcode did there; a
word unseen in the window simply does not appear in the map.

Outputs (with --trace <lifted.json> --outdir out):
  opcode_map.json  word -> {class, count, shapes, pc_deltas, example}
  constpool.json   ordered plaintext constants from CONST_EMIT words
  annotated.txt    the lifted listing re-rendered with class tags

Usage:
    py -m obfuscator.deobfuscator.moonveil.opcode_semantics --test
    py -m obfuscator.deobfuscator.moonveil.opcode_semantics --trace out\\lifted.json --outdir out
"""

import os
import sys
import json
import argparse
from collections import Counter, defaultdict

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

GIANT = 5000  # operand string longer than this = embedded program payload


# --------------------------------------------------------------------------- #
# instruction helpers
# --------------------------------------------------------------------------- #

def op_types(instr):
    return ''.join(t for t, _v in instr.get('operands', []))


def is_pc_write(w, pc_tid):
    tid, key, _val = w
    return tid == pc_tid and isinstance(key, list) and key == ['n', 1]


def detect_pc_tid(instrs):
    """The pc register table = the tid whose key ['n',1] is written most."""
    cnt = Counter()
    for i in instrs:
        for tid, key, _v in i.get('writes', []):
            if key == ['n', 1]:
                cnt[tid] += 1
    return cnt.most_common(1)[0][0] if cnt else None


def shape(instr):
    return op_types(instr) + '|' + str(len(instr.get('writes', [])))


# --------------------------------------------------------------------------- #
# classifier
# --------------------------------------------------------------------------- #

def classify(instrs):
    """Return (opcode_map, const_pool, pc_deltas_per_word).

    opcode_map: word -> dict(class, count, shapes, pc_deltas, example)
    const_pool: list of plaintext strings emitted by CONST_EMIT words, in
                trace order (key ascension verified).
    """
    pc_tid = detect_pc_tid(instrs)
    by_word = defaultdict(list)
    for i in instrs:
        by_word[i.get('word')].append(i)

    # per-instance pc deltas in trace order
    cur_pc = None
    delta_of = {}
    for idx, i in enumerate(instrs):
        for tid, key, val in i.get('writes', []):
            if pc_tid is not None and tid == pc_tid and key == ['n', 1] \
                    and isinstance(val, list) and val[0] == 'n':
                if cur_pc is not None:
                    delta_of[idx] = val[1] - cur_pc
                cur_pc = val[1]

    # seen tids over time for NEWFRAME detection
    seen_tids = set()
    fresh_count = defaultdict(int)
    for i in instrs:
        nf = 0
        for tid, _k, _v in i.get('writes', []):
            if tid not in seen_tids:
                seen_tids.add(tid)
                nf += 1
        if nf >= 2:
            fresh_count[i.get('word')] += 1

    # CONST_EMIT detection: writes only string values, keys ascending per word
    const_pool = []
    const_words = set()
    for w, lst in by_word.items():
        if w is None:
            continue
        keys = []
        strs = True
        for i in lst:
            ws = i.get('writes', [])
            if not ws:
                strs = False
                break
            for tid, key, val in ws:
                if not (isinstance(val, list) and val[0] in ('s', '?')):
                    strs = False
                if isinstance(key, list) and key[0] == 'n':
                    keys.append(key[1])
        if strs and keys and keys == sorted(keys) and len(set(keys)) == len(keys):
            const_words.add(w)
            for i in lst:
                for _tid, _key, val in i.get('writes', []):
                    if val[0] == 's':
                        const_pool.append(val[1])

    opcode_map = {}
    deltas_per_word = defaultdict(Counter)
    for idx, i in enumerate(instrs):
        if idx in delta_of:
            deltas_per_word[i.get('word')][delta_of[idx]] += 1

    for w, lst in by_word.items():
        shapes = Counter(shape(i) for i in lst)
        ex = lst[0]
        ops = ex.get('operands', [])
        giant = any(t == 's' and isinstance(v, str) and len(v) > GIANT
                     for i in lst for t, v in i.get('operands', []))
        giant_len = max((len(v) for i in lst for t, v in i.get('operands', [])
                         if t == 's' and isinstance(v, str)), default=0)
        bulk = max((max(len(i.get('writes', [])), len(i.get('operands', [])))
                    for i in lst), default=0) > 1000
        writes = ex.get('writes', [])
        all_w = [wr for i in lst for wr in i.get('writes', [])]
        all_pc = all(is_pc_write(wr, pc_tid) for wr in all_w) and bool(all_w)
        some_pc = any(is_pc_write(wr, pc_tid) for wr in all_w)
        any_writes = bool(all_w)
        no_writes = not any_writes
        nop = all(not i.get('operands') for i in lst)
        dl = deltas_per_word.get(w, {})
        var_delta = len(dl) > 1

        if giant or bulk:
            cls = 'PROG_LOAD'
        elif w in const_words:
            cls = 'CONST_EMIT'
        elif fresh_count.get(w, 0) == len(lst) and len(lst) > 0:
            cls = 'NEWFRAME'
        elif nop and all_w and not some_pc and all(
                isinstance(v, list) and v[0] == 'T' for _t, _k, v in all_w):
            cls = 'FRAME_BIND'
        elif all_pc and var_delta:
            cls = 'JMP'
        elif all_pc and nop:
            cls = 'PC_STEP'
        elif all_pc:
            cls = 'ADVANCE'
        elif some_pc and any_writes:
            cls = 'MIXED'
        elif no_writes and nop:
            cls = 'TICK'
        elif no_writes and all(t in '?Tn' for t in op_types(ex)):
            cls = 'FETCH' if '?' in op_types(ex) else 'GUARD'
        elif no_writes:
            cls = 'GUARD'
        elif any_writes:
            sparse = all(isinstance(k, list) and k[0] == 'n' and k[1] != 1
                         for i in lst for _t, k, _v in i.get('writes', []))
            cls = 'REG_WRITE' if sparse else 'OTHER'
        else:
            cls = 'OTHER'

        opcode_map[w] = {
            'class': cls,
            'count': len(lst),
            'giant_operand_len': giant_len,
            'max_io': max((max(len(i.get('writes', [])), len(i.get('operands', [])))
                           for i in lst), default=0),
            'shapes': dict(shapes),
            'pc_deltas': dict(deltas_per_word.get(w, {})),
            'example': {
                'step': ex.get('step'),
                'operands': [[t, (v[:40] + '...' if isinstance(v, str) and len(v) > 40 else v)]
                             for t, v in ops[:6]],
                'writes': writes[:4],
            },
        }
    return opcode_map, const_pool, pc_tid


def annotate(instrs, opcode_map):
    lines = []
    for i in instrs:
        w = i.get('word')
        info = opcode_map.get(w, {})
        cls = info.get('class', '?')
        ops = ' '.join('%s:%s' % (t, repr(v)[:28]) for t, v in i.get('operands', [])[:5])
        wr = ' '.join('%s=%s' % (k, repr(v)[:28]) for _t, k, v in i.get('writes', [])[:3])
        lines.append('step %-9s word %-8s %-10s | %s%s' % (
            i.get('step'), w, cls, ops, ('  -> ' + wr) if wr else ''))
    return '\n'.join(lines)


# --------------------------------------------------------------------------- #
# self-test (synthetic trace, no sample needed)
# --------------------------------------------------------------------------- #

def _selftest():
    fails = []

    def chk(tag, cond, extra=''):
        print(('[OK] ' if cond else '[XX] ') + tag + (' ' + extra if extra else ''))
        if not cond:
            fails.append(tag)

    PC = 1000
    CONST = 2000
    fresh1, fresh2 = 3000, 3001
    trace = [
        # baseline pc write so later deltas are computable
        {'step': 0, 'word': 251, 'operands': [],
         'writes': [[PC, ['n', 1], ['n', 100]]], 'tid': 9},
        # TICK: no ops, no writes
        {'step': 1, 'word': 26, 'operands': [], 'writes': [], 'tid': 9},
        # FETCH: one function operand, no writes
        {'step': 2, 'word': 68, 'operands': [['?', 'function']], 'writes': [], 'tid': 9},
        # ADVANCE: ops + pc write 100 -> 104 (delta 4)
        {'step': 3, 'word': 15, 'operands': [['?', 'function'], ['s', 'enc']],
         'writes': [[PC, ['n', 1], ['n', 104]]], 'tid': 9},
        # PC_STEP: no ops, pc write 104 -> 105 (delta 1)
        {'step': 4, 'word': 227, 'operands': [],
         'writes': [[PC, ['n', 1], ['n', 105]]], 'tid': 9},
        # CONST_EMIT: ascending string writes
        {'step': 5, 'word': 133, 'operands': [],
         'writes': [[CONST, ['n', 7], ['s', 'CreateWindow']]], 'tid': 9},
        {'step': 6, 'word': 133, 'operands': [],
         'writes': [[CONST, ['n', 8], ['s', 'Key System']]], 'tid': 9},
        # NEWFRAME: two fresh tables, no ops
        {'step': 7, 'word': 343, 'operands': [],
         'writes': [[fresh1, ['n', 1], ['n', 4]], [fresh2, ['n', 2], ['n', 1]]], 'tid': 9},
        # PROG_LOAD: giant string operand
        {'step': 8, 'word': 628, 'operands': [['s', 'x' * 6000]],
         'writes': [[PC, ['n', 1], ['n', 0]]], 'tid': 9},
        # REG_WRITE: sparse non-pc numeric writes
        {'step': 9, 'word': 883, 'operands': [],
         'writes': [[5000, ['n', 21], ['n', 121]]], 'tid': 9},
        # GUARD: ops, never any writes
        {'step': 10, 'word': 734, 'operands': [['T', 1], ['n', 4]], 'writes': [], 'tid': 9},
        # JMP: pc-only writes with varying deltas (0 -> 50 -> 60)
        {'step': 11, 'word': 627, 'operands': [['?', 'function']],
         'writes': [[PC, ['n', 1], ['n', 50]]], 'tid': 9},
        {'step': 12, 'word': 627, 'operands': [['?', 'function']],
         'writes': [[PC, ['n', 1], ['n', 60]]], 'tid': 9},
        # NEWFRAME with operands: two fresh tables
        {'step': 13, 'word': 267, 'operands': [['?', 'function'], ['T', 1]],
         'writes': [[4000, ['n', 1], ['n', 83]], [4001, ['n', 1], ['T', 1]]], 'tid': 9},
        # MIXED: pc advance + sparse register write
        {'step': 14, 'word': 673, 'operands': [],
         'writes': [[PC, ['n', 1], ['n', 61]], [5000, ['n', 34259], ['n', 111]]], 'tid': 9},
        # FRAME_BIND: no ops, writes only table refs (non-pc)
        {'step': 15, 'word': 250, 'operands': [],
         'writes': [[6000, ['n', 1], ['T', 0]]], 'tid': 9},
    ]
    # pc_tid detection must pick PC (3 pc writes vs 1 fresh1 n:1)
    omap, pool, pc_tid = classify(trace)
    chk('T1 pc register auto-detected', pc_tid == PC, str(pc_tid))
    chk('T2 classes assigned',
        (omap[26]['class'], omap[68]['class'], omap[15]['class'], omap[227]['class'])
        == ('TICK', 'FETCH', 'ADVANCE', 'PC_STEP'),
        str({w: omap[w]['class'] for w in (26, 68, 15, 227)}))
    chk('T3 const pool in order', pool == ['CreateWindow', 'Key System'], str(pool))
    chk('T4 pc deltas recorded', omap[15]['pc_deltas'].get('4', 0) + omap[15]['pc_deltas'].get(4, 0) == 1
        and omap[227]['pc_deltas'].get('1', 0) + omap[227]['pc_deltas'].get(1, 0) == 1,
        str((omap[15]['pc_deltas'], omap[227]['pc_deltas'])))
    chk('T5 NEWFRAME / PROG_LOAD / REG_WRITE / GUARD',
        (omap[343]['class'], omap[628]['class'], omap[883]['class'], omap[734]['class'])
        == ('NEWFRAME', 'PROG_LOAD', 'REG_WRITE', 'GUARD'),
        str({w: omap[w]['class'] for w in (343, 628, 883, 734)}))
    chk('T5b JMP / NEWFRAME-with-ops / MIXED',
        (omap[627]['class'], omap[267]['class'], omap[673]['class'])
        == ('JMP', 'NEWFRAME', 'MIXED'),
        str({w: omap[w]['class'] for w in (627, 267, 673)}))
    chk('T5c FRAME_BIND (table-ref writes, no ops)',
        omap[250]['class'] == 'FRAME_BIND', omap[250]['class'])
    txt = annotate(trace, omap)
    chk('T6 annotated listing renders', 'CONST_EMIT' in txt and 'PROG_LOAD' in txt
        and len(txt.splitlines()) == len(trace))

    print('')
    print('Result: %d/8' % (8 - len(fails)))
    if fails:
        print('[XX] FAILURES: %d' % len(fails))
        return 1
    print('[OK] ALL PASSED')
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description='MoonVeil opcode semantics classifier')
    ap.add_argument('--test', action='store_true')
    ap.add_argument('--trace', default=None, help='lifted instructions json (vm_lift output)')
    ap.add_argument('--outdir', default='out')
    a = ap.parse_args(argv)
    if a.test:
        return _selftest()
    if not a.trace:
        print('need --trace <lifted.json> (or --test)')
        return 2
    instrs = json.load(open(a.trace, encoding='utf-8'))
    omap, pool, pc_tid = classify(instrs)
    os.makedirs(a.outdir, exist_ok=True)
    # json keys must be strings
    jmap = {(str(k) if k is not None else 'null'): v for k, v in omap.items()}
    p1 = os.path.join(a.outdir, 'opcode_map.json')
    json.dump(jmap, open(p1, 'w', encoding='utf-8'), indent=1)
    p2 = os.path.join(a.outdir, 'constpool.json')
    json.dump(pool, open(p2, 'w', encoding='utf-8'), indent=1)
    p3 = os.path.join(a.outdir, 'annotated.txt')
    open(p3, 'w', encoding='utf-8').write(annotate(instrs, omap))
    # PROG_LOAD payload: the longest encoded operand string in the trace
    payload = ''
    for i in instrs:
        for t, v in i.get('operands', []):
            if t == 's' and isinstance(v, str) and len(v) > len(payload):
                payload = v
    p4 = None
    if payload:
        p4 = os.path.join(a.outdir, 'prog_payload.txt')
        open(p4, 'wb').write(payload.encode('latin1', 'replace'))
    cls = Counter(v['class'] for v in omap.values())
    print('instructions=%d distinct_words=%d pc_tid=%s' % (len(instrs), len(omap), pc_tid))
    print('classes:', dict(cls))
    print('const pool: %d strings, first: %s' % (len(pool), [c[:24] for c in pool[:8]]))
    print('saved ->', p1, p2, p3)
    if p4:
        print('prog payload ->', p4, '(%d chars)' % len(payload))
    return 0


if __name__ == '__main__':
    sys.exit(main())
