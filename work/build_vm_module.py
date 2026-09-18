# -*- coding: utf-8 -*-
import re

NAMES = {
 4:"SETTABLE", 8:"MULK", 9:"DEADLOCK", 10:"LSHIFT", 14:"GETUPVAL", 15:"APPEND", 16:"LOADNIL",
 17:"BOR", 24:"CONCAT_TABLE", 26:"SETTABLEKS", 27:"JUMPIFEQK", 29:"GETTABLE", 31:"LOADK", 33:"MUL",
 39:"CONCAT_STR", 41:"JUMPBACK", 43:"NOOP_FALSE", 44:"NOOP", 45:"ERROR", 46:"MATH_M2", 48:"FLOOR",
 49:"PACK_REGS", 50:"CALL2", 51:"UNM", 52:"MATH_H2", 59:"DIVK", 60:"JUMPIFNOT", 61:"JUMPIF", 66:"GE",
 68:"SPLIT", 72:"INDEX_OF", 73:"LROTATE", 80:"GETMETATABLE", 81:"NOOP", 83:"EQ", 84:"RROTATE",
 85:"STR_C2", 86:"NOOP", 87:"SUB_AND_JUMP", 88:"PACK_INTO", 91:"MOVE", 93:"JUMPNIL_SKIP", 96:"NOOP",
 99:"LT", 100:"ADD", 104:"SUBK", 106:"LTK", 107:"POW", 109:"TONUMBER", 112:"MATH_Y2", 113:"MOD",
 116:"NOT", 117:"SIGN", 119:"STR_BYTE", 121:"LOADNIL", 125:"IDIV", 128:"NE", 132:"APPEND_TO",
 133:"GETGLOBAL", 134:"TOSTRING", 136:"MOVE", 138:"RETURN", 141:"SETTABLE", 144:"LEN", 145:"BAND",
 146:"NOOP", 148:"GETTABLE", 150:"SUB_STRING", 151:"LEK", 153:"LOADBOOL_B", 155:"DIV", 156:"SWAP",
 157:"SETGLOBAL", 160:"MODK", 161:"SETUPVAL", 162:"BXOR", 163:"STR_W1", 164:"NOOP", 165:"SETTABLEKS",
 166:"RSHIFT", 170:"NOOP", 172:"ASSERT", 174:"TAILCALL", 176:"STR_S1", 178:"NOOP", 179:"EQK",
 182:"NOOP_TRUE", 183:"GETTABLEKS", 185:"SUB", 188:"CALL", 189:"STR_V1", 191:"GT", 194:"GETTABLE_N",
 196:"LEN", 200:"UNPACK_REGS", 203:"CLEAR_REGS", 205:"NOOP", 207:"FORLOOP", 208:"ADDK", 209:"GETTABLEKS",
 213:"NOTNOT", 214:"CLOSURE", 216:"JUMP", 219:"AND", 225:"TYPE", 231:"REMOVE", 234:"LOADINT_B",
 237:"VARARG", 242:"BNOT", 243:"MATH_Z2", 244:"MATH_K2", 245:"NEWTABLE", 248:"OR", 252:"SETMETATABLE",
 253:"CHAR", 255:"LE",
}
DESC = {
 4:"regs[A][regs[B]] = regs[C]", 8:"regs[A] = regs[B] * K[D+1]", 9:"while true do end  -- ЛОВУШКА: вечный цикл",
 10:"regs[A] = lshift(regs[B], regs[C])", 14:"regs[A] = upval[B]  (открытый upvalue: regs создателя)",
 15:"regs[A][#regs[A]+1] = regs[B]", 16:"regs[A] = nil", 17:"regs[A] = bor(regs[B], regs[C])",
 24:"regs[A] = table.concat(regs[B], regs[C])", 26:"regs[A][K[D+1]] = regs[B]", 27:"if regs[A] == K[D+1] then pc+1",
 29:"regs[A] = regs[B][regs[C]]", 31:"regs[A] = K[D+1]", 33:"regs[A] = regs[B] * regs[C]",
 39:"regs[A] = tostring(regs[B])..tostring(regs[C])", 41:"pc = pc - D   (прыжок назад)", 43:"regs[A] = (#tostring(type(nil))==4) -> всегда false",
 44:"заглушка (no-op)", 45:"error(regs[A])", 46:"regs[A] = math.M2(regs[B])   <НЕТ в стандартной библиотеке>",
 48:"regs[A] = floor(regs[B])", 49:"regs[A] = {regs[B]..regs[C]}", 50:"вызов regs[A](regs[A+1],regs[A+2]), результаты в regs[A+3..]",
 51:"regs[A] = -regs[B]", 52:"regs[A] = math.h2(regs[B])   <НЕТ в стандартной библиотеке>",
 59:"regs[A] = regs[B] / K[D+1]", 60:"if not regs[A] then pc+D", 61:"if regs[A] then pc+D",
 66:"regs[A] = (regs[B] >= regs[C])", 68:"regs[A] = split(regs[B], regs[C])",
 72:"regs[A] = индекс regs[C] в таблице regs[B]", 73:"regs[A] = lrotate(regs[B], regs[C])",
 80:"regs[A] = getmetatable(regs[B])", 81:"заглушка (no-op)", 83:"regs[A] = (regs[B] == regs[C])",
 84:"regs[A] = rrotate(regs[B], regs[C])", 85:"regs[A] = string.C2(regs[B], regs[C])  <НЕСТАНДАРТНОЕ имя>",
 86:"заглушка (no-op)", 87:"regs[A] = regs[A] - regs[A+2]; pc+D   (странная семантика)",
 88:"for i=1..B: regs[A][C+i] = regs[A+i]", 91:"regs[A] = regs[B]", 93:"if regs[A+3] ~= nil then regs[A+2]=regs[A+3]; pc+D",
 96:"заглушка (no-op)", 99:"regs[A] = (regs[B] < regs[C])", 100:"regs[A] = regs[B] + regs[C]",
 104:"regs[A] = regs[B] - K[D+1]", 106:"regs[A] = (regs[B] < K[D+1])", 107:"regs[A] = regs[B] ^ regs[C]",
 109:"regs[A] = tonumber(regs[B])", 112:"regs[A] = math.y2(regs[B], regs[C])   <НЕТ в стандартной библиотеке>",
 113:"regs[A] = regs[B] % regs[C]", 116:"regs[A] = not regs[B]", 117:"regs[A] = sign(regs[B])",
 119:"regs[A] = string.byte(regs[B], regs[C])", 121:"regs[A] = nil", 125:"regs[A] = floor(regs[B] / regs[C])",
 128:"regs[A] = (regs[B] ~= regs[C])", 132:"regs[B][#regs[B]+1] = regs[C]", 133:"regs[A] = env[K[D+1]]  (глобальная переменная)",
 134:"regs[A] = tostring(regs[B])", 136:"regs[A] = regs[B]", 138:"return regs[A] .. regs[A+B-1]",
 141:"regs[A][regs[B]] = regs[C]   (копия опкода 4)", 144:"regs[A] = #regs[B]", 145:"regs[A] = band(regs[B], regs[C])",
 146:"заглушка (no-op)", 148:"regs[A] = regs[B][regs[C]]   (копия опкода 29)", 150:"regs[A] = string.sub(regs[B], regs[C], regs[C+1])",
 151:"regs[A] = (regs[B] <= K[D+1])", 153:"regs[A] = (B ~= 0)  -- bool из операнда", 155:"regs[A] = regs[B] / regs[C]",
 156:"regs[A], regs[B] = regs[B], regs[A]", 157:"env[K[D+1]] = regs[A]  (запись в глобальную)",
 160:"regs[A] = regs[B] % K[D+1]", 161:"upval[B] = regs[A]", 162:"regs[A] = bxor(regs[B], regs[C])",
 163:"regs[A] = string.W1(regs[B])   <НЕСТАНДАРТНОЕ имя>", 164:"заглушка (no-op)",
 165:"regs[A][K[D+1]] = regs[B]   (копия опкода 26)", 166:"regs[A] = rshift(regs[B], regs[C])", 170:"заглушка (no-op)",
 172:"assert(regs[A], regs[B])", 174:"return regs[A](regs[A+1]..regs[A+B-1])  (хвостовой вызов)",
 176:"regs[A] = string.S1(regs[B], regs[C])   <НЕСТАНДАРТНОЕ имя>", 178:"заглушка (no-op)",
 179:"regs[A] = (regs[B] == K[D+1])", 182:"regs[A] = (#tostring(type(nil))==3) -> всегда true", 183:"regs[A] = regs[B][K[D+1]]",
 185:"regs[A] = regs[B] - regs[C]", 188:"вызов regs[A](regs[A+1]..regs[A+B-1])", 189:"regs[A] = string.V1(regs[B])   <НЕСТАНДАРТНОЕ имя>",
 191:"regs[A] = (regs[B] > regs[C])", 194:"regs[A+1] = regs[B]; regs[A] = regs[B][regs[C]]",
 196:"regs[A] = #regs[B]   (копия опкода 144)", 200:"распаковать таблицу regs[B][1..D] в regs[A..]",
 203:"regs[A .. A+B] = nil", 205:"заглушка (no-op)", 207:"числовой for: шаг/сравнение/условный прыжок pc+D",
 208:"regs[A] = regs[B] + K[D+1]", 209:"regs[A] = regs[B][K[D+1]]   (копия опкода 183)", 213:"regs[A] = not not regs[B]",
 214:"regs[A] = замыкание(proto[D]) с захватом upvalue", 216:"pc = pc + D   (прыжок вперёд)", 219:"regs[A] = regs[B] and regs[C]",
 225:"regs[A] = type(regs[B])", 231:"удалить regs[B][regs[C]] со сдвигом (table.remove-подобное)",
 234:"regs[A] = знаковый байт B (-128..127)", 237:"regs[A] = varargs (или таблица varargs)",
 242:"regs[A] = bnot(regs[B])", 243:"regs[A] = math.z2(regs[B], regs[C])   <НЕТ в стандартной библиотеке>",
 244:"regs[A] = math.k2(regs[B])   <НЕТ в стандартной библиотеке>", 245:"regs[A] = {}",
 248:"regs[A] = regs[B] or regs[C]", 252:"setmetatable(regs[A], regs[B])",
 253:"regs[A] = string.char(regs[B]..regs[C])", 255:"regs[A] = (regs[B] <= regs[C])",
}
DEAD = [44,81,86,96,146,164,170,178,205]

clean = open('vm_clean.lua', encoding='utf-8').read()
clean = clean.split('\n',1)[1] if clean.startswith('local strByte') else clean
# --- вытащить диспетчер из runProto ---
start = clean.index('while true do', clean.index('local function runProto'))
tail = clean[start:].rstrip()
assert tail.endswith('end end end') or tail.endswith('end\nend\nend'), tail[-60:]
tail = tail[:-len('end end end')].rstrip() if tail.endswith('end end end') else tail
disp = tail[len('while true do'):]
parts = re.split(r'(?=\b(?:elseif|if) op==\d+ then do)', disp)
branches = []
preamble = parts[0].strip() if parts and not re.match(r'^(?:elseif|if) op==', parts[0].strip()) else ''
for p in parts:
    p = p.strip()
    if not p or not re.match(r'^(?:elseif|if) op==', p): continue
    mm = re.match(r'^(?:elseif|if) op==(\d+) then do(.*)end$', p, re.S)
    assert mm, p[:80]
    branches.append((int(mm.group(1)), mm.group(2).strip()))
# --- собрать новый диспетчер с комментариями ---
out = [preamble]
for i,(num,body) in enumerate(branches):
    kw = 'if' if i == 0 else 'elseif'
    name = NAMES.get(num, 'UNKNOWN_%d' % num)
    desc = DESC.get(num, '')
    if num in DEAD:
        out.append('  -- [%d] %s — %s (вырезано: реального эффекта нет)' % (num, name, desc))
        continue
    out.append('  %s op == %d then  -- [%d] %s — %s' % (kw, num, num, name, desc))
    out.append('    ' + body)
newdisp = '\n'.join(out) + '\n'
clean2 = clean[:start] + 'while true do\n' + newdisp + 'end end end\n'

clean2 = clean2.replace('ins.strByte', 'ins.D_').replace('instr.strByte,D_=readI32', 'instr.D_=readI32')
open('dispatcher_clean.lua','w').write(clean2)
opnames = ',\n'.join('  [%d] = "%s"' % (k, v) for k, v in sorted(NAMES.items()))
open('dispatcher_clean.lua','w').write(clean2)
open('names_lua.txt','w').write(opnames)
print("ветвей:", len(branches), "| мёртвых:", len(DEAD), "| опкодов:", len(NAMES))
