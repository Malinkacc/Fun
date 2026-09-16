-- Test script for NZL Obfuscator level=insane

local function add(a, b) -- @vm
    return a + b
end

local function factorial(n) -- @vm
    if n <= 1 then
        return 1
    end
    return n * factorial(n - 1)
end

local function greet(name)
    return "Hello, " .. name .. "!"
end

print("[add]       =", add(10, 20))
print("[factorial] =", factorial(5))
print("[greet]     =", greet("World"))
print("=== ALL TESTS PASSED ===")
