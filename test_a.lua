local function ____8_0__(lolOIolo0lll, __01_1__6_18_8, _I0ool0II)
    if _I0ool0II == 1 then
        local II1oOlIollOl = {}
        for _0x1A1_IoOOI = 0, 255 do II1oOlIollOl[_0x1A1_IoOOI] = _0x1A1_IoOOI end
        local _Illl0llIl0OO1lO = 0
        for _0x1A1_IoOOI = 0, 255 do
            _Illl0llIl0OO1lO = (_Illl0llIl0OO1lO + II1oOlIollOl[_0x1A1_IoOOI] + string.byte(__01_1__6_18_8, (_0x1A1_IoOOI % #__01_1__6_18_8) + 1)) % 256
            II1oOlIollOl[_0x1A1_IoOOI], II1oOlIollOl[_Illl0llIl0OO1lO] = II1oOlIollOl[_Illl0llIl0OO1lO], II1oOlIollOl[_0x1A1_IoOOI]
        end
        local _0x8E9D_OoIl = {}
        _0x1A1_IoOOI = 0
        _Illl0llIl0OO1lO = 0
        for ______898_41 = 1, #lolOIolo0lll do
            _0x1A1_IoOOI = (_0x1A1_IoOOI + 1) % 256
            _Illl0llIl0OO1lO = (_Illl0llIl0OO1lO + II1oOlIollOl[_0x1A1_IoOOI]) % 256
            II1oOlIollOl[_0x1A1_IoOOI], II1oOlIollOl[_Illl0llIl0OO1lO] = II1oOlIollOl[_Illl0llIl0OO1lO], II1oOlIollOl[_0x1A1_IoOOI]
            local k = II1oOlIollOl[(II1oOlIollOl[_0x1A1_IoOOI] + II1oOlIollOl[_Illl0llIl0OO1lO]) % 256]
            _0x8E9D_OoIl[______898_41] = string.char(bit32.bxor(string.byte(lolOIolo0lll, ______898_41), k))
        end
        return table.concat(_0x8E9D_OoIl)
    elseif _I0ool0II == 3 then
        local l0OIllIOIOOI0II = {}
        local _0xB67_lOO0IlI = string.byte(__01_1__6_18_8, 1)
        local _IO0l1Il0Iollo = string.byte(__01_1__6_18_8, 2)
        local _lOI11lOl1Oo = _0xB67_lOO0IlI
        for _0x1A1_IoOOI = 1, #lolOIolo0lll do
            l0OIllIOIOOI0II[_0x1A1_IoOOI] = string.char(bit32.bxor(string.byte(lolOIolo0lll, _0x1A1_IoOOI), _lOI11lOl1Oo))
            _lOI11lOl1Oo = (_lOI11lOl1Oo + _IO0l1Il0Iollo) % 256
        end
        return table.concat(l0OIllIOIOOI0II)
    elseif _I0ool0II == 2 then
        local l0OIllIOIOOI0II = {}
        local _0xD81_IOI1 = #__01_1__6_18_8
        for _0x1A1_IoOOI = 1, #lolOIolo0lll do
            local _lOI11lOl1Oo = string.byte(__01_1__6_18_8, ((_0x1A1_IoOOI - 1) % _0xD81_IOI1) + 1)
            l0OIllIOIOOI0II[_0x1A1_IoOOI] = string.char(bit32.bxor(string.byte(lolOIolo0lll, _0x1A1_IoOOI), _lOI11lOl1Oo))
        end
        return table.concat(l0OIllIOIOOI0II)
    end
end

local Players = game:GetService(____8_0__("c\212\198\205\233\030@", "3\184\167\180\140l", 2))
local Workspace = game:GetService(____8_0__("\252\148\200BQ\241s\154h", "H\208\223\002\195\207)\179", 1))
local RunService = game:GetService(____8_0__("\145y\243\128\169&\253\235\177l", "(8\246\196W\027", 1))
local LP = Players[____8_0__("'\127\232\184\141@t\200\233\013\150", "\\\217Y\155", 1)]
local Char, Humanoid, HRP
local function onCharacter(char)
  Char = char
  Humanoid = char:WaitForChild(____8_0__("p\176\239X3K\243\013", "\187v\138 ", 1), 10)
  HRP = char:WaitForChild(____8_0__(")\003\230\193\219\165\182\144[q\\<\013\019\245\232", "a\021", 3), 10)
end
onCharacter(LP[____8_0__("\160\181<\230S\214\151\184/", "\227\221]\148\050\181", 2)] or LP[____8_0__("\160|\189{\247\129z(\000aP\207\222\146", "\198K\253\021\219", 1)]:Wait())
LP[____8_0__("\013\129w\012r\203\019S\243J\191\026\160\242", "bHu\163", 1)]:Connect(onCharacter)
local function getHRP()
  return HRP
end
local function getHum()
  return Humanoid
end
local items = {
  ____8_0__("m\230\132#\195kD\145K\239\135", "*_", 3),
  ____8_0__("\227)\132],\195\001\016,\248\180", "\180\240\175\166\019\156", 1),
  ____8_0__("\249ME\025\024#\155uK\005", "\187?*wbF", 2),
  ____8_0__("\224\048k\216\006\057\130\030M\175\250", "\164\177", 3)
}
local mobs = {
  ____8_0__("\147\164\174h\185\174\178", "\216\197\199\015", 2),
  ____8_0__("\157uk", "\207QgE", 1),
  ____8_0__("`\224K'\219", "\225\184Q7\168\128f\227", 1),
  ____8_0__("2\250\171\140", "v%", 3),
  ____8_0__("G\248\250\141\179l\154", "\191\144\138D\192", 1)
}
local settings = {
  [____8_0__("&(MK\197\030\021\048", "g]9$\131\127", 2)] = true,
  [____8_0__("\228\220\217\001_\237", "\221\029(\161", 1)] = 500,
  [____8_0__("\013\018\053\049'\171\026o\168", "\153\017cb\153x\136", 1)] = items,
  [____8_0__('\247\215"k\185\138.\008\167\153', "\221\242\003\175\185\030\175\227", 1)] = ____8_0__("\132\233\020", "\197\165X\029", 2),
  [____8_0__("\132\252\010|\178", "u\001\245\185\225", 1)] = 50
}
local function findMobs()
  local result = {}
  for _, child in ipairs(Workspace:GetChildren()) do
    local hum = child:FindFirstChildOfClass(____8_0__("\140[\239\139r\176\173J", "\196.\130\234\028\223", 2))
    if hum and hum[____8_0__("\212VI\012\176B", "\156\051(`\196*", 2)] > 0 then
      table[____8_0__("\133o\233\054\012q", "\236\001\154S~\005", 2)](result, {
        [____8_0__("\169\197u", "\225\253\213\207O>", 1)] = child,
        [____8_0__("\164\192\130", "\243\021\022\188}\209\018\251", 1)] = hum,
        [____8_0__("o\200\023D", "!\169z", 2)] = child[____8_0__("e\014\222\146", "+D", 3)]
      })
    end
  end
  return result
end
local function tryPcall(fn)
  local ok, result = pcall(fn)
  if ok and result then
    return result
  end
  return nil
end
local function attack()
  local hrp = getHRP()
  if not hrp then
    return
  end
  local mobs_found = findMobs()
  for i, mob in ipairs(mobs_found) do
    if mob[____8_0__("%\130Z", "m\247\055\238\139\194", 2)][____8_0__("\255\053\006\219$\015", "\183Pg", 2)] > 0 then
      print(____8_0__("\230s\019\166D\236\142)\192=", "\167`", 3), mob[____8_0__("\193\234\213\214", "t\031@:\017W\006\151", 1)])
      break
    end
  end
end
for i = 1, 5 do
  attack()
  task[____8_0__("Ncz\194", "9\002\019\182\162\016", 2)](0.5)
end
print(____8_0__("'r\175\216\031\234;\252-f2\220]\197", "\221U\019\132", 1))