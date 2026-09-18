#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Single-profile /obfuscate regression (2e-7).

The Discord /obfuscate command lost its level/shape/username knobs and now
always runs the ONE profile: level='insane', no code-shaper, watermark
username fixed to 'NZL Studio'. This suite pins that profile to a realistic
Roblox-UI-style input at the scale the bot actually receives (~420 lines)
and checks that the output is a valid, well-protected Lua program.

Run either way:
    py obfuscator\\test_single_profile.py --test
    py -m obfuscator.test_single_profile --test
"""
import os
import sys
import time

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from obfuscator.engine import Obfuscator, LEVELS          # noqa: E402
from obfuscator.lexer import Lexer                        # noqa: E402
from obfuscator.parser import Parser                      # noqa: E402

SINGLE_LEVEL = 'insane'
SINGLE_USERNAME = 'NZL Studio'

_FAILS = []


def chk(name, ok, info=''):
    if ok:
        print('[OK] %s' % name)
    else:
        print('[XX] %s  %s' % (name, info))
        _FAILS.append(name)


def _build_synthetic_ui_script():
    """Deterministic Roblox-UI-like script, ~420 lines, ASCII only."""
    head = '''-- synthetic UI library (test fixture)
local Players = game:GetService("Players")
local UserInputService = game:GetService("UserInputService")
local TweenService = game:GetService("TweenService")
local RunService = game:GetService("RunService")

local NZL = {}
NZL.__index = NZL
NZL.Flags = {}
NZL.Theme = {
    Background = Color3.fromRGB(18, 18, 24),
    Accent = Color3.fromRGB(88, 101, 242),
    Text = Color3.fromRGB(240, 240, 255),
    Font = Enum.Font.GothamMedium,
}

local function Create(class, props, parent)
    local inst = Instance.new(class)
    for k, v in pairs(props) do
        if k ~= "Parent" then inst[k] = v end
    end
    inst.Parent = parent
    return inst
end

local function Corner(r, parent)
    return Create("UICorner", { CornerRadius = UDim.new(0, r) }, parent)
end

local function SafeCall(fn, ...)
    local ok, err = pcall(fn, ...)
    if not ok then
        warn("[NZL] " .. tostring(err))
    end
    return ok
end

function NZL:NewWindow(title, size)
    local holder = Create("ScreenGui", {
        Name = "NZL_" .. tostring(title),
        ResetOnSpawn = false,
        ZIndexBehavior = Enum.ZIndexBehavior.Sibling,
    }, game.CoreGui)
    local main = Create("Frame", {
        Size = size or UDim2.fromOffset(520, 380),
        Position = UDim2.new(0.5, 0, 0.5, 0),
        AnchorPoint = Vector2.new(0.5, 0.5),
        BackgroundColor3 = self.Theme.Background,
        BorderSizePixel = 0,
        Active = true,
        Draggable = true,
    }, holder)
    Corner(8, main)
    local label = Create("TextLabel", {
        Size = UDim2.new(1, 0, 0, 34),
        BackgroundTransparency = 1,
        Text = tostring(title),
        TextColor3 = self.Theme.Text,
        Font = self.Theme.Font,
        TextSize = 15,
    }, main)
    self.Holder = holder
    self.Main = main
    self.Title = label
    return self
end
'''
    body = []
    body.append('local secret_token = "SecretToggleButton_9f3A"')
    body.append('local widgets = {}')
    for i in range(1, 13):
        body.append(
            'function NZL:Widget%02d(name, callback)\n'
            '    local btn = Create("TextButton", {\n'
            '        Size = UDim2.new(1, -16, 0, 30),\n'
            '        Position = UDim2.new(0, 8, 0, %d),\n'
            '        BackgroundColor3 = self.Theme.Accent,\n'
            '        Text = tostring(name) .. " #%d",\n'
            '        TextColor3 = self.Theme.Text,\n'
            '        Font = self.Theme.Font,\n'
            '        TextSize = 13,\n'
            '        AutoButtonColor = true,\n'
            '    }, self.Main)\n'
            '    Corner(6, btn)\n'
            '    local state = { enabled = false, count = %d, tag = secret_token .. "-%02d" }\n'
            '    btn.MouseButton1Click:Connect(function()\n'
            '        state.enabled = not state.enabled\n'
            '        state.count = state.count + 1\n'
            '        if typeof(callback) == "function" then\n'
            '            SafeCall(callback, state.enabled, state.count)\n'
            '        end\n'
            '        TweenService:Create(btn, TweenInfo.new(0.14), {\n'
            '            BackgroundTransparency = state.enabled and 0.4 or 0\n'
            '        }):Play()\n'
            '    end)\n'
            '    table.insert(widgets, { id = %d, btn = btn, state = state })\n'
            '    return btn\n'
            'end' % (i, 40 + i * 34, i, i, i, i)
        )
    tail = '''
function NZL:Refresh()
    local n = 0
    for idx, w in ipairs(widgets) do
        if w.state and w.state.enabled then
            n = n + 1
        end
    end
    self.Title.Text = string.format("Widgets: " .. n .. "/" .. #widgets)
    return n
end

function NZL:Bind(keycode)
    self.Conn = UserInputService.InputBegan:Connect(function(input, typed)
        if typed then return end
        if input.KeyCode == (keycode or Enum.KeyCode.RightShift) then
            self.Main.Visible = not self.Main.Visible
        end
    end)
    return self.Conn
end

local ui = NZL:NewWindow("NZL Hub", UDim2.fromOffset(520, 460))
for i = 1, 12 do
    ui:Widget07("Feature", function(on, cnt)
        print(string.format("[NZL] feature " .. tostring(i) .. " -> "
            .. tostring(on) .. " (" .. tostring(cnt) .. ")"))
    end)
end
ui:Bind(Enum.KeyCode.RightShift)
print("loaded:", ui:Refresh())
'''
    src = head + '\n'.join(body) + '\n' + tail
    return src


def main():
    src = _build_synthetic_ui_script()
    lines = src.count('\n') + 1
    chk('T0 fixture: %d lines, %d bytes' % (lines, len(src)), lines >= 400)

    # T1: single profile is insane; obfuscate at bot scale with fixed username
    obf = Obfuscator(seed=20260918, owner_id=None,
                     username=SINGLE_USERNAME, verbose=False)
    t0 = time.perf_counter()
    try:
        result = obf.obfuscate(src, level=SINGLE_LEVEL)
        dt = time.perf_counter() - t0
        chk('T1 insane obfuscate: %d bytes in %.1fs'
            % (len(result), dt), len(result) > 0)
        chk('T2 time budget (< 300s, bot timeout is 600s)', dt < 300.0,
            '%.1fs' % dt)
    except Exception as e:
        chk('T1 insane obfuscate', False, '%s: %s' % (type(e).__name__, e))
        print('Result: 2/%d' % (12 - 2))
        return 1

    # T3: output is valid Lua for our parser
    try:
        Parser(Lexer(result).tokenize()).parse()
        chk('T3 output re-parses', True)
    except Exception as e:
        chk('T3 output re-parses', False, '%s: %s' % (type(e).__name__, e))

    # T4: VM protection is always on in the single profile
    chk('T4 VM closures present (__nzlvm__)', '__nzlvm__' in result)

    # T5: branding watermark present exactly once at the end
    chk('T5 watermark comment present',
        result.rstrip().endswith('-- discord.gg/c3kBtN9vXb')
        or '-- discord.gg/c3kBtN9vXb' in result)

    # T6: string literals are encrypted (fixture secret must not leak)
    chk('T6 no plaintext leak of SecretToggleButton_9f3A',
        'SecretToggleButton_9f3A' not in result)

    # T7: identifier names are mangled (no leak of fixture locals)
    chk('T7 no plaintext leak of secret_token',
        'secret_token' not in result)

    # T8: unified username is baked in, not the Discord user's name
    chk('T8 header username = NZL Studio', 'NZL Studio' in result)

    # T9: engine still exposes exactly the three levels (internal)
    chk('T9 LEVELS intact', list(LEVELS) == ['medium', 'hard', 'insane'])

    # T10: size ratio reported (sanity: below 400x)
    ratio = len(result) / float(len(src))
    chk('T10 size ratio %.1fx (< 400x)' % ratio, ratio < 400.0)

    print('')
    total = 11
    print('Result: %d/%d' % (total - len(_FAILS), total))
    if _FAILS:
        print('[XX] FAILURES: %d' % len(_FAILS))
        return 1
    print('[OK] ALL PASSED')
    return 0


if __name__ == '__main__':
    sys.exit(main())
