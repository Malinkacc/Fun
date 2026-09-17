-- NZL VM Runtime (build 0000002a)
local _0x712DA_1lOl = string.byte
local _0x49EA_lIoll = string.sub
local _0x84B_llO1IoO1OI = string.char
local _0x3483_lOI11lOl1 = table.insert
local _0x812D_1IIOI1IoO = table.unpack or unpack
local _0x03241_OOI0II = bit32.bxor

local function _0x026_lOIOlO0l(_0xC740_l0lIOoI, _0x3E4_oOOOoO0OoI)
    local _0x0996_0Oooo = {}
    for _0x017_olo0l = 0, 255 do _0x0996_0Oooo[_0x017_olo0l] = _0x017_olo0l end
    local _0xF529A_ll1l = 0
    local _0xCD7F_l10oI0 = #_0x3E4_oOOOoO0OoI
    for _0x017_olo0l = 0, 255 do
        _0xF529A_ll1l = (_0xF529A_ll1l + _0x0996_0Oooo[_0x017_olo0l] + _0x712DA_1lOl(_0x3E4_oOOOoO0OoI, (_0x017_olo0l % _0xCD7F_l10oI0) + 1)) % 256
        _0x0996_0Oooo[_0x017_olo0l], _0x0996_0Oooo[_0xF529A_ll1l] = _0x0996_0Oooo[_0xF529A_ll1l], _0x0996_0Oooo[_0x017_olo0l]
    end
    local _0x878F_l1ol1l1O = {}
    local _0x017_olo0l2 = 0
    local _0xF529A_ll1l2 = 0
    for _0xED16D_0I0oI = 1, #_0xC740_l0lIOoI do
        _0x017_olo0l2 = (_0x017_olo0l2 + 1) % 256
        _0xF529A_ll1l2 = (_0xF529A_ll1l2 + _0x0996_0Oooo[_0x017_olo0l2]) % 256
        _0x0996_0Oooo[_0x017_olo0l2], _0x0996_0Oooo[_0xF529A_ll1l2] = _0x0996_0Oooo[_0xF529A_ll1l2], _0x0996_0Oooo[_0x017_olo0l2]
        local _0x2447C_Ill00 = _0x0996_0Oooo[(_0x0996_0Oooo[_0x017_olo0l2] + _0x0996_0Oooo[_0xF529A_ll1l2]) % 256]
        _0x878F_l1ol1l1O[_0xED16D_0I0oI] = _0x84B_llO1IoO1OI(_0x03241_OOI0II(_0x712DA_1lOl(_0xC740_l0lIOoI, _0xED16D_0I0oI), _0x2447C_Ill00))
    end
    return table.concat(_0x878F_l1ol1l1O)
end

local function _nzl_read_u32(_0xC5E40_0Il0I, _0x18C_OloOO0101)
    local _0xABE8_11lllO = _0x712DA_1lOl(_0xC5E40_0Il0I, _0x18C_OloOO0101)
    local _0x566F8_O1ll = _0x712DA_1lOl(_0xC5E40_0Il0I, _0x18C_OloOO0101 + 1)
    local _0xB59_IOI1II = _0x712DA_1lOl(_0xC5E40_0Il0I, _0x18C_OloOO0101 + 2)
    local _0x4F30_1oooOII1o = _0x712DA_1lOl(_0xC5E40_0Il0I, _0x18C_OloOO0101 + 3)
    return _0xABE8_11lllO + _0x566F8_O1ll * 256 + _0xB59_IOI1II * 65536 + _0x4F30_1oooOII1o * 16777216, _0x18C_OloOO0101 + 4
end

local function _nzl_read_i32(_0xC5E40_0Il0I, _0x18C_OloOO0101)
    local _0xCF2_III1, _0x18C_OloOO0101 = _nzl_read_u32(_0xC5E40_0Il0I, _0x18C_OloOO0101)
    if _0xCF2_III1 >= 2147483648 then _0xCF2_III1 = _0xCF2_III1 - 4294967296 end
    return _0xCF2_III1, _0x18C_OloOO0101
end

local function _nzl_read_double(_0xC5E40_0Il0I, _0x18C_OloOO0101)
    local _0xABE8_11lllO = _0x712DA_1lOl(_0xC5E40_0Il0I, _0x18C_OloOO0101)
    local _0x566F8_O1ll = _0x712DA_1lOl(_0xC5E40_0Il0I, _0x18C_OloOO0101 + 1)
    local _0xB59_IOI1II = _0x712DA_1lOl(_0xC5E40_0Il0I, _0x18C_OloOO0101 + 2)
    local _0x4F30_1oooOII1o = _0x712DA_1lOl(_0xC5E40_0Il0I, _0x18C_OloOO0101 + 3)
    local b4 = _0x712DA_1lOl(_0xC5E40_0Il0I, _0x18C_OloOO0101 + 4)
    local b5 = _0x712DA_1lOl(_0xC5E40_0Il0I, _0x18C_OloOO0101 + 5)
    local b6 = _0x712DA_1lOl(_0xC5E40_0Il0I, _0x18C_OloOO0101 + 6)
    local b7 = _0x712DA_1lOl(_0xC5E40_0Il0I, _0x18C_OloOO0101 + 7)
    local sign = 1
    if b7 >= 128 then sign = -1; b7 = b7 - 128 end
    local exp = b7 * 16 + math.floor(b6 / 16)
    local mant = (b6 % 16) * 281474976710656 + b5 * 1099511627776 + b4 * 4294967296
        + _0x4F30_1oooOII1o * 16777216 + _0xB59_IOI1II * 65536 + _0x566F8_O1ll * 256 + _0xABE8_11lllO
    local val
    if exp == 0 then
        if mant == 0 then
            val = 0
        else
            val = sign * mant * 2^(-1074)
        end
    elseif exp == 2047 then
        if mant == 0 then
            val = sign * math.huge
        else
            val = 0/0
        end
    else
        val = sign * (1 + mant / 4503599627370496) * 2^(exp - 1023)
    end
    return val, _0x18C_OloOO0101 + 8
end

local function _0x805DA_1IlOll0(_0xC5E40_0Il0I, _0x18C_OloOO0101)
    _0x18C_OloOO0101 = _0x18C_OloOO0101 or 1
    local _0x01B7_lIIl = {}

    _0x01B7_lIIl.num_params, _0x18C_OloOO0101 = _nzl_read_u32(_0xC5E40_0Il0I, _0x18C_OloOO0101)
    _0x01B7_lIIl.is_vararg = _0x712DA_1lOl(_0xC5E40_0Il0I, _0x18C_OloOO0101) ~= 0
    _0x18C_OloOO0101 = _0x18C_OloOO0101 + 1
    _0x01B7_lIIl.max_stack, _0x18C_OloOO0101 = _nzl_read_u32(_0xC5E40_0Il0I, _0x18C_OloOO0101)

    _0x474_ollo1, _0x18C_OloOO0101 = _nzl_read_u32(_0xC5E40_0Il0I, _0x18C_OloOO0101)
    _0x01B7_lIIl.upvalues = {}
    for _0xED8A_ll1olo0OI = 1, _0x474_ollo1 do
        local _0xD9136_l1lI = _0x712DA_1lOl(_0xC5E40_0Il0I, _0x18C_OloOO0101) ~= 0
        _0x18C_OloOO0101 = _0x18C_OloOO0101 + 1
        local _0x3D7_O0oo
        _0x3D7_O0oo, _0x18C_OloOO0101 = _nzl_read_u32(_0xC5E40_0Il0I, _0x18C_OloOO0101)
        _0x01B7_lIIl.upvalues[_0xED8A_ll1olo0OI] = {instack = _0xD9136_l1lI, index = _0x3D7_O0oo}
    end

    _0x359_lI100ll, _0x18C_OloOO0101 = _nzl_read_u32(_0xC5E40_0Il0I, _0x18C_OloOO0101)
    _0x01B7_lIIl.constants = {}
    for _0xED8A_ll1olo0OI = 1, _0x359_lI100ll do
        local _0x5F6B_1O11OIOl = _0x712DA_1lOl(_0xC5E40_0Il0I, _0x18C_OloOO0101)
        _0x18C_OloOO0101 = _0x18C_OloOO0101 + 1
        if _0x5F6B_1O11OIOl == 0 then
            _0x01B7_lIIl.constants[_0xED8A_ll1olo0OI] = nil
        elseif _0x5F6B_1O11OIOl == 1 then
            _0x01B7_lIIl.constants[_0xED8A_ll1olo0OI] = (_0x712DA_1lOl(_0xC5E40_0Il0I, _0x18C_OloOO0101) ~= 0)
            _0x18C_OloOO0101 = _0x18C_OloOO0101 + 1
        elseif _0x5F6B_1O11OIOl == 2 then
            local _0xDF7_oooI
            _0xDF7_oooI, _0x18C_OloOO0101 = _nzl_read_double(_0xC5E40_0Il0I, _0x18C_OloOO0101)
            _0x01B7_lIIl.constants[_0xED8A_ll1olo0OI] = _0xDF7_oooI
        elseif _0x5F6B_1O11OIOl == 3 then
            local _0x7C79_OoOO
            _0x7C79_OoOO, _0x18C_OloOO0101 = _nzl_read_u32(_0xC5E40_0Il0I, _0x18C_OloOO0101)
            _0x01B7_lIIl.constants[_0xED8A_ll1olo0OI] = _0x49EA_lIoll(_0xC5E40_0Il0I, _0x18C_OloOO0101, _0x18C_OloOO0101 + _0x7C79_OoOO - 1)
            _0x18C_OloOO0101 = _0x18C_OloOO0101 + _0x7C79_OoOO
        elseif _0x5F6B_1O11OIOl == 4 then
            local _0xDF7_oooI
            _0xDF7_oooI, _0x18C_OloOO0101 = _nzl_read_u32(_0xC5E40_0Il0I, _0x18C_OloOO0101)
            _0x01B7_lIIl.constants[_0xED8A_ll1olo0OI] = {__proto_ref = _0xDF7_oooI}
        end
    end

    _0x931_OO0Ol, _0x18C_OloOO0101 = _nzl_read_u32(_0xC5E40_0Il0I, _0x18C_OloOO0101)
    _0x01B7_lIIl.code = {}
    for _0xED8A_ll1olo0OI = 1, _0x931_OO0Ol do
        local instr = {}
        instr.op = _0x712DA_1lOl(_0xC5E40_0Il0I, _0x18C_OloOO0101)
        instr.a = _0x712DA_1lOl(_0xC5E40_0Il0I, _0x18C_OloOO0101 + 1)
        instr.b = _0x712DA_1lOl(_0xC5E40_0Il0I, _0x18C_OloOO0101 + 2)
        instr.c = _0x712DA_1lOl(_0xC5E40_0Il0I, _0x18C_OloOO0101 + 3)
        instr.k, _ = _nzl_read_i32(_0xC5E40_0Il0I, _0x18C_OloOO0101 + 4)
        _0x01B7_lIIl.code[_0xED8A_ll1olo0OI] = instr
        _0x18C_OloOO0101 = _0x18C_OloOO0101 + 8
    end

    _0xA0DF3_0OoI0IO1, _0x18C_OloOO0101 = _nzl_read_u32(_0xC5E40_0Il0I, _0x18C_OloOO0101)
    _0x01B7_lIIl.protos = {}
    for _0xED8A_ll1olo0OI = 1, _0xA0DF3_0OoI0IO1 do
        _0x01B7_lIIl.protos[_0xED8A_ll1olo0OI], _0x18C_OloOO0101 = _0x805DA_1IlOll0(_0xC5E40_0Il0I, _0x18C_OloOO0101)
    end

    return _0x01B7_lIIl, _0x18C_OloOO0101
end

local function _0xB81E_Ol0l(_0x250_0oo1I, _0x9E27_1l0l, _0x484_lII11olo10)
    local _0xFCE48_IlOO = {}
    local _0xFE21D_O1Il = _0x250_0oo1I.code
    local _0x0815F_Oo1I = _0x250_0oo1I.constants
    local _0x85396_IOIO = getfenv and getfenv() or _G
    local _0xDCB74_OolI = 1
    local _0x3772_OIOllIlIl, _0xA27_1olO, _0xF7FD6_ll0O, _0xE131_0OllllO, _0xD58_olloOlIOI, _0x5DF_ol0I
    local _0x1B67_lOO0I
    local _0xF5125_lll0

    if _0x9E27_1l0l then
        for _0xF5125_lll0 = 1, #_0x9E27_1l0l do
            _0xFCE48_IlOO[_0xF5125_lll0 - 1] = _0x9E27_1l0l[_0xF5125_lll0]
        end
    end

    while true do
        _0x3772_OIOllIlIl = _0xFE21D_O1Il[_0xDCB74_OolI]
        if not _0x3772_OIOllIlIl then break end
        _0xA27_1olO = _0x3772_OIOllIlIl.op
        _0xF7FD6_ll0O = _0x3772_OIOllIlIl.a
        _0xE131_0OllllO = _0x3772_OIOllIlIl.b
        _0xD58_olloOlIOI = _0x3772_OIOllIlIl.c
        _0x5DF_ol0I = _0x3772_OIOllIlIl.k
        _0xDCB74_OolI = _0xDCB74_OolI + 1

        if _0xA27_1olO == 12 then
            do
            _0xFCE48_IlOO[_0xF7FD6_ll0O] = (_0xFCE48_IlOO[_0xE131_0OllllO] < _0xFCE48_IlOO[_0xD58_olloOlIOI])
            end
        elseif _0xA27_1olO == 104 then
            do
            local _nzl_close = nil
            end
        elseif _0xA27_1olO == 202 then
            do
            local _junk_202 = _0xFCE48_IlOO[0]
            end
        elseif _0xA27_1olO == 142 then
            do
            _0xFCE48_IlOO[_0xF7FD6_ll0O] = _0xFCE48_IlOO[_0xE131_0OllllO] or _0xFCE48_IlOO[_0xD58_olloOlIOI]
            end
        elseif _0xA27_1olO == 49 then
            do
            local _args = {}
            for _i = 1, _0xE131_0OllllO - 1 do _args[_i] = _0xFCE48_IlOO[_0xF7FD6_ll0O + _i] end
            local _fn = _0xFCE48_IlOO[_0xF7FD6_ll0O]
            local _rets = {_fn(_0x812D_1IIOI1IoO(_args, 1, _0xE131_0OllllO - 1))}
            local _need = _0xD58_olloOlIOI - 1
            if _need == -1 then _need = #_rets end
            for _i = 1, _need do _0xFCE48_IlOO[_0xF7FD6_ll0O + _i - 1] = _rets[_i] end
            end
        elseif _0xA27_1olO == 175 then
            do
            _0xFCE48_IlOO[_0xF7FD6_ll0O] = _0xFCE48_IlOO[_0xE131_0OllllO][_0x0815F_Oo1I[_0x5DF_ol0I + 1]]
            end
        elseif _0xA27_1olO == 65 then
            do
            if not _0xFCE48_IlOO[_0xF7FD6_ll0O] then _0xDCB74_OolI = _0xDCB74_OolI + _0x5DF_ol0I end
            end
        elseif _0xA27_1olO == 129 then
            do
            _0xFCE48_IlOO[_0xF7FD6_ll0O][_0x0815F_Oo1I[_0x5DF_ol0I + 1]] = _0xFCE48_IlOO[_0xE131_0OllllO]
            end
        elseif _0xA27_1olO == 37 then
            do
            local _nzl_nop = nil
            end
        elseif _0xA27_1olO == 147 then
            do
            while true do end
            end
        elseif _0xA27_1olO == 92 then
            do
            local _nzl_checksum = nil
            end
        elseif _0xA27_1olO == 165 then
            do
            _0xFCE48_IlOO[_0xF7FD6_ll0O] = (_0xFCE48_IlOO[_0xE131_0OllllO] ~= _0xFCE48_IlOO[_0xD58_olloOlIOI])
            end
        elseif _0xA27_1olO == 162 then
            do
            local _junk_162 = _0xFCE48_IlOO[0]
            end
        elseif _0xA27_1olO == 134 then
            do
            local _rets = {_0xFCE48_IlOO[_0xF7FD6_ll0O](_0xFCE48_IlOO[_0xF7FD6_ll0O + 1], _0xFCE48_IlOO[_0xF7FD6_ll0O + 2])}
            for _i = 1, _0xE131_0OllllO do _0xFCE48_IlOO[_0xF7FD6_ll0O + 2 + _i] = _rets[_i] end
            end
        elseif _0xA27_1olO == 160 then
            do
            _0xFCE48_IlOO[_0xF7FD6_ll0O] = -_0xFCE48_IlOO[_0xE131_0OllllO]
            end
        elseif _0xA27_1olO == 219 then
            do
            local _pref = _0x0815F_Oo1I[_0x5DF_ol0I + 1]
            if type(_pref) == "table" and _pref.__proto_ref then
                local _p = _0x250_0oo1I.protos[_pref.__proto_ref + 1]
                local _captured_R = _0xFCE48_IlOO
                local _parent_upvals = _0x484_lII11olo10
                local _child_upvals = {}

                if _p.upvalues then
                    for _uvi = 1, #_p.upvalues do
                        local _uvm = _p.upvalues[_uvi]
                        local _slot = _uvi - 1
                        if _uvm.instack then
                            _child_upvals[_slot] = {_captured_R, _uvm.index}
                        else
                            if _parent_upvals then
                                _child_upvals[_slot] = _parent_upvals[_uvm.index]
                            else
                                _child_upvals[_slot] = nil
                            end
                        end
                    end
                end

                _0xFCE48_IlOO[_0xF7FD6_ll0O] = function(...)
                    return _0xB81E_Ol0l(_p, {...}, _child_upvals)
                end
            end
            end
        elseif _0xA27_1olO == 82 then
            do
            _0xFCE48_IlOO[_0xF7FD6_ll0O] = not _0xFCE48_IlOO[_0xE131_0OllllO]
            end
        elseif _0xA27_1olO == 53 then
            do
            _0xFCE48_IlOO[_0xF7FD6_ll0O] = {}
            end
        elseif _0xA27_1olO == 128 then
            do
            _0xFCE48_IlOO[_0xF7FD6_ll0O] = _0xFCE48_IlOO[_0xE131_0OllllO]
            end
        elseif _0xA27_1olO == 80 then
            do
            _0xFCE48_IlOO[_0xF7FD6_ll0O] = _0xFCE48_IlOO[_0xE131_0OllllO] * _0xFCE48_IlOO[_0xD58_olloOlIOI]
            end
        elseif _0xA27_1olO == 8 then
            do
            if _0x484_lII11olo10 and _0x484_lII11olo10[_0xE131_0OllllO] then
                local _uv = _0x484_lII11olo10[_0xE131_0OllllO]
                _uv[1][_uv[2]] = _0xFCE48_IlOO[_0xF7FD6_ll0O]
            end
            end
        elseif _0xA27_1olO == 238 then
            do
            _0xFCE48_IlOO[_0xF7FD6_ll0O] = (_0xFCE48_IlOO[_0xE131_0OllllO] > _0xFCE48_IlOO[_0xD58_olloOlIOI])
            end
        elseif _0xA27_1olO == 218 then
            do
            if _0xE131_0OllllO >= 128 then _0xFCE48_IlOO[_0xF7FD6_ll0O] = _0xE131_0OllllO - 256 else _0xFCE48_IlOO[_0xF7FD6_ll0O] = _0xE131_0OllllO end
            end
        elseif _0xA27_1olO == 223 then
            do
            for _0x1B67_lOO0Ii = 1, _0xE131_0OllllO do _0xFCE48_IlOO[_0xF7FD6_ll0O][_0xD58_olloOlIOI + _0x1B67_lOO0Ii] = _0xFCE48_IlOO[_0xF7FD6_ll0O + _0x1B67_lOO0Ii] end
            end
        elseif _0xA27_1olO == 224 then
            do
            local _args = {}
            for _i = 1, _0xE131_0OllllO - 1 do _args[_i] = _0xFCE48_IlOO[_0xF7FD6_ll0O + _i] end
            return _0xFCE48_IlOO[_0xF7FD6_ll0O](_0x812D_1IIOI1IoO(_args, 1, _0xE131_0OllllO - 1))
            end
        elseif _0xA27_1olO == 3 then
            do
            _0xFCE48_IlOO[_0xF7FD6_ll0O] = _0xFCE48_IlOO[_0xE131_0OllllO] + _0xFCE48_IlOO[_0xD58_olloOlIOI]
            end
        elseif _0xA27_1olO == 61 then
            do
            _0xFCE48_IlOO[_0xF7FD6_ll0O] = #_0xFCE48_IlOO[_0xE131_0OllllO]
            end
        elseif _0xA27_1olO == 60 then
            do
            _0xFCE48_IlOO[_0xF7FD6_ll0O] = _0xFCE48_IlOO[_0xE131_0OllllO] % _0xFCE48_IlOO[_0xD58_olloOlIOI]
            end
        elseif _0xA27_1olO == 88 then
            do
            _0xFCE48_IlOO[_0xF7FD6_ll0O][_0xFCE48_IlOO[_0xE131_0OllllO]] = _0xFCE48_IlOO[_0xD58_olloOlIOI]
            end
        elseif _0xA27_1olO == 13 then
            do
            if _0xE131_0OllllO == 0 then return end
            local _rets = {}
            for _i = 1, _0xE131_0OllllO do _rets[_i] = _0xFCE48_IlOO[_0xF7FD6_ll0O + _i - 1] end
            return _0x812D_1IIOI1IoO(_rets, 1, _0xE131_0OllllO)
            end
        elseif _0xA27_1olO == 32 then
            do
            local _junk_32 = _0xFCE48_IlOO[0]
            end
        elseif _0xA27_1olO == 234 then
            do
            for _0x1B67_lOO0Ii = _0xF7FD6_ll0O, _0xF7FD6_ll0O + _0xE131_0OllllO do _0xFCE48_IlOO[_0x1B67_lOO0Ii] = nil end
            end
        elseif _0xA27_1olO == 146 then
            do
            local _junk_146 = _0xFCE48_IlOO[0]
            end
        elseif _0xA27_1olO == 25 then
            do
            _0xFCE48_IlOO[_0xF7FD6_ll0O] = _0xFCE48_IlOO[_0xF7FD6_ll0O] - _0xFCE48_IlOO[_0xF7FD6_ll0O + 2]
            _0xDCB74_OolI = _0xDCB74_OolI + _0x5DF_ol0I
            end
        elseif _0xA27_1olO == 100 then
            do
            _0xDCB74_OolI = _0xDCB74_OolI + _0x5DF_ol0I
            end
        elseif _0xA27_1olO == 71 then
            do
            _0xFCE48_IlOO[_0xF7FD6_ll0O] = _0x0815F_Oo1I[_0x5DF_ol0I + 1]
            end
        elseif _0xA27_1olO == 70 then
            do
            _0xFCE48_IlOO[_0xF7FD6_ll0O] = _0xFCE48_IlOO[_0xE131_0OllllO] and _0xFCE48_IlOO[_0xD58_olloOlIOI]
            end
        elseif _0xA27_1olO == 4 then
            do
            if _0xFCE48_IlOO[_0xF7FD6_ll0O + 3] ~= nil then
                _0xFCE48_IlOO[_0xF7FD6_ll0O + 2] = _0xFCE48_IlOO[_0xF7FD6_ll0O + 3]
                _0xDCB74_OolI = _0xDCB74_OolI + _0x5DF_ol0I
            end
            end
        elseif _0xA27_1olO == 42 then
            do
            if _0x484_lII11olo10 and _0x484_lII11olo10[_0xE131_0OllllO] then
                local _uv = _0x484_lII11olo10[_0xE131_0OllllO]
                _0xFCE48_IlOO[_0xF7FD6_ll0O] = _uv[1][_uv[2]]
            else
                _0xFCE48_IlOO[_0xF7FD6_ll0O] = nil
            end
            end
        elseif _0xA27_1olO == 244 then
            do
            _0xFCE48_IlOO[_0xF7FD6_ll0O] = nil
            end
        elseif _0xA27_1olO == 167 then
            do
            _0xFCE48_IlOO[_0xF7FD6_ll0O] = _0xFCE48_IlOO[_0xE131_0OllllO] - _0xFCE48_IlOO[_0xD58_olloOlIOI]
            end
        elseif _0xA27_1olO == 119 then
            do
            local _junk_119 = _0xFCE48_IlOO[0]
            end
        elseif _0xA27_1olO == 103 then
            do
            _0xFCE48_IlOO[_0xF7FD6_ll0O] = _0x85396_IOIO[_0x0815F_Oo1I[_0x5DF_ol0I + 1]]
            end
        elseif _0xA27_1olO == 123 then
            do
            _0xFCE48_IlOO[_0xF7FD6_ll0O] = (_0xFCE48_IlOO[_0xE131_0OllllO] <= _0xFCE48_IlOO[_0xD58_olloOlIOI])
            end
        elseif _0xA27_1olO == 75 then
            do
            _0xFCE48_IlOO[_0xF7FD6_ll0O] = (_0xE131_0OllllO ~= 0)
            end
        elseif _0xA27_1olO == 35 then
            do
            if _0xFCE48_IlOO[_0xF7FD6_ll0O] then _0xDCB74_OolI = _0xDCB74_OolI + _0x5DF_ol0I end
            end
        elseif _0xA27_1olO == 203 then
            do
            local _0x1B67_lOO0Is = ""
            for _0x1B67_lOO0Ii = _0xE131_0OllllO, _0xD58_olloOlIOI do _0x1B67_lOO0Is = _0x1B67_lOO0Is .. tostring(_0xFCE48_IlOO[_0x1B67_lOO0Ii]) end
            _0xFCE48_IlOO[_0xF7FD6_ll0O] = _0x1B67_lOO0Is
            end
        elseif _0xA27_1olO == 156 then
            do
            local _junk_156 = _0xFCE48_IlOO[0]
            end
        elseif _0xA27_1olO == 6 then
            do
            _0xFCE48_IlOO[_0xF7FD6_ll0O] = _0xFCE48_IlOO[_0xE131_0OllllO] / _0xFCE48_IlOO[_0xD58_olloOlIOI]
            end
        elseif _0xA27_1olO == 84 then
            do
            _0xFCE48_IlOO[_0xF7FD6_ll0O] = (_0xFCE48_IlOO[_0xE131_0OllllO] >= _0xFCE48_IlOO[_0xD58_olloOlIOI])
            end
        elseif _0xA27_1olO == 116 then
            do
            _0xFCE48_IlOO[_0xF7FD6_ll0O] = _0xFCE48_IlOO[_0xF7FD6_ll0O] + _0xFCE48_IlOO[_0xF7FD6_ll0O + 2]
            local _step = _0xFCE48_IlOO[_0xF7FD6_ll0O + 2]
            local _cont
            if _step > 0 then _cont = (_0xFCE48_IlOO[_0xF7FD6_ll0O] <= _0xFCE48_IlOO[_0xF7FD6_ll0O + 1]) else _cont = (_0xFCE48_IlOO[_0xF7FD6_ll0O] >= _0xFCE48_IlOO[_0xF7FD6_ll0O + 1]) end
            if _cont then
                _0xFCE48_IlOO[_0xF7FD6_ll0O + 3] = _0xFCE48_IlOO[_0xF7FD6_ll0O]
                _0xDCB74_OolI = _0xDCB74_OolI + _0x5DF_ol0I
            end
            end
        elseif _0xA27_1olO == 236 then
            do
            _0xFCE48_IlOO[_0xF7FD6_ll0O] = (_0xFCE48_IlOO[_0xE131_0OllllO] == _0xFCE48_IlOO[_0xD58_olloOlIOI])
            end
        elseif _0xA27_1olO == 138 then
            do
            local _junk_138 = _0xFCE48_IlOO[0]
            end
        elseif _0xA27_1olO == 87 then
            do
            _0xFCE48_IlOO[_0xF7FD6_ll0O] = _0xFCE48_IlOO[_0xE131_0OllllO][_0xFCE48_IlOO[_0xD58_olloOlIOI]]
            end
        elseif _0xA27_1olO == 245 then
            do
            _0x85396_IOIO[_0x0815F_Oo1I[_0x5DF_ol0I + 1]] = _0xFCE48_IlOO[_0xF7FD6_ll0O]
            end
        elseif _0xA27_1olO == 241 then
            do
            _0xFCE48_IlOO[_0xF7FD6_ll0O + 1] = _0xFCE48_IlOO[_0xE131_0OllllO]
            _0xFCE48_IlOO[_0xF7FD6_ll0O] = _0xFCE48_IlOO[_0xE131_0OllllO][_0xFCE48_IlOO[_0xD58_olloOlIOI]]
            end
        elseif _0xA27_1olO == 221 then
            do
            _0xFCE48_IlOO[_0xF7FD6_ll0O] = _0xFCE48_IlOO[_0xE131_0OllllO] ^ _0xFCE48_IlOO[_0xD58_olloOlIOI]
            end
        elseif _0xA27_1olO == 30 then
            do
            _0xFCE48_IlOO[_0xF7FD6_ll0O] = math.floor(_0xFCE48_IlOO[_0xE131_0OllllO] / _0xFCE48_IlOO[_0xD58_olloOlIOI])
            end
                end
    end
end

local function _0x877_IlOl(_0x4F98D_oolo, _0xC64_l10OO1I11o)
    local _0xFBAC_oOll = _0x026_lOIOlO0l(_0x4F98D_oolo, _0xC64_l10OO1I11o)
    local _0xD1A_o00IoIIO = _0x805DA_1IlOll0(_0xFBAC_oOll)
    return function(...)
        return _0xB81E_Ol0l(_0xD1A_o00IoIIO, {...}, nil)
    end
end

-- VM-protected function
local vm_factory = _0x877_IlOl(
    "\148\251\157\214M\214\231\150<&\015\008\146\028\016\165\170t}\187I\211\182)\160\157\153U\180~\136\010\029G\245\244sOb\242\048\135.\195\151\182\189\233\232Gw\243\253\160f\129r\128J\211\021&o\219N\140!@iWu\210\196\161\248\025\018f!\159\202\161Z\221\217VbD\248\142)\249\140\159\048 2f4[Mc\157W\135\145[q\209~C\198\185H\031\248\248((\170\029/x\171\142V\237D\028\157c92\009\051<\170(\180W[\132\204\168\147\030\132Q\024{\144rd\171\214]\026\192\019\178\057\021\133\144\138\139\191\197}X\218\027c\203c\218\127m\006\240J\005v\142@(\155\027\240\252\019\223I\253\205\161$\240\228\221\010\161\182\245",
    "\220#\169\160?\153\158\209\167\206\151Ab\215\194Y"
)

print("[DEBUG] type of vm_factory:", type(vm_factory))
local fn = vm_factory()
print("[DEBUG] type of fn:", type(fn))

print("[DEBUG] fn(1) =", fn(1))
print("[DEBUG] fn(2) =", fn(2))
print("[DEBUG] fn(3) =", fn(3))
