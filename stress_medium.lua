--[[⁠​‌​​‌‌‌​‍​‌​‌‌​‌​‍​‌​​‌‌​​‍​​‌‌‌​‌​‍​​‌‌​‌​‌‍​​‌‌‌​​​‍​​‌‌​​‌​‍​​‌‌‌​​​‍​​‌‌​​‌​‍​​‌‌​​​‌‍​​‌‌​​​‌‍​​‌‌​​​​‍​​‌‌​‌‌‌‍​​‌‌​​​​‍​​‌‌​‌‌​‍​​‌‌​‌​‌‍​​‌‌​‌‌​‍​​‌‌‌​​​‍​​‌‌​​‌‌‍​​‌‌‌​​‌‍​​‌‌​‌‌‌‍​​‌‌​​​‌‍​​‌‌‌​‌​‍​‌​​​​​‌‍​‌​​​​‌​‍​​‌‌​​​​‍​‌​​​‌‌​‍​​‌‌​‌​​‍​​‌‌‌​​​‍​​‌‌​‌​‌‍​​‌‌‌​​​‍﻿
╔═══════════════════════════════════════╗
║   NZL Studio Obfuscator v1.0                  ║
║   Discord: discord.gg/c3kBtN9vXb       ║
║   Build: AB0F4858                      ║
║   Owner: 582821107065683971            ║
╚═══════════════════════════════════════╝
]]

--⁠​‌​​‌‌‌​‍​‌​‌‌​‌​‍​‌​​‌‌​​‍​​‌‌‌​‌​‍​​‌‌​​​‌‍​​‌‌​‌​‌‍​​‌‌​​​​‍​​‌‌​‌‌​‍​‌​​​‌​‌‍​​‌‌​‌​​‍​​‌‌​‌​‌‍​​‌‌‌​​​‍﻿
-- NZL Studio Obfuscator | discord.gg/c3kBtN9vXb
-- Tampering detected → infinite loop
-- while true do end

local _00 = 2056735577 -- 1506E458

-- [env]
local _0x2152_1olI = pcall(function()
    local _0xEBF_o1OI = 76
    if not ("" == "") then while true do end end
    local _0xE6FE_100IOo = game:GetService("Players")
    if not _0xE6FE_100IOo then if (44 + 75) == 119 then while true do end end end
    local _0x2D0_OlIO = not (not true)
    if not (not (not true)) then while true do end end
    local _0x564_OOlI = bit32 and bit32.bxor
    if type(_0x564_OOlI) ~= "function" then if (22 + 15) == 37 then while (1==1) do end end end
    
    if not (#"abc" == 3) then while true do end end
    local _0x544A_1loO = pcall(function()
        for _ = 1, 1 do
            if false then continue end
        end
    end)
    if not _0x544A_1loO then while (1==1) do end end
    local _0xB0B2_lIoOl0oo = Enum and Enum.KeyCode
    if not _0xB0B2_lIoOl0oo then if (87 + 28) == 115 then while true do end end end
    local _0x8703_IOIloO = task and task.wait
    if type(_0x8703_IOIloO) ~= "function" then if (56 + 34) == 90 then while (1==1) do end end end
    local _0x5E6E6_IO1lOo0 = string and string.byte
    if type(_0x5E6E6_IO1lOo0) ~= "function" then while 1 do end end
    local _0x2633_lII1OI1ol = math and math.floor
    if type(_0x2633_lII1OI1ol) ~= "function" then repeat until false end
    local _0xABFC_ol00 = getgenv and getgenv()
    if not _0xABFC_ol00 then while (1==1) do end end
end)
if not _0x2152_1olI then if (55 + 90) == 145 then while 1 do end end end
-- [string_decryptor]
local function loOO1o10lOll(_OIIOoI0OIlI, I0lIIII0O, _Oool00OlOlOOI0O)
    if _Oool00OlOlOOI0O == 3 then
        local lIO1OI0I = {}
        local I0IIlOool1o0II = string.byte(I0lIIII0O, 1)
        local _1IlOllI1OlOO = string.byte(I0lIIII0O, 2)
        local lOOol1OIl = I0IIlOool1o0II
--[[ NZL:1506E458 ]]
        for _1O0IOoI0oIl0llI = 1, #_OIIOoI0OIlI do
            lIO1OI0I[_1O0IOoI0oIl0llI] = string.char(bit32.bxor(string.byte(_OIIOoI0OIlI, _1O0IOoI0oIl0llI), lOOol1OIl))
            lOOol1OIl = (lOOol1OIl + _1IlOllI1OlOO) % 256
        end
        return table.concat(lIO1OI0I)
    elseif _Oool00OlOlOOI0O == 1 then
        local lOllO00O0 = {}
        for _1O0IOoI0oIl0llI = 0, 255 do lOllO00O0[_1O0IOoI0oIl0llI] = _1O0IOoI0oIl0llI end
        local IO0ll1OIo = 0
        for _1O0IOoI0oIl0llI = 0, 255 do
            IO0ll1OIo = (IO0ll1OIo + lOllO00O0[_1O0IOoI0oIl0llI] + string.byte(I0lIIII0O, (_1O0IOoI0oIl0llI % #I0lIIII0O) + 1)) % 256
            lOllO00O0[_1O0IOoI0oIl0llI], lOllO00O0[IO0ll1OIo] = lOllO00O0[IO0ll1OIo], lOllO00O0[_1O0IOoI0oIl0llI]
        end
        local lOIIOIIIolllO = {}
        _1O0IOoI0oIl0llI = 0
        IO0ll1OIo = 0
        for IO11IIIOIOOlI = 1, #_OIIOoI0OIlI do
            _1O0IOoI0oIl0llI = (_1O0IOoI0oIl0llI + 1) % 256
            IO0ll1OIo = (IO0ll1OIo + lOllO00O0[_1O0IOoI0oIl0llI]) % 256
            lOllO00O0[_1O0IOoI0oIl0llI], lOllO00O0[IO0ll1OIo] = lOllO00O0[IO0ll1OIo], lOllO00O0[_1O0IOoI0oIl0llI]
            local k = lOllO00O0[(lOllO00O0[_1O0IOoI0oIl0llI] + lOllO00O0[IO0ll1OIo]) % 256]
            lOIIOIIIolllO[IO11IIIOIOOlI] = string.char(bit32.bxor(string.byte(_OIIOoI0OIlI, IO11IIIOIOOlI), k))
        end
        return table.concat(lOIIOIIIolllO)
    elseif _Oool00OlOlOOI0O == 2 then
        local lIO1OI0I = {}
        local lllo0o10IOOIOIIO = #I0lIIII0O
        for _1O0IOoI0oIl0llI = 1, #_OIIOoI0OIlI do
            local lOOol1OIl = string.byte(I0lIIII0O, ((_1O0IOoI0oIl0llI - 1) % lllo0o10IOOIOIIO) + 1)
            lIO1OI0I[_1O0IOoI0oIl0llI] = string.char(bit32.bxor(string.byte(_OIIOoI0OIlI, _1O0IOoI0oIl0llI), lOOol1OIl))
        end
        return table.concat(lIO1OI0I)
    end
end

local Players = game:GetService(loOO1o10lOll("\\29f\\166\\253$\\140\\200", "M\\189", 3))
local Workspace = game:GetService(loOO1o10lOll("\\200\\192{\\221\\\\V\\179b\\147", "\\168s$\\25[\\2", 1))
--⁠​​‌‌​‌​‌‍​​‌‌‌​​​‍​​‌‌​​‌​‍​​‌‌‌​​​‍​​‌‌​​‌​‍​​‌‌​​​‌‍​​‌‌​​​‌‍​​‌‌​​​​‍​​‌‌​‌‌‌‍​​‌‌​​​​‍​​‌‌​‌‌​‍​​‌‌​‌​‌‍​​‌‌​‌‌​‍​​‌‌‌​​​‍​​‌‌​​‌‌‍​​‌‌‌​​‌‍​​‌‌​‌‌‌‍​​‌‌​​​‌‍​​‌‌‌​‌​‍​‌​​​​​‌‍​‌​​​​‌​‍​​‌‌​​​​‍​‌​​​‌‌​‍​​‌‌​‌​​‍​​‌‌‌​​​‍​​‌‌​‌​‌‍​​‌‌‌​​​‍﻿
local RunService = game:GetService(loOO1o10lOll("+77*'+\\15+:\\28", "yBY", 2))
local _0IIll1Ol0IoIoOl = Players[loOO1o10lOll("v\\236U\\145%\\232V\\226O\\149;", ":\\1316\\240I\\184", 2)]
local lOOlIO1lOo0IOl1, lIIO1loO0l, IolOoo100IOol
local function IOllIlIOO(_oI1IlOol)
  lOOlIO1lOo0IOl1 = _oI1IlOol
  lIIO1loO0l = _oI1IlOol:WaitForChild(loOO1o10lOll("\\166#\\n(\\246q?", "\\25\\8^\\195\\172\\255", 1), 10)
  IolOoo100IOol = _oI1IlOol:WaitForChild(loOO1o10lOll("\\241\\136&\\11w\\216\\253\\8\\176\\215\\2348!\\157u\\242", "\\175&\\244m\\2\\208\\196\\160", 1), ((142 + 496) - (715 + (-87))))
end
IOllIlIOO(_0IIll1Ol0IoIoOl[loOO1o10lOll("\\191\\21\\159\\ra\\226v\\230v", "\\252\\129", 3)] or _0IIll1Ol0IoIoOl[loOO1o10lOll("7X\\221\\248F\\156\\1316G\\211\\191\\129\\132\\227", "\\30\\19#\\135", 1)]:Wait())
_0IIll1Ol0IoIoOl[loOO1o10lOll("\\214\\23\\213\\31\\176P\\1784\\23\\174\\163$\\209`", "\\242\\160\\254\\31\\176", 1)]:Connect(IOllIlIOO)
local function _llII1OI1ol()
  return IolOoo100IOol
end
local function lOOO1OOlIlIOI()
  return lIIO1loO0l
end
local IOoO01IoOOo = {
  loOO1o10lOll("\\231\\180B\\173f\\20\\14\\195\\181V\\237", "\\19\\1>7\\203|", 1),
  loOO1o10lOll("P \\17\\243 \\249\\208#.\\11\\151", "O\\191I\\238K", 1),
  loOO1o10lOll("ar\\178\\212\\237\\17qdj\\154", "#\\221", 3),
  loOO1o10lOll("\\226S\\n\\8y\\249\\12b\\188\\232\\175", "\\12\\143l&\\190\\232T", 1)
}
local lol00oIo0OOIOO = {
  loOO1o10lOll("\\2l_\\252\\219\\204U", "[\\210\\200\\216@", 1),
  loOO1o10lOll("8J}", "j\\213", 3),
  loOO1o10lOll("\\214\\208\\6\\158\\216", "\\202\\170>\\20\\29?\\241", 1),
  loOO1o10lOll("i\\134\\2022", "-\\186", 3),
  loOO1o10lOll("'\\212\\177H\\245\\176*", "\\184\\140\\252\\248:N\\131:", 1)
}
local llIoOl0oo = {
  [loOO1o10lOll("\\r\\237\\144_:\\169f\\r", "LL", 3)] = true,
  [loOO1o10lOll("\\235w\\167V}\\166", "\\30\\247\\1970\\234\\167\\137", 1)] = 500,
  [loOO1o10lOll("\\178\\183:\\150\\141>\\150\\166,", "\\251\\195_", 2)] = IOoO01IoOOo,
  [loOO1o10lOll("0\\162\\48\\140\\20\\161\\5}\\182", "\\230\\19w\\22C\\160\\201", 1)] = loOO1o10lOll("\\236\\133\\170", "\\233\\27n\\242\\223\\204\\211", 1),
  [loOO1o10lOll("21\\212\\142\\176", "N\\129\\136}]\\29\\190", 1)] = 50
}
local function _lllIoOOo()
-- "\49\53\48\54\69\52\53\56"
  local IOIlo0I1IIlIo0l = {}
  for IlOIIl0I, _IOIOo101IOlo in ipairs(Workspace:GetChildren()) do
    local IIOlIIl1olIllI = _IOIOo101IOlo:FindFirstChildOfClass(loOO1o10lOll("ZE\\169S&\\232J\\240", "\\174r\\142\\222", 1))
    if IIOlIIl1olIllI and IIOlIIl1olIllI[loOO1o10lOll("\\183\\21\\131\\184\\139\\24", "\\255p\\226\\212", 2)] > 0 then
      table[loOO1o10lOll("\\1\\199-\\201\\144/", "\\135\\220:*\\226\\158\\1673", 1)](IOIlo0I1IIlIo0l, {
        [loOO1o10lOll("t\\137\\241", ";\\176", 3)] = _IOIOo101IOlo,
        [loOO1o10lOll("\\210I\\210", "W'\\12\\29m", 1)] = IIOlIIl1olIllI,
        [loOO1o10lOll("\\227\\2\\5\\206", "\\173ch\\171", 2)] = _IOIOo101IOlo[loOO1o10lOll("y\\n?V", "I\\180J\\19E\\238", 1)]
      })
    end
  end
  return IOIlo0I1IIlIo0l
end
local function l110Ol0OololIl(Io10llOIIIoolIoI)
  local IlIllll0OO, IolOlolO = pcall(Io10llOIIIoolIoI)
  if IlIllll0OO and IolOlolO then
    return IolOlolO
  end
  return nil
end
local function l00O1oOl0O1OlI()
  local I1OIIlIolO0olo1o = _llII1OI1ol()
  if not I1OIIlIolO0olo1o then
    return
  end
  local lOI0OllIlO0 = _lllIoOOo()
  for lI1ol1IO00Il, _Iol01oOl1Il in ipairs(lOI0OllIlO0) do
    if _Iol01oOl1Il[loOO1o10lOll("\\231\\254\\n", "\\175\\220", 3)][loOO1o10lOll("\\176\\221\\199\\185(^", "_\\191pk\\24", 1)] > 0 then
      print(loOO1o10lOll("\\201\\161\\147\\9\\226J\\173\\n\\5^", "(\\167p\\165", 1), _Iol01oOl1Il[loOO1o10lOll("sw\\193:", "O\\145\\230\\208f]U", 1)])
      break
    end
  end
end
for _olIOIIIoI = 1, 5 do
  l00O1oOl0O1OlI()
  task[loOO1o10lOll("\\200\\162\\235\\241", "MlZ\\r\\146}\\195\\177", 1)](0.5)
end
print(loOO1o10lOll("\\198z\\223M\\2300\\143\\0\\138\\235q\\213K\\154", "\\146\\141", 3))
-- discord.gg/c3kBtN9vXb