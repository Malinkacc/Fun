-- NZL VM Test
-- NZL VM Runtime (build 0000002a)
local _0x49EA_lIoll = string.byte
local _0x84B_llO1IoO1OI  = string.sub
local _0x3483_lOI11lOl1 = string.char
local _0x812D_1IIOI1IoO = table.insert
local _0x03241_OOI0II = table.unpack or unpack
local _0x1B67_lOO0I = bit32.bxor

local function _0x026_lOIOlO0l(_0x3E4_oOOOoO0OoI, _0x878F_l1ol1l1O)
    local _0xF529A_ll1l = {}
    for _0xC740_l0lIOoI = 0, 255 do _0xF529A_ll1l[_0xC740_l0lIOoI] = _0xC740_l0lIOoI end
    local _0x017_olo0l = 0
    local _0xC5E40_0Il0I = #_0x878F_l1ol1l1O
    for _0xC740_l0lIOoI = 0, 255 do
        _0x017_olo0l = (_0x017_olo0l + _0xF529A_ll1l[_0xC740_l0lIOoI] + _0x49EA_lIoll(_0x878F_l1ol1l1O, (_0xC740_l0lIOoI % _0xC5E40_0Il0I) + 1)) % 256
        _0xF529A_ll1l[_0xC740_l0lIOoI], _0xF529A_ll1l[_0x017_olo0l] = _0xF529A_ll1l[_0x017_olo0l], _0xF529A_ll1l[_0xC740_l0lIOoI]
    end
    local _0x2447C_Ill00 = {}
    local _0xC740_l0lIOoI2 = 0
    local _0x017_olo0l2 = 0
    for _0xCD7F_l10oI0 = 1, #_0x3E4_oOOOoO0OoI do
        _0xC740_l0lIOoI2 = (_0xC740_l0lIOoI2 + 1) % 256
        _0x017_olo0l2 = (_0x017_olo0l2 + _0xF529A_ll1l[_0xC740_l0lIOoI2]) % 256
        _0xF529A_ll1l[_0xC740_l0lIOoI2], _0xF529A_ll1l[_0x017_olo0l2] = _0xF529A_ll1l[_0x017_olo0l2], _0xF529A_ll1l[_0xC740_l0lIOoI2]
        local _0xED16D_0I0oI = _0xF529A_ll1l[(_0xF529A_ll1l[_0xC740_l0lIOoI2] + _0xF529A_ll1l[_0x017_olo0l2]) % 256]
        _0x2447C_Ill00[_0xCD7F_l10oI0] = _0x3483_lOI11lOl1(_0x1B67_lOO0I(_0x49EA_lIoll(_0x3E4_oOOOoO0OoI, _0xCD7F_l10oI0), _0xED16D_0I0oI))
    end
    return table.concat(_0x2447C_Ill00)
end

-- Read little-endian unsigned 32
local function _nzl_read_u32(_0x18C_OloOO0101, _0x01B7_lIIl)
    local _0xABE8_11lllO = _0x49EA_lIoll(_0x18C_OloOO0101, _0x01B7_lIIl)
    local _0x566F8_O1ll = _0x49EA_lIoll(_0x18C_OloOO0101, _0x01B7_lIIl + 1)
    local _0xB59_IOI1II = _0x49EA_lIoll(_0x18C_OloOO0101, _0x01B7_lIIl + 2)
    local _0x4F30_1oooOII1o = _0x49EA_lIoll(_0x18C_OloOO0101, _0x01B7_lIIl + 3)
    return _0xABE8_11lllO + _0x566F8_O1ll * 256 + _0xB59_IOI1II * 65536 + _0x4F30_1oooOII1o * 16777216, _0x01B7_lIIl + 4
end

local function _nzl_read_i32(_0x18C_OloOO0101, _0x01B7_lIIl)
    local _0xCF2_III1, _0x01B7_lIIl = _nzl_read_u32(_0x18C_OloOO0101, _0x01B7_lIIl)
    if _0xCF2_III1 >= 2147483648 then _0xCF2_III1 = _0xCF2_III1 - 4294967296 end
    return _0xCF2_III1, _0x01B7_lIIl
end

-- Read double (IEEE 754 little-endian, 8 bytes)
local function _nzl_read_double(_0x18C_OloOO0101, _0x01B7_lIIl)
    local _0xABE8_11lllO = _0x49EA_lIoll(_0x18C_OloOO0101, _0x01B7_lIIl)
    local _0x566F8_O1ll = _0x49EA_lIoll(_0x18C_OloOO0101, _0x01B7_lIIl + 1)
    local _0xB59_IOI1II = _0x49EA_lIoll(_0x18C_OloOO0101, _0x01B7_lIIl + 2)
    local _0x4F30_1oooOII1o = _0x49EA_lIoll(_0x18C_OloOO0101, _0x01B7_lIIl + 3)
    local b4 = _0x49EA_lIoll(_0x18C_OloOO0101, _0x01B7_lIIl + 4)
    local b5 = _0x49EA_lIoll(_0x18C_OloOO0101, _0x01B7_lIIl + 5)
    local b6 = _0x49EA_lIoll(_0x18C_OloOO0101, _0x01B7_lIIl + 6)
    local b7 = _0x49EA_lIoll(_0x18C_OloOO0101, _0x01B7_lIIl + 7)
    local sign = 1
    if b7 >= 128 then sign = -1; b7 = b7 - 128 end
    local exp = b7 * 16 + math.floor(b6 / 16)
    local mant = (b6 % 16) * 281474976710656 + b5 * 1099511627776 + b4 * 4294967296
                 + _0x4F30_1oooOII1o * 16777216 + _0xB59_IOI1II * 65536 + _0x566F8_O1ll * 256 + _0xABE8_11lllO
    local val
    if exp == 0 then
        if mant == 0 then val = 0 else val = sign * mant * 2^(-1074) end
    elseif exp == 2047 then
        if mant == 0 then val = sign * math.huge else val = 0/0 end
    else
        val = sign * (1 + mant / 4503599627370496) * 2^(exp - 1023)
    end
    return val, _0x01B7_lIIl + 8
end

local function _0x805DA_1IlOll0(_0x18C_OloOO0101, _0x01B7_lIIl)
    _0x01B7_lIIl = _0x01B7_lIIl or 1
    local _0x474_ollo1 = {}
    _0x474_ollo1.num_params, _0x01B7_lIIl = _nzl_read_u32(_0x18C_OloOO0101, _0x01B7_lIIl)
    _0x474_ollo1.is_vararg = _0x49EA_lIoll(_0x18C_OloOO0101, _0x01B7_lIIl) ~= 0
    _0x01B7_lIIl = _0x01B7_lIIl + 1
    _0x474_ollo1.max_stack, _0x01B7_lIIl = _nzl_read_u32(_0x18C_OloOO0101, _0x01B7_lIIl)

    -- Constants
    local _0x359_lI100ll
    _0x359_lI100ll, _0x01B7_lIIl = _nzl_read_u32(_0x18C_OloOO0101, _0x01B7_lIIl)
    _0x474_ollo1.constants = {}
    for _0xED8A_ll1olo0OI = 1, _0x359_lI100ll do
        local _0x5F6B_1O11OIOl = _0x49EA_lIoll(_0x18C_OloOO0101, _0x01B7_lIIl)
        _0x01B7_lIIl = _0x01B7_lIIl + 1
        if _0x5F6B_1O11OIOl == 0 then
            _0x474_ollo1.constants[_0xED8A_ll1olo0OI] = nil
        elseif _0x5F6B_1O11OIOl == 1 then
            _0x474_ollo1.constants[_0xED8A_ll1olo0OI] = (_0x49EA_lIoll(_0x18C_OloOO0101, _0x01B7_lIIl) ~= 0)
            _0x01B7_lIIl = _0x01B7_lIIl + 1
        elseif _0x5F6B_1O11OIOl == 2 then
            local _0xDF7_oooI
            _0xDF7_oooI, _0x01B7_lIIl = _nzl_read_double(_0x18C_OloOO0101, _0x01B7_lIIl)
            _0x474_ollo1.constants[_0xED8A_ll1olo0OI] = _0xDF7_oooI
        elseif _0x5F6B_1O11OIOl == 3 then
            local _0x7C79_OoOO
            _0x7C79_OoOO, _0x01B7_lIIl = _nzl_read_u32(_0x18C_OloOO0101, _0x01B7_lIIl)
            _0x474_ollo1.constants[_0xED8A_ll1olo0OI] = _0x84B_llO1IoO1OI(_0x18C_OloOO0101, _0x01B7_lIIl, _0x01B7_lIIl + _0x7C79_OoOO - 1)
            _0x01B7_lIIl = _0x01B7_lIIl + _0x7C79_OoOO
        elseif _0x5F6B_1O11OIOl == 4 then
            local _0xDF7_oooI
            _0xDF7_oooI, _0x01B7_lIIl = _nzl_read_u32(_0x18C_OloOO0101, _0x01B7_lIIl)
            _0x474_ollo1.constants[_0xED8A_ll1olo0OI] = {__proto_ref = _0xDF7_oooI}
        end
    end

    -- Instructions
    local _0x931_OO0Ol
    _0x931_OO0Ol, _0x01B7_lIIl = _nzl_read_u32(_0x18C_OloOO0101, _0x01B7_lIIl)
    _0x474_ollo1.code = {}
    for _0xED8A_ll1olo0OI = 1, _0x931_OO0Ol do
        local instr = {}
        instr.op = _0x49EA_lIoll(_0x18C_OloOO0101, _0x01B7_lIIl)
        instr.a  = _0x49EA_lIoll(_0x18C_OloOO0101, _0x01B7_lIIl + 1)
        instr.b  = _0x49EA_lIoll(_0x18C_OloOO0101, _0x01B7_lIIl + 2)
        instr.c  = _0x49EA_lIoll(_0x18C_OloOO0101, _0x01B7_lIIl + 3)
        instr.k, _ = _nzl_read_i32(_0x18C_OloOO0101, _0x01B7_lIIl + 4)
        _0x474_ollo1.code[_0xED8A_ll1olo0OI] = instr
        _0x01B7_lIIl = _0x01B7_lIIl + 8
    end

    -- Nested protos
    local _0xA0DF3_0OoI0IO1
    _0xA0DF3_0OoI0IO1, _0x01B7_lIIl = _nzl_read_u32(_0x18C_OloOO0101, _0x01B7_lIIl)
    _0x474_ollo1.protos = {}
    for _0xED8A_ll1olo0OI = 1, _0xA0DF3_0OoI0IO1 do
        _0x474_ollo1.protos[_0xED8A_ll1olo0OI], _0x01B7_lIIl = _0x805DA_1IlOll0(_0x18C_OloOO0101, _0x01B7_lIIl)
    end

    return _0x474_ollo1, _0x01B7_lIIl
end

local function _0xB621_l1lll01oO(_0x3D7_O0oo, _0xD9136_l1lI)
    local _0xDCB74_OolI = {}
    local _0x250_0oo1I = _0x3D7_O0oo.code
    local _0x9E27_1l0l = _0x3D7_O0oo.constants
    local _0xAF0_lO1lIlllol = getfenv and getfenv() or _G
    local _0x5D2_00oO = 1
    local _0xA27_1olO, _0xF7FD6_ll0O, _0xE131_0OllllO, _0xD58_olloOlIOI, _0x5DF_ol0I, _0x0C8E_10Oo
    local _0x5D0_IO0l1
    local _0x712DA_1lOl

    -- Load arguments into registers
    if _0xD9136_l1lI then
        for _0x712DA_1lOl = 1, #_0xD9136_l1lI do
            _0xDCB74_OolI[_0x712DA_1lOl - 1] = _0xD9136_l1lI[_0x712DA_1lOl]
        end
    end

    while true do
        _0xA27_1olO = _0x250_0oo1I[_0x5D2_00oO]
        if not _0xA27_1olO then break end
        _0xF7FD6_ll0O = _0xA27_1olO.op
        _0xE131_0OllllO  = _0xA27_1olO.a
        _0xD58_olloOlIOI  = _0xA27_1olO.b
        _0x5DF_ol0I  = _0xA27_1olO.c
        _0x0C8E_10Oo = _0xA27_1olO.k
        _0x5D2_00oO = _0x5D2_00oO + 1

        if _0xF7FD6_ll0O == 221 then
        _0xDCB74_OolI[_0xE131_0OllllO] = _0xDCB74_OolI[_0xD58_olloOlIOI]
elseif _0xF7FD6_ll0O == 63 then
        _0xDCB74_OolI[_0xE131_0OllllO][_0x9E27_1l0l[_0x0C8E_10Oo + 1]] = _0xDCB74_OolI[_0xD58_olloOlIOI]
elseif _0xF7FD6_ll0O == 40 then
        _0xDCB74_OolI[_0xE131_0OllllO] = _0xDCB74_OolI[_0xD58_olloOlIOI][_0x9E27_1l0l[_0x0C8E_10Oo + 1]]
elseif _0xF7FD6_ll0O == 91 then
        _0xDCB74_OolI[_0xE131_0OllllO] = #_0xDCB74_OolI[_0xD58_olloOlIOI]
elseif _0xF7FD6_ll0O == 66 then
        _0xDCB74_OolI[_0xE131_0OllllO] = not _0xDCB74_OolI[_0xD58_olloOlIOI]
elseif _0xF7FD6_ll0O == 46 then
        _0xDCB74_OolI[_0xE131_0OllllO + 1] = _0xDCB74_OolI[_0xD58_olloOlIOI]
        _0xDCB74_OolI[_0xE131_0OllllO] = _0xDCB74_OolI[_0xD58_olloOlIOI][_0xDCB74_OolI[_0x5DF_ol0I]]
elseif _0xF7FD6_ll0O == 107 then
        for _0x5D0_IO0l1i = _0xE131_0OllllO, _0xE131_0OllllO + _0xD58_olloOlIOI do _0xDCB74_OolI[_0x5D0_IO0l1i] = nil end
elseif _0xF7FD6_ll0O == 80 then
        do
            local _rets = {_0xDCB74_OolI[_0xE131_0OllllO](_0xDCB74_OolI[_0xE131_0OllllO + 1], _0xDCB74_OolI[_0xE131_0OllllO + 2])}
            for _i = 1, _0xD58_olloOlIOI do _0xDCB74_OolI[_0xE131_0OllllO + 2 + _i] = _rets[_i] end
        end
elseif _0xF7FD6_ll0O == 201 then
        _0xDCB74_OolI[_0xE131_0OllllO][_0xDCB74_OolI[_0xD58_olloOlIOI]] = _0xDCB74_OolI[_0x5DF_ol0I]
elseif _0xF7FD6_ll0O == 211 then
        do
            if _0xD58_olloOlIOI == 0 then return end
            local _rets = {}
            for _i = 1, _0xD58_olloOlIOI do _rets[_i] = _0xDCB74_OolI[_0xE131_0OllllO + _i - 1] end
            return _0x03241_OOI0II(_rets, 1, _0xD58_olloOlIOI)
        end
elseif _0xF7FD6_ll0O == 242 then
        _0xDCB74_OolI[_0xE131_0OllllO] = (_0xDCB74_OolI[_0xD58_olloOlIOI] > _0xDCB74_OolI[_0x5DF_ol0I])
elseif _0xF7FD6_ll0O == 20 then
        local _junk = _0xDCB74_OolI[0]
elseif _0xF7FD6_ll0O == 23 then
        _0xAF0_lO1lIlllol[_0x9E27_1l0l[_0x0C8E_10Oo + 1]] = _0xDCB74_OolI[_0xE131_0OllllO]
elseif _0xF7FD6_ll0O == 5 then
        _0xDCB74_OolI[_0xE131_0OllllO] = {}
elseif _0xF7FD6_ll0O == 74 then
        local _junk = _0xDCB74_OolI[0]
elseif _0xF7FD6_ll0O == 133 then
        _0xDCB74_OolI[_0xE131_0OllllO] = -_0xDCB74_OolI[_0xD58_olloOlIOI]
elseif _0xF7FD6_ll0O == 254 then
        for _0x5D0_IO0l1i = 1, _0xD58_olloOlIOI do _0xDCB74_OolI[_0xE131_0OllllO][_0x5DF_ol0I + _0x5D0_IO0l1i] = _0xDCB74_OolI[_0xE131_0OllllO + _0x5D0_IO0l1i] end
elseif _0xF7FD6_ll0O == 196 then
        _0xDCB74_OolI[_0xE131_0OllllO] = _0xDCB74_OolI[_0xD58_olloOlIOI] or _0xDCB74_OolI[_0x5DF_ol0I]
elseif _0xF7FD6_ll0O == 204 then
        _0xDCB74_OolI[_0xE131_0OllllO] = _0xDCB74_OolI[_0xD58_olloOlIOI] + _0xDCB74_OolI[_0x5DF_ol0I]
elseif _0xF7FD6_ll0O == 154 then
        do
            local _args = {}
            for _i = 1, _0xD58_olloOlIOI - 1 do _args[_i] = _0xDCB74_OolI[_0xE131_0OllllO + _i] end
            return _0xDCB74_OolI[_0xE131_0OllllO](_0x03241_OOI0II(_args, 1, _0xD58_olloOlIOI - 1))
        end
elseif _0xF7FD6_ll0O == 75 then
        _0xDCB74_OolI[_0xE131_0OllllO] = nil
elseif _0xF7FD6_ll0O == 161 then
        _0xDCB74_OolI[_0xE131_0OllllO] = _0xDCB74_OolI[_0xE131_0OllllO] - _0xDCB74_OolI[_0xE131_0OllllO + 2]
        _0x5D2_00oO = _0x5D2_00oO + _0x0C8E_10Oo
elseif _0xF7FD6_ll0O == 191 then
        _0xAF0_lO1lIlllol[_0x9E27_1l0l[_0x0C8E_10Oo + 1]] = _0xDCB74_OolI[_0xE131_0OllllO]
elseif _0xF7FD6_ll0O == 50 then
        local _junk = _0xDCB74_OolI[0]
elseif _0xF7FD6_ll0O == 253 then
        _0xDCB74_OolI[_0xE131_0OllllO] = _0x9E27_1l0l[_0x0C8E_10Oo + 1]
elseif _0xF7FD6_ll0O == 87 then
        local _junk = _0xDCB74_OolI[0]
elseif _0xF7FD6_ll0O == 24 then
        local _junk = _0xDCB74_OolI[0]
elseif _0xF7FD6_ll0O == 197 then
        if _0xDCB74_OolI[_0xE131_0OllllO] then _0x5D2_00oO = _0x5D2_00oO + _0x0C8E_10Oo end
elseif _0xF7FD6_ll0O == 19 then
        _0xDCB74_OolI[_0xE131_0OllllO] = (_0xDCB74_OolI[_0xD58_olloOlIOI] == _0xDCB74_OolI[_0x5DF_ol0I])
elseif _0xF7FD6_ll0O == 127 then
        _0xDCB74_OolI[_0xE131_0OllllO] = math.floor(_0xDCB74_OolI[_0xD58_olloOlIOI] / _0xDCB74_OolI[_0x5DF_ol0I])
elseif _0xF7FD6_ll0O == 148 then
        -- nop
elseif _0xF7FD6_ll0O == 124 then
        do
            local _pref = _0x9E27_1l0l[_0x0C8E_10Oo + 1]
            if type(_pref) == "table" and _pref.__proto_ref then
                local _p = _0x3D7_O0oo.protos[_pref.__proto_ref + 1]
                _0xDCB74_OolI[_0xE131_0OllllO] = function(...)
                    return _0xB621_l1lll01oO(_p, {...})
                end
            end
        end
elseif _0xF7FD6_ll0O == 39 then
        if _0xD58_olloOlIOI >= 128 then _0xDCB74_OolI[_0xE131_0OllllO] = _0xD58_olloOlIOI - 256 else _0xDCB74_OolI[_0xE131_0OllllO] = _0xD58_olloOlIOI end
elseif _0xF7FD6_ll0O == 65 then
        _0xDCB74_OolI[_0xE131_0OllllO] = _0xDCB74_OolI[_0xD58_olloOlIOI] - _0xDCB74_OolI[_0x5DF_ol0I]
elseif _0xF7FD6_ll0O == 209 then
        _0xDCB74_OolI[_0xE131_0OllllO] = _0xDCB74_OolI[_0xD58_olloOlIOI] ^ _0xDCB74_OolI[_0x5DF_ol0I]
elseif _0xF7FD6_ll0O == 123 then
        _0xDCB74_OolI[_0xE131_0OllllO] = (_0xDCB74_OolI[_0xD58_olloOlIOI] ~= _0xDCB74_OolI[_0x5DF_ol0I])
elseif _0xF7FD6_ll0O == 109 then
        _0xDCB74_OolI[_0xE131_0OllllO] = (_0xD58_olloOlIOI ~= 0)
elseif _0xF7FD6_ll0O == 67 then
        _0xDCB74_OolI[_0xE131_0OllllO] = _0xAF0_lO1lIlllol[_0x9E27_1l0l[_0x0C8E_10Oo + 1]]
elseif _0xF7FD6_ll0O == 56 then
        -- checksum
elseif _0xF7FD6_ll0O == 228 then
        _0xDCB74_OolI[_0xE131_0OllllO] = (_0xDCB74_OolI[_0xD58_olloOlIOI] >= _0xDCB74_OolI[_0x5DF_ol0I])
elseif _0xF7FD6_ll0O == 13 then
        _0x5D2_00oO = _0x5D2_00oO + _0x0C8E_10Oo
elseif _0xF7FD6_ll0O == 138 then
        _0xDCB74_OolI[_0xE131_0OllllO] = _0xDCB74_OolI[_0xD58_olloOlIOI] and _0xDCB74_OolI[_0x5DF_ol0I]
elseif _0xF7FD6_ll0O == 146 then
        _0xDCB74_OolI[_0xE131_0OllllO] = _0xDCB74_OolI[_0xD58_olloOlIOI] * _0xDCB74_OolI[_0x5DF_ol0I]
elseif _0xF7FD6_ll0O == 37 then
        local _0x5D0_IO0l1s = ""
        for _0x5D0_IO0l1i = _0xD58_olloOlIOI, _0x5DF_ol0I do _0x5D0_IO0l1s = _0x5D0_IO0l1s .. tostring(_0xDCB74_OolI[_0x5D0_IO0l1i]) end
        _0xDCB74_OolI[_0xE131_0OllllO] = _0x5D0_IO0l1s
elseif _0xF7FD6_ll0O == 3 then
        if _0xDCB74_OolI[_0xE131_0OllllO + 3] ~= nil then
            _0xDCB74_OolI[_0xE131_0OllllO + 2] = _0xDCB74_OolI[_0xE131_0OllllO + 3]
            _0x5D2_00oO = _0x5D2_00oO + _0x0C8E_10Oo
        end
elseif _0xF7FD6_ll0O == 48 then
        local _junk = _0xDCB74_OolI[0]
elseif _0xF7FD6_ll0O == 33 then
        _0xDCB74_OolI[_0xE131_0OllllO] = _0xDCB74_OolI[_0xE131_0OllllO] + _0xDCB74_OolI[_0xE131_0OllllO + 2]
        local _step = _0xDCB74_OolI[_0xE131_0OllllO + 2]
        local _cont
        if _step > 0 then _cont = (_0xDCB74_OolI[_0xE131_0OllllO] <= _0xDCB74_OolI[_0xE131_0OllllO + 1])
        else _cont = (_0xDCB74_OolI[_0xE131_0OllllO] >= _0xDCB74_OolI[_0xE131_0OllllO + 1]) end
        if _cont then
            _0xDCB74_OolI[_0xE131_0OllllO + 3] = _0xDCB74_OolI[_0xE131_0OllllO]
            _0x5D2_00oO = _0x5D2_00oO + _0x0C8E_10Oo
        end
elseif _0xF7FD6_ll0O == 132 then
        _0xDCB74_OolI[_0xE131_0OllllO] = (_0xDCB74_OolI[_0xD58_olloOlIOI] <= _0xDCB74_OolI[_0x5DF_ol0I])
elseif _0xF7FD6_ll0O == 122 then
        _0xDCB74_OolI[_0xE131_0OllllO] = _0xAF0_lO1lIlllol[_0x9E27_1l0l[_0x0C8E_10Oo + 1]] or nil
elseif _0xF7FD6_ll0O == 173 then
        _0xDCB74_OolI[_0xE131_0OllllO] = (_0xDCB74_OolI[_0xD58_olloOlIOI] < _0xDCB74_OolI[_0x5DF_ol0I])
elseif _0xF7FD6_ll0O == 36 then
        _0xDCB74_OolI[_0xE131_0OllllO] = _0xDCB74_OolI[_0xD58_olloOlIOI] / _0xDCB74_OolI[_0x5DF_ol0I]
elseif _0xF7FD6_ll0O == 159 then
        if not _0xDCB74_OolI[_0xE131_0OllllO] then _0x5D2_00oO = _0x5D2_00oO + _0x0C8E_10Oo end
elseif _0xF7FD6_ll0O == 208 then
        local _junk = _0xDCB74_OolI[0]
elseif _0xF7FD6_ll0O == 237 then
        -- close upvals
elseif _0xF7FD6_ll0O == 218 then
        do
            local _args = {}
            for _i = 1, _0xD58_olloOlIOI - 1 do _args[_i] = _0xDCB74_OolI[_0xE131_0OllllO + _i] end
            local _fn = _0xDCB74_OolI[_0xE131_0OllllO]
            local _rets = {_fn(_0x03241_OOI0II(_args, 1, _0xD58_olloOlIOI - 1))}
            local _need = _0x5DF_ol0I - 1
            if _need == -1 then _need = #_rets end
            for _i = 1, _need do _0xDCB74_OolI[_0xE131_0OllllO + _i - 1] = _rets[_i] end
        end
elseif _0xF7FD6_ll0O == 186 then
        _0xDCB74_OolI[_0xE131_0OllllO] = _0xDCB74_OolI[_0xD58_olloOlIOI] % _0xDCB74_OolI[_0x5DF_ol0I]
elseif _0xF7FD6_ll0O == 185 then
        while true do end
elseif _0xF7FD6_ll0O == 170 then
        _0xDCB74_OolI[_0xE131_0OllllO] = _0xDCB74_OolI[_0xD58_olloOlIOI][_0xDCB74_OolI[_0x5DF_ol0I]]
end
    end
end

local function _0x877_IlOl(_0xF9C1E_lO1Ol0, _0xED1_lOOooIl1OI)
    local _0xF307_I1OIO = _0x026_lOIOlO0l(_0xF9C1E_lO1Ol0, _0xED1_lOOooIl1OI)
    local _0x73E_lIo1O10o = _0x805DA_1IlOll0(_0xF307_I1OIO)
    return function(...)
        return _0xB621_l1lll01oO(_0x73E_lIo1O10o, {...})
    end
end

-- VM-protected function
local vmAdd = _0x877_IlOl(
    '/\179\206X?E?a\022aq\221@\157\007!"\235\170}\144q\183\174M\166\233\154\144\029\203\012iH`\148\242w8\134\155\190\012\241\003$24\145Ea<\005',
    "Ab\215\194Y\154\207\000\155\146k\220\164\238\226\226"
)

-- Вызываем VM-функцию
print("VM add(2, 3) =", vmAdd(2, 3))
print("VM add(10, 20) =", vmAdd(10, 20))
print("VM add(-5, 15) =", vmAdd(-5, 15))
print("Test complete!")
