local Players = game:GetService("Players")
local Workspace = game:GetService("Workspace")
local RunService = game:GetService("RunService")
local _1llIlOl0 = Players.LocalPlayer
local _lllOIOl, Ilo1II0O1IlOll0l, I1IoOl0lO1Oll
local function ll1lll01(lOIOOl1lIOlIo01)
  _lllOIOl = lOIOOl1lIOlIo01
  Ilo1II0O1IlOll0l = lOIOOl1lIOlIo01:WaitForChild("Humanoid", 10)
  I1IoOl0lO1Oll = lOIOOl1lIOlIo01:WaitForChild("HumanoidRootPart", 10)
end
ll1lll01(_1llIlOl0.Character or _1llIlOl0.CharacterAdded:Wait())
_1llIlOl0.CharacterAdded:Connect(ll1lll01)
local function _OIlIO01llOlo0oI()
  return I1IoOl0lO1Oll
end
local function _lOO100OlIOo()
  return Ilo1II0O1IlOll0l
end
local _lII0l00o = {"Golden Ring", "Silver Coin", "Bronze Jar", "Demon Heart"}
local IOIlO1Ol10IoI1OI = {
  "Kaigaku",
  "Rui",
  "Akaza",
  "Daki",
  "Gyutaro"
}
local _1OlIOIOOIOoIlO1 = {
  ["AutoFarm"] = true,
  ["Radius"] = 500,
  ["ItemNames"] = _lII0l00o,
  ["MobsTarget"] = "ALL",
  ["Speed"] = 50
}
local function _lllolOIIoO()
  local IO0lOl10Oo = {}
  for IllllOIOllIlIllI, _Ol1olOIolo0l in ipairs(Workspace:GetChildren()) do
    local _0O00oIlI = _Ol1olOIolo0l:FindFirstChildOfClass("Humanoid")
    if _0O00oIlI and _0O00oIlI.Health > 0 then
      table.insert(IO0lOl10Oo, {
        Obj = _Ol1olOIolo0l,
        Hum = _0O00oIlI,
        Name = _Ol1olOIolo0l.Name
      })
    end
  end
  return IO0lOl10Oo
end
local function lOllllOoI0I1ol(IOlIOIllI)
  local Iol0II0I01o10O, _l1lIOIOIIoOOII = pcall(IOlIOIllI)
  if Iol0II0I01o10O and _l1lIOIOIIoOOII then
    return _l1lIOIOIIoOOII
  end
  return nil
end
local function _Illl0llIl0OO1lO()
  local I0I1oOlIoll = _OIlIO01llOlo0oI()
  if not I0I1oOlIoll then
    return
  end
  local _O1IOllO1IoO1OIO = _lllolOIIoO()
  for llI1llOI11lO, l1Oo1Il01II in ipairs(_O1IOllO1IoO1OIO) do
    if l1Oo1Il01II.Hum.Health > 0 then
      print("Attacking:", l1Oo1Il01II.Name)
      break
    end
  end
end
for _1IoO0OIllIOI = 1, 5 do
  _Illl0llIl0OO1lO()
  task.wait(0.5)
end
print("Test complete!")