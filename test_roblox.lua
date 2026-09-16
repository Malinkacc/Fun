-- Простой Roblox тест-скрипт
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")

local player = Players.LocalPlayer
local character = player.Character or player.CharacterAdded:Wait()
local humanoid = character:WaitForChild("Humanoid")

local settings = {
    speed = 50,
    jumpPower = 100,
    infiniteJump = true,
    esp = false,
}

local function applyModifications()
    humanoid.WalkSpeed = settings.speed
    humanoid.JumpPower = settings.jumpPower
    print("Modifications applied: speed=" .. settings.speed)
end

local function toggleESP()
    settings.esp = not settings.esp
    for _, plr in pairs(Players:GetPlayers()) do
        if plr ~= player and plr.Character then
            local head = plr.Character:FindFirstChild("Head")
            if head then
                if settings.esp then
                    local billboard = Instance.new("BillboardGui")
                    billboard.Name = "ESP_" .. plr.Name
                    billboard.Size = UDim2.new(0, 100, 0, 50)
                    billboard.Parent = head
                    
                    local label = Instance.new("TextLabel")
                    label.Text = plr.Name
                    label.TextColor3 = Color3.new(1, 0, 0)
                    label.Size = UDim2.new(1, 0, 1, 0)
                    label.BackgroundTransparency = 1
                    label.Parent = billboard
                else
                    local existing = head:FindFirstChild("ESP_" .. plr.Name)
                    if existing then existing:Destroy() end
                end
            end
        end
    end
end

local function infiniteJump()
    if settings.infiniteJump then
        game:GetService("UserInputService").JumpRequest:Connect(function()
            humanoid:ChangeState(Enum.HumanoidStateType.Jumping)
        end)
    end
end

for i = 1, 10 do
    if i % 2 == 0 then
        print("Even: " .. i)
    else
        print("Odd: " .. i)
    end
end

local counter = 0
for name, value in pairs(settings) do
    counter = counter + 1
    print(counter, name, tostring(value))
end

applyModifications()
infiniteJump()
toggleESP()

print("Script loaded successfully!")
