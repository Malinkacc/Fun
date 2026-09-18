# Таблица опкодов интерпретатора

Оригинальный диспетчер реализует **116 опкодов из 256** (остальные 140 номеров не используются — балласт;
коды 0–3 отсутствуют вовсе). Обозначения: `regs` — таблица регистров (0-based), `K[i]` — константа пула
(операнд D — индекс константы, 0-based, т.е. K[D+1] внутри Lua-таблицы), `upvals` — upvalue-боксы,
`env` — окружение (`getfenv()` либо `_G`), `pc` — счётчик инструкций.

| # | Имя | Что делает | Примечания |
|---|-----|------------|------------|
| 4 | `SETTABLE` | regs[A][regs[B]] = regs[C] |  |
| 8 | `MULK` | regs[A] = regs[B] * K[D+1] |  |
| 9 | `DEADLOCK` | while true do end  -- ЛОВУШКА: вечный цикл | **ловушка: бесконечный цикл** |
| 10 | `LSHIFT` | regs[A] = lshift(regs[B], regs[C]) |  |
| 14 | `GETUPVAL` | regs[A] = upval[B]  (открытый upvalue: regs создателя) |  |
| 15 | `APPEND` | regs[A][#regs[A]+1] = regs[B] |  |
| 16 | `LOADNIL` | regs[A] = nil | дубль опкода 121 |
| 17 | `BOR` | regs[A] = bor(regs[B], regs[C]) |  |
| 24 | `CONCAT_TABLE` | regs[A] = table.concat(regs[B], regs[C]) |  |
| 26 | `SETTABLEKS` | regs[A][K[D+1]] = regs[B] |  |
| 27 | `JUMPIFEQK` | if regs[A] == K[D+1] then pc+1 |  |
| 29 | `GETTABLE` | regs[A] = regs[B][regs[C]] |  |
| 31 | `LOADK` | regs[A] = K[D+1] |  |
| 33 | `MUL` | regs[A] = regs[B] * regs[C] |  |
| 39 | `CONCAT_STR` | regs[A] = tostring(regs[B])..tostring(regs[C]) |  |
| 41 | `JUMPBACK` | pc = pc - D   (прыжок назад) |  |
| 43 | `NOOP_FALSE` | regs[A] = (#tostring(type(nil))==4) -> всегда false | константа: всегда false |
| 44 | `NOOP` | заглушка (no-op) | **заглушка / мёртвый код** |
| 45 | `ERROR` | error(regs[A]) |  |
| 46 | `MATH_M2` | regs[A] = math.M2(regs[B])   <НЕТ в стандартной библиотеке> | **зовёт несуществующую math.M2()** |
| 48 | `FLOOR` | regs[A] = floor(regs[B]) |  |
| 49 | `PACK_REGS` | regs[A] = {regs[B]..regs[C]} |  |
| 50 | `CALL2` | вызов regs[A](regs[A+1],regs[A+2]), результаты в regs[A+3..] |  |
| 51 | `UNM` | regs[A] = -regs[B] |  |
| 52 | `MATH_H2` | regs[A] = math.h2(regs[B])   <НЕТ в стандартной библиотеке> | **зовёт несуществующую math.h2()** |
| 59 | `DIVK` | regs[A] = regs[B] / K[D+1] |  |
| 60 | `JUMPIFNOT` | if not regs[A] then pc+D |  |
| 61 | `JUMPIF` | if regs[A] then pc+D |  |
| 66 | `GE` | regs[A] = (regs[B] >= regs[C]) |  |
| 68 | `SPLIT` | regs[A] = split(regs[B], regs[C]) | **зовёт несуществующую string.m2()** |
| 72 | `INDEX_OF` | regs[A] = индекс regs[C] в таблице regs[B] |  |
| 73 | `LROTATE` | regs[A] = lrotate(regs[B], regs[C]) |  |
| 80 | `GETMETATABLE` | regs[A] = getmetatable(regs[B]) |  |
| 81 | `NOOP` | заглушка (no-op) | **заглушка / мёртвый код**; дубль опкода 44 |
| 83 | `EQ` | regs[A] = (regs[B] == regs[C]) |  |
| 84 | `RROTATE` | regs[A] = rrotate(regs[B], regs[C]) |  |
| 85 | `STR_C2` | regs[A] = string.C2(regs[B], regs[C])  <НЕСТАНДАРТНОЕ имя> | **зовёт несуществующую string.C2()** |
| 86 | `NOOP` | заглушка (no-op) | **заглушка / мёртвый код** |
| 87 | `SUB_AND_JUMP` | regs[A] = regs[A] - regs[A+2]; pc+D   (странная семантика) | подозрительная семантика (затирает regs[A]) |
| 88 | `PACK_INTO` | for i=1..B: regs[A][C+i] = regs[A+i] |  |
| 91 | `MOVE` | regs[A] = regs[B] | дубль опкода 136 |
| 93 | `JUMPNIL_SKIP` | if regs[A+3] ~= nil then regs[A+2]=regs[A+3]; pc+D |  |
| 96 | `NOOP` | заглушка (no-op) | **заглушка / мёртвый код** |
| 99 | `LT` | regs[A] = (regs[B] < regs[C]) |  |
| 100 | `ADD` | regs[A] = regs[B] + regs[C] |  |
| 104 | `SUBK` | regs[A] = regs[B] - K[D+1] |  |
| 106 | `LTK` | regs[A] = (regs[B] < K[D+1]) |  |
| 107 | `POW` | regs[A] = regs[B] ^ regs[C] |  |
| 109 | `TONUMBER` | regs[A] = tonumber(regs[B]) |  |
| 112 | `MATH_Y2` | regs[A] = math.y2(regs[B], regs[C])   <НЕТ в стандартной библиотеке> | **зовёт несуществующую math.y2()** |
| 113 | `MOD` | regs[A] = regs[B] % regs[C] |  |
| 116 | `NOT` | regs[A] = not regs[B] |  |
| 117 | `SIGN` | regs[A] = sign(regs[B]) |  |
| 119 | `STR_BYTE` | regs[A] = string.byte(regs[B], regs[C]) |  |
| 121 | `LOADNIL` | regs[A] = nil |  |
| 125 | `IDIV` | regs[A] = floor(regs[B] / regs[C]) |  |
| 128 | `NE` | regs[A] = (regs[B] ~= regs[C]) |  |
| 132 | `APPEND_TO` | regs[B][#regs[B]+1] = regs[C] |  |
| 133 | `GETGLOBAL` | regs[A] = env[K[D+1]]  (глобальная переменная) | доступ к глобальным переменным |
| 134 | `TOSTRING` | regs[A] = tostring(regs[B]) |  |
| 136 | `MOVE` | regs[A] = regs[B] |  |
| 138 | `RETURN` | return regs[A] .. regs[A+B-1] |  |
| 141 | `SETTABLE` | regs[A][regs[B]] = regs[C]   (копия опкода 4) | дубль опкода 4 |
| 144 | `LEN` | regs[A] = #regs[B] |  |
| 145 | `BAND` | regs[A] = band(regs[B], regs[C]) |  |
| 146 | `NOOP` | заглушка (no-op) | **заглушка / мёртвый код** |
| 148 | `GETTABLE` | regs[A] = regs[B][regs[C]]   (копия опкода 29) | дубль опкода 29 |
| 150 | `SUB_STRING` | regs[A] = string.sub(regs[B], regs[C], regs[C+1]) |  |
| 151 | `LEK` | regs[A] = (regs[B] <= K[D+1]) |  |
| 153 | `LOADBOOL_B` | regs[A] = (B ~= 0)  -- bool из операнда |  |
| 155 | `DIV` | regs[A] = regs[B] / regs[C] |  |
| 156 | `SWAP` | regs[A], regs[B] = regs[B], regs[A] |  |
| 157 | `SETGLOBAL` | env[K[D+1]] = regs[A]  (запись в глобальную) | доступ к глобальным переменным |
| 160 | `MODK` | regs[A] = regs[B] % K[D+1] |  |
| 161 | `SETUPVAL` | upval[B] = regs[A] |  |
| 162 | `BXOR` | regs[A] = bxor(regs[B], regs[C]) |  |
| 163 | `STR_W1` | regs[A] = string.W1(regs[B])   <НЕСТАНДАРТНОЕ имя> | **зовёт несуществующую string.W1()** |
| 164 | `NOOP` | заглушка (no-op) | **заглушка / мёртвый код** |
| 165 | `SETTABLEKS` | regs[A][K[D+1]] = regs[B]   (копия опкода 26) | дубль опкода 26 |
| 166 | `RSHIFT` | regs[A] = rshift(regs[B], regs[C]) |  |
| 170 | `NOOP` | заглушка (no-op) | **заглушка / мёртвый код** |
| 172 | `ASSERT` | assert(regs[A], regs[B]) |  |
| 174 | `TAILCALL` | return regs[A](regs[A+1]..regs[A+B-1])  (хвостовой вызов) |  |
| 176 | `STR_S1` | regs[A] = string.S1(regs[B], regs[C])   <НЕСТАНДАРТНОЕ имя> | **зовёт несуществующую string.S1()** |
| 178 | `NOOP` | заглушка (no-op) | **заглушка / мёртвый код** |
| 179 | `EQK` | regs[A] = (regs[B] == K[D+1]) |  |
| 182 | `NOOP_TRUE` | regs[A] = (#tostring(type(nil))==3) -> всегда true | константа: всегда true |
| 183 | `GETTABLEKS` | regs[A] = regs[B][K[D+1]] |  |
| 185 | `SUB` | regs[A] = regs[B] - regs[C] |  |
| 188 | `CALL` | вызов regs[A](regs[A+1]..regs[A+B-1]) |  |
| 189 | `STR_V1` | regs[A] = string.V1(regs[B])   <НЕСТАНДАРТНОЕ имя> | **зовёт несуществующую string.V1()** |
| 191 | `GT` | regs[A] = (regs[B] > regs[C]) |  |
| 194 | `GETTABLE_N` | regs[A+1] = regs[B]; regs[A] = regs[B][regs[C]] |  |
| 196 | `LEN` | regs[A] = #regs[B]   (копия опкода 144) | дубль опкода 144 |
| 200 | `UNPACK_REGS` | распаковать таблицу regs[B][1..D] в regs[A..] |  |
| 203 | `CLEAR_REGS` | regs[A .. A+B] = nil |  |
| 205 | `NOOP` | заглушка (no-op) | **заглушка / мёртвый код** |
| 207 | `FORLOOP` | числовой for: шаг/сравнение/условный прыжок pc+D |  |
| 208 | `ADDK` | regs[A] = regs[B] + K[D+1] |  |
| 209 | `GETTABLEKS` | regs[A] = regs[B][K[D+1]]   (копия опкода 183) | дубль опкода 183 |
| 213 | `NOTNOT` | regs[A] = not not regs[B] |  |
| 214 | `CLOSURE` | regs[A] = замыкание(proto[D]) с захватом upvalue | захват ссылки на таблицу регистров родителя |
| 216 | `JUMP` | pc = pc + D   (прыжок вперёд) |  |
| 219 | `AND` | regs[A] = regs[B] and regs[C] |  |
| 225 | `TYPE` | regs[A] = type(regs[B]) |  |
| 231 | `REMOVE` | удалить regs[B][regs[C]] со сдвигом (table.remove-подобное) |  |
| 234 | `LOADINT_B` | regs[A] = знаковый байт B (-128..127) |  |
| 237 | `VARARG` | regs[A] = varargs (или таблица varargs) |  |
| 242 | `BNOT` | regs[A] = bnot(regs[B]) |  |
| 243 | `MATH_Z2` | regs[A] = math.z2(regs[B], regs[C])   <НЕТ в стандартной библиотеке> | **зовёт несуществующую math.z2()** |
| 244 | `MATH_K2` | regs[A] = math.k2(regs[B])   <НЕТ в стандартной библиотеке> | **зовёт несуществующую math.k2()** |
| 245 | `NEWTABLE` | regs[A] = {} |  |
| 248 | `OR` | regs[A] = regs[B] or regs[C] |  |
| 252 | `SETMETATABLE` | setmetatable(regs[A], regs[B]) |  |
| 253 | `CHAR` | regs[A] = string.char(regs[B]..regs[C]) |  |
| 255 | `LE` | regs[A] = (regs[B] <= regs[C]) |  |

## Сводка

* **Мёртвые заглушки (9):** 44, 81, 86, 96, 146, 164, 170, 178, 205 — не делают ничего.
* **Полные дубли (8 пар):** 4 = 141, 26 = 165, 121 = 16, 136 = 91, 148 = 29, 183 = 209, 196 = 144, 44 = 81.
* **Ловушка:** опкод 9 — `while true do end`; попав в исполнение, намертво вешает интерпретатор.
* **Несуществующие функции окружения:** 46 (`math.M2`), 52 (`math.h2`), 68 (`string.m2` — используется в «split»),
  85 (`string.C2`), 112 (`math.y2`), 163 (`string.W1`), 176 (`string.S1`), 189 (`string.V1`), 243 (`math.z2`),
  244 (`math.k2`). Ни в стандартном Lua, ни в Luau таких имён нет (проверено запуском).
* **Неизвестные номера опкодов игнорируются** — цепочка `if/elseif` без `else` (проверено: код 250 ничего не делает,
  исполнение продолжается). Повреждённый байткод «пройдёт» молча.

Поведение опкодов проверено исполнением синтетических чанков через оригинальный и деобфусцированный интерпретатор;
результаты совпали. Имена в таблице соответствуют деобфусцированному коду (`deobfuscated/vm.lua`).