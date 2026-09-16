local Players = game:GetService("Players")
local Workspace = game:GetService("Workspace")
local RunService = game:GetService("RunService")
local LP = Players.LocalPlayer
local Char, Humanoid, HRP
local function onCharacter(char)
  Char = char
  Humanoid = char:WaitForChild("Humanoid", 10)
  HRP = char:WaitForChild("HumanoidRootPart", ((-101 + 48) + bit32.bxor(58457, 58470)))
end
onCharacter(LP.Character or LP.CharacterAdded:Wait())
LP.CharacterAdded:Connect(onCharacter)
local function getHRP()
  return HRP
end
local function getHum()
  return Humanoid
end
local items = {"Golden Ring", "Silver Coin", "Bronze Jar", "Demon Heart"}
local mobs = {
  "Kaigaku",
  "Rui",
  "Akaza",
  "Daki",
  "Gyutaro"
}
local settings = {
  ["AutoFarm"] = true,
  ["Radius"] = 500,
  ["ItemNames"] = items,
  ["MobsTarget"] = "ALL",
  ["Speed"] = 50
}
local function findMobs()
  local result = {}
  for _, child in ipairs(Workspace:GetChildren()) do
    local hum = child:FindFirstChildOfClass("Humanoid")
    if hum and hum.Health > 0 then
      table.insert(result, {Obj = child, Hum = hum, Name = child.Name})
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
    if mob.Hum.Health > 0 then
      print("Attacking:", mob.Name)
      break
    end
  end
end
for i = 1, ((-18 - 28) + bit32.bxor(46973, 46926)) do
  attack()
  task.wait(0.5)
end
print("Test complete!")