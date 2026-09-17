"""MoonSec V3 VM architecture model (Sprint 7, slice 2b-4, part 1).

Slices 2b-1..2b-3 mirrored the constant pipeline: stage1 (6 primitives),
stage2 (57 numeric constants under obfuscated names), stage3 (72-entry VM
toolbelt).  This module models what those constants PARAMETERISE: the VM
program representation and its assembly chain, extracted statically from
the sample text (no sandbox, deterministic).

Findings encoded here (all anchored to verbatim source forms):

1. Proto-stream decoder ``de``::

       local function de(u,...) local a=t(e,">4^Kcmin{?U-...")

   ``e`` is a ~60 KB encoded blob (the original program); ``a`` = decoded
   byte string; ``t`` = the payload decoder mirrored in mirror.py.

2. Proto assembler ``ee`` (function-closure factory)::

       function ee()
         local e={}   -- proto slot (a)
         local m={}   -- nested protos
         local b={}   -- instruction array
         local a={b,m,nil,e}
         local e=n()                       -- #constants
         local s={}                        -- constant pool
         for d=1,e do                      -- typed constants:
           local l=o()                     --   tag 2 -> boolean (o()~=#{})
           ...                             --   tag 1 -> string  (_(), 0-strip)
           ...                             --   tag 0 -> number  (p())
           s[d]=n
         end
         for a=1,n() do                    -- #instructions
           local e=o()                     -- packed opcode/mode byte
           if l(e,1,1)==0 then             -- bit0: instruction (not data)
             local f=l(e,2,3)              -- operand-B kind
             local o=l(e,4,6)              -- operand addressing bits
             local e={t(),t(),nil,nil}     -- e[1]=opcode e[2]=operand A
             if f==0 then e[3]=t();e[4]=t()
             elseif f==1 then e[3]=n()
             elseif f==u[2] then e[3]=n()-(2^16)
             elseif f==u[3] then e[3]=n()-(2^16); e[4]=t() end
             -- constant substitution by addressing bits of o:
             if bit(o,1)==1 then e[1]=s[e[1]] end
             if bit(o,2)==1 then e[3]=s[e[3]] end
             if bit(o,3)==1 then e[4]=s[e[4]] end
             b[a]=e
           end
         end
         for e=1,n() do m[e-1]=ee() end    -- nested protos (recursive)
         a[3]=o()                          -- #params
         return a
       end

   So one proto = {instructions, nested_protos, nparams, {const_pool_ref}}
   and each instruction = {opcode, A, B, C} with operands either raw
   numbers or constant-pool substitutions.

3. VM closure wiring: the marker ``\\006`` stream entry installs
   ``d[name]=function(n,e) return f(8,nil,f,e,n) end``; factory mode 8
   is ``do return n(l,nil,n) end`` -- the closure-creation channel that
   hands a proto table to the VM closure ``_(z,o,m)``.

4. VM preamble (constants resolved through the stage2 mirror):
   ``l=f(7)`` (env proxy), ``p=#(...)-1``, ``ee={}; y={...}; b={}``,
   ``t=f(6,49,1,79,z)``, ``k=f(6,63,2,43,z)``, ``j=f(6,98,3,28,z)``;
   factory mode 6 = ``do return d[n] end`` => t=z[49], k=z[63], j=z[98]
   (instruction array, constant array, varargs boundary -- keys are the
   decoded stage2 constants XiHzKHKe=49, grtQZmMW=63, dbYQXyMl=98).

5. VM dispatch: ``f=e[g]`` with g=1 (opcode = instruction field 1) and
   NUMERIC compare guards against the stage2 constants; observed bounds
   76, 96, 99, 101, 104, 114 with literal leaves 98..104 => opcode
   domain ~[77..114], leaves are unrolled Lua 5.1 opcode groups.

Honesty note: this is a STRUCTURAL model with source anchors, not an
executing mirror of de/ee (the reader closures n/o/t/_/p inside de are
position-scanned over the decoded blob; mirroring their exact framing is
the next step, 2b-5).

Usage:
    py -m obfuscator.deobfuscator.moonsec.vm_model --test
    py -m obfuscator.deobfuscator.moonsec.vm_model --sample path\\moonsec_v3.lua --outdir out
"""

import os
import re
import sys
import json
import argparse
from collections import Counter

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)


def model_source(src):
    """Extract the VM architecture model from raw MoonSec source text."""
    out = {}

    # 1. de(u,...) + encoded blob
    m = re.search(r'local function de\(u,\.\.\.\)local a=t\(e,"([^"]*)"', src)
    if m:
        blob = m.group(1)
        alpha = sorted(set(blob))
        out['de'] = {
            'found': True,
            'blob_len': len(blob),
            'blob_alphabet': ''.join(alpha),
            'blob_alphabet_size': len(alpha),
            'blob_head': blob[:32],
        }
    else:
        out['de'] = {'found': False}

    # 2. ee() proto assembler
    i = src.find('function ee()local e={};local m={};local b={}')
    out['ee'] = {'found': i >= 0, 'pos': i}
    if i >= 0:
        head = src[i:i + 4000]
        out['ee']['has_const_loop'] = 's[d]=n;end' in head
        out['ee']['has_instr_loop'] = 'b[a]=e;end' in head
        out['ee']['has_nested'] = 'm[e-' in head and 'ee()' in head
        out['ee']['has_bool_tag'] = '~=#{}' in head
        out['ee']['has_neg_offset'] = re.search(r'n\(\)-\(h\.[A-Za-z0-9_]+\^h\.[A-Za-z0-9_]+\)', head) is not None

    # 3. mode-8 wrapper install (stream marker \006)
    out['wrapper8'] = {
        'form': 'return f(8,nil,f,e,n)end' in src,
        'mode8_factory': 'do return n(l,nil,n);end' in src
                         or 'do return n(l,nil,n)end' in src,
    }

    # 4. instruction-array wiring f(6,key,...,z)
    wires = re.findall(r'([a-z])=f\(h\.ejXWheOX,h\.([A-Za-z0-9_]+),h\.([A-Za-z0-9_]+),h\.([A-Za-z0-9_]+),z\)', src)
    out['wiring'] = [{'dst': w[0], 'key': w[1], 'a2': w[2], 'a3': w[3]} for w in wires]
    out['mode6_factory'] = 'do return d[n]end' in src

    # 5. VM function bounds + dispatch numerics
    vm = src.find('function ne(...)local t,k,j,ne,u,n,a,ee,y,p,b,l;')
    out['vm'] = {'found': vm >= 0, 'pos': vm}
    if vm >= 0:
        end = src.find('local c=0xff;local o={};local f=(1);', vm)
        out['vm']['end_pos'] = end
        out['vm']['len'] = (end - vm) if end > vm else -1
        body = src[vm:end] if end > vm else src[vm:vm + 60000]
        # numeric opcode literals in guards/leaves
        nums = top_int_literals(body)
        out['vm']['numeric_literals_top'] = nums[:12]
        out['vm']['instr_fetch'] = 'e=t[n];f=e[g]' in body
        out['vm']['pc_wrap'] = re.search(r'if n<-h\.[A-Za-z0-9_]+ then n=n\+h\.[A-Za-z0-9_]+ end', body) is not None

    # 6. factory mode list (the (function(l,e,n,c,d,t) dispatcher)
    fac = src.find('(function(l,e,n,c,d,t)local t;if 3<l then')
    out['factory'] = {'found': fac >= 0, 'pos': fac}
    if fac >= 0:
        fbody = src[fac:fac + 2200]
        modes = {}
        modes['m8_closure'] = 'do return n(l,nil,n);end' in fbody
        modes['m7_metatable'] = 'setmetatable' in fbody
        modes['m6_index'] = 'do return d[n]end' in fbody
        modes['m45_readers'] = 'local e,n,f,h=e(n,l(l,l),l(l,l)+3)' in fbody
        modes['m1_bit'] = '(l/2^(e-1))%2^' in fbody
        modes['m2_bases'] = 'do return 16777216,65536,256 end' in fbody
        out['factory']['modes'] = modes
    return out


def top_int_literals(body, limit=12):
    """Most common standalone integer literals in a source region."""
    c = Counter(int(m.group(1)) for m in
                re.finditer(r'(?<![A-Za-z0-9_.^])(\d{2,4})(?![A-Za-z0-9_.])', body))
    return [{'value': v, 'count': n} for v, n in c.most_common(limit)]


def summary(model):
    lines = []
    de = model.get('de', {})
    lines.append('de: found=%s blob_len=%s alphabet(%s)=%s' % (
        de.get('found'), de.get('blob_len'), de.get('blob_alphabet_size'),
        de.get('blob_alphabet')))
    ee = model.get('ee', {})
    lines.append('ee: found=%s consts=%s instrs=%s nested=%s bool=%s negoffs=%s' % (
        ee.get('found'), ee.get('has_const_loop'), ee.get('has_instr_loop'),
        ee.get('has_nested'), ee.get('has_bool_tag'), ee.get('has_neg_offset')))
    lines.append('wrapper8: %s ; mode6 factory: %s' % (
        model.get('wrapper8'), model.get('mode6_factory')))
    lines.append('wiring: %s' % model.get('wiring'))
    vm = model.get('vm', {})
    lines.append('vm: found=%s len=%s fetch=%s pcwrap=%s' % (
        vm.get('found'), vm.get('len'), vm.get('instr_fetch'), vm.get('pc_wrap')))
    lines.append('vm top numerics: %s' % [d['value'] for d in vm.get('numeric_literals_top', [])])
    lines.append('factory: %s' % model.get('factory', {}))
    return '\n'.join(lines)


# --------------------------------------------------------------------------- #
# self-test on synthetic snippets
# --------------------------------------------------------------------------- #

_SYNTH = (
    'x=1 local function de(u,...)local a=t(e,">4^Kcmin{?U-lwZ3cU<{tl4r4m4")'
    ' more stuff '
    'function ee()local e={};local m={};local b={};local a={b,m,nil,e};'
    'local e=n()local s={}for d=h.XbwBnQSK,e do local l=o();local n;'
    'if(l==h._BdCcYgA)then n=(o()~=#{});elseif(l==h.XbwBnQSK)then n=_();end;s[d]=n;end;'
    'for a=h.XbwBnQSK,n()do local e=o();if(l(e,h.XbwBnQSK,h.XbwBnQSK)==h.hcQSdrdZ)then '
    'local f=l(e,h._BdCcYgA,h.kfzWnmpq);local e={t(),t(),nil,nil};'
    'if(f==u[h._BdCcYgA])then e[c]=n()-(h._BdCcYgA^h.jMwTqemz)end;b[a]=e;end end;'
    'for e=h.XbwBnQSK,n()do m[e-(#{h.XbwBnQSK})]=ee();end;a[h.kfzWnmpq]=o();return a;end;'
    ' elseif l==6 then do return d[n]end; else do return n(l,nil,n);end end '
    ' d[e]=function(n,e)return f(8,nil,f,e,n)end '
    'function ne(...)local t,k,j,ne,u,n,a,ee,y,p,b,l;local e=h.hcQSdrdZ;'
    't=f(h.ejXWheOX,h.XiHzKHKe,h.XbwBnQSK,h.twsMoWMa,z);'
    'k=f(h.ejXWheOX,h.grtQZmMW,h._BdCcYgA,h.ZLUUhYwa,z);'
    'j=f(h.ejXWheOX,h.dbYQXyMl,h.kfzWnmpq,h.ROdrfCJy,z);'
    'if n<-h.gtWTPyqI then n=n+h.ROzjrxmk end e=t[n];f=e[g];'
    'if 99<=f then l[e[d]]=l[e[c]]+e[r];end end '
    'local c=0xff;local o={};local f=(1); '
    '(function(l,e,n,c,d,t)local t;if 3<l then if l<6 then '
    'local l=c;local c,d,t=d(2);do return function()local e,n,f,h=e(n,l(l,l),l(l,l)+3);l(4);'
    'return(h*c)+(f*d)+(n*t)+e;end;end; else do return n(l,nil,n);end end '
    'else if l==6 then do return d[n]end else do return 16777216,65536,256 end end end '
    'if l==7 then do return setmetatable({},{}) end end '
    'do return function(l,e,n)if n then local e=(l/2^(e-1))%2^((n-1)-(e-1)+1);return e-e%1;end end '
)


def _selftest():
    fails = []

    def chk(tag, cond, extra=''):
        print(('[OK] ' if cond else '[XX] ') + tag + (' ' + extra if extra else ''))
        if not cond:
            fails.append(tag)

    m = model_source(_SYNTH)
    chk('T1 de blob extracted', m['de']['found'] and m['de']['blob_len'] == 27
        and m['de']['blob_alphabet_size'] == 19
        and m['de']['blob_head'] == '>4^Kcmin{?U-lwZ3cU<{tl4r4m4',
        str(m['de']))
    chk('T2 ee assembler features', m['ee']['found'] and m['ee']['has_const_loop']
        and m['ee']['has_instr_loop'] and m['ee']['has_nested']
        and m['ee']['has_bool_tag'] and m['ee']['has_neg_offset'])
    chk('T3 mode-8 wrapper + factory', m['wrapper8']['form'] and m['wrapper8']['mode8_factory']
        and m['mode6_factory'])
    wire = {w['dst']: w['key'] for w in m['wiring']}
    chk('T4 instruction wiring t/k/j', wire == {'t': 'XiHzKHKe', 'k': 'grtQZmMW', 'j': 'dbYQXyMl'},
        str(wire))
    chk('T5 vm bounds + fetch + pc wrap', m['vm']['found'] and m['vm']['len'] > 0
        and m['vm']['instr_fetch'] and m['vm']['pc_wrap'])
    fm = m['factory'].get('modes', {})
    chk('T6 factory modes', fm.get('m8_closure') and fm.get('m6_index')
        and fm.get('m45_readers') and fm.get('m1_bit') and fm.get('m2_bases')
        and fm.get('m7_metatable'), str(fm))

    print('')
    print('Result: %d/6' % (6 - len(fails)))
    if fails:
        print('[XX] FAILURES: %d' % len(fails))
        return 1
    print('[OK] ALL PASSED')
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description='MoonSec VM architecture model')
    ap.add_argument('--test', action='store_true')
    ap.add_argument('--sample', default=None)
    ap.add_argument('--outdir', default='out')
    a = ap.parse_args(argv)
    if a.test:
        return _selftest()
    if not a.sample:
        print('need --sample path (or --test)')
        return 2
    src = open(a.sample, encoding='utf-8', errors='replace').read()
    m = model_source(src)
    os.makedirs(a.outdir, exist_ok=True)
    p = os.path.join(a.outdir, 'vm_model.json')
    json.dump(m, open(p, 'w', encoding='utf-8'), indent=1)
    print(summary(m))
    print('saved ->', p)
    return 0


if __name__ == '__main__':
    sys.exit(main())
