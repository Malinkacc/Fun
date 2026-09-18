-- Чистая реализация используемых функций bit32 (для сред, где нет bit32: Lua 5.1, Lua 5.4, LuaJIT).
-- Все константные маски записаны как вещественные числа (x.0), чтобы избежать проблем
-- с 32-битной целочисленной арифметикой в некоторых сборках Lua.
local bit32 = _G.bit32   -- если библиотека уже есть (Luau/Lua 5.2-5.3) - используем её
if not bit32 then
  local TWO32 = 4294967296.0
  local MASK16 = 65536.0
  local NIB = {}
  for i = 0, 15 do
    NIB[i] = {}
    for j = 0, 15 do
      local a, b, rA, rO, rX, bit = i + 0.0, j + 0.0, 0.0, 0.0, 0.0, 1.0
      for _ = 1, 4 do
        local x, y = a % 2, b % 2
        if x == 1 and y == 1 then rA = rA + bit end
        if x == 1 or  y == 1 then rO = rO + bit end
        if x ~= y             then rX = rX + bit end
        a, b, bit = (a - x) / 2, (b - y) / 2, bit * 2
      end
      NIB[i][j] = {rA, rO, rX}
    end
  end
  local function bin(a, b, which)
    a, b = a % TWO32, b % TWO32
    local r, mul = 0.0, 1.0
    for _ = 1, 8 do
      local an, bn = a % 16, b % 16
      r = r + NIB[an][bn][which] * mul
      a, b, mul = (a - an) / 16, (b - bn) / 16, mul * 16
    end
    return r
  end
  local function fold(f, a, ...)
    for i = 1, select("#", ...) do a = f(a, select(i, ...)) end
    return a
  end
  local function lshift(a, n)
    if n < 0 or n >= 32 then return 0.0 end
    a = a % TWO32
    local hi, lo = math.floor(a / MASK16), a % MASK16
    return (((hi * 2 ^ n) % MASK16) * MASK16 + lo * 2 ^ n) % TWO32
  end
  local function rshift(a, n)
    if n < 0 or n >= 32 then return 0.0 end
    return math.floor((a % TWO32) / 2 ^ n)
  end
  local function lrotate(a, n)
    n = n % 32
    if n == 0 then return a % TWO32 end
    return (lshift(a, n) + rshift(a, 32 - n)) % TWO32
  end
  bit32 = {
    band = function(a, ...) return fold(function(x, y) return bin(x, y, 1) end, a, ...) end,
    bor  = function(a, ...) return fold(function(x, y) return bin(x, y, 2) end, a, ...) end,
    bxor = function(a, ...) return fold(function(x, y) return bin(x, y, 3) end, a, ...) end,
    bnot = function(a) return 4294967295.0 - (a % TWO32) end,
    lshift = lshift,
    rshift = rshift,
    lrotate = lrotate,
    rrotate = function(a, n) return lrotate(a, (32 - (n % 32)) % 32) end,
  }
end
return bit32
