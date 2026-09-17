-- KILL OLD
pcall(function() if Library and Library.Unload then Library:Unload() end end)
pcall(function()
    for _, g in ipairs(game:GetService("CoreGui"):GetChildren()) do
        if g.Name == "DFStatus" or g.Name == "BossNotify" or g.Name:find("Obsidian") or g.Name:find("Library") then
            g:Destroy()
        end
    end
end)
Library = nil; ThemeManager = nil; SaveManager = nil
task.wait(0.2)

local Library, ThemeManager, SaveManager
local function tryLoad(url)
    local ok, result = pcall(function() return loadstring(game:HttpGet(url))() end)
    if ok and result then return result end
end

Library    = tryLoad('https://raw.githubusercontent.com/deividcomsono/Obsidian/main/Library.lua')
if not Library then warn("[NZL] OBSIDIAN FAILED!") return end

local Players      = game:GetService("Players")
local Workspace    = game:GetService("Workspace")
local RunService   = game:GetService("RunService")
local TweenService = game:GetService("TweenService")
local UIS          = game:GetService("UserInputService")
local LP           = Players.LocalPlayer

local Character, Humanoid, HRP

local function RefreshCharacter(char)
    Character = char
    Humanoid  = char:WaitForChild("Humanoid", 10)
    HRP       = char:WaitForChild("HumanoidRootPart", 10)
end

RefreshCharacter(LP.Character or LP.CharacterAdded:Wait())
LP.CharacterAdded:Connect(RefreshCharacter)

local function GetCharacter() return Character end
local function GetHRP()       return HRP end
local function GetHumanoid()  return Humanoid end

local ITEM_NAMES = {
    "Golden Ring","Gold Jar","Gold Crown","Gold Coin","Gold Goblet",
    "Silver Ring","Silver Jar","Silver Goblet","Silver Coin",
    "Bronze Jar","Bronze Coin","Bronze Goblet",
}

local ITEM_SET = {}
for _, n in ipairs(ITEM_NAMES) do ITEM_SET[n] = true end

local function GetDistance(a, b) return (a - b).Magnitude end

local function GetPartFromObject(obj)
    if not obj then return nil end
    if obj:IsA("BasePart") then return obj end
    if obj:IsA("Model") then
        return obj.PrimaryPart
            or obj:FindFirstChild("HumanoidRootPart")
            or obj:FindFirstChild("Torso")
            or obj:FindFirstChild("UpperTorso")
            or obj:FindFirstChildWhichIsA("BasePart")
    elseif obj:IsA("Tool") then
        return obj:FindFirstChild("Handle") or obj:FindFirstChildWhichIsA("BasePart")
    end
end

local function IsRealMob(obj)
    if not obj or not obj:IsA("Model") then return false end
    if not obj:FindFirstChildOfClass("Humanoid") then return false end
    return true
end

local function notify(text, dur)
    pcall(function() Library:Notify(text, dur or 3) end)
end

local SessionStats = { ItemsCollected=0, MobsKilled=0, BossesKilled=0, StartTime=tick() }

for i = 1, 10 do
    if i % 2 == 0 then
        print("Even: " .. i)
    else
        print("Odd: " .. i)
    end
end

local counter = 0
for name, value in pairs(ITEM_SET) do
    counter = counter + 1
    print(counter, name, tostring(value))
end

notify("NZL Studio Test loaded!", 5)