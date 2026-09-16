-- NZL VM Extended Tests

-- NZL VM Runtime (build 00000064)
local _0xA6A_1Ilo = string.byte
local _0x5F1_OoOI = string.sub
local _0x1DC4_l0Il = string.char
local _0x69CC_1OI1l = table.insert
local _0x1D2_OlIoOlOl0I = table.unpack or unpack
local _0x18F1_lOI1o1O0 = bit32.bxor

local function _0xE81_lOl1(_0x5FBB_O01l0, _0x091B_o01o)
    local _0xC37_IloI = {}
    for _0xDCC70_lll0 = 0, 255 do _0xC37_IloI[_0xDCC70_lll0] = _0xDCC70_lll0 end
    local _0x9CCC_olOIIOI = 0
    local _0x9E777_OI0o = #_0x091B_o01o
    for _0xDCC70_lll0 = 0, 255 do
        _0x9CCC_olOIIOI = (_0x9CCC_olOIIOI + _0xC37_IloI[_0xDCC70_lll0] + _0xA6A_1Ilo(_0x091B_o01o, (_0xDCC70_lll0 % _0x9E777_OI0o) + 1)) % 256
        _0xC37_IloI[_0xDCC70_lll0], _0xC37_IloI[_0x9CCC_olOIIOI] = _0xC37_IloI[_0x9CCC_olOIIOI], _0xC37_IloI[_0xDCC70_lll0]
    end
    local _0xFB902_0lO0 = {}
    local _0xDCC70_lll02 = 0
    local _0x9CCC_olOIIOI2 = 0
    for _0x6A799_OOO1l = 1, #_0x5FBB_O01l0 do
        _0xDCC70_lll02 = (_0xDCC70_lll02 + 1) % 256
        _0x9CCC_olOIIOI2 = (_0x9CCC_olOIIOI2 + _0xC37_IloI[_0xDCC70_lll02]) % 256
        _0xC37_IloI[_0xDCC70_lll02], _0xC37_IloI[_0x9CCC_olOIIOI2] = _0xC37_IloI[_0x9CCC_olOIIOI2], _0xC37_IloI[_0xDCC70_lll02]
        local _0x58112_OoOI = _0xC37_IloI[(_0xC37_IloI[_0xDCC70_lll02] + _0xC37_IloI[_0x9CCC_olOIIOI2]) % 256]
        _0xFB902_0lO0[_0x6A799_OOO1l] = _0x1DC4_l0Il(_0x18F1_lOI1o1O0(_0xA6A_1Ilo(_0x5FBB_O01l0, _0x6A799_OOO1l), _0x58112_OoOI))
    end
    return table.concat(_0xFB902_0lO0)
end

local function _nzl_read_u32(_0xCB5_ll11o1O1O, _0xCDF9_O0IO)
    local _0x85E15_lIOOI = _0xA6A_1Ilo(_0xCB5_ll11o1O1O, _0xCDF9_O0IO)
    local _0xF61B7_loll = _0xA6A_1Ilo(_0xCB5_ll11o1O1O, _0xCDF9_O0IO + 1)
    local _0x1F5DE_o0o1ol1 = _0xA6A_1Ilo(_0xCB5_ll11o1O1O, _0xCDF9_O0IO + 2)
    local _0x6362_OIOlI0 = _0xA6A_1Ilo(_0xCB5_ll11o1O1O, _0xCDF9_O0IO + 3)
    return _0x85E15_lIOOI + _0xF61B7_loll * 256 + _0x1F5DE_o0o1ol1 * 65536 + _0x6362_OIOlI0 * 16777216, _0xCDF9_O0IO + 4
end

local function _nzl_read_i32(_0xCB5_ll11o1O1O, _0xCDF9_O0IO)
    local _0x18BB2_lIOIoIo, _0xCDF9_O0IO = _nzl_read_u32(_0xCB5_ll11o1O1O, _0xCDF9_O0IO)
    if _0x18BB2_lIOIoIo >= 2147483648 then _0x18BB2_lIOIoIo = _0x18BB2_lIOIoIo - 4294967296 end
    return _0x18BB2_lIOIoIo, _0xCDF9_O0IO
end

local function _nzl_read_double(_0xCB5_ll11o1O1O, _0xCDF9_O0IO)
    local _0x85E15_lIOOI = _0xA6A_1Ilo(_0xCB5_ll11o1O1O, _0xCDF9_O0IO)
    local _0xF61B7_loll = _0xA6A_1Ilo(_0xCB5_ll11o1O1O, _0xCDF9_O0IO + 1)
    local _0x1F5DE_o0o1ol1 = _0xA6A_1Ilo(_0xCB5_ll11o1O1O, _0xCDF9_O0IO + 2)
    local _0x6362_OIOlI0 = _0xA6A_1Ilo(_0xCB5_ll11o1O1O, _0xCDF9_O0IO + 3)
    local b4 = _0xA6A_1Ilo(_0xCB5_ll11o1O1O, _0xCDF9_O0IO + 4)
    local b5 = _0xA6A_1Ilo(_0xCB5_ll11o1O1O, _0xCDF9_O0IO + 5)
    local b6 = _0xA6A_1Ilo(_0xCB5_ll11o1O1O, _0xCDF9_O0IO + 6)
    local b7 = _0xA6A_1Ilo(_0xCB5_ll11o1O1O, _0xCDF9_O0IO + 7)
    local sign = 1
    if b7 >= 128 then sign = -1; b7 = b7 - 128 end
    local exp = b7 * 16 + math.floor(b6 / 16)
    local mant = (b6 % 16) * 281474976710656 + b5 * 1099511627776 + b4 * 4294967296
        + _0x6362_OIOlI0 * 16777216 + _0x1F5DE_o0o1ol1 * 65536 + _0xF61B7_loll * 256 + _0x85E15_lIOOI
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
    return val, _0xCDF9_O0IO + 8
end

local function _0x46B_O0l0o(_0xCB5_ll11o1O1O, _0xCDF9_O0IO)
    _0xCDF9_O0IO = _0xCDF9_O0IO or 1
    local _0x4A8BB_0lIIll = {}

    _0x4A8BB_0lIIll.num_params, _0xCDF9_O0IO = _nzl_read_u32(_0xCB5_ll11o1O1O, _0xCDF9_O0IO)
    _0x4A8BB_0lIIll.is_vararg = _0xA6A_1Ilo(_0xCB5_ll11o1O1O, _0xCDF9_O0IO) ~= 0
    _0xCDF9_O0IO = _0xCDF9_O0IO + 1
    _0x4A8BB_0lIIll.max_stack, _0xCDF9_O0IO = _nzl_read_u32(_0xCB5_ll11o1O1O, _0xCDF9_O0IO)

    _0x651_OOoo1l0lO, _0xCDF9_O0IO = _nzl_read_u32(_0xCB5_ll11o1O1O, _0xCDF9_O0IO)
    _0x4A8BB_0lIIll.upvalues = {}
    for _0x7C1C0_l1I0 = 1, _0x651_OOoo1l0lO do
        local _0x703A0_0I1lI10 = _0xA6A_1Ilo(_0xCB5_ll11o1O1O, _0xCDF9_O0IO) ~= 0
        _0xCDF9_O0IO = _0xCDF9_O0IO + 1
        local _0xE0C_lOl1Il
        _0xE0C_lOl1Il, _0xCDF9_O0IO = _nzl_read_u32(_0xCB5_ll11o1O1O, _0xCDF9_O0IO)
        _0x4A8BB_0lIIll.upvalues[_0x7C1C0_l1I0] = {instack = _0x703A0_0I1lI10, index = _0xE0C_lOl1Il}
    end

    _0xEE914_lIolOII, _0xCDF9_O0IO = _nzl_read_u32(_0xCB5_ll11o1O1O, _0xCDF9_O0IO)
    _0x4A8BB_0lIIll.constants = {}
    for _0x7C1C0_l1I0 = 1, _0xEE914_lIolOII do
        local _0xD56_1llI = _0xA6A_1Ilo(_0xCB5_ll11o1O1O, _0xCDF9_O0IO)
        _0xCDF9_O0IO = _0xCDF9_O0IO + 1
        if _0xD56_1llI == 0 then
            _0x4A8BB_0lIIll.constants[_0x7C1C0_l1I0] = nil
        elseif _0xD56_1llI == 1 then
            _0x4A8BB_0lIIll.constants[_0x7C1C0_l1I0] = (_0xA6A_1Ilo(_0xCB5_ll11o1O1O, _0xCDF9_O0IO) ~= 0)
            _0xCDF9_O0IO = _0xCDF9_O0IO + 1
        elseif _0xD56_1llI == 2 then
            local _0xA39_ll0OIO0IOO
            _0xA39_ll0OIO0IOO, _0xCDF9_O0IO = _nzl_read_double(_0xCB5_ll11o1O1O, _0xCDF9_O0IO)
            _0x4A8BB_0lIIll.constants[_0x7C1C0_l1I0] = _0xA39_ll0OIO0IOO
        elseif _0xD56_1llI == 3 then
            local _0xA952E_0lII
            _0xA952E_0lII, _0xCDF9_O0IO = _nzl_read_u32(_0xCB5_ll11o1O1O, _0xCDF9_O0IO)
            _0x4A8BB_0lIIll.constants[_0x7C1C0_l1I0] = _0x5F1_OoOI(_0xCB5_ll11o1O1O, _0xCDF9_O0IO, _0xCDF9_O0IO + _0xA952E_0lII - 1)
            _0xCDF9_O0IO = _0xCDF9_O0IO + _0xA952E_0lII
        elseif _0xD56_1llI == 4 then
            local _0xA39_ll0OIO0IOO
            _0xA39_ll0OIO0IOO, _0xCDF9_O0IO = _nzl_read_u32(_0xCB5_ll11o1O1O, _0xCDF9_O0IO)
            _0x4A8BB_0lIIll.constants[_0x7C1C0_l1I0] = {__proto_ref = _0xA39_ll0OIO0IOO}
        end
    end

    _0x332BD_Ol1IOIoI, _0xCDF9_O0IO = _nzl_read_u32(_0xCB5_ll11o1O1O, _0xCDF9_O0IO)
    _0x4A8BB_0lIIll.code = {}
    for _0x7C1C0_l1I0 = 1, _0x332BD_Ol1IOIoI do
        local instr = {}
        instr.op = _0xA6A_1Ilo(_0xCB5_ll11o1O1O, _0xCDF9_O0IO)
        instr.a = _0xA6A_1Ilo(_0xCB5_ll11o1O1O, _0xCDF9_O0IO + 1)
        instr.b = _0xA6A_1Ilo(_0xCB5_ll11o1O1O, _0xCDF9_O0IO + 2)
        instr.c = _0xA6A_1Ilo(_0xCB5_ll11o1O1O, _0xCDF9_O0IO + 3)
        instr.k, _ = _nzl_read_i32(_0xCB5_ll11o1O1O, _0xCDF9_O0IO + 4)
        _0x4A8BB_0lIIll.code[_0x7C1C0_l1I0] = instr
        _0xCDF9_O0IO = _0xCDF9_O0IO + 8
    end

    _0xD1A8F_lIoo, _0xCDF9_O0IO = _nzl_read_u32(_0xCB5_ll11o1O1O, _0xCDF9_O0IO)
    _0x4A8BB_0lIIll.protos = {}
    for _0x7C1C0_l1I0 = 1, _0xD1A8F_lIoo do
        _0x4A8BB_0lIIll.protos[_0x7C1C0_l1I0], _0xCDF9_O0IO = _0x46B_O0l0o(_0xCB5_ll11o1O1O, _0xCDF9_O0IO)
    end

    return _0x4A8BB_0lIIll, _0xCDF9_O0IO
end

local function _0xC535_I0IIlIIlo(_0x59B_11o0OIO, _0xADF_lIII, _0x217_l0OoO1oI00)
    local _0xBAE03_olOl = {}
    local _0x069_0IlO0llOIl = _0x59B_11o0OIO.code
    local _0x95ADE_loo00 = _0x59B_11o0OIO.constants
    local _0xEAE6_10Il0l1 = getfenv and getfenv() or _G
    local _0xC3C_IoOIo = 1
    local _0xB45_IIOO, _0xCCE_llIO1loI, _0x39437_I0o0Ol, _0xED0_Ioll, _0x34445_O0lo, _0xF97_OlIIlOl
    local _0x545A_o00lol
    local _0xE6A2_IOIl0

    if _0xADF_lIII then
        for _0xE6A2_IOIl0 = 1, #_0xADF_lIII do
            _0xBAE03_olOl[_0xE6A2_IOIl0 - 1] = _0xADF_lIII[_0xE6A2_IOIl0]
        end
    end

    while true do
        _0xB45_IIOO = _0x069_0IlO0llOIl[_0xC3C_IoOIo]
        if not _0xB45_IIOO then break end
        _0xCCE_llIO1loI = _0xB45_IIOO.op
        _0x39437_I0o0Ol = _0xB45_IIOO.a
        _0xED0_Ioll = _0xB45_IIOO.b
        _0x34445_O0lo = _0xB45_IIOO.c
        _0xF97_OlIIlOl = _0xB45_IIOO.k
        _0xC3C_IoOIo = _0xC3C_IoOIo + 1

        if _0xCCE_llIO1loI == 160 then
            do
            _0xBAE03_olOl[_0x39437_I0o0Ol + 1] = _0xBAE03_olOl[_0xED0_Ioll]
            _0xBAE03_olOl[_0x39437_I0o0Ol] = _0xBAE03_olOl[_0xED0_Ioll][_0xBAE03_olOl[_0x34445_O0lo]]
            end
        elseif _0xCCE_llIO1loI == 112 then
            do
            local _junk_112 = _0xBAE03_olOl[0]
            end
        elseif _0xCCE_llIO1loI == 85 then
            do
            local _nzl_checksum = nil
            end
        elseif _0xCCE_llIO1loI == 131 then
            do
            _0xBAE03_olOl[_0x39437_I0o0Ol] = (_0xBAE03_olOl[_0xED0_Ioll] < _0xBAE03_olOl[_0x34445_O0lo])
            end
        elseif _0xCCE_llIO1loI == 101 then
            do
            _0xBAE03_olOl[_0x39437_I0o0Ol] = _0xBAE03_olOl[_0xED0_Ioll] * _0xBAE03_olOl[_0x34445_O0lo]
            end
        elseif _0xCCE_llIO1loI == 13 then
            do
            _0xBAE03_olOl[_0x39437_I0o0Ol] = not _0xBAE03_olOl[_0xED0_Ioll]
            end
        elseif _0xCCE_llIO1loI == 239 then
            do
            local _nzl_nop = nil
            end
        elseif _0xCCE_llIO1loI == 250 then
            do
            _0xBAE03_olOl[_0x39437_I0o0Ol] = (_0xBAE03_olOl[_0xED0_Ioll] ~= _0xBAE03_olOl[_0x34445_O0lo])
            end
        elseif _0xCCE_llIO1loI == 72 then
            do
            _0xBAE03_olOl[_0x39437_I0o0Ol] = _0xBAE03_olOl[_0xED0_Ioll][_0x95ADE_loo00[_0xF97_OlIIlOl + 1]]
            end
        elseif _0xCCE_llIO1loI == 135 then
            do
            _0xBAE03_olOl[_0x39437_I0o0Ol] = _0xBAE03_olOl[_0xED0_Ioll] + _0xBAE03_olOl[_0x34445_O0lo]
            end
        elseif _0xCCE_llIO1loI == 214 then
            do
            _0xBAE03_olOl[_0x39437_I0o0Ol] = _0xBAE03_olOl[_0xED0_Ioll] % _0xBAE03_olOl[_0x34445_O0lo]
            end
        elseif _0xCCE_llIO1loI == 154 then
            do
            _0xEAE6_10Il0l1[_0x95ADE_loo00[_0xF97_OlIIlOl + 1]] = _0xBAE03_olOl[_0x39437_I0o0Ol]
            end
        elseif _0xCCE_llIO1loI == 37 then
            do
            if _0xED0_Ioll >= 128 then _0xBAE03_olOl[_0x39437_I0o0Ol] = _0xED0_Ioll - 256 else _0xBAE03_olOl[_0x39437_I0o0Ol] = _0xED0_Ioll end
            end
        elseif _0xCCE_llIO1loI == 168 then
            do
            if _0xBAE03_olOl[_0x39437_I0o0Ol + 3] ~= nil then
                _0xBAE03_olOl[_0x39437_I0o0Ol + 2] = _0xBAE03_olOl[_0x39437_I0o0Ol + 3]
                _0xC3C_IoOIo = _0xC3C_IoOIo + _0xF97_OlIIlOl
            end
            end
        elseif _0xCCE_llIO1loI == 174 then
            do
            local _rets = {_0xBAE03_olOl[_0x39437_I0o0Ol](_0xBAE03_olOl[_0x39437_I0o0Ol + 1], _0xBAE03_olOl[_0x39437_I0o0Ol + 2])}
            for _i = 1, _0xED0_Ioll do _0xBAE03_olOl[_0x39437_I0o0Ol + 2 + _i] = _rets[_i] end
            end
        elseif _0xCCE_llIO1loI == 87 then
            do
            _0xBAE03_olOl[_0x39437_I0o0Ol] = (_0xED0_Ioll ~= 0)
            end
        elseif _0xCCE_llIO1loI == 202 then
            do
            _0xBAE03_olOl[_0x39437_I0o0Ol] = _0xBAE03_olOl[_0xED0_Ioll]
            end
        elseif _0xCCE_llIO1loI == 155 then
            do
            _0xBAE03_olOl[_0x39437_I0o0Ol] = _0xBAE03_olOl[_0xED0_Ioll] ^ _0xBAE03_olOl[_0x34445_O0lo]
            end
        elseif _0xCCE_llIO1loI == 60 then
            do
            local _junk_60 = _0xBAE03_olOl[0]
            end
        elseif _0xCCE_llIO1loI == 88 then
            do
            _0xBAE03_olOl[_0x39437_I0o0Ol] = #_0xBAE03_olOl[_0xED0_Ioll]
            end
        elseif _0xCCE_llIO1loI == 116 then
            do
            if _0xBAE03_olOl[_0x39437_I0o0Ol] then _0xC3C_IoOIo = _0xC3C_IoOIo + _0xF97_OlIIlOl end
            end
        elseif _0xCCE_llIO1loI == 234 then
            do
            if _0x217_l0OoO1oI00 and _0x217_l0OoO1oI00[_0xED0_Ioll] then
                local _uv = _0x217_l0OoO1oI00[_0xED0_Ioll]
                _0xBAE03_olOl[_0x39437_I0o0Ol] = _uv[1][_uv[2]]
            else
                _0xBAE03_olOl[_0x39437_I0o0Ol] = nil
            end
            end
        elseif _0xCCE_llIO1loI == 74 then
            do
            _0xBAE03_olOl[_0x39437_I0o0Ol] = _0xBAE03_olOl[_0xED0_Ioll][_0xBAE03_olOl[_0x34445_O0lo]]
            end
        elseif _0xCCE_llIO1loI == 36 then
            do
            _0xBAE03_olOl[_0x39437_I0o0Ol] = (_0xBAE03_olOl[_0xED0_Ioll] <= _0xBAE03_olOl[_0x34445_O0lo])
            end
        elseif _0xCCE_llIO1loI == 42 then
            do
            _0xBAE03_olOl[_0x39437_I0o0Ol] = _0xBAE03_olOl[_0xED0_Ioll] / _0xBAE03_olOl[_0x34445_O0lo]
            end
        elseif _0xCCE_llIO1loI == 106 then
            do
            _0xBAE03_olOl[_0x39437_I0o0Ol] = (_0xBAE03_olOl[_0xED0_Ioll] > _0xBAE03_olOl[_0x34445_O0lo])
            end
        elseif _0xCCE_llIO1loI == 201 then
            do
            _0xBAE03_olOl[_0x39437_I0o0Ol] = {}
            end
        elseif _0xCCE_llIO1loI == 9 then
            do
            _0xBAE03_olOl[_0x39437_I0o0Ol] = -_0xBAE03_olOl[_0xED0_Ioll]
            end
        elseif _0xCCE_llIO1loI == 96 then
            do
            _0xBAE03_olOl[_0x39437_I0o0Ol] = math.floor(_0xBAE03_olOl[_0xED0_Ioll] / _0xBAE03_olOl[_0x34445_O0lo])
            end
        elseif _0xCCE_llIO1loI == 92 then
            do
            local _0x545A_o00lols = ""
            for _0x545A_o00loli = _0xED0_Ioll, _0x34445_O0lo do _0x545A_o00lols = _0x545A_o00lols .. tostring(_0xBAE03_olOl[_0x545A_o00loli]) end
            _0xBAE03_olOl[_0x39437_I0o0Ol] = _0x545A_o00lols
            end
        elseif _0xCCE_llIO1loI == 203 then
            do
            for _0x545A_o00loli = 1, _0xED0_Ioll do _0xBAE03_olOl[_0x39437_I0o0Ol][_0x34445_O0lo + _0x545A_o00loli] = _0xBAE03_olOl[_0x39437_I0o0Ol + _0x545A_o00loli] end
            end
        elseif _0xCCE_llIO1loI == 124 then
            do
            local _args = {}
            for _i = 1, _0xED0_Ioll - 1 do _args[_i] = _0xBAE03_olOl[_0x39437_I0o0Ol + _i] end
            local _fn = _0xBAE03_olOl[_0x39437_I0o0Ol]
            local _rets = {_fn(_0x1D2_OlIoOlOl0I(_args, 1, _0xED0_Ioll - 1))}
            local _need = _0x34445_O0lo - 1
            if _need == -1 then _need = #_rets end
            for _i = 1, _need do _0xBAE03_olOl[_0x39437_I0o0Ol + _i - 1] = _rets[_i] end
            end
        elseif _0xCCE_llIO1loI == 153 then
            do
            local _junk_153 = _0xBAE03_olOl[0]
            end
        elseif _0xCCE_llIO1loI == 253 then
            do
            _0xBAE03_olOl[_0x39437_I0o0Ol] = _0xEAE6_10Il0l1[_0x95ADE_loo00[_0xF97_OlIIlOl + 1]]
            end
        elseif _0xCCE_llIO1loI == 215 then
            do
            if _0xED0_Ioll == 0 then return end
            local _rets = {}
            for _i = 1, _0xED0_Ioll do _rets[_i] = _0xBAE03_olOl[_0x39437_I0o0Ol + _i - 1] end
            return _0x1D2_OlIoOlOl0I(_rets, 1, _0xED0_Ioll)
            end
        elseif _0xCCE_llIO1loI == 64 then
            do
            if not _0xBAE03_olOl[_0x39437_I0o0Ol] then _0xC3C_IoOIo = _0xC3C_IoOIo + _0xF97_OlIIlOl end
            end
        elseif _0xCCE_llIO1loI == 52 then
            do
            _0xBAE03_olOl[_0x39437_I0o0Ol] = _0xBAE03_olOl[_0xED0_Ioll] and _0xBAE03_olOl[_0x34445_O0lo]
            end
        elseif _0xCCE_llIO1loI == 65 then
            do
            _0xBAE03_olOl[_0x39437_I0o0Ol][_0xBAE03_olOl[_0xED0_Ioll]] = _0xBAE03_olOl[_0x34445_O0lo]
            end
        elseif _0xCCE_llIO1loI == 179 then
            do
            _0xBAE03_olOl[_0x39437_I0o0Ol] = _0x95ADE_loo00[_0xF97_OlIIlOl + 1]
            end
        elseif _0xCCE_llIO1loI == 219 then
            do
            local _args = {}
            for _i = 1, _0xED0_Ioll - 1 do _args[_i] = _0xBAE03_olOl[_0x39437_I0o0Ol + _i] end
            return _0xBAE03_olOl[_0x39437_I0o0Ol](_0x1D2_OlIoOlOl0I(_args, 1, _0xED0_Ioll - 1))
            end
        elseif _0xCCE_llIO1loI == 115 then
            do
            _0xBAE03_olOl[_0x39437_I0o0Ol] = _0xBAE03_olOl[_0xED0_Ioll] or _0xBAE03_olOl[_0x34445_O0lo]
            end
        elseif _0xCCE_llIO1loI == 172 then
            do
            _0xBAE03_olOl[_0x39437_I0o0Ol] = _0xBAE03_olOl[_0xED0_Ioll] - _0xBAE03_olOl[_0x34445_O0lo]
            end
        elseif _0xCCE_llIO1loI == 233 then
            do
            _0xBAE03_olOl[_0x39437_I0o0Ol] = _0xBAE03_olOl[_0x39437_I0o0Ol] - _0xBAE03_olOl[_0x39437_I0o0Ol + 2]
            _0xC3C_IoOIo = _0xC3C_IoOIo + _0xF97_OlIIlOl
            end
        elseif _0xCCE_llIO1loI == 44 then
            do
            _0xBAE03_olOl[_0x39437_I0o0Ol] = _0xBAE03_olOl[_0x39437_I0o0Ol] + _0xBAE03_olOl[_0x39437_I0o0Ol + 2]
            local _step = _0xBAE03_olOl[_0x39437_I0o0Ol + 2]
            local _cont
            if _step > 0 then _cont = (_0xBAE03_olOl[_0x39437_I0o0Ol] <= _0xBAE03_olOl[_0x39437_I0o0Ol + 1]) else _cont = (_0xBAE03_olOl[_0x39437_I0o0Ol] >= _0xBAE03_olOl[_0x39437_I0o0Ol + 1]) end
            if _cont then
                _0xBAE03_olOl[_0x39437_I0o0Ol + 3] = _0xBAE03_olOl[_0x39437_I0o0Ol]
                _0xC3C_IoOIo = _0xC3C_IoOIo + _0xF97_OlIIlOl
            end
            end
        elseif _0xCCE_llIO1loI == 33 then
            do
            _0xC3C_IoOIo = _0xC3C_IoOIo + _0xF97_OlIIlOl
            end
        elseif _0xCCE_llIO1loI == 183 then
            do
            for _0x545A_o00loli = _0x39437_I0o0Ol, _0x39437_I0o0Ol + _0xED0_Ioll do _0xBAE03_olOl[_0x545A_o00loli] = nil end
            end
        elseif _0xCCE_llIO1loI == 181 then
            do
            local _pref = _0x95ADE_loo00[_0xF97_OlIIlOl + 1]
            if type(_pref) == "table" and _pref.__proto_ref then
                local _p = _0x59B_11o0OIO.protos[_pref.__proto_ref + 1]
                local _captured_R = _0xBAE03_olOl
                local _parent_upvals = _0x217_l0OoO1oI00
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

                _0xBAE03_olOl[_0x39437_I0o0Ol] = function(...)
                    return _0xC535_I0IIlIIlo(_p, {...}, _child_upvals)
                end
            end
            end
        elseif _0xCCE_llIO1loI == 76 then
            do
            if _0x217_l0OoO1oI00 and _0x217_l0OoO1oI00[_0xED0_Ioll] then
                local _uv = _0x217_l0OoO1oI00[_0xED0_Ioll]
                _uv[1][_uv[2]] = _0xBAE03_olOl[_0x39437_I0o0Ol]
            end
            end
        elseif _0xCCE_llIO1loI == 94 then
            do
            _0xBAE03_olOl[_0x39437_I0o0Ol] = nil
            end
        elseif _0xCCE_llIO1loI == 16 then
            do
            while true do end
            end
        elseif _0xCCE_llIO1loI == 140 then
            do
            _0xBAE03_olOl[_0x39437_I0o0Ol] = (_0xBAE03_olOl[_0xED0_Ioll] >= _0xBAE03_olOl[_0x34445_O0lo])
            end
        elseif _0xCCE_llIO1loI == 139 then
            do
            _0xBAE03_olOl[_0x39437_I0o0Ol] = (_0xBAE03_olOl[_0xED0_Ioll] == _0xBAE03_olOl[_0x34445_O0lo])
            end
        elseif _0xCCE_llIO1loI == 21 then
            do
            local _nzl_close = nil
            end
        elseif _0xCCE_llIO1loI == 122 then
            do
            _0xBAE03_olOl[_0x39437_I0o0Ol][_0x95ADE_loo00[_0xF97_OlIIlOl + 1]] = _0xBAE03_olOl[_0xED0_Ioll]
            end
        elseif _0xCCE_llIO1loI == 20 then
            do
            local _junk_20 = _0xBAE03_olOl[0]
            end
                end
    end
end

local function _0xE5CB_0OlO(_0x527_O0OOlO, _0xCEF_lIII1l)
    local _0xB6A_lI1Io = _0xE81_lOl1(_0x527_O0OOlO, _0xCEF_lIII1l)
    local _0x79536_lll1Ilo = _0x46B_O0l0o(_0xB6A_lI1Io)
    return function(...)
        return _0xC535_I0IIlIIlo(_0x79536_lll1Ilo, {...}, nil)
    end
end

-- VM-protected function
local vm_simple_return_factory = _0xE5CB_0OlO(
    "d9\029\171\053\056\234>\170\027\173\002*\021\238\156\208j\244\228\025\205vk\178\210s\249\204\203\234\230Ji\240\172\175\208\004\028\171\231\145\193_\238\242b^\174\057\185z\027\212U>!\179)x\006uy\158X\234\048\234\133\253\240M\160o\016[}\130N\201\130\196)\207\248[0\185c\178\159\155\050y",
    "\188\000\147\216\004\230\147e\229\250@\242Hi\146\199"
)

local vm_simple_return = vm_simple_return_factory()

print("[simple_return] =", vm_simple_return())

-- NZL VM Runtime (build 00000065)
local _0x8BE_1Io1lIIO = string.byte
local _0xC1B_IlI0Io0lI = string.sub
local _0xE8B69_0IIOo1 = string.char
local _0x1130_o1oO = table.insert
local _0xBF7_Iol0lo = table.unpack or unpack
local _0x1E8BC_IlOl = bit32.bxor

local function _0x865_loOOloOl0(_0xBA21_lo01, _0x6564_OO11)
    local _0xB2569_III0 = {}
    for _0xA2DE_OIOoI = 0, 255 do _0xB2569_III0[_0xA2DE_OIOoI] = _0xA2DE_OIOoI end
    local _0x6F47B_IIool = 0
    local _0x109C2_oOl0 = #_0x6564_OO11
    for _0xA2DE_OIOoI = 0, 255 do
        _0x6F47B_IIool = (_0x6F47B_IIool + _0xB2569_III0[_0xA2DE_OIOoI] + _0x8BE_1Io1lIIO(_0x6564_OO11, (_0xA2DE_OIOoI % _0x109C2_oOl0) + 1)) % 256
        _0xB2569_III0[_0xA2DE_OIOoI], _0xB2569_III0[_0x6F47B_IIool] = _0xB2569_III0[_0x6F47B_IIool], _0xB2569_III0[_0xA2DE_OIOoI]
    end
    local _0x4B05D_O1OO = {}
    local _0xA2DE_OIOoI2 = 0
    local _0x6F47B_IIool2 = 0
    for _0x292_1O1IOIl = 1, #_0xBA21_lo01 do
        _0xA2DE_OIOoI2 = (_0xA2DE_OIOoI2 + 1) % 256
        _0x6F47B_IIool2 = (_0x6F47B_IIool2 + _0xB2569_III0[_0xA2DE_OIOoI2]) % 256
        _0xB2569_III0[_0xA2DE_OIOoI2], _0xB2569_III0[_0x6F47B_IIool2] = _0xB2569_III0[_0x6F47B_IIool2], _0xB2569_III0[_0xA2DE_OIOoI2]
        local _0x7D10_1Oll = _0xB2569_III0[(_0xB2569_III0[_0xA2DE_OIOoI2] + _0xB2569_III0[_0x6F47B_IIool2]) % 256]
        _0x4B05D_O1OO[_0x292_1O1IOIl] = _0xE8B69_0IIOo1(_0x1E8BC_IlOl(_0x8BE_1Io1lIIO(_0xBA21_lo01, _0x292_1O1IOIl), _0x7D10_1Oll))
    end
    return table.concat(_0x4B05D_O1OO)
end

local function _nzl_read_u32(_0xAD23_11Ool0l, _0x7F5_llOI)
    local _0x83FA_IOolOIIo = _0x8BE_1Io1lIIO(_0xAD23_11Ool0l, _0x7F5_llOI)
    local _0x81761_IooOOO = _0x8BE_1Io1lIIO(_0xAD23_11Ool0l, _0x7F5_llOI + 1)
    local _0xE8B_110l0O = _0x8BE_1Io1lIIO(_0xAD23_11Ool0l, _0x7F5_llOI + 2)
    local _0xA05A7_l0OO = _0x8BE_1Io1lIIO(_0xAD23_11Ool0l, _0x7F5_llOI + 3)
    return _0x83FA_IOolOIIo + _0x81761_IooOOO * 256 + _0xE8B_110l0O * 65536 + _0xA05A7_l0OO * 16777216, _0x7F5_llOI + 4
end

local function _nzl_read_i32(_0xAD23_11Ool0l, _0x7F5_llOI)
    local _0xA87_OIIOl0Ol1, _0x7F5_llOI = _nzl_read_u32(_0xAD23_11Ool0l, _0x7F5_llOI)
    if _0xA87_OIIOl0Ol1 >= 2147483648 then _0xA87_OIIOl0Ol1 = _0xA87_OIIOl0Ol1 - 4294967296 end
    return _0xA87_OIIOl0Ol1, _0x7F5_llOI
end

local function _nzl_read_double(_0xAD23_11Ool0l, _0x7F5_llOI)
    local _0x83FA_IOolOIIo = _0x8BE_1Io1lIIO(_0xAD23_11Ool0l, _0x7F5_llOI)
    local _0x81761_IooOOO = _0x8BE_1Io1lIIO(_0xAD23_11Ool0l, _0x7F5_llOI + 1)
    local _0xE8B_110l0O = _0x8BE_1Io1lIIO(_0xAD23_11Ool0l, _0x7F5_llOI + 2)
    local _0xA05A7_l0OO = _0x8BE_1Io1lIIO(_0xAD23_11Ool0l, _0x7F5_llOI + 3)
    local b4 = _0x8BE_1Io1lIIO(_0xAD23_11Ool0l, _0x7F5_llOI + 4)
    local b5 = _0x8BE_1Io1lIIO(_0xAD23_11Ool0l, _0x7F5_llOI + 5)
    local b6 = _0x8BE_1Io1lIIO(_0xAD23_11Ool0l, _0x7F5_llOI + 6)
    local b7 = _0x8BE_1Io1lIIO(_0xAD23_11Ool0l, _0x7F5_llOI + 7)
    local sign = 1
    if b7 >= 128 then sign = -1; b7 = b7 - 128 end
    local exp = b7 * 16 + math.floor(b6 / 16)
    local mant = (b6 % 16) * 281474976710656 + b5 * 1099511627776 + b4 * 4294967296
        + _0xA05A7_l0OO * 16777216 + _0xE8B_110l0O * 65536 + _0x81761_IooOOO * 256 + _0x83FA_IOolOIIo
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
    return val, _0x7F5_llOI + 8
end

local function _0x2DE_1llO100l(_0xAD23_11Ool0l, _0x7F5_llOI)
    _0x7F5_llOI = _0x7F5_llOI or 1
    local _0x96CE2_I1OIll1I = {}

    _0x96CE2_I1OIll1I.num_params, _0x7F5_llOI = _nzl_read_u32(_0xAD23_11Ool0l, _0x7F5_llOI)
    _0x96CE2_I1OIll1I.is_vararg = _0x8BE_1Io1lIIO(_0xAD23_11Ool0l, _0x7F5_llOI) ~= 0
    _0x7F5_llOI = _0x7F5_llOI + 1
    _0x96CE2_I1OIll1I.max_stack, _0x7F5_llOI = _nzl_read_u32(_0xAD23_11Ool0l, _0x7F5_llOI)

    _0x1C15_0OIO, _0x7F5_llOI = _nzl_read_u32(_0xAD23_11Ool0l, _0x7F5_llOI)
    _0x96CE2_I1OIll1I.upvalues = {}
    for _0x96A_loll = 1, _0x1C15_0OIO do
        local _0x405F_llIO = _0x8BE_1Io1lIIO(_0xAD23_11Ool0l, _0x7F5_llOI) ~= 0
        _0x7F5_llOI = _0x7F5_llOI + 1
        local _0x084C_1OlO
        _0x084C_1OlO, _0x7F5_llOI = _nzl_read_u32(_0xAD23_11Ool0l, _0x7F5_llOI)
        _0x96CE2_I1OIll1I.upvalues[_0x96A_loll] = {instack = _0x405F_llIO, index = _0x084C_1OlO}
    end

    _0x6F2_0I0I0, _0x7F5_llOI = _nzl_read_u32(_0xAD23_11Ool0l, _0x7F5_llOI)
    _0x96CE2_I1OIll1I.constants = {}
    for _0x96A_loll = 1, _0x6F2_0I0I0 do
        local _0x67FE3_OllO = _0x8BE_1Io1lIIO(_0xAD23_11Ool0l, _0x7F5_llOI)
        _0x7F5_llOI = _0x7F5_llOI + 1
        if _0x67FE3_OllO == 0 then
            _0x96CE2_I1OIll1I.constants[_0x96A_loll] = nil
        elseif _0x67FE3_OllO == 1 then
            _0x96CE2_I1OIll1I.constants[_0x96A_loll] = (_0x8BE_1Io1lIIO(_0xAD23_11Ool0l, _0x7F5_llOI) ~= 0)
            _0x7F5_llOI = _0x7F5_llOI + 1
        elseif _0x67FE3_OllO == 2 then
            local _0x1E5_1lIIll
            _0x1E5_1lIIll, _0x7F5_llOI = _nzl_read_double(_0xAD23_11Ool0l, _0x7F5_llOI)
            _0x96CE2_I1OIll1I.constants[_0x96A_loll] = _0x1E5_1lIIll
        elseif _0x67FE3_OllO == 3 then
            local _0xC91_IIOl
            _0xC91_IIOl, _0x7F5_llOI = _nzl_read_u32(_0xAD23_11Ool0l, _0x7F5_llOI)
            _0x96CE2_I1OIll1I.constants[_0x96A_loll] = _0xC1B_IlI0Io0lI(_0xAD23_11Ool0l, _0x7F5_llOI, _0x7F5_llOI + _0xC91_IIOl - 1)
            _0x7F5_llOI = _0x7F5_llOI + _0xC91_IIOl
        elseif _0x67FE3_OllO == 4 then
            local _0x1E5_1lIIll
            _0x1E5_1lIIll, _0x7F5_llOI = _nzl_read_u32(_0xAD23_11Ool0l, _0x7F5_llOI)
            _0x96CE2_I1OIll1I.constants[_0x96A_loll] = {__proto_ref = _0x1E5_1lIIll}
        end
    end

    _0xA230D_IOoI1OOo, _0x7F5_llOI = _nzl_read_u32(_0xAD23_11Ool0l, _0x7F5_llOI)
    _0x96CE2_I1OIll1I.code = {}
    for _0x96A_loll = 1, _0xA230D_IOoI1OOo do
        local instr = {}
        instr.op = _0x8BE_1Io1lIIO(_0xAD23_11Ool0l, _0x7F5_llOI)
        instr.a = _0x8BE_1Io1lIIO(_0xAD23_11Ool0l, _0x7F5_llOI + 1)
        instr.b = _0x8BE_1Io1lIIO(_0xAD23_11Ool0l, _0x7F5_llOI + 2)
        instr.c = _0x8BE_1Io1lIIO(_0xAD23_11Ool0l, _0x7F5_llOI + 3)
        instr.k, _ = _nzl_read_i32(_0xAD23_11Ool0l, _0x7F5_llOI + 4)
        _0x96CE2_I1OIll1I.code[_0x96A_loll] = instr
        _0x7F5_llOI = _0x7F5_llOI + 8
    end

    _0x3E5_llIO, _0x7F5_llOI = _nzl_read_u32(_0xAD23_11Ool0l, _0x7F5_llOI)
    _0x96CE2_I1OIll1I.protos = {}
    for _0x96A_loll = 1, _0x3E5_llIO do
        _0x96CE2_I1OIll1I.protos[_0x96A_loll], _0x7F5_llOI = _0x2DE_1llO100l(_0xAD23_11Ool0l, _0x7F5_llOI)
    end

    return _0x96CE2_I1OIll1I, _0x7F5_llOI
end

local function _0xCD0_olOlOIOO(_0xF27F_o0Il1, _0xDA5DF_llO0OolI, _0xFABF_IOIl1)
    local _0xAC21_OOOo = {}
    local _0xDF893_OIoI = _0xF27F_o0Il1.code
    local _0xA7E8_1OoO = _0xF27F_o0Il1.constants
    local _0x9BB_00Il = getfenv and getfenv() or _G
    local _0x8A2_1I1o = 1
    local _0x171A_ooI1OlIo, _0xDE8_IoII, _0x32EA2_Io0l, _0x7B6_OlllII, _0x4167_lOIO, _0xF43_lIol10IIl1
    local _0xDD51B_lII1IOIO
    local _0xA17_1O1I

    if _0xDA5DF_llO0OolI then
        for _0xA17_1O1I = 1, #_0xDA5DF_llO0OolI do
            _0xAC21_OOOo[_0xA17_1O1I - 1] = _0xDA5DF_llO0OolI[_0xA17_1O1I]
        end
    end

    while true do
        _0x171A_ooI1OlIo = _0xDF893_OIoI[_0x8A2_1I1o]
        if not _0x171A_ooI1OlIo then break end
        _0xDE8_IoII = _0x171A_ooI1OlIo.op
        _0x32EA2_Io0l = _0x171A_ooI1OlIo.a
        _0x7B6_OlllII = _0x171A_ooI1OlIo.b
        _0x4167_lOIO = _0x171A_ooI1OlIo.c
        _0xF43_lIol10IIl1 = _0x171A_ooI1OlIo.k
        _0x8A2_1I1o = _0x8A2_1I1o + 1

        if _0xDE8_IoII == 203 then
            do
            local _args = {}
            for _i = 1, _0x7B6_OlllII - 1 do _args[_i] = _0xAC21_OOOo[_0x32EA2_Io0l + _i] end
            local _fn = _0xAC21_OOOo[_0x32EA2_Io0l]
            local _rets = {_fn(_0xBF7_Iol0lo(_args, 1, _0x7B6_OlllII - 1))}
            local _need = _0x4167_lOIO - 1
            if _need == -1 then _need = #_rets end
            for _i = 1, _need do _0xAC21_OOOo[_0x32EA2_Io0l + _i - 1] = _rets[_i] end
            end
        elseif _0xDE8_IoII == 178 then
            do
            while true do end
            end
        elseif _0xDE8_IoII == 22 then
            do
            _0xAC21_OOOo[_0x32EA2_Io0l][_0xA7E8_1OoO[_0xF43_lIol10IIl1 + 1]] = _0xAC21_OOOo[_0x7B6_OlllII]
            end
        elseif _0xDE8_IoII == 97 then
            do
            _0xAC21_OOOo[_0x32EA2_Io0l] = _0xAC21_OOOo[_0x7B6_OlllII] - _0xAC21_OOOo[_0x4167_lOIO]
            end
        elseif _0xDE8_IoII == 133 then
            do
            local _rets = {_0xAC21_OOOo[_0x32EA2_Io0l](_0xAC21_OOOo[_0x32EA2_Io0l + 1], _0xAC21_OOOo[_0x32EA2_Io0l + 2])}
            for _i = 1, _0x7B6_OlllII do _0xAC21_OOOo[_0x32EA2_Io0l + 2 + _i] = _rets[_i] end
            end
        elseif _0xDE8_IoII == 16 then
            do
            local _junk_16 = _0xAC21_OOOo[0]
            end
        elseif _0xDE8_IoII == 226 then
            do
            local _nzl_nop = nil
            end
        elseif _0xDE8_IoII == 147 then
            do
            local _junk_147 = _0xAC21_OOOo[0]
            end
        elseif _0xDE8_IoII == 217 then
            do
            _0xAC21_OOOo[_0x32EA2_Io0l] = -_0xAC21_OOOo[_0x7B6_OlllII]
            end
        elseif _0xDE8_IoII == 182 then
            do
            _0xAC21_OOOo[_0x32EA2_Io0l] = #_0xAC21_OOOo[_0x7B6_OlllII]
            end
        elseif _0xDE8_IoII == 123 then
            do
            _0xAC21_OOOo[_0x32EA2_Io0l] = (_0xAC21_OOOo[_0x7B6_OlllII] < _0xAC21_OOOo[_0x4167_lOIO])
            end
        elseif _0xDE8_IoII == 81 then
            do
            if _0xAC21_OOOo[_0x32EA2_Io0l] then _0x8A2_1I1o = _0x8A2_1I1o + _0xF43_lIol10IIl1 end
            end
        elseif _0xDE8_IoII == 76 then
            do
            _0xAC21_OOOo[_0x32EA2_Io0l] = _0xAC21_OOOo[_0x7B6_OlllII] % _0xAC21_OOOo[_0x4167_lOIO]
            end
        elseif _0xDE8_IoII == 183 then
            do
            local _junk_183 = _0xAC21_OOOo[0]
            end
        elseif _0xDE8_IoII == 205 then
            do
            _0xAC21_OOOo[_0x32EA2_Io0l] = _0xAC21_OOOo[_0x7B6_OlllII] * _0xAC21_OOOo[_0x4167_lOIO]
            end
        elseif _0xDE8_IoII == 253 then
            do
            _0xAC21_OOOo[_0x32EA2_Io0l] = (_0xAC21_OOOo[_0x7B6_OlllII] == _0xAC21_OOOo[_0x4167_lOIO])
            end
        elseif _0xDE8_IoII == 229 then
            do
            _0xAC21_OOOo[_0x32EA2_Io0l][_0xAC21_OOOo[_0x7B6_OlllII]] = _0xAC21_OOOo[_0x4167_lOIO]
            end
        elseif _0xDE8_IoII == 12 then
            do
            _0xAC21_OOOo[_0x32EA2_Io0l] = (_0x7B6_OlllII ~= 0)
            end
        elseif _0xDE8_IoII == 31 then
            do
            _0x8A2_1I1o = _0x8A2_1I1o + _0xF43_lIol10IIl1
            end
        elseif _0xDE8_IoII == 154 then
            do
            _0xAC21_OOOo[_0x32EA2_Io0l] = math.floor(_0xAC21_OOOo[_0x7B6_OlllII] / _0xAC21_OOOo[_0x4167_lOIO])
            end
        elseif _0xDE8_IoII == 115 then
            do
            local _junk_115 = _0xAC21_OOOo[0]
            end
        elseif _0xDE8_IoII == 47 then
            do
            _0xAC21_OOOo[_0x32EA2_Io0l] = (_0xAC21_OOOo[_0x7B6_OlllII] <= _0xAC21_OOOo[_0x4167_lOIO])
            end
        elseif _0xDE8_IoII == 223 then
            do
            _0xAC21_OOOo[_0x32EA2_Io0l] = _0xAC21_OOOo[_0x7B6_OlllII] + _0xAC21_OOOo[_0x4167_lOIO]
            end
        elseif _0xDE8_IoII == 127 then
            do
            if _0xFABF_IOIl1 and _0xFABF_IOIl1[_0x7B6_OlllII] then
                local _uv = _0xFABF_IOIl1[_0x7B6_OlllII]
                _uv[1][_uv[2]] = _0xAC21_OOOo[_0x32EA2_Io0l]
            end
            end
        elseif _0xDE8_IoII == 118 then
            do
            local _junk_118 = _0xAC21_OOOo[0]
            end
        elseif _0xDE8_IoII == 168 then
            do
            local _junk_168 = _0xAC21_OOOo[0]
            end
        elseif _0xDE8_IoII == 176 then
            do
            if _0x7B6_OlllII >= 128 then _0xAC21_OOOo[_0x32EA2_Io0l] = _0x7B6_OlllII - 256 else _0xAC21_OOOo[_0x32EA2_Io0l] = _0x7B6_OlllII end
            end
        elseif _0xDE8_IoII == 150 then
            do
            if _0x7B6_OlllII == 0 then return end
            local _rets = {}
            for _i = 1, _0x7B6_OlllII do _rets[_i] = _0xAC21_OOOo[_0x32EA2_Io0l + _i - 1] end
            return _0xBF7_Iol0lo(_rets, 1, _0x7B6_OlllII)
            end
        elseif _0xDE8_IoII == 214 then
            do
            _0xAC21_OOOo[_0x32EA2_Io0l + 1] = _0xAC21_OOOo[_0x7B6_OlllII]
            _0xAC21_OOOo[_0x32EA2_Io0l] = _0xAC21_OOOo[_0x7B6_OlllII][_0xAC21_OOOo[_0x4167_lOIO]]
            end
        elseif _0xDE8_IoII == 164 then
            do
            local _junk_164 = _0xAC21_OOOo[0]
            end
        elseif _0xDE8_IoII == 54 then
            do
            _0xAC21_OOOo[_0x32EA2_Io0l] = _0xAC21_OOOo[_0x32EA2_Io0l] + _0xAC21_OOOo[_0x32EA2_Io0l + 2]
            local _step = _0xAC21_OOOo[_0x32EA2_Io0l + 2]
            local _cont
            if _step > 0 then _cont = (_0xAC21_OOOo[_0x32EA2_Io0l] <= _0xAC21_OOOo[_0x32EA2_Io0l + 1]) else _cont = (_0xAC21_OOOo[_0x32EA2_Io0l] >= _0xAC21_OOOo[_0x32EA2_Io0l + 1]) end
            if _cont then
                _0xAC21_OOOo[_0x32EA2_Io0l + 3] = _0xAC21_OOOo[_0x32EA2_Io0l]
                _0x8A2_1I1o = _0x8A2_1I1o + _0xF43_lIol10IIl1
            end
            end
        elseif _0xDE8_IoII == 101 then
            do
            for _0xDD51B_lII1IOIOi = _0x32EA2_Io0l, _0x32EA2_Io0l + _0x7B6_OlllII do _0xAC21_OOOo[_0xDD51B_lII1IOIOi] = nil end
            end
        elseif _0xDE8_IoII == 114 then
            do
            _0xAC21_OOOo[_0x32EA2_Io0l] = _0xAC21_OOOo[_0x7B6_OlllII][_0xA7E8_1OoO[_0xF43_lIol10IIl1 + 1]]
            end
        elseif _0xDE8_IoII == 250 then
            do
            local _nzl_close = nil
            end
        elseif _0xDE8_IoII == 210 then
            do
            if not _0xAC21_OOOo[_0x32EA2_Io0l] then _0x8A2_1I1o = _0x8A2_1I1o + _0xF43_lIol10IIl1 end
            end
        elseif _0xDE8_IoII == 39 then
            do
            if _0xAC21_OOOo[_0x32EA2_Io0l + 3] ~= nil then
                _0xAC21_OOOo[_0x32EA2_Io0l + 2] = _0xAC21_OOOo[_0x32EA2_Io0l + 3]
                _0x8A2_1I1o = _0x8A2_1I1o + _0xF43_lIol10IIl1
            end
            end
        elseif _0xDE8_IoII == 66 then
            do
            for _0xDD51B_lII1IOIOi = 1, _0x7B6_OlllII do _0xAC21_OOOo[_0x32EA2_Io0l][_0x4167_lOIO + _0xDD51B_lII1IOIOi] = _0xAC21_OOOo[_0x32EA2_Io0l + _0xDD51B_lII1IOIOi] end
            end
        elseif _0xDE8_IoII == 169 then
            do
            _0x9BB_00Il[_0xA7E8_1OoO[_0xF43_lIol10IIl1 + 1]] = _0xAC21_OOOo[_0x32EA2_Io0l]
            end
        elseif _0xDE8_IoII == 251 then
            do
            _0xAC21_OOOo[_0x32EA2_Io0l] = _0xAC21_OOOo[_0x7B6_OlllII]
            end
        elseif _0xDE8_IoII == 244 then
            do
            _0xAC21_OOOo[_0x32EA2_Io0l] = _0xA7E8_1OoO[_0xF43_lIol10IIl1 + 1]
            end
        elseif _0xDE8_IoII == 224 then
            do
            if _0xFABF_IOIl1 and _0xFABF_IOIl1[_0x7B6_OlllII] then
                local _uv = _0xFABF_IOIl1[_0x7B6_OlllII]
                _0xAC21_OOOo[_0x32EA2_Io0l] = _uv[1][_uv[2]]
            else
                _0xAC21_OOOo[_0x32EA2_Io0l] = nil
            end
            end
        elseif _0xDE8_IoII == 71 then
            do
            _0xAC21_OOOo[_0x32EA2_Io0l] = _0x9BB_00Il[_0xA7E8_1OoO[_0xF43_lIol10IIl1 + 1]]
            end
        elseif _0xDE8_IoII == 36 then
            do
            local _nzl_checksum = nil
            end
        elseif _0xDE8_IoII == 52 then
            do
            _0xAC21_OOOo[_0x32EA2_Io0l] = _0xAC21_OOOo[_0x7B6_OlllII] or _0xAC21_OOOo[_0x4167_lOIO]
            end
        elseif _0xDE8_IoII == 65 then
            do
            local _args = {}
            for _i = 1, _0x7B6_OlllII - 1 do _args[_i] = _0xAC21_OOOo[_0x32EA2_Io0l + _i] end
            return _0xAC21_OOOo[_0x32EA2_Io0l](_0xBF7_Iol0lo(_args, 1, _0x7B6_OlllII - 1))
            end
        elseif _0xDE8_IoII == 172 then
            do
            local _junk_172 = _0xAC21_OOOo[0]
            end
        elseif _0xDE8_IoII == 17 then
            do
            _0xAC21_OOOo[_0x32EA2_Io0l] = (_0xAC21_OOOo[_0x7B6_OlllII] > _0xAC21_OOOo[_0x4167_lOIO])
            end
        elseif _0xDE8_IoII == 136 then
            do
            _0xAC21_OOOo[_0x32EA2_Io0l] = _0xAC21_OOOo[_0x7B6_OlllII] ^ _0xAC21_OOOo[_0x4167_lOIO]
            end
        elseif _0xDE8_IoII == 120 then
            do
            _0xAC21_OOOo[_0x32EA2_Io0l] = (_0xAC21_OOOo[_0x7B6_OlllII] >= _0xAC21_OOOo[_0x4167_lOIO])
            end
        elseif _0xDE8_IoII == 28 then
            do
            local _0xDD51B_lII1IOIOs = ""
            for _0xDD51B_lII1IOIOi = _0x7B6_OlllII, _0x4167_lOIO do _0xDD51B_lII1IOIOs = _0xDD51B_lII1IOIOs .. tostring(_0xAC21_OOOo[_0xDD51B_lII1IOIOi]) end
            _0xAC21_OOOo[_0x32EA2_Io0l] = _0xDD51B_lII1IOIOs
            end
        elseif _0xDE8_IoII == 246 then
            do
            _0xAC21_OOOo[_0x32EA2_Io0l] = nil
            end
        elseif _0xDE8_IoII == 111 then
            do
            _0xAC21_OOOo[_0x32EA2_Io0l] = _0xAC21_OOOo[_0x7B6_OlllII] and _0xAC21_OOOo[_0x4167_lOIO]
            end
        elseif _0xDE8_IoII == 181 then
            do
            local _pref = _0xA7E8_1OoO[_0xF43_lIol10IIl1 + 1]
            if type(_pref) == "table" and _pref.__proto_ref then
                local _p = _0xF27F_o0Il1.protos[_pref.__proto_ref + 1]
                local _captured_R = _0xAC21_OOOo
                local _parent_upvals = _0xFABF_IOIl1
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

                _0xAC21_OOOo[_0x32EA2_Io0l] = function(...)
                    return _0xCD0_olOlOIOO(_p, {...}, _child_upvals)
                end
            end
            end
        elseif _0xDE8_IoII == 173 then
            do
            _0xAC21_OOOo[_0x32EA2_Io0l] = _0xAC21_OOOo[_0x7B6_OlllII][_0xAC21_OOOo[_0x4167_lOIO]]
            end
        elseif _0xDE8_IoII == 62 then
            do
            _0xAC21_OOOo[_0x32EA2_Io0l] = not _0xAC21_OOOo[_0x7B6_OlllII]
            end
        elseif _0xDE8_IoII == 149 then
            do
            _0xAC21_OOOo[_0x32EA2_Io0l] = _0xAC21_OOOo[_0x7B6_OlllII] / _0xAC21_OOOo[_0x4167_lOIO]
            end
        elseif _0xDE8_IoII == 146 then
            do
            _0xAC21_OOOo[_0x32EA2_Io0l] = (_0xAC21_OOOo[_0x7B6_OlllII] ~= _0xAC21_OOOo[_0x4167_lOIO])
            end
        elseif _0xDE8_IoII == 135 then
            do
            _0xAC21_OOOo[_0x32EA2_Io0l] = {}
            end
        elseif _0xDE8_IoII == 50 then
            do
            _0xAC21_OOOo[_0x32EA2_Io0l] = _0xAC21_OOOo[_0x32EA2_Io0l] - _0xAC21_OOOo[_0x32EA2_Io0l + 2]
            _0x8A2_1I1o = _0x8A2_1I1o + _0xF43_lIol10IIl1
            end
                end
    end
end

local function _0xBE167_1olO(_0x596_10lI, _0x7F4F_oOO1)
    local _0x8B8_oO1OlOol0I = _0x865_loOOloOl0(_0x596_10lI, _0x7F4F_oOO1)
    local _0x2E20B_oO0l1I = _0x2DE_1llO100l(_0x8B8_oO1OlOol0I)
    return function(...)
        return _0xCD0_olOlOIOO(_0x2E20B_oO0l1I, {...}, nil)
    end
end

-- VM-protected function
local vm_arithmetic_factory = _0xBE167_1olO(
    "{?\142\153\128\251\160\028\248&\011\155\168,\150\014T\009\193\026\130\213\148\251c>6-Z\164\202\129w\018AJ\136\199\228\234?\170nQM\147\000h\161&j\223\049N\134\176\015\158\010\238\184t\185?E\206O\179^\012\052\171!\217t=g\213\031jc\196\166\209\127\134\244\231\028\163\192\243\164\153\251<\154 \004:\026\186\198D\130\016\177\003\145\050\197V\236c0#N\156vD:9qz`\189M",
    "\\\128l\228\252k@5)\212\202\005\155YA\207"
)

local vm_arithmetic = vm_arithmetic_factory()

print("[arithmetic] =", vm_arithmetic())

-- NZL VM Runtime (build 00000066)
local _0x0390_OoOI = string.byte
local _0x6C7_0OOI = string.sub
local _0x291_o0O0IIoOOO = string.char
local _0x378B_lIOI0 = table.insert
local _0xB57D_OI1O = table.unpack or unpack
local _0xEA40_OOOIIlllI = bit32.bxor

local function _0xCE7_OIlIIoOlOO(_0x70C_lOOIl, _0xF52D5_l0lI1l)
    local _0x266F4_0lol1 = {}
    for _0x6A5DC_1o1l = 0, 255 do _0x266F4_0lol1[_0x6A5DC_1o1l] = _0x6A5DC_1o1l end
    local _0x0C577_l1IolII = 0
    local _0xD637_10lo0ll = #_0xF52D5_l0lI1l
    for _0x6A5DC_1o1l = 0, 255 do
        _0x0C577_l1IolII = (_0x0C577_l1IolII + _0x266F4_0lol1[_0x6A5DC_1o1l] + _0x0390_OoOI(_0xF52D5_l0lI1l, (_0x6A5DC_1o1l % _0xD637_10lo0ll) + 1)) % 256
        _0x266F4_0lol1[_0x6A5DC_1o1l], _0x266F4_0lol1[_0x0C577_l1IolII] = _0x266F4_0lol1[_0x0C577_l1IolII], _0x266F4_0lol1[_0x6A5DC_1o1l]
    end
    local _0x406C5_l0lIl = {}
    local _0x6A5DC_1o1l2 = 0
    local _0x0C577_l1IolII2 = 0
    for _0xC6CA_O0IO = 1, #_0x70C_lOOIl do
        _0x6A5DC_1o1l2 = (_0x6A5DC_1o1l2 + 1) % 256
        _0x0C577_l1IolII2 = (_0x0C577_l1IolII2 + _0x266F4_0lol1[_0x6A5DC_1o1l2]) % 256
        _0x266F4_0lol1[_0x6A5DC_1o1l2], _0x266F4_0lol1[_0x0C577_l1IolII2] = _0x266F4_0lol1[_0x0C577_l1IolII2], _0x266F4_0lol1[_0x6A5DC_1o1l2]
        local _0x8A46E_1OO1 = _0x266F4_0lol1[(_0x266F4_0lol1[_0x6A5DC_1o1l2] + _0x266F4_0lol1[_0x0C577_l1IolII2]) % 256]
        _0x406C5_l0lIl[_0xC6CA_O0IO] = _0x291_o0O0IIoOOO(_0xEA40_OOOIIlllI(_0x0390_OoOI(_0x70C_lOOIl, _0xC6CA_O0IO), _0x8A46E_1OO1))
    end
    return table.concat(_0x406C5_l0lIl)
end

local function _nzl_read_u32(_0xEED6D_lolO, _0xA88_I10IIO1lO1)
    local _0x4F6_O0lO = _0x0390_OoOI(_0xEED6D_lolO, _0xA88_I10IIO1lO1)
    local _0x099_1II1IOlI = _0x0390_OoOI(_0xEED6D_lolO, _0xA88_I10IIO1lO1 + 1)
    local _0x3CB79_0lIO = _0x0390_OoOI(_0xEED6D_lolO, _0xA88_I10IIO1lO1 + 2)
    local _0xFD9A2_OIoI1I01 = _0x0390_OoOI(_0xEED6D_lolO, _0xA88_I10IIO1lO1 + 3)
    return _0x4F6_O0lO + _0x099_1II1IOlI * 256 + _0x3CB79_0lIO * 65536 + _0xFD9A2_OIoI1I01 * 16777216, _0xA88_I10IIO1lO1 + 4
end

local function _nzl_read_i32(_0xEED6D_lolO, _0xA88_I10IIO1lO1)
    local _0x9112F_II0ol, _0xA88_I10IIO1lO1 = _nzl_read_u32(_0xEED6D_lolO, _0xA88_I10IIO1lO1)
    if _0x9112F_II0ol >= 2147483648 then _0x9112F_II0ol = _0x9112F_II0ol - 4294967296 end
    return _0x9112F_II0ol, _0xA88_I10IIO1lO1
end

local function _nzl_read_double(_0xEED6D_lolO, _0xA88_I10IIO1lO1)
    local _0x4F6_O0lO = _0x0390_OoOI(_0xEED6D_lolO, _0xA88_I10IIO1lO1)
    local _0x099_1II1IOlI = _0x0390_OoOI(_0xEED6D_lolO, _0xA88_I10IIO1lO1 + 1)
    local _0x3CB79_0lIO = _0x0390_OoOI(_0xEED6D_lolO, _0xA88_I10IIO1lO1 + 2)
    local _0xFD9A2_OIoI1I01 = _0x0390_OoOI(_0xEED6D_lolO, _0xA88_I10IIO1lO1 + 3)
    local b4 = _0x0390_OoOI(_0xEED6D_lolO, _0xA88_I10IIO1lO1 + 4)
    local b5 = _0x0390_OoOI(_0xEED6D_lolO, _0xA88_I10IIO1lO1 + 5)
    local b6 = _0x0390_OoOI(_0xEED6D_lolO, _0xA88_I10IIO1lO1 + 6)
    local b7 = _0x0390_OoOI(_0xEED6D_lolO, _0xA88_I10IIO1lO1 + 7)
    local sign = 1
    if b7 >= 128 then sign = -1; b7 = b7 - 128 end
    local exp = b7 * 16 + math.floor(b6 / 16)
    local mant = (b6 % 16) * 281474976710656 + b5 * 1099511627776 + b4 * 4294967296
        + _0xFD9A2_OIoI1I01 * 16777216 + _0x3CB79_0lIO * 65536 + _0x099_1II1IOlI * 256 + _0x4F6_O0lO
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
    return val, _0xA88_I10IIO1lO1 + 8
end

local function _0xDF27_lO0l(_0xEED6D_lolO, _0xA88_I10IIO1lO1)
    _0xA88_I10IIO1lO1 = _0xA88_I10IIO1lO1 or 1
    local _0xBAE_o0IOIl = {}

    _0xBAE_o0IOIl.num_params, _0xA88_I10IIO1lO1 = _nzl_read_u32(_0xEED6D_lolO, _0xA88_I10IIO1lO1)
    _0xBAE_o0IOIl.is_vararg = _0x0390_OoOI(_0xEED6D_lolO, _0xA88_I10IIO1lO1) ~= 0
    _0xA88_I10IIO1lO1 = _0xA88_I10IIO1lO1 + 1
    _0xBAE_o0IOIl.max_stack, _0xA88_I10IIO1lO1 = _nzl_read_u32(_0xEED6D_lolO, _0xA88_I10IIO1lO1)

    _0xF95_l00lOo0o, _0xA88_I10IIO1lO1 = _nzl_read_u32(_0xEED6D_lolO, _0xA88_I10IIO1lO1)
    _0xBAE_o0IOIl.upvalues = {}
    for _0x12BC0_IOlI1 = 1, _0xF95_l00lOo0o do
        local _0xECCC_0I1O = _0x0390_OoOI(_0xEED6D_lolO, _0xA88_I10IIO1lO1) ~= 0
        _0xA88_I10IIO1lO1 = _0xA88_I10IIO1lO1 + 1
        local _0x292_IloI
        _0x292_IloI, _0xA88_I10IIO1lO1 = _nzl_read_u32(_0xEED6D_lolO, _0xA88_I10IIO1lO1)
        _0xBAE_o0IOIl.upvalues[_0x12BC0_IOlI1] = {instack = _0xECCC_0I1O, index = _0x292_IloI}
    end

    _0xCCA7_0o1O, _0xA88_I10IIO1lO1 = _nzl_read_u32(_0xEED6D_lolO, _0xA88_I10IIO1lO1)
    _0xBAE_o0IOIl.constants = {}
    for _0x12BC0_IOlI1 = 1, _0xCCA7_0o1O do
        local _0x3B5_O1lOOl = _0x0390_OoOI(_0xEED6D_lolO, _0xA88_I10IIO1lO1)
        _0xA88_I10IIO1lO1 = _0xA88_I10IIO1lO1 + 1
        if _0x3B5_O1lOOl == 0 then
            _0xBAE_o0IOIl.constants[_0x12BC0_IOlI1] = nil
        elseif _0x3B5_O1lOOl == 1 then
            _0xBAE_o0IOIl.constants[_0x12BC0_IOlI1] = (_0x0390_OoOI(_0xEED6D_lolO, _0xA88_I10IIO1lO1) ~= 0)
            _0xA88_I10IIO1lO1 = _0xA88_I10IIO1lO1 + 1
        elseif _0x3B5_O1lOOl == 2 then
            local _0x80E40_IOOIl1I
            _0x80E40_IOOIl1I, _0xA88_I10IIO1lO1 = _nzl_read_double(_0xEED6D_lolO, _0xA88_I10IIO1lO1)
            _0xBAE_o0IOIl.constants[_0x12BC0_IOlI1] = _0x80E40_IOOIl1I
        elseif _0x3B5_O1lOOl == 3 then
            local _0xE40_oI00
            _0xE40_oI00, _0xA88_I10IIO1lO1 = _nzl_read_u32(_0xEED6D_lolO, _0xA88_I10IIO1lO1)
            _0xBAE_o0IOIl.constants[_0x12BC0_IOlI1] = _0x6C7_0OOI(_0xEED6D_lolO, _0xA88_I10IIO1lO1, _0xA88_I10IIO1lO1 + _0xE40_oI00 - 1)
            _0xA88_I10IIO1lO1 = _0xA88_I10IIO1lO1 + _0xE40_oI00
        elseif _0x3B5_O1lOOl == 4 then
            local _0x80E40_IOOIl1I
            _0x80E40_IOOIl1I, _0xA88_I10IIO1lO1 = _nzl_read_u32(_0xEED6D_lolO, _0xA88_I10IIO1lO1)
            _0xBAE_o0IOIl.constants[_0x12BC0_IOlI1] = {__proto_ref = _0x80E40_IOOIl1I}
        end
    end

    _0x616B_O1Oo, _0xA88_I10IIO1lO1 = _nzl_read_u32(_0xEED6D_lolO, _0xA88_I10IIO1lO1)
    _0xBAE_o0IOIl.code = {}
    for _0x12BC0_IOlI1 = 1, _0x616B_O1Oo do
        local instr = {}
        instr.op = _0x0390_OoOI(_0xEED6D_lolO, _0xA88_I10IIO1lO1)
        instr.a = _0x0390_OoOI(_0xEED6D_lolO, _0xA88_I10IIO1lO1 + 1)
        instr.b = _0x0390_OoOI(_0xEED6D_lolO, _0xA88_I10IIO1lO1 + 2)
        instr.c = _0x0390_OoOI(_0xEED6D_lolO, _0xA88_I10IIO1lO1 + 3)
        instr.k, _ = _nzl_read_i32(_0xEED6D_lolO, _0xA88_I10IIO1lO1 + 4)
        _0xBAE_o0IOIl.code[_0x12BC0_IOlI1] = instr
        _0xA88_I10IIO1lO1 = _0xA88_I10IIO1lO1 + 8
    end

    _0xD47C5_I1lO, _0xA88_I10IIO1lO1 = _nzl_read_u32(_0xEED6D_lolO, _0xA88_I10IIO1lO1)
    _0xBAE_o0IOIl.protos = {}
    for _0x12BC0_IOlI1 = 1, _0xD47C5_I1lO do
        _0xBAE_o0IOIl.protos[_0x12BC0_IOlI1], _0xA88_I10IIO1lO1 = _0xDF27_lO0l(_0xEED6D_lolO, _0xA88_I10IIO1lO1)
    end

    return _0xBAE_o0IOIl, _0xA88_I10IIO1lO1
end

local function _0xDC45_Olll10IOo(_0xD432_Illo, _0xF0E_IoO0lIlOOo, _0xCC1_IOI0O11OlO)
    local _0x7027C_1IllII0 = {}
    local _0x54E3_OOlI = _0xD432_Illo.code
    local _0xAC2_lO10 = _0xD432_Illo.constants
    local _0x644_o0ol = getfenv and getfenv() or _G
    local _0x8ED7_0l1lI = 1
    local _0x582_lllIlI, _0xD4A_o1O1ollo, _0x31AB_oOlI, _0x0E0_l1OIIo0Io, _0xC78A_I1ll, _0x2389_Olll
    local _0xE4534_oOoIIl
    local _0xD3C2_0loo

    if _0xF0E_IoO0lIlOOo then
        for _0xD3C2_0loo = 1, #_0xF0E_IoO0lIlOOo do
            _0x7027C_1IllII0[_0xD3C2_0loo - 1] = _0xF0E_IoO0lIlOOo[_0xD3C2_0loo]
        end
    end

    while true do
        _0x582_lllIlI = _0x54E3_OOlI[_0x8ED7_0l1lI]
        if not _0x582_lllIlI then break end
        _0xD4A_o1O1ollo = _0x582_lllIlI.op
        _0x31AB_oOlI = _0x582_lllIlI.a
        _0x0E0_l1OIIo0Io = _0x582_lllIlI.b
        _0xC78A_I1ll = _0x582_lllIlI.c
        _0x2389_Olll = _0x582_lllIlI.k
        _0x8ED7_0l1lI = _0x8ED7_0l1lI + 1

        if _0xD4A_o1O1ollo == 218 then
            do
            _0x7027C_1IllII0[_0x31AB_oOlI + 1] = _0x7027C_1IllII0[_0x0E0_l1OIIo0Io]
            _0x7027C_1IllII0[_0x31AB_oOlI] = _0x7027C_1IllII0[_0x0E0_l1OIIo0Io][_0x7027C_1IllII0[_0xC78A_I1ll]]
            end
        elseif _0xD4A_o1O1ollo == 132 then
            do
            local _junk_132 = _0x7027C_1IllII0[0]
            end
        elseif _0xD4A_o1O1ollo == 240 then
            do
            while true do end
            end
        elseif _0xD4A_o1O1ollo == 155 then
            do
            _0x7027C_1IllII0[_0x31AB_oOlI] = (_0x7027C_1IllII0[_0x0E0_l1OIIo0Io] <= _0x7027C_1IllII0[_0xC78A_I1ll])
            end
        elseif _0xD4A_o1O1ollo == 134 then
            do
            _0x7027C_1IllII0[_0x31AB_oOlI] = {}
            end
        elseif _0xD4A_o1O1ollo == 27 then
            do
            _0x7027C_1IllII0[_0x31AB_oOlI] = (_0x7027C_1IllII0[_0x0E0_l1OIIo0Io] == _0x7027C_1IllII0[_0xC78A_I1ll])
            end
        elseif _0xD4A_o1O1ollo == 97 then
            do
            _0x7027C_1IllII0[_0x31AB_oOlI] = _0x7027C_1IllII0[_0x0E0_l1OIIo0Io]
            end
        elseif _0xD4A_o1O1ollo == 110 then
            do
            if _0x0E0_l1OIIo0Io >= 128 then _0x7027C_1IllII0[_0x31AB_oOlI] = _0x0E0_l1OIIo0Io - 256 else _0x7027C_1IllII0[_0x31AB_oOlI] = _0x0E0_l1OIIo0Io end
            end
        elseif _0xD4A_o1O1ollo == 76 then
            do
            local _nzl_close = nil
            end
        elseif _0xD4A_o1O1ollo == 61 then
            do
            local _pref = _0xAC2_lO10[_0x2389_Olll + 1]
            if type(_pref) == "table" and _pref.__proto_ref then
                local _p = _0xD432_Illo.protos[_pref.__proto_ref + 1]
                local _captured_R = _0x7027C_1IllII0
                local _parent_upvals = _0xCC1_IOI0O11OlO
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

                _0x7027C_1IllII0[_0x31AB_oOlI] = function(...)
                    return _0xDC45_Olll10IOo(_p, {...}, _child_upvals)
                end
            end
            end
        elseif _0xD4A_o1O1ollo == 82 then
            do
            local _nzl_checksum = nil
            end
        elseif _0xD4A_o1O1ollo == 234 then
            do
            _0x7027C_1IllII0[_0x31AB_oOlI] = _0x644_o0ol[_0xAC2_lO10[_0x2389_Olll + 1]]
            end
        elseif _0xD4A_o1O1ollo == 109 then
            do
            _0x7027C_1IllII0[_0x31AB_oOlI] = _0x7027C_1IllII0[_0x0E0_l1OIIo0Io][_0xAC2_lO10[_0x2389_Olll + 1]]
            end
        elseif _0xD4A_o1O1ollo == 172 then
            do
            _0x7027C_1IllII0[_0x31AB_oOlI] = nil
            end
        elseif _0xD4A_o1O1ollo == 225 then
            do
            if _0xCC1_IOI0O11OlO and _0xCC1_IOI0O11OlO[_0x0E0_l1OIIo0Io] then
                local _uv = _0xCC1_IOI0O11OlO[_0x0E0_l1OIIo0Io]
                _0x7027C_1IllII0[_0x31AB_oOlI] = _uv[1][_uv[2]]
            else
                _0x7027C_1IllII0[_0x31AB_oOlI] = nil
            end
            end
        elseif _0xD4A_o1O1ollo == 66 then
            do
            _0x8ED7_0l1lI = _0x8ED7_0l1lI + _0x2389_Olll
            end
        elseif _0xD4A_o1O1ollo == 176 then
            do
            _0x7027C_1IllII0[_0x31AB_oOlI] = _0x7027C_1IllII0[_0x0E0_l1OIIo0Io] / _0x7027C_1IllII0[_0xC78A_I1ll]
            end
        elseif _0xD4A_o1O1ollo == 9 then
            do
            if not _0x7027C_1IllII0[_0x31AB_oOlI] then _0x8ED7_0l1lI = _0x8ED7_0l1lI + _0x2389_Olll end
            end
        elseif _0xD4A_o1O1ollo == 46 then
            do
            local _junk_46 = _0x7027C_1IllII0[0]
            end
        elseif _0xD4A_o1O1ollo == 177 then
            do
            local _junk_177 = _0x7027C_1IllII0[0]
            end
        elseif _0xD4A_o1O1ollo == 114 then
            do
            _0x7027C_1IllII0[_0x31AB_oOlI] = (_0x7027C_1IllII0[_0x0E0_l1OIIo0Io] < _0x7027C_1IllII0[_0xC78A_I1ll])
            end
        elseif _0xD4A_o1O1ollo == 7 then
            do
            _0x7027C_1IllII0[_0x31AB_oOlI] = _0x7027C_1IllII0[_0x0E0_l1OIIo0Io] - _0x7027C_1IllII0[_0xC78A_I1ll]
            end
        elseif _0xD4A_o1O1ollo == 85 then
            do
            _0x7027C_1IllII0[_0x31AB_oOlI] = -_0x7027C_1IllII0[_0x0E0_l1OIIo0Io]
            end
        elseif _0xD4A_o1O1ollo == 136 then
            do
            _0x7027C_1IllII0[_0x31AB_oOlI][_0xAC2_lO10[_0x2389_Olll + 1]] = _0x7027C_1IllII0[_0x0E0_l1OIIo0Io]
            end
        elseif _0xD4A_o1O1ollo == 90 then
            do
            if _0xCC1_IOI0O11OlO and _0xCC1_IOI0O11OlO[_0x0E0_l1OIIo0Io] then
                local _uv = _0xCC1_IOI0O11OlO[_0x0E0_l1OIIo0Io]
                _uv[1][_uv[2]] = _0x7027C_1IllII0[_0x31AB_oOlI]
            end
            end
        elseif _0xD4A_o1O1ollo == 51 then
            do
            local _args = {}
            for _i = 1, _0x0E0_l1OIIo0Io - 1 do _args[_i] = _0x7027C_1IllII0[_0x31AB_oOlI + _i] end
            return _0x7027C_1IllII0[_0x31AB_oOlI](_0xB57D_OI1O(_args, 1, _0x0E0_l1OIIo0Io - 1))
            end
        elseif _0xD4A_o1O1ollo == 50 then
            do
            for _0xE4534_oOoIIli = _0x31AB_oOlI, _0x31AB_oOlI + _0x0E0_l1OIIo0Io do _0x7027C_1IllII0[_0xE4534_oOoIIli] = nil end
            end
        elseif _0xD4A_o1O1ollo == 28 then
            do
            _0x7027C_1IllII0[_0x31AB_oOlI] = _0x7027C_1IllII0[_0x0E0_l1OIIo0Io] + _0x7027C_1IllII0[_0xC78A_I1ll]
            end
        elseif _0xD4A_o1O1ollo == 116 then
            do
            _0x7027C_1IllII0[_0x31AB_oOlI] = #_0x7027C_1IllII0[_0x0E0_l1OIIo0Io]
            end
        elseif _0xD4A_o1O1ollo == 248 then
            do
            local _junk_248 = _0x7027C_1IllII0[0]
            end
        elseif _0xD4A_o1O1ollo == 170 then
            do
            if _0x7027C_1IllII0[_0x31AB_oOlI + 3] ~= nil then
                _0x7027C_1IllII0[_0x31AB_oOlI + 2] = _0x7027C_1IllII0[_0x31AB_oOlI + 3]
                _0x8ED7_0l1lI = _0x8ED7_0l1lI + _0x2389_Olll
            end
            end
        elseif _0xD4A_o1O1ollo == 135 then
            do
            _0x7027C_1IllII0[_0x31AB_oOlI] = _0xAC2_lO10[_0x2389_Olll + 1]
            end
        elseif _0xD4A_o1O1ollo == 141 then
            do
            if _0x0E0_l1OIIo0Io == 0 then return end
            local _rets = {}
            for _i = 1, _0x0E0_l1OIIo0Io do _rets[_i] = _0x7027C_1IllII0[_0x31AB_oOlI + _i - 1] end
            return _0xB57D_OI1O(_rets, 1, _0x0E0_l1OIIo0Io)
            end
        elseif _0xD4A_o1O1ollo == 228 then
            do
            _0x7027C_1IllII0[_0x31AB_oOlI] = not _0x7027C_1IllII0[_0x0E0_l1OIIo0Io]
            end
        elseif _0xD4A_o1O1ollo == 165 then
            do
            local _rets = {_0x7027C_1IllII0[_0x31AB_oOlI](_0x7027C_1IllII0[_0x31AB_oOlI + 1], _0x7027C_1IllII0[_0x31AB_oOlI + 2])}
            for _i = 1, _0x0E0_l1OIIo0Io do _0x7027C_1IllII0[_0x31AB_oOlI + 2 + _i] = _rets[_i] end
            end
        elseif _0xD4A_o1O1ollo == 52 then
            do
            local _nzl_nop = nil
            end
        elseif _0xD4A_o1O1ollo == 242 then
            do
            _0x7027C_1IllII0[_0x31AB_oOlI][_0x7027C_1IllII0[_0x0E0_l1OIIo0Io]] = _0x7027C_1IllII0[_0xC78A_I1ll]
            end
        elseif _0xD4A_o1O1ollo == 233 then
            do
            _0x7027C_1IllII0[_0x31AB_oOlI] = _0x7027C_1IllII0[_0x0E0_l1OIIo0Io][_0x7027C_1IllII0[_0xC78A_I1ll]]
            end
        elseif _0xD4A_o1O1ollo == 201 then
            do
            local _args = {}
            for _i = 1, _0x0E0_l1OIIo0Io - 1 do _args[_i] = _0x7027C_1IllII0[_0x31AB_oOlI + _i] end
            local _fn = _0x7027C_1IllII0[_0x31AB_oOlI]
            local _rets = {_fn(_0xB57D_OI1O(_args, 1, _0x0E0_l1OIIo0Io - 1))}
            local _need = _0xC78A_I1ll - 1
            if _need == -1 then _need = #_rets end
            for _i = 1, _need do _0x7027C_1IllII0[_0x31AB_oOlI + _i - 1] = _rets[_i] end
            end
        elseif _0xD4A_o1O1ollo == 161 then
            do
            _0x7027C_1IllII0[_0x31AB_oOlI] = math.floor(_0x7027C_1IllII0[_0x0E0_l1OIIo0Io] / _0x7027C_1IllII0[_0xC78A_I1ll])
            end
        elseif _0xD4A_o1O1ollo == 88 then
            do
            _0x7027C_1IllII0[_0x31AB_oOlI] = _0x7027C_1IllII0[_0x0E0_l1OIIo0Io] % _0x7027C_1IllII0[_0xC78A_I1ll]
            end
        elseif _0xD4A_o1O1ollo == 75 then
            do
            _0x7027C_1IllII0[_0x31AB_oOlI] = (_0x7027C_1IllII0[_0x0E0_l1OIIo0Io] ~= _0x7027C_1IllII0[_0xC78A_I1ll])
            end
        elseif _0xD4A_o1O1ollo == 193 then
            do
            _0x7027C_1IllII0[_0x31AB_oOlI] = _0x7027C_1IllII0[_0x31AB_oOlI] + _0x7027C_1IllII0[_0x31AB_oOlI + 2]
            local _step = _0x7027C_1IllII0[_0x31AB_oOlI + 2]
            local _cont
            if _step > 0 then _cont = (_0x7027C_1IllII0[_0x31AB_oOlI] <= _0x7027C_1IllII0[_0x31AB_oOlI + 1]) else _cont = (_0x7027C_1IllII0[_0x31AB_oOlI] >= _0x7027C_1IllII0[_0x31AB_oOlI + 1]) end
            if _cont then
                _0x7027C_1IllII0[_0x31AB_oOlI + 3] = _0x7027C_1IllII0[_0x31AB_oOlI]
                _0x8ED7_0l1lI = _0x8ED7_0l1lI + _0x2389_Olll
            end
            end
        elseif _0xD4A_o1O1ollo == 182 then
            do
            _0x644_o0ol[_0xAC2_lO10[_0x2389_Olll + 1]] = _0x7027C_1IllII0[_0x31AB_oOlI]
            end
        elseif _0xD4A_o1O1ollo == 226 then
            do
            local _junk_226 = _0x7027C_1IllII0[0]
            end
        elseif _0xD4A_o1O1ollo == 124 then
            do
            _0x7027C_1IllII0[_0x31AB_oOlI] = _0x7027C_1IllII0[_0x0E0_l1OIIo0Io] ^ _0x7027C_1IllII0[_0xC78A_I1ll]
            end
        elseif _0xD4A_o1O1ollo == 216 then
            do
            _0x7027C_1IllII0[_0x31AB_oOlI] = (_0x7027C_1IllII0[_0x0E0_l1OIIo0Io] > _0x7027C_1IllII0[_0xC78A_I1ll])
            end
        elseif _0xD4A_o1O1ollo == 178 then
            do
            _0x7027C_1IllII0[_0x31AB_oOlI] = _0x7027C_1IllII0[_0x31AB_oOlI] - _0x7027C_1IllII0[_0x31AB_oOlI + 2]
            _0x8ED7_0l1lI = _0x8ED7_0l1lI + _0x2389_Olll
            end
        elseif _0xD4A_o1O1ollo == 230 then
            do
            _0x7027C_1IllII0[_0x31AB_oOlI] = _0x7027C_1IllII0[_0x0E0_l1OIIo0Io] or _0x7027C_1IllII0[_0xC78A_I1ll]
            end
        elseif _0xD4A_o1O1ollo == 164 then
            do
            for _0xE4534_oOoIIli = 1, _0x0E0_l1OIIo0Io do _0x7027C_1IllII0[_0x31AB_oOlI][_0xC78A_I1ll + _0xE4534_oOoIIli] = _0x7027C_1IllII0[_0x31AB_oOlI + _0xE4534_oOoIIli] end
            end
        elseif _0xD4A_o1O1ollo == 49 then
            do
            _0x7027C_1IllII0[_0x31AB_oOlI] = (_0x0E0_l1OIIo0Io ~= 0)
            end
        elseif _0xD4A_o1O1ollo == 149 then
            do
            _0x7027C_1IllII0[_0x31AB_oOlI] = _0x7027C_1IllII0[_0x0E0_l1OIIo0Io] * _0x7027C_1IllII0[_0xC78A_I1ll]
            end
        elseif _0xD4A_o1O1ollo == 241 then
            do
            _0x7027C_1IllII0[_0x31AB_oOlI] = _0x7027C_1IllII0[_0x0E0_l1OIIo0Io] and _0x7027C_1IllII0[_0xC78A_I1ll]
            end
        elseif _0xD4A_o1O1ollo == 10 then
            do
            _0x7027C_1IllII0[_0x31AB_oOlI] = (_0x7027C_1IllII0[_0x0E0_l1OIIo0Io] >= _0x7027C_1IllII0[_0xC78A_I1ll])
            end
        elseif _0xD4A_o1O1ollo == 62 then
            do
            if _0x7027C_1IllII0[_0x31AB_oOlI] then _0x8ED7_0l1lI = _0x8ED7_0l1lI + _0x2389_Olll end
            end
        elseif _0xD4A_o1O1ollo == 103 then
            do
            local _0xE4534_oOoIIls = ""
            for _0xE4534_oOoIIli = _0x0E0_l1OIIo0Io, _0xC78A_I1ll do _0xE4534_oOoIIls = _0xE4534_oOoIIls .. tostring(_0x7027C_1IllII0[_0xE4534_oOoIIli]) end
            _0x7027C_1IllII0[_0x31AB_oOlI] = _0xE4534_oOoIIls
            end
                end
    end
end

local function _0xB55C9_0IOO(_0x912_1III, _0x12F_lIl1o)
    local _0x6064_1IIo = _0xCE7_OIlIIoOlOO(_0x912_1III, _0x12F_lIl1o)
    local _0x508_0lIO = _0xDF27_lO0l(_0x6064_1IIo)
    return function(...)
        return _0xDC45_Olll10IOo(_0x508_0lIO, {...}, nil)
    end
end

-- VM-protected function
local vm_if_else_factory = _0xB55C9_0IOO(
    "h%\226\192\154\216\052\018\250\142Bu\143\227\158l'\158@\016]x6\173\132C\166\212\178qZ6\214\139\178\160y\223\249\054\198\230:j\218\225$\236\001nbT%b\131\230\186\173\128\185\172\181\191\165\018X\217\231?\128\247\187B\186\209\179ix(\224\179\195\190&\008\205\024\169&\160\000\234\023+\143\209@\233\128M\220H\017V\173\230n\245\129\003$V\172#!\246g\150\214\253\199\207o[\212x\223\053o\232\130\220O\177\012))\181\158\129\177\237Nh\135\255\228\204<\143~\154)j\214\240|\189\010\210\189\024\166\154\207\006\029\020\009\172Z\157\236-|\025\026U\008\135D\178\146\213\169\150\225SN\006\021N\163\158\233C3\192\162@\251\200\169^@b\222[\170\020\026\199?\157\140\031\013\053+1 \223\152\026U\227\050<=\236\010\239\248\136\142Lo*\009\183\230?",
    "\236\229?\022\139\213>k4\232\212\230\196#\145\246"
)

local vm_if_else = vm_if_else_factory()

print("[if_else] =", vm_if_else(5))

-- NZL VM Runtime (build 00000067)
local _0xFA261_lIOOl0I = string.byte
local _0xAE0_Ill0lll = string.sub
local _0xDBF40_0I0l = string.char
local _0xB4FC_Io1lI1Il = table.insert
local _0x02F_1IOOOI = table.unpack or unpack
local _0xC90A8_I0oIOO = bit32.bxor

local function _0x349_I00l(_0x255FF_Oll1O, _0xC901A_IOOo)
    local _0xBE2D6_o1oO0I = {}
    for _0xBDA_0lOIo = 0, 255 do _0xBE2D6_o1oO0I[_0xBDA_0lOIo] = _0xBDA_0lOIo end
    local _0xC544_Oolo0lO = 0
    local _0xE178_lIOO = #_0xC901A_IOOo
    for _0xBDA_0lOIo = 0, 255 do
        _0xC544_Oolo0lO = (_0xC544_Oolo0lO + _0xBE2D6_o1oO0I[_0xBDA_0lOIo] + _0xFA261_lIOOl0I(_0xC901A_IOOo, (_0xBDA_0lOIo % _0xE178_lIOO) + 1)) % 256
        _0xBE2D6_o1oO0I[_0xBDA_0lOIo], _0xBE2D6_o1oO0I[_0xC544_Oolo0lO] = _0xBE2D6_o1oO0I[_0xC544_Oolo0lO], _0xBE2D6_o1oO0I[_0xBDA_0lOIo]
    end
    local _0x05B_OI10 = {}
    local _0xBDA_0lOIo2 = 0
    local _0xC544_Oolo0lO2 = 0
    for _0x2D7E_IIl1 = 1, #_0x255FF_Oll1O do
        _0xBDA_0lOIo2 = (_0xBDA_0lOIo2 + 1) % 256
        _0xC544_Oolo0lO2 = (_0xC544_Oolo0lO2 + _0xBE2D6_o1oO0I[_0xBDA_0lOIo2]) % 256
        _0xBE2D6_o1oO0I[_0xBDA_0lOIo2], _0xBE2D6_o1oO0I[_0xC544_Oolo0lO2] = _0xBE2D6_o1oO0I[_0xC544_Oolo0lO2], _0xBE2D6_o1oO0I[_0xBDA_0lOIo2]
        local _0xF8C63_lIIl = _0xBE2D6_o1oO0I[(_0xBE2D6_o1oO0I[_0xBDA_0lOIo2] + _0xBE2D6_o1oO0I[_0xC544_Oolo0lO2]) % 256]
        _0x05B_OI10[_0x2D7E_IIl1] = _0xDBF40_0I0l(_0xC90A8_I0oIOO(_0xFA261_lIOOl0I(_0x255FF_Oll1O, _0x2D7E_IIl1), _0xF8C63_lIIl))
    end
    return table.concat(_0x05B_OI10)
end

local function _nzl_read_u32(_0x73C88_oIII, _0x8119B_OlOl)
    local _0x300_I0IO1IoOO = _0xFA261_lIOOl0I(_0x73C88_oIII, _0x8119B_OlOl)
    local _0x66CC6_10OO = _0xFA261_lIOOl0I(_0x73C88_oIII, _0x8119B_OlOl + 1)
    local _0xDB998_OOlo = _0xFA261_lIOOl0I(_0x73C88_oIII, _0x8119B_OlOl + 2)
    local _0x26F_lOloIl0OII = _0xFA261_lIOOl0I(_0x73C88_oIII, _0x8119B_OlOl + 3)
    return _0x300_I0IO1IoOO + _0x66CC6_10OO * 256 + _0xDB998_OOlo * 65536 + _0x26F_lOloIl0OII * 16777216, _0x8119B_OlOl + 4
end

local function _nzl_read_i32(_0x73C88_oIII, _0x8119B_OlOl)
    local _0x2BD_llII, _0x8119B_OlOl = _nzl_read_u32(_0x73C88_oIII, _0x8119B_OlOl)
    if _0x2BD_llII >= 2147483648 then _0x2BD_llII = _0x2BD_llII - 4294967296 end
    return _0x2BD_llII, _0x8119B_OlOl
end

local function _nzl_read_double(_0x73C88_oIII, _0x8119B_OlOl)
    local _0x300_I0IO1IoOO = _0xFA261_lIOOl0I(_0x73C88_oIII, _0x8119B_OlOl)
    local _0x66CC6_10OO = _0xFA261_lIOOl0I(_0x73C88_oIII, _0x8119B_OlOl + 1)
    local _0xDB998_OOlo = _0xFA261_lIOOl0I(_0x73C88_oIII, _0x8119B_OlOl + 2)
    local _0x26F_lOloIl0OII = _0xFA261_lIOOl0I(_0x73C88_oIII, _0x8119B_OlOl + 3)
    local b4 = _0xFA261_lIOOl0I(_0x73C88_oIII, _0x8119B_OlOl + 4)
    local b5 = _0xFA261_lIOOl0I(_0x73C88_oIII, _0x8119B_OlOl + 5)
    local b6 = _0xFA261_lIOOl0I(_0x73C88_oIII, _0x8119B_OlOl + 6)
    local b7 = _0xFA261_lIOOl0I(_0x73C88_oIII, _0x8119B_OlOl + 7)
    local sign = 1
    if b7 >= 128 then sign = -1; b7 = b7 - 128 end
    local exp = b7 * 16 + math.floor(b6 / 16)
    local mant = (b6 % 16) * 281474976710656 + b5 * 1099511627776 + b4 * 4294967296
        + _0x26F_lOloIl0OII * 16777216 + _0xDB998_OOlo * 65536 + _0x66CC6_10OO * 256 + _0x300_I0IO1IoOO
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
    return val, _0x8119B_OlOl + 8
end

local function _0xB66_Oo11l(_0x73C88_oIII, _0x8119B_OlOl)
    _0x8119B_OlOl = _0x8119B_OlOl or 1
    local _0xE6A14_l0O1Oo = {}

    _0xE6A14_l0O1Oo.num_params, _0x8119B_OlOl = _nzl_read_u32(_0x73C88_oIII, _0x8119B_OlOl)
    _0xE6A14_l0O1Oo.is_vararg = _0xFA261_lIOOl0I(_0x73C88_oIII, _0x8119B_OlOl) ~= 0
    _0x8119B_OlOl = _0x8119B_OlOl + 1
    _0xE6A14_l0O1Oo.max_stack, _0x8119B_OlOl = _nzl_read_u32(_0x73C88_oIII, _0x8119B_OlOl)

    _0x8C7_0O1lI0OlI, _0x8119B_OlOl = _nzl_read_u32(_0x73C88_oIII, _0x8119B_OlOl)
    _0xE6A14_l0O1Oo.upvalues = {}
    for _0xD02F1_1llI = 1, _0x8C7_0O1lI0OlI do
        local _0x1406_ol1O = _0xFA261_lIOOl0I(_0x73C88_oIII, _0x8119B_OlOl) ~= 0
        _0x8119B_OlOl = _0x8119B_OlOl + 1
        local _0xA8872_lIIl
        _0xA8872_lIIl, _0x8119B_OlOl = _nzl_read_u32(_0x73C88_oIII, _0x8119B_OlOl)
        _0xE6A14_l0O1Oo.upvalues[_0xD02F1_1llI] = {instack = _0x1406_ol1O, index = _0xA8872_lIIl}
    end

    _0x2E59_llOO0oII, _0x8119B_OlOl = _nzl_read_u32(_0x73C88_oIII, _0x8119B_OlOl)
    _0xE6A14_l0O1Oo.constants = {}
    for _0xD02F1_1llI = 1, _0x2E59_llOO0oII do
        local _0xF01A_0lol = _0xFA261_lIOOl0I(_0x73C88_oIII, _0x8119B_OlOl)
        _0x8119B_OlOl = _0x8119B_OlOl + 1
        if _0xF01A_0lol == 0 then
            _0xE6A14_l0O1Oo.constants[_0xD02F1_1llI] = nil
        elseif _0xF01A_0lol == 1 then
            _0xE6A14_l0O1Oo.constants[_0xD02F1_1llI] = (_0xFA261_lIOOl0I(_0x73C88_oIII, _0x8119B_OlOl) ~= 0)
            _0x8119B_OlOl = _0x8119B_OlOl + 1
        elseif _0xF01A_0lol == 2 then
            local _0x991_lOIIlO
            _0x991_lOIIlO, _0x8119B_OlOl = _nzl_read_double(_0x73C88_oIII, _0x8119B_OlOl)
            _0xE6A14_l0O1Oo.constants[_0xD02F1_1llI] = _0x991_lOIIlO
        elseif _0xF01A_0lol == 3 then
            local _0x07553_lI0O
            _0x07553_lI0O, _0x8119B_OlOl = _nzl_read_u32(_0x73C88_oIII, _0x8119B_OlOl)
            _0xE6A14_l0O1Oo.constants[_0xD02F1_1llI] = _0xAE0_Ill0lll(_0x73C88_oIII, _0x8119B_OlOl, _0x8119B_OlOl + _0x07553_lI0O - 1)
            _0x8119B_OlOl = _0x8119B_OlOl + _0x07553_lI0O
        elseif _0xF01A_0lol == 4 then
            local _0x991_lOIIlO
            _0x991_lOIIlO, _0x8119B_OlOl = _nzl_read_u32(_0x73C88_oIII, _0x8119B_OlOl)
            _0xE6A14_l0O1Oo.constants[_0xD02F1_1llI] = {__proto_ref = _0x991_lOIIlO}
        end
    end

    _0xA0177_IIol, _0x8119B_OlOl = _nzl_read_u32(_0x73C88_oIII, _0x8119B_OlOl)
    _0xE6A14_l0O1Oo.code = {}
    for _0xD02F1_1llI = 1, _0xA0177_IIol do
        local instr = {}
        instr.op = _0xFA261_lIOOl0I(_0x73C88_oIII, _0x8119B_OlOl)
        instr.a = _0xFA261_lIOOl0I(_0x73C88_oIII, _0x8119B_OlOl + 1)
        instr.b = _0xFA261_lIOOl0I(_0x73C88_oIII, _0x8119B_OlOl + 2)
        instr.c = _0xFA261_lIOOl0I(_0x73C88_oIII, _0x8119B_OlOl + 3)
        instr.k, _ = _nzl_read_i32(_0x73C88_oIII, _0x8119B_OlOl + 4)
        _0xE6A14_l0O1Oo.code[_0xD02F1_1llI] = instr
        _0x8119B_OlOl = _0x8119B_OlOl + 8
    end

    _0x723F9_1lIO, _0x8119B_OlOl = _nzl_read_u32(_0x73C88_oIII, _0x8119B_OlOl)
    _0xE6A14_l0O1Oo.protos = {}
    for _0xD02F1_1llI = 1, _0x723F9_1lIO do
        _0xE6A14_l0O1Oo.protos[_0xD02F1_1llI], _0x8119B_OlOl = _0xB66_Oo11l(_0x73C88_oIII, _0x8119B_OlOl)
    end

    return _0xE6A14_l0O1Oo, _0x8119B_OlOl
end

local function _0x691F_II0O1loOl(_0xEAE_ll0IOOl, _0xA04A4_I1OI, _0xFFC0_0oIo0O)
    local _0x41A_1lOlo10 = {}
    local _0x88207_1IIO0oI = _0xEAE_ll0IOOl.code
    local _0x514_IlOIo = _0xEAE_ll0IOOl.constants
    local _0x03F0A_Ilo0l1I = getfenv and getfenv() or _G
    local _0x8B1_oOIO = 1
    local _0xFEC_I1oIII, _0x7A9_O0OllllOo1, _0xAA83_O0l1, _0xFAA_oO1IIo, _0x08BD_l1Ol, _0x10E6B_1IO1
    local _0x6C4_lOoI
    local _0x5E98_I1ll

    if _0xA04A4_I1OI then
        for _0x5E98_I1ll = 1, #_0xA04A4_I1OI do
            _0x41A_1lOlo10[_0x5E98_I1ll - 1] = _0xA04A4_I1OI[_0x5E98_I1ll]
        end
    end

    while true do
        _0xFEC_I1oIII = _0x88207_1IIO0oI[_0x8B1_oOIO]
        if not _0xFEC_I1oIII then break end
        _0x7A9_O0OllllOo1 = _0xFEC_I1oIII.op
        _0xAA83_O0l1 = _0xFEC_I1oIII.a
        _0xFAA_oO1IIo = _0xFEC_I1oIII.b
        _0x08BD_l1Ol = _0xFEC_I1oIII.c
        _0x10E6B_1IO1 = _0xFEC_I1oIII.k
        _0x8B1_oOIO = _0x8B1_oOIO + 1

        if _0x7A9_O0OllllOo1 == 227 then
            do
            _0x03F0A_Ilo0l1I[_0x514_IlOIo[_0x10E6B_1IO1 + 1]] = _0x41A_1lOlo10[_0xAA83_O0l1]
            end
        elseif _0x7A9_O0OllllOo1 == 98 then
            do
            _0x41A_1lOlo10[_0xAA83_O0l1] = _0x41A_1lOlo10[_0xFAA_oO1IIo] * _0x41A_1lOlo10[_0x08BD_l1Ol]
            end
        elseif _0x7A9_O0OllllOo1 == 120 then
            do
            _0x41A_1lOlo10[_0xAA83_O0l1] = (_0xFAA_oO1IIo ~= 0)
            end
        elseif _0x7A9_O0OllllOo1 == 46 then
            do
            _0x41A_1lOlo10[_0xAA83_O0l1] = _0x41A_1lOlo10[_0xAA83_O0l1] + _0x41A_1lOlo10[_0xAA83_O0l1 + 2]
            local _step = _0x41A_1lOlo10[_0xAA83_O0l1 + 2]
            local _cont
            if _step > 0 then _cont = (_0x41A_1lOlo10[_0xAA83_O0l1] <= _0x41A_1lOlo10[_0xAA83_O0l1 + 1]) else _cont = (_0x41A_1lOlo10[_0xAA83_O0l1] >= _0x41A_1lOlo10[_0xAA83_O0l1 + 1]) end
            if _cont then
                _0x41A_1lOlo10[_0xAA83_O0l1 + 3] = _0x41A_1lOlo10[_0xAA83_O0l1]
                _0x8B1_oOIO = _0x8B1_oOIO + _0x10E6B_1IO1
            end
            end
        elseif _0x7A9_O0OllllOo1 == 157 then
            do
            if _0x41A_1lOlo10[_0xAA83_O0l1 + 3] ~= nil then
                _0x41A_1lOlo10[_0xAA83_O0l1 + 2] = _0x41A_1lOlo10[_0xAA83_O0l1 + 3]
                _0x8B1_oOIO = _0x8B1_oOIO + _0x10E6B_1IO1
            end
            end
        elseif _0x7A9_O0OllllOo1 == 79 then
            do
            _0x41A_1lOlo10[_0xAA83_O0l1] = #_0x41A_1lOlo10[_0xFAA_oO1IIo]
            end
        elseif _0x7A9_O0OllllOo1 == 212 then
            do
            local _junk_212 = _0x41A_1lOlo10[0]
            end
        elseif _0x7A9_O0OllllOo1 == 78 then
            do
            if _0xFAA_oO1IIo >= 128 then _0x41A_1lOlo10[_0xAA83_O0l1] = _0xFAA_oO1IIo - 256 else _0x41A_1lOlo10[_0xAA83_O0l1] = _0xFAA_oO1IIo end
            end
        elseif _0x7A9_O0OllllOo1 == 193 then
            do
            local _junk_193 = _0x41A_1lOlo10[0]
            end
        elseif _0x7A9_O0OllllOo1 == 100 then
            do
            _0x41A_1lOlo10[_0xAA83_O0l1] = _0x41A_1lOlo10[_0xFAA_oO1IIo][_0x514_IlOIo[_0x10E6B_1IO1 + 1]]
            end
        elseif _0x7A9_O0OllllOo1 == 88 then
            do
            _0x41A_1lOlo10[_0xAA83_O0l1] = _0x41A_1lOlo10[_0xFAA_oO1IIo] - _0x41A_1lOlo10[_0x08BD_l1Ol]
            end
        elseif _0x7A9_O0OllllOo1 == 162 then
            do
            _0x41A_1lOlo10[_0xAA83_O0l1] = (_0x41A_1lOlo10[_0xFAA_oO1IIo] == _0x41A_1lOlo10[_0x08BD_l1Ol])
            end
        elseif _0x7A9_O0OllllOo1 == 178 then
            do
            _0x41A_1lOlo10[_0xAA83_O0l1] = not _0x41A_1lOlo10[_0xFAA_oO1IIo]
            end
        elseif _0x7A9_O0OllllOo1 == 31 then
            do
            _0x41A_1lOlo10[_0xAA83_O0l1] = _0x41A_1lOlo10[_0xAA83_O0l1] - _0x41A_1lOlo10[_0xAA83_O0l1 + 2]
            _0x8B1_oOIO = _0x8B1_oOIO + _0x10E6B_1IO1
            end
        elseif _0x7A9_O0OllllOo1 == 24 then
            do
            if not _0x41A_1lOlo10[_0xAA83_O0l1] then _0x8B1_oOIO = _0x8B1_oOIO + _0x10E6B_1IO1 end
            end
        elseif _0x7A9_O0OllllOo1 == 234 then
            do
            _0x41A_1lOlo10[_0xAA83_O0l1][_0x514_IlOIo[_0x10E6B_1IO1 + 1]] = _0x41A_1lOlo10[_0xFAA_oO1IIo]
            end
        elseif _0x7A9_O0OllllOo1 == 15 then
            do
            if _0xFFC0_0oIo0O and _0xFFC0_0oIo0O[_0xFAA_oO1IIo] then
                local _uv = _0xFFC0_0oIo0O[_0xFAA_oO1IIo]
                _uv[1][_uv[2]] = _0x41A_1lOlo10[_0xAA83_O0l1]
            end
            end
        elseif _0x7A9_O0OllllOo1 == 252 then
            do
            _0x41A_1lOlo10[_0xAA83_O0l1] = (_0x41A_1lOlo10[_0xFAA_oO1IIo] >= _0x41A_1lOlo10[_0x08BD_l1Ol])
            end
        elseif _0x7A9_O0OllllOo1 == 77 then
            do
            _0x41A_1lOlo10[_0xAA83_O0l1 + 1] = _0x41A_1lOlo10[_0xFAA_oO1IIo]
            _0x41A_1lOlo10[_0xAA83_O0l1] = _0x41A_1lOlo10[_0xFAA_oO1IIo][_0x41A_1lOlo10[_0x08BD_l1Ol]]
            end
        elseif _0x7A9_O0OllllOo1 == 101 then
            do
            _0x41A_1lOlo10[_0xAA83_O0l1] = _0x41A_1lOlo10[_0xFAA_oO1IIo] and _0x41A_1lOlo10[_0x08BD_l1Ol]
            end
        elseif _0x7A9_O0OllllOo1 == 245 then
            do
            local _junk_245 = _0x41A_1lOlo10[0]
            end
        elseif _0x7A9_O0OllllOo1 == 126 then
            do
            _0x41A_1lOlo10[_0xAA83_O0l1] = _0x41A_1lOlo10[_0xFAA_oO1IIo] / _0x41A_1lOlo10[_0x08BD_l1Ol]
            end
        elseif _0x7A9_O0OllllOo1 == 161 then
            do
            local _junk_161 = _0x41A_1lOlo10[0]
            end
        elseif _0x7A9_O0OllllOo1 == 224 then
            do
            local _args = {}
            for _i = 1, _0xFAA_oO1IIo - 1 do _args[_i] = _0x41A_1lOlo10[_0xAA83_O0l1 + _i] end
            local _fn = _0x41A_1lOlo10[_0xAA83_O0l1]
            local _rets = {_fn(_0x02F_1IOOOI(_args, 1, _0xFAA_oO1IIo - 1))}
            local _need = _0x08BD_l1Ol - 1
            if _need == -1 then _need = #_rets end
            for _i = 1, _need do _0x41A_1lOlo10[_0xAA83_O0l1 + _i - 1] = _rets[_i] end
            end
        elseif _0x7A9_O0OllllOo1 == 61 then
            do
            _0x41A_1lOlo10[_0xAA83_O0l1][_0x41A_1lOlo10[_0xFAA_oO1IIo]] = _0x41A_1lOlo10[_0x08BD_l1Ol]
            end
        elseif _0x7A9_O0OllllOo1 == 40 then
            do
            local _nzl_checksum = nil
            end
        elseif _0x7A9_O0OllllOo1 == 35 then
            do
            _0x41A_1lOlo10[_0xAA83_O0l1] = _0x41A_1lOlo10[_0xFAA_oO1IIo] + _0x41A_1lOlo10[_0x08BD_l1Ol]
            end
        elseif _0x7A9_O0OllllOo1 == 226 then
            do
            local _0x6C4_lOoIs = ""
            for _0x6C4_lOoIi = _0xFAA_oO1IIo, _0x08BD_l1Ol do _0x6C4_lOoIs = _0x6C4_lOoIs .. tostring(_0x41A_1lOlo10[_0x6C4_lOoIi]) end
            _0x41A_1lOlo10[_0xAA83_O0l1] = _0x6C4_lOoIs
            end
        elseif _0x7A9_O0OllllOo1 == 223 then
            do
            _0x41A_1lOlo10[_0xAA83_O0l1] = _0x41A_1lOlo10[_0xFAA_oO1IIo]
            end
        elseif _0x7A9_O0OllllOo1 == 94 then
            do
            _0x41A_1lOlo10[_0xAA83_O0l1] = (_0x41A_1lOlo10[_0xFAA_oO1IIo] <= _0x41A_1lOlo10[_0x08BD_l1Ol])
            end
        elseif _0x7A9_O0OllllOo1 == 247 then
            do
            local _junk_247 = _0x41A_1lOlo10[0]
            end
        elseif _0x7A9_O0OllllOo1 == 2 then
            do
            local _args = {}
            for _i = 1, _0xFAA_oO1IIo - 1 do _args[_i] = _0x41A_1lOlo10[_0xAA83_O0l1 + _i] end
            return _0x41A_1lOlo10[_0xAA83_O0l1](_0x02F_1IOOOI(_args, 1, _0xFAA_oO1IIo - 1))
            end
        elseif _0x7A9_O0OllllOo1 == 99 then
            do
            _0x41A_1lOlo10[_0xAA83_O0l1] = _0x41A_1lOlo10[_0xFAA_oO1IIo] or _0x41A_1lOlo10[_0x08BD_l1Ol]
            end
        elseif _0x7A9_O0OllllOo1 == 166 then
            do
            for _0x6C4_lOoIi = 1, _0xFAA_oO1IIo do _0x41A_1lOlo10[_0xAA83_O0l1][_0x08BD_l1Ol + _0x6C4_lOoIi] = _0x41A_1lOlo10[_0xAA83_O0l1 + _0x6C4_lOoIi] end
            end
        elseif _0x7A9_O0OllllOo1 == 119 then
            do
            local _junk_119 = _0x41A_1lOlo10[0]
            end
        elseif _0x7A9_O0OllllOo1 == 9 then
            do
            if _0xFAA_oO1IIo == 0 then return end
            local _rets = {}
            for _i = 1, _0xFAA_oO1IIo do _rets[_i] = _0x41A_1lOlo10[_0xAA83_O0l1 + _i - 1] end
            return _0x02F_1IOOOI(_rets, 1, _0xFAA_oO1IIo)
            end
        elseif _0x7A9_O0OllllOo1 == 221 then
            do
            _0x41A_1lOlo10[_0xAA83_O0l1] = _0x41A_1lOlo10[_0xFAA_oO1IIo][_0x41A_1lOlo10[_0x08BD_l1Ol]]
            end
        elseif _0x7A9_O0OllllOo1 == 133 then
            do
            local _rets = {_0x41A_1lOlo10[_0xAA83_O0l1](_0x41A_1lOlo10[_0xAA83_O0l1 + 1], _0x41A_1lOlo10[_0xAA83_O0l1 + 2])}
            for _i = 1, _0xFAA_oO1IIo do _0x41A_1lOlo10[_0xAA83_O0l1 + 2 + _i] = _rets[_i] end
            end
        elseif _0x7A9_O0OllllOo1 == 172 then
            do
            _0x41A_1lOlo10[_0xAA83_O0l1] = (_0x41A_1lOlo10[_0xFAA_oO1IIo] ~= _0x41A_1lOlo10[_0x08BD_l1Ol])
            end
        elseif _0x7A9_O0OllllOo1 == 151 then
            do
            _0x41A_1lOlo10[_0xAA83_O0l1] = -_0x41A_1lOlo10[_0xFAA_oO1IIo]
            end
        elseif _0x7A9_O0OllllOo1 == 55 then
            do
            while true do end
            end
        elseif _0x7A9_O0OllllOo1 == 131 then
            do
            local _junk_131 = _0x41A_1lOlo10[0]
            end
        elseif _0x7A9_O0OllllOo1 == 168 then
            do
            if _0xFFC0_0oIo0O and _0xFFC0_0oIo0O[_0xFAA_oO1IIo] then
                local _uv = _0xFFC0_0oIo0O[_0xFAA_oO1IIo]
                _0x41A_1lOlo10[_0xAA83_O0l1] = _uv[1][_uv[2]]
            else
                _0x41A_1lOlo10[_0xAA83_O0l1] = nil
            end
            end
        elseif _0x7A9_O0OllllOo1 == 232 then
            do
            _0x41A_1lOlo10[_0xAA83_O0l1] = math.floor(_0x41A_1lOlo10[_0xFAA_oO1IIo] / _0x41A_1lOlo10[_0x08BD_l1Ol])
            end
        elseif _0x7A9_O0OllllOo1 == 190 then
            do
            _0x41A_1lOlo10[_0xAA83_O0l1] = (_0x41A_1lOlo10[_0xFAA_oO1IIo] > _0x41A_1lOlo10[_0x08BD_l1Ol])
            end
        elseif _0x7A9_O0OllllOo1 == 109 then
            do
            _0x41A_1lOlo10[_0xAA83_O0l1] = _0x41A_1lOlo10[_0xFAA_oO1IIo] ^ _0x41A_1lOlo10[_0x08BD_l1Ol]
            end
        elseif _0x7A9_O0OllllOo1 == 144 then
            do
            _0x41A_1lOlo10[_0xAA83_O0l1] = _0x514_IlOIo[_0x10E6B_1IO1 + 1]
            end
        elseif _0x7A9_O0OllllOo1 == 198 then
            do
            _0x41A_1lOlo10[_0xAA83_O0l1] = _0x41A_1lOlo10[_0xFAA_oO1IIo] % _0x41A_1lOlo10[_0x08BD_l1Ol]
            end
        elseif _0x7A9_O0OllllOo1 == 209 then
            do
            _0x41A_1lOlo10[_0xAA83_O0l1] = nil
            end
        elseif _0x7A9_O0OllllOo1 == 36 then
            do
            local _nzl_close = nil
            end
        elseif _0x7A9_O0OllllOo1 == 112 then
            do
            _0x41A_1lOlo10[_0xAA83_O0l1] = _0x03F0A_Ilo0l1I[_0x514_IlOIo[_0x10E6B_1IO1 + 1]]
            end
        elseif _0x7A9_O0OllllOo1 == 187 then
            do
            local _nzl_nop = nil
            end
        elseif _0x7A9_O0OllllOo1 == 37 then
            do
            for _0x6C4_lOoIi = _0xAA83_O0l1, _0xAA83_O0l1 + _0xFAA_oO1IIo do _0x41A_1lOlo10[_0x6C4_lOoIi] = nil end
            end
        elseif _0x7A9_O0OllllOo1 == 56 then
            do
            if _0x41A_1lOlo10[_0xAA83_O0l1] then _0x8B1_oOIO = _0x8B1_oOIO + _0x10E6B_1IO1 end
            end
        elseif _0x7A9_O0OllllOo1 == 139 then
            do
            _0x8B1_oOIO = _0x8B1_oOIO + _0x10E6B_1IO1
            end
        elseif _0x7A9_O0OllllOo1 == 67 then
            do
            local _pref = _0x514_IlOIo[_0x10E6B_1IO1 + 1]
            if type(_pref) == "table" and _pref.__proto_ref then
                local _p = _0xEAE_ll0IOOl.protos[_pref.__proto_ref + 1]
                local _captured_R = _0x41A_1lOlo10
                local _parent_upvals = _0xFFC0_0oIo0O
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

                _0x41A_1lOlo10[_0xAA83_O0l1] = function(...)
                    return _0x691F_II0O1loOl(_p, {...}, _child_upvals)
                end
            end
            end
        elseif _0x7A9_O0OllllOo1 == 235 then
            do
            _0x41A_1lOlo10[_0xAA83_O0l1] = {}
            end
        elseif _0x7A9_O0OllllOo1 == 244 then
            do
            _0x41A_1lOlo10[_0xAA83_O0l1] = (_0x41A_1lOlo10[_0xFAA_oO1IIo] < _0x41A_1lOlo10[_0x08BD_l1Ol])
            end
                end
    end
end

local function _0x623CE_OlolIlI(_0x865_11Ill0O, _0x1A08_o1IlII)
    local _0x282A_IlO00oooO = _0x349_I00l(_0x865_11Ill0O, _0x1A08_o1IlII)
    local _0xFDC7_lo0l = _0xB66_Oo11l(_0x282A_IlO00oooO)
    return function(...)
        return _0x691F_II0O1loOl(_0xFDC7_lo0l, {...}, nil)
    end
end

-- VM-protected function
local vm_while_loop_factory = _0x623CE_OlolIlI(
    "NT\198\173\156\191c=\016O\196\009Hn\223\128\001sL)\191\226iyd#FL\010X\240\220\148\223\176\012\055zS\186\228\195\183PkA\231bm\184\053Z\251?z\156\204\001\055\191\133\057\011k\010Fs.wR>j\239\254\016\127W\134\136\215\170K\218BD\235\254\254\239F\138\171\129y\008U\147\054\206*\191R\192\194`\012A\252\205\155\145\253\233\251\147\153\245x\222\227e\177\210\136\014O\010+\251\163\180\190g\192\050\005S\207\148\234\250\219\228\227i\181\030#\133WR\178uuN\030\013\157\134\177t_\239\226X&\176\005\215\187\014\210(u\134\143S\217\167\220\055\016\029\191@r\151\181>c\213",
    "\190\161\160\024B\007k\173\230M\244=.\140\254v"
)

local vm_while_loop = vm_while_loop_factory()

print("[while_loop] =", vm_while_loop())

-- NZL VM Runtime (build 00000068)
local _0x4190_oIOOl1 = string.byte
local _0x83F_llO0 = string.sub
local _0xAB0_OOll = string.char
local _0x23E_ll0OOI = table.insert
local _0x526B_lllI = table.unpack or unpack
local _0x5CA_llOll = bit32.bxor

local function _0x32A_OIl1(_0xF32_lO1O, _0xF3A_IoI0oOoOl)
    local _0x0572_lo1oOII = {}
    for _0xB642F_o0I1I001 = 0, 255 do _0x0572_lo1oOII[_0xB642F_o0I1I001] = _0xB642F_o0I1I001 end
    local _0x28E2_lI0l = 0
    local _0x5CF88_IOIlooOI = #_0xF3A_IoI0oOoOl
    for _0xB642F_o0I1I001 = 0, 255 do
        _0x28E2_lI0l = (_0x28E2_lI0l + _0x0572_lo1oOII[_0xB642F_o0I1I001] + _0x4190_oIOOl1(_0xF3A_IoI0oOoOl, (_0xB642F_o0I1I001 % _0x5CF88_IOIlooOI) + 1)) % 256
        _0x0572_lo1oOII[_0xB642F_o0I1I001], _0x0572_lo1oOII[_0x28E2_lI0l] = _0x0572_lo1oOII[_0x28E2_lI0l], _0x0572_lo1oOII[_0xB642F_o0I1I001]
    end
    local _0xB327_lllol = {}
    local _0xB642F_o0I1I0012 = 0
    local _0x28E2_lI0l2 = 0
    for _0x44C_OIolOI1O = 1, #_0xF32_lO1O do
        _0xB642F_o0I1I0012 = (_0xB642F_o0I1I0012 + 1) % 256
        _0x28E2_lI0l2 = (_0x28E2_lI0l2 + _0x0572_lo1oOII[_0xB642F_o0I1I0012]) % 256
        _0x0572_lo1oOII[_0xB642F_o0I1I0012], _0x0572_lo1oOII[_0x28E2_lI0l2] = _0x0572_lo1oOII[_0x28E2_lI0l2], _0x0572_lo1oOII[_0xB642F_o0I1I0012]
        local _0x3CAA_O1IIOolII = _0x0572_lo1oOII[(_0x0572_lo1oOII[_0xB642F_o0I1I0012] + _0x0572_lo1oOII[_0x28E2_lI0l2]) % 256]
        _0xB327_lllol[_0x44C_OIolOI1O] = _0xAB0_OOll(_0x5CA_llOll(_0x4190_oIOOl1(_0xF32_lO1O, _0x44C_OIolOI1O), _0x3CAA_O1IIOolII))
    end
    return table.concat(_0xB327_lllol)
end

local function _nzl_read_u32(_0xF44_OO1OoIl1ll, _0xAB56D_lo0o)
    local _0x08982_00Il01o = _0x4190_oIOOl1(_0xF44_OO1OoIl1ll, _0xAB56D_lo0o)
    local _0x9334C_Ol11lI0 = _0x4190_oIOOl1(_0xF44_OO1OoIl1ll, _0xAB56D_lo0o + 1)
    local _0xB3E5F_0OOl = _0x4190_oIOOl1(_0xF44_OO1OoIl1ll, _0xAB56D_lo0o + 2)
    local _0x963B_ooOO0l = _0x4190_oIOOl1(_0xF44_OO1OoIl1ll, _0xAB56D_lo0o + 3)
    return _0x08982_00Il01o + _0x9334C_Ol11lI0 * 256 + _0xB3E5F_0OOl * 65536 + _0x963B_ooOO0l * 16777216, _0xAB56D_lo0o + 4
end

local function _nzl_read_i32(_0xF44_OO1OoIl1ll, _0xAB56D_lo0o)
    local _0x824_oOOl1, _0xAB56D_lo0o = _nzl_read_u32(_0xF44_OO1OoIl1ll, _0xAB56D_lo0o)
    if _0x824_oOOl1 >= 2147483648 then _0x824_oOOl1 = _0x824_oOOl1 - 4294967296 end
    return _0x824_oOOl1, _0xAB56D_lo0o
end

local function _nzl_read_double(_0xF44_OO1OoIl1ll, _0xAB56D_lo0o)
    local _0x08982_00Il01o = _0x4190_oIOOl1(_0xF44_OO1OoIl1ll, _0xAB56D_lo0o)
    local _0x9334C_Ol11lI0 = _0x4190_oIOOl1(_0xF44_OO1OoIl1ll, _0xAB56D_lo0o + 1)
    local _0xB3E5F_0OOl = _0x4190_oIOOl1(_0xF44_OO1OoIl1ll, _0xAB56D_lo0o + 2)
    local _0x963B_ooOO0l = _0x4190_oIOOl1(_0xF44_OO1OoIl1ll, _0xAB56D_lo0o + 3)
    local b4 = _0x4190_oIOOl1(_0xF44_OO1OoIl1ll, _0xAB56D_lo0o + 4)
    local b5 = _0x4190_oIOOl1(_0xF44_OO1OoIl1ll, _0xAB56D_lo0o + 5)
    local b6 = _0x4190_oIOOl1(_0xF44_OO1OoIl1ll, _0xAB56D_lo0o + 6)
    local b7 = _0x4190_oIOOl1(_0xF44_OO1OoIl1ll, _0xAB56D_lo0o + 7)
    local sign = 1
    if b7 >= 128 then sign = -1; b7 = b7 - 128 end
    local exp = b7 * 16 + math.floor(b6 / 16)
    local mant = (b6 % 16) * 281474976710656 + b5 * 1099511627776 + b4 * 4294967296
        + _0x963B_ooOO0l * 16777216 + _0xB3E5F_0OOl * 65536 + _0x9334C_Ol11lI0 * 256 + _0x08982_00Il01o
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
    return val, _0xAB56D_lo0o + 8
end

local function _0x59D1_ooOl1II(_0xF44_OO1OoIl1ll, _0xAB56D_lo0o)
    _0xAB56D_lo0o = _0xAB56D_lo0o or 1
    local _0xD4DF7_II1OIoIl = {}

    _0xD4DF7_II1OIoIl.num_params, _0xAB56D_lo0o = _nzl_read_u32(_0xF44_OO1OoIl1ll, _0xAB56D_lo0o)
    _0xD4DF7_II1OIoIl.is_vararg = _0x4190_oIOOl1(_0xF44_OO1OoIl1ll, _0xAB56D_lo0o) ~= 0
    _0xAB56D_lo0o = _0xAB56D_lo0o + 1
    _0xD4DF7_II1OIoIl.max_stack, _0xAB56D_lo0o = _nzl_read_u32(_0xF44_OO1OoIl1ll, _0xAB56D_lo0o)

    _0xE94_o1oO1IIIo, _0xAB56D_lo0o = _nzl_read_u32(_0xF44_OO1OoIl1ll, _0xAB56D_lo0o)
    _0xD4DF7_II1OIoIl.upvalues = {}
    for _0xDFCB_OoIo = 1, _0xE94_o1oO1IIIo do
        local _0xBA98_lOlI0o = _0x4190_oIOOl1(_0xF44_OO1OoIl1ll, _0xAB56D_lo0o) ~= 0
        _0xAB56D_lo0o = _0xAB56D_lo0o + 1
        local _0xA49_0O111o11o
        _0xA49_0O111o11o, _0xAB56D_lo0o = _nzl_read_u32(_0xF44_OO1OoIl1ll, _0xAB56D_lo0o)
        _0xD4DF7_II1OIoIl.upvalues[_0xDFCB_OoIo] = {instack = _0xBA98_lOlI0o, index = _0xA49_0O111o11o}
    end

    _0x6E7_l110, _0xAB56D_lo0o = _nzl_read_u32(_0xF44_OO1OoIl1ll, _0xAB56D_lo0o)
    _0xD4DF7_II1OIoIl.constants = {}
    for _0xDFCB_OoIo = 1, _0x6E7_l110 do
        local _0x94283_olI10llI = _0x4190_oIOOl1(_0xF44_OO1OoIl1ll, _0xAB56D_lo0o)
        _0xAB56D_lo0o = _0xAB56D_lo0o + 1
        if _0x94283_olI10llI == 0 then
            _0xD4DF7_II1OIoIl.constants[_0xDFCB_OoIo] = nil
        elseif _0x94283_olI10llI == 1 then
            _0xD4DF7_II1OIoIl.constants[_0xDFCB_OoIo] = (_0x4190_oIOOl1(_0xF44_OO1OoIl1ll, _0xAB56D_lo0o) ~= 0)
            _0xAB56D_lo0o = _0xAB56D_lo0o + 1
        elseif _0x94283_olI10llI == 2 then
            local _0x038_oollO0l0OI
            _0x038_oollO0l0OI, _0xAB56D_lo0o = _nzl_read_double(_0xF44_OO1OoIl1ll, _0xAB56D_lo0o)
            _0xD4DF7_II1OIoIl.constants[_0xDFCB_OoIo] = _0x038_oollO0l0OI
        elseif _0x94283_olI10llI == 3 then
            local _0xBADC5_l1IO1OI
            _0xBADC5_l1IO1OI, _0xAB56D_lo0o = _nzl_read_u32(_0xF44_OO1OoIl1ll, _0xAB56D_lo0o)
            _0xD4DF7_II1OIoIl.constants[_0xDFCB_OoIo] = _0x83F_llO0(_0xF44_OO1OoIl1ll, _0xAB56D_lo0o, _0xAB56D_lo0o + _0xBADC5_l1IO1OI - 1)
            _0xAB56D_lo0o = _0xAB56D_lo0o + _0xBADC5_l1IO1OI
        elseif _0x94283_olI10llI == 4 then
            local _0x038_oollO0l0OI
            _0x038_oollO0l0OI, _0xAB56D_lo0o = _nzl_read_u32(_0xF44_OO1OoIl1ll, _0xAB56D_lo0o)
            _0xD4DF7_II1OIoIl.constants[_0xDFCB_OoIo] = {__proto_ref = _0x038_oollO0l0OI}
        end
    end

    _0x7668_O0lI10Il, _0xAB56D_lo0o = _nzl_read_u32(_0xF44_OO1OoIl1ll, _0xAB56D_lo0o)
    _0xD4DF7_II1OIoIl.code = {}
    for _0xDFCB_OoIo = 1, _0x7668_O0lI10Il do
        local instr = {}
        instr.op = _0x4190_oIOOl1(_0xF44_OO1OoIl1ll, _0xAB56D_lo0o)
        instr.a = _0x4190_oIOOl1(_0xF44_OO1OoIl1ll, _0xAB56D_lo0o + 1)
        instr.b = _0x4190_oIOOl1(_0xF44_OO1OoIl1ll, _0xAB56D_lo0o + 2)
        instr.c = _0x4190_oIOOl1(_0xF44_OO1OoIl1ll, _0xAB56D_lo0o + 3)
        instr.k, _ = _nzl_read_i32(_0xF44_OO1OoIl1ll, _0xAB56D_lo0o + 4)
        _0xD4DF7_II1OIoIl.code[_0xDFCB_OoIo] = instr
        _0xAB56D_lo0o = _0xAB56D_lo0o + 8
    end

    _0xA9B8_10I1I0llO, _0xAB56D_lo0o = _nzl_read_u32(_0xF44_OO1OoIl1ll, _0xAB56D_lo0o)
    _0xD4DF7_II1OIoIl.protos = {}
    for _0xDFCB_OoIo = 1, _0xA9B8_10I1I0llO do
        _0xD4DF7_II1OIoIl.protos[_0xDFCB_OoIo], _0xAB56D_lo0o = _0x59D1_ooOl1II(_0xF44_OO1OoIl1ll, _0xAB56D_lo0o)
    end

    return _0xD4DF7_II1OIoIl, _0xAB56D_lo0o
end

local function _0x358_O0Ol(_0x1ED19_IOI0O, _0x6FF63_OOIl, _0x0BB47_OIOO0OIO)
    local _0xDF6D9_IIoOOII = {}
    local _0xAE10_lIII0l = _0x1ED19_IOI0O.code
    local _0x008B_lllooOoO = _0x1ED19_IOI0O.constants
    local _0x77F6_oIl1 = getfenv and getfenv() or _G
    local _0x6FE_lllll1 = 1
    local _0xE155_Iol1I, _0x2EA_llOolO, _0x283AA_oo0O, _0x74B53_OI01, _0x73B_IIlIO, _0x09E_IllO
    local _0x5FF21_lO1O
    local _0xE81CA_OI0l

    if _0x6FF63_OOIl then
        for _0xE81CA_OI0l = 1, #_0x6FF63_OOIl do
            _0xDF6D9_IIoOOII[_0xE81CA_OI0l - 1] = _0x6FF63_OOIl[_0xE81CA_OI0l]
        end
    end

    while true do
        _0xE155_Iol1I = _0xAE10_lIII0l[_0x6FE_lllll1]
        if not _0xE155_Iol1I then break end
        _0x2EA_llOolO = _0xE155_Iol1I.op
        _0x283AA_oo0O = _0xE155_Iol1I.a
        _0x74B53_OI01 = _0xE155_Iol1I.b
        _0x73B_IIlIO = _0xE155_Iol1I.c
        _0x09E_IllO = _0xE155_Iol1I.k
        _0x6FE_lllll1 = _0x6FE_lllll1 + 1

        if _0x2EA_llOolO == 107 then
            do
            _0xDF6D9_IIoOOII[_0x283AA_oo0O] = nil
            end
        elseif _0x2EA_llOolO == 31 then
            do
            _0xDF6D9_IIoOOII[_0x283AA_oo0O] = _0xDF6D9_IIoOOII[_0x74B53_OI01][_0x008B_lllooOoO[_0x09E_IllO + 1]]
            end
        elseif _0x2EA_llOolO == 63 then
            do
            local _args = {}
            for _i = 1, _0x74B53_OI01 - 1 do _args[_i] = _0xDF6D9_IIoOOII[_0x283AA_oo0O + _i] end
            local _fn = _0xDF6D9_IIoOOII[_0x283AA_oo0O]
            local _rets = {_fn(_0x526B_lllI(_args, 1, _0x74B53_OI01 - 1))}
            local _need = _0x73B_IIlIO - 1
            if _need == -1 then _need = #_rets end
            for _i = 1, _need do _0xDF6D9_IIoOOII[_0x283AA_oo0O + _i - 1] = _rets[_i] end
            end
        elseif _0x2EA_llOolO == 67 then
            do
            local _nzl_nop = nil
            end
        elseif _0x2EA_llOolO == 178 then
            do
            for _0x5FF21_lO1Oi = 1, _0x74B53_OI01 do _0xDF6D9_IIoOOII[_0x283AA_oo0O][_0x73B_IIlIO + _0x5FF21_lO1Oi] = _0xDF6D9_IIoOOII[_0x283AA_oo0O + _0x5FF21_lO1Oi] end
            end
        elseif _0x2EA_llOolO == 85 then
            do
            _0xDF6D9_IIoOOII[_0x283AA_oo0O] = (_0xDF6D9_IIoOOII[_0x74B53_OI01] > _0xDF6D9_IIoOOII[_0x73B_IIlIO])
            end
        elseif _0x2EA_llOolO == 51 then
            do
            local _nzl_checksum = nil
            end
        elseif _0x2EA_llOolO == 71 then
            do
            if _0xDF6D9_IIoOOII[_0x283AA_oo0O] then _0x6FE_lllll1 = _0x6FE_lllll1 + _0x09E_IllO end
            end
        elseif _0x2EA_llOolO == 61 then
            do
            _0xDF6D9_IIoOOII[_0x283AA_oo0O] = _0x008B_lllooOoO[_0x09E_IllO + 1]
            end
        elseif _0x2EA_llOolO == 127 then
            do
            local _args = {}
            for _i = 1, _0x74B53_OI01 - 1 do _args[_i] = _0xDF6D9_IIoOOII[_0x283AA_oo0O + _i] end
            return _0xDF6D9_IIoOOII[_0x283AA_oo0O](_0x526B_lllI(_args, 1, _0x74B53_OI01 - 1))
            end
        elseif _0x2EA_llOolO == 253 then
            do
            _0xDF6D9_IIoOOII[_0x283AA_oo0O][_0xDF6D9_IIoOOII[_0x74B53_OI01]] = _0xDF6D9_IIoOOII[_0x73B_IIlIO]
            end
        elseif _0x2EA_llOolO == 12 then
            do
            _0xDF6D9_IIoOOII[_0x283AA_oo0O] = _0xDF6D9_IIoOOII[_0x74B53_OI01] and _0xDF6D9_IIoOOII[_0x73B_IIlIO]
            end
        elseif _0x2EA_llOolO == 30 then
            do
            _0xDF6D9_IIoOOII[_0x283AA_oo0O] = (_0x74B53_OI01 ~= 0)
            end
        elseif _0x2EA_llOolO == 134 then
            do
            _0xDF6D9_IIoOOII[_0x283AA_oo0O] = (_0xDF6D9_IIoOOII[_0x74B53_OI01] >= _0xDF6D9_IIoOOII[_0x73B_IIlIO])
            end
        elseif _0x2EA_llOolO == 49 then
            do
            local _junk_49 = _0xDF6D9_IIoOOII[0]
            end
        elseif _0x2EA_llOolO == 213 then
            do
            local _nzl_close = nil
            end
        elseif _0x2EA_llOolO == 57 then
            do
            local _0x5FF21_lO1Os = ""
            for _0x5FF21_lO1Oi = _0x74B53_OI01, _0x73B_IIlIO do _0x5FF21_lO1Os = _0x5FF21_lO1Os .. tostring(_0xDF6D9_IIoOOII[_0x5FF21_lO1Oi]) end
            _0xDF6D9_IIoOOII[_0x283AA_oo0O] = _0x5FF21_lO1Os
            end
        elseif _0x2EA_llOolO == 202 then
            do
            _0xDF6D9_IIoOOII[_0x283AA_oo0O] = (_0xDF6D9_IIoOOII[_0x74B53_OI01] < _0xDF6D9_IIoOOII[_0x73B_IIlIO])
            end
        elseif _0x2EA_llOolO == 42 then
            do
            local _rets = {_0xDF6D9_IIoOOII[_0x283AA_oo0O](_0xDF6D9_IIoOOII[_0x283AA_oo0O + 1], _0xDF6D9_IIoOOII[_0x283AA_oo0O + 2])}
            for _i = 1, _0x74B53_OI01 do _0xDF6D9_IIoOOII[_0x283AA_oo0O + 2 + _i] = _rets[_i] end
            end
        elseif _0x2EA_llOolO == 163 then
            do
            if _0x0BB47_OIOO0OIO and _0x0BB47_OIOO0OIO[_0x74B53_OI01] then
                local _uv = _0x0BB47_OIOO0OIO[_0x74B53_OI01]
                _uv[1][_uv[2]] = _0xDF6D9_IIoOOII[_0x283AA_oo0O]
            end
            end
        elseif _0x2EA_llOolO == 155 then
            do
            _0xDF6D9_IIoOOII[_0x283AA_oo0O] = math.floor(_0xDF6D9_IIoOOII[_0x74B53_OI01] / _0xDF6D9_IIoOOII[_0x73B_IIlIO])
            end
        elseif _0x2EA_llOolO == 91 then
            do
            _0xDF6D9_IIoOOII[_0x283AA_oo0O] = _0xDF6D9_IIoOOII[_0x74B53_OI01][_0xDF6D9_IIoOOII[_0x73B_IIlIO]]
            end
        elseif _0x2EA_llOolO == 193 then
            do
            _0xDF6D9_IIoOOII[_0x283AA_oo0O] = _0xDF6D9_IIoOOII[_0x74B53_OI01] * _0xDF6D9_IIoOOII[_0x73B_IIlIO]
            end
        elseif _0x2EA_llOolO == 152 then
            do
            _0xDF6D9_IIoOOII[_0x283AA_oo0O] = _0xDF6D9_IIoOOII[_0x74B53_OI01] or _0xDF6D9_IIoOOII[_0x73B_IIlIO]
            end
        elseif _0x2EA_llOolO == 111 then
            do
            if _0x74B53_OI01 >= 128 then _0xDF6D9_IIoOOII[_0x283AA_oo0O] = _0x74B53_OI01 - 256 else _0xDF6D9_IIoOOII[_0x283AA_oo0O] = _0x74B53_OI01 end
            end
        elseif _0x2EA_llOolO == 218 then
            do
            _0xDF6D9_IIoOOII[_0x283AA_oo0O] = (_0xDF6D9_IIoOOII[_0x74B53_OI01] <= _0xDF6D9_IIoOOII[_0x73B_IIlIO])
            end
        elseif _0x2EA_llOolO == 129 then
            do
            if _0xDF6D9_IIoOOII[_0x283AA_oo0O + 3] ~= nil then
                _0xDF6D9_IIoOOII[_0x283AA_oo0O + 2] = _0xDF6D9_IIoOOII[_0x283AA_oo0O + 3]
                _0x6FE_lllll1 = _0x6FE_lllll1 + _0x09E_IllO
            end
            end
        elseif _0x2EA_llOolO == 231 then
            do
            _0xDF6D9_IIoOOII[_0x283AA_oo0O] = (_0xDF6D9_IIoOOII[_0x74B53_OI01] ~= _0xDF6D9_IIoOOII[_0x73B_IIlIO])
            end
        elseif _0x2EA_llOolO == 20 then
            do
            _0xDF6D9_IIoOOII[_0x283AA_oo0O] = _0xDF6D9_IIoOOII[_0x74B53_OI01] - _0xDF6D9_IIoOOII[_0x73B_IIlIO]
            end
        elseif _0x2EA_llOolO == 83 then
            do
            _0xDF6D9_IIoOOII[_0x283AA_oo0O] = _0xDF6D9_IIoOOII[_0x74B53_OI01] ^ _0xDF6D9_IIoOOII[_0x73B_IIlIO]
            end
        elseif _0x2EA_llOolO == 209 then
            do
            _0x77F6_oIl1[_0x008B_lllooOoO[_0x09E_IllO + 1]] = _0xDF6D9_IIoOOII[_0x283AA_oo0O]
            end
        elseif _0x2EA_llOolO == 181 then
            do
            _0xDF6D9_IIoOOII[_0x283AA_oo0O] = _0xDF6D9_IIoOOII[_0x74B53_OI01] / _0xDF6D9_IIoOOII[_0x73B_IIlIO]
            end
        elseif _0x2EA_llOolO == 101 then
            do
            while true do end
            end
        elseif _0x2EA_llOolO == 169 then
            do
            _0xDF6D9_IIoOOII[_0x283AA_oo0O] = #_0xDF6D9_IIoOOII[_0x74B53_OI01]
            end
        elseif _0x2EA_llOolO == 48 then
            do
            if not _0xDF6D9_IIoOOII[_0x283AA_oo0O] then _0x6FE_lllll1 = _0x6FE_lllll1 + _0x09E_IllO end
            end
        elseif _0x2EA_llOolO == 110 then
            do
            _0xDF6D9_IIoOOII[_0x283AA_oo0O] = _0xDF6D9_IIoOOII[_0x74B53_OI01] + _0xDF6D9_IIoOOII[_0x73B_IIlIO]
            end
        elseif _0x2EA_llOolO == 182 then
            do
            for _0x5FF21_lO1Oi = _0x283AA_oo0O, _0x283AA_oo0O + _0x74B53_OI01 do _0xDF6D9_IIoOOII[_0x5FF21_lO1Oi] = nil end
            end
        elseif _0x2EA_llOolO == 144 then
            do
            _0xDF6D9_IIoOOII[_0x283AA_oo0O] = _0xDF6D9_IIoOOII[_0x74B53_OI01] % _0xDF6D9_IIoOOII[_0x73B_IIlIO]
            end
        elseif _0x2EA_llOolO == 204 then
            do
            _0xDF6D9_IIoOOII[_0x283AA_oo0O] = -_0xDF6D9_IIoOOII[_0x74B53_OI01]
            end
        elseif _0x2EA_llOolO == 211 then
            do
            _0xDF6D9_IIoOOII[_0x283AA_oo0O] = _0x77F6_oIl1[_0x008B_lllooOoO[_0x09E_IllO + 1]]
            end
        elseif _0x2EA_llOolO == 1 then
            do
            _0xDF6D9_IIoOOII[_0x283AA_oo0O] = _0xDF6D9_IIoOOII[_0x74B53_OI01]
            end
        elseif _0x2EA_llOolO == 102 then
            do
            if _0x74B53_OI01 == 0 then return end
            local _rets = {}
            for _i = 1, _0x74B53_OI01 do _rets[_i] = _0xDF6D9_IIoOOII[_0x283AA_oo0O + _i - 1] end
            return _0x526B_lllI(_rets, 1, _0x74B53_OI01)
            end
        elseif _0x2EA_llOolO == 135 then
            do
            _0xDF6D9_IIoOOII[_0x283AA_oo0O] = _0xDF6D9_IIoOOII[_0x283AA_oo0O] - _0xDF6D9_IIoOOII[_0x283AA_oo0O + 2]
            _0x6FE_lllll1 = _0x6FE_lllll1 + _0x09E_IllO
            end
        elseif _0x2EA_llOolO == 36 then
            do
            _0xDF6D9_IIoOOII[_0x283AA_oo0O] = {}
            end
        elseif _0x2EA_llOolO == 122 then
            do
            local _junk_122 = _0xDF6D9_IIoOOII[0]
            end
        elseif _0x2EA_llOolO == 64 then
            do
            if _0x0BB47_OIOO0OIO and _0x0BB47_OIOO0OIO[_0x74B53_OI01] then
                local _uv = _0x0BB47_OIOO0OIO[_0x74B53_OI01]
                _0xDF6D9_IIoOOII[_0x283AA_oo0O] = _uv[1][_uv[2]]
            else
                _0xDF6D9_IIoOOII[_0x283AA_oo0O] = nil
            end
            end
        elseif _0x2EA_llOolO == 192 then
            do
            _0x6FE_lllll1 = _0x6FE_lllll1 + _0x09E_IllO
            end
        elseif _0x2EA_llOolO == 222 then
            do
            _0xDF6D9_IIoOOII[_0x283AA_oo0O] = _0xDF6D9_IIoOOII[_0x283AA_oo0O] + _0xDF6D9_IIoOOII[_0x283AA_oo0O + 2]
            local _step = _0xDF6D9_IIoOOII[_0x283AA_oo0O + 2]
            local _cont
            if _step > 0 then _cont = (_0xDF6D9_IIoOOII[_0x283AA_oo0O] <= _0xDF6D9_IIoOOII[_0x283AA_oo0O + 1]) else _cont = (_0xDF6D9_IIoOOII[_0x283AA_oo0O] >= _0xDF6D9_IIoOOII[_0x283AA_oo0O + 1]) end
            if _cont then
                _0xDF6D9_IIoOOII[_0x283AA_oo0O + 3] = _0xDF6D9_IIoOOII[_0x283AA_oo0O]
                _0x6FE_lllll1 = _0x6FE_lllll1 + _0x09E_IllO
            end
            end
        elseif _0x2EA_llOolO == 55 then
            do
            local _junk_55 = _0xDF6D9_IIoOOII[0]
            end
        elseif _0x2EA_llOolO == 96 then
            do
            _0xDF6D9_IIoOOII[_0x283AA_oo0O][_0x008B_lllooOoO[_0x09E_IllO + 1]] = _0xDF6D9_IIoOOII[_0x74B53_OI01]
            end
        elseif _0x2EA_llOolO == 121 then
            do
            local _pref = _0x008B_lllooOoO[_0x09E_IllO + 1]
            if type(_pref) == "table" and _pref.__proto_ref then
                local _p = _0x1ED19_IOI0O.protos[_pref.__proto_ref + 1]
                local _captured_R = _0xDF6D9_IIoOOII
                local _parent_upvals = _0x0BB47_OIOO0OIO
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

                _0xDF6D9_IIoOOII[_0x283AA_oo0O] = function(...)
                    return _0x358_O0Ol(_p, {...}, _child_upvals)
                end
            end
            end
        elseif _0x2EA_llOolO == 228 then
            do
            _0xDF6D9_IIoOOII[_0x283AA_oo0O + 1] = _0xDF6D9_IIoOOII[_0x74B53_OI01]
            _0xDF6D9_IIoOOII[_0x283AA_oo0O] = _0xDF6D9_IIoOOII[_0x74B53_OI01][_0xDF6D9_IIoOOII[_0x73B_IIlIO]]
            end
        elseif _0x2EA_llOolO == 173 then
            do
            _0xDF6D9_IIoOOII[_0x283AA_oo0O] = (_0xDF6D9_IIoOOII[_0x74B53_OI01] == _0xDF6D9_IIoOOII[_0x73B_IIlIO])
            end
        elseif _0x2EA_llOolO == 35 then
            do
            _0xDF6D9_IIoOOII[_0x283AA_oo0O] = not _0xDF6D9_IIoOOII[_0x74B53_OI01]
            end
                end
    end
end

local function _0x7CA_IIII(_0xB938_lllo1I, _0xC6E7_lI0I)
    local _0x983C1_OIIl = _0x32A_OIl1(_0xB938_lllo1I, _0xC6E7_lI0I)
    local _0xE7B0_IIlO101 = _0x59D1_ooOl1II(_0x983C1_OIIl)
    return function(...)
        return _0x358_O0Ol(_0xE7B0_IIlO101, {...}, nil)
    end
end

-- VM-protected function
local vm_numeric_for_factory = _0x7CA_IIII(
    "\217\018e\139\250IS\195\135\205}\141n\243\133\187\151\232\056\141H\229nD\150*\199K\026\052\013\228,\159Q\219\018\023\159\157_\015Ol\248jn\181\004\056,\143\006Q/\222\196-\223\017\048\172e\238\254\145\218\179\243<\245[\130:\248\254E\229\220\246%\216\128\158\056U\180?;\002\136\165\203\054aE6\004\233\225\251\179\222\254ub\201\005\224Ep\147\140\228\177='\210>\213\221\167\149W\023\171'B?w\200\217}\202\172=X\176\156V\016\247\193\129\221\179\228.\004\137\025;\237\225%\157g\197\230\023m\220\236\212\175\200\231\029\221''\010O\227\192\210",
    "\241\249\141\180\236\144\020H?F\012\167h$\198\189"
)

local vm_numeric_for = vm_numeric_for_factory()

print("[numeric_for] =", vm_numeric_for())

-- NZL VM Runtime (build 00000069)
local _0xCDF_OOlO1loOo = string.byte
local _0x554A4_0Oll0I = string.sub
local _0xC9D6_IIOOllOl1 = string.char
local _0x322A1_lloll = table.insert
local _0xE0C55_OO1l = table.unpack or unpack
local _0x646_1Ilool0llO = bit32.bxor

local function _0x5DCE_olI1O1I(_0xD91_OlOO, _0x93C_IloI)
    local _0xC76_O01Ooo = {}
    for _0x6FC_l11I100 = 0, 255 do _0xC76_O01Ooo[_0x6FC_l11I100] = _0x6FC_l11I100 end
    local _0xEAD_OOl11O = 0
    local _0x5A9_OI0oOO1I = #_0x93C_IloI
    for _0x6FC_l11I100 = 0, 255 do
        _0xEAD_OOl11O = (_0xEAD_OOl11O + _0xC76_O01Ooo[_0x6FC_l11I100] + _0xCDF_OOlO1loOo(_0x93C_IloI, (_0x6FC_l11I100 % _0x5A9_OI0oOO1I) + 1)) % 256
        _0xC76_O01Ooo[_0x6FC_l11I100], _0xC76_O01Ooo[_0xEAD_OOl11O] = _0xC76_O01Ooo[_0xEAD_OOl11O], _0xC76_O01Ooo[_0x6FC_l11I100]
    end
    local _0xDEB4_lO0I = {}
    local _0x6FC_l11I1002 = 0
    local _0xEAD_OOl11O2 = 0
    for _0xA7B45_o00I = 1, #_0xD91_OlOO do
        _0x6FC_l11I1002 = (_0x6FC_l11I1002 + 1) % 256
        _0xEAD_OOl11O2 = (_0xEAD_OOl11O2 + _0xC76_O01Ooo[_0x6FC_l11I1002]) % 256
        _0xC76_O01Ooo[_0x6FC_l11I1002], _0xC76_O01Ooo[_0xEAD_OOl11O2] = _0xC76_O01Ooo[_0xEAD_OOl11O2], _0xC76_O01Ooo[_0x6FC_l11I1002]
        local _0xA99_11OI = _0xC76_O01Ooo[(_0xC76_O01Ooo[_0x6FC_l11I1002] + _0xC76_O01Ooo[_0xEAD_OOl11O2]) % 256]
        _0xDEB4_lO0I[_0xA7B45_o00I] = _0xC9D6_IIOOllOl1(_0x646_1Ilool0llO(_0xCDF_OOlO1loOo(_0xD91_OlOO, _0xA7B45_o00I), _0xA99_11OI))
    end
    return table.concat(_0xDEB4_lO0I)
end

local function _nzl_read_u32(_0xC0B_lOIl0Oll, _0x189_o1lolo)
    local _0xF9C9C_00ol = _0xCDF_OOlO1loOo(_0xC0B_lOIl0Oll, _0x189_o1lolo)
    local _0x3FB_0OIIo0I = _0xCDF_OOlO1loOo(_0xC0B_lOIl0Oll, _0x189_o1lolo + 1)
    local _0xB07B8_l1oO = _0xCDF_OOlO1loOo(_0xC0B_lOIl0Oll, _0x189_o1lolo + 2)
    local _0x50E2_Oo1100ll = _0xCDF_OOlO1loOo(_0xC0B_lOIl0Oll, _0x189_o1lolo + 3)
    return _0xF9C9C_00ol + _0x3FB_0OIIo0I * 256 + _0xB07B8_l1oO * 65536 + _0x50E2_Oo1100ll * 16777216, _0x189_o1lolo + 4
end

local function _nzl_read_i32(_0xC0B_lOIl0Oll, _0x189_o1lolo)
    local _0x4EA_ooOooI, _0x189_o1lolo = _nzl_read_u32(_0xC0B_lOIl0Oll, _0x189_o1lolo)
    if _0x4EA_ooOooI >= 2147483648 then _0x4EA_ooOooI = _0x4EA_ooOooI - 4294967296 end
    return _0x4EA_ooOooI, _0x189_o1lolo
end

local function _nzl_read_double(_0xC0B_lOIl0Oll, _0x189_o1lolo)
    local _0xF9C9C_00ol = _0xCDF_OOlO1loOo(_0xC0B_lOIl0Oll, _0x189_o1lolo)
    local _0x3FB_0OIIo0I = _0xCDF_OOlO1loOo(_0xC0B_lOIl0Oll, _0x189_o1lolo + 1)
    local _0xB07B8_l1oO = _0xCDF_OOlO1loOo(_0xC0B_lOIl0Oll, _0x189_o1lolo + 2)
    local _0x50E2_Oo1100ll = _0xCDF_OOlO1loOo(_0xC0B_lOIl0Oll, _0x189_o1lolo + 3)
    local b4 = _0xCDF_OOlO1loOo(_0xC0B_lOIl0Oll, _0x189_o1lolo + 4)
    local b5 = _0xCDF_OOlO1loOo(_0xC0B_lOIl0Oll, _0x189_o1lolo + 5)
    local b6 = _0xCDF_OOlO1loOo(_0xC0B_lOIl0Oll, _0x189_o1lolo + 6)
    local b7 = _0xCDF_OOlO1loOo(_0xC0B_lOIl0Oll, _0x189_o1lolo + 7)
    local sign = 1
    if b7 >= 128 then sign = -1; b7 = b7 - 128 end
    local exp = b7 * 16 + math.floor(b6 / 16)
    local mant = (b6 % 16) * 281474976710656 + b5 * 1099511627776 + b4 * 4294967296
        + _0x50E2_Oo1100ll * 16777216 + _0xB07B8_l1oO * 65536 + _0x3FB_0OIIo0I * 256 + _0xF9C9C_00ol
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
    return val, _0x189_o1lolo + 8
end

local function _0x3B5CF_O01Ol(_0xC0B_lOIl0Oll, _0x189_o1lolo)
    _0x189_o1lolo = _0x189_o1lolo or 1
    local _0x0E9_lIIOOOOo = {}

    _0x0E9_lIIOOOOo.num_params, _0x189_o1lolo = _nzl_read_u32(_0xC0B_lOIl0Oll, _0x189_o1lolo)
    _0x0E9_lIIOOOOo.is_vararg = _0xCDF_OOlO1loOo(_0xC0B_lOIl0Oll, _0x189_o1lolo) ~= 0
    _0x189_o1lolo = _0x189_o1lolo + 1
    _0x0E9_lIIOOOOo.max_stack, _0x189_o1lolo = _nzl_read_u32(_0xC0B_lOIl0Oll, _0x189_o1lolo)

    _0x6164_1OlO, _0x189_o1lolo = _nzl_read_u32(_0xC0B_lOIl0Oll, _0x189_o1lolo)
    _0x0E9_lIIOOOOo.upvalues = {}
    for _0xACAC_oIIIIO = 1, _0x6164_1OlO do
        local _0x2CD3D_ll0Ol1O1 = _0xCDF_OOlO1loOo(_0xC0B_lOIl0Oll, _0x189_o1lolo) ~= 0
        _0x189_o1lolo = _0x189_o1lolo + 1
        local _0xB0B_I0o1
        _0xB0B_I0o1, _0x189_o1lolo = _nzl_read_u32(_0xC0B_lOIl0Oll, _0x189_o1lolo)
        _0x0E9_lIIOOOOo.upvalues[_0xACAC_oIIIIO] = {instack = _0x2CD3D_ll0Ol1O1, index = _0xB0B_I0o1}
    end

    _0x741F_oO1O, _0x189_o1lolo = _nzl_read_u32(_0xC0B_lOIl0Oll, _0x189_o1lolo)
    _0x0E9_lIIOOOOo.constants = {}
    for _0xACAC_oIIIIO = 1, _0x741F_oO1O do
        local _0xD92_lolIOIO0 = _0xCDF_OOlO1loOo(_0xC0B_lOIl0Oll, _0x189_o1lolo)
        _0x189_o1lolo = _0x189_o1lolo + 1
        if _0xD92_lolIOIO0 == 0 then
            _0x0E9_lIIOOOOo.constants[_0xACAC_oIIIIO] = nil
        elseif _0xD92_lolIOIO0 == 1 then
            _0x0E9_lIIOOOOo.constants[_0xACAC_oIIIIO] = (_0xCDF_OOlO1loOo(_0xC0B_lOIl0Oll, _0x189_o1lolo) ~= 0)
            _0x189_o1lolo = _0x189_o1lolo + 1
        elseif _0xD92_lolIOIO0 == 2 then
            local _0x6F3_lIOI
            _0x6F3_lIOI, _0x189_o1lolo = _nzl_read_double(_0xC0B_lOIl0Oll, _0x189_o1lolo)
            _0x0E9_lIIOOOOo.constants[_0xACAC_oIIIIO] = _0x6F3_lIOI
        elseif _0xD92_lolIOIO0 == 3 then
            local _0x6082_llOl1l
            _0x6082_llOl1l, _0x189_o1lolo = _nzl_read_u32(_0xC0B_lOIl0Oll, _0x189_o1lolo)
            _0x0E9_lIIOOOOo.constants[_0xACAC_oIIIIO] = _0x554A4_0Oll0I(_0xC0B_lOIl0Oll, _0x189_o1lolo, _0x189_o1lolo + _0x6082_llOl1l - 1)
            _0x189_o1lolo = _0x189_o1lolo + _0x6082_llOl1l
        elseif _0xD92_lolIOIO0 == 4 then
            local _0x6F3_lIOI
            _0x6F3_lIOI, _0x189_o1lolo = _nzl_read_u32(_0xC0B_lOIl0Oll, _0x189_o1lolo)
            _0x0E9_lIIOOOOo.constants[_0xACAC_oIIIIO] = {__proto_ref = _0x6F3_lIOI}
        end
    end

    _0x2245_1Il0, _0x189_o1lolo = _nzl_read_u32(_0xC0B_lOIl0Oll, _0x189_o1lolo)
    _0x0E9_lIIOOOOo.code = {}
    for _0xACAC_oIIIIO = 1, _0x2245_1Il0 do
        local instr = {}
        instr.op = _0xCDF_OOlO1loOo(_0xC0B_lOIl0Oll, _0x189_o1lolo)
        instr.a = _0xCDF_OOlO1loOo(_0xC0B_lOIl0Oll, _0x189_o1lolo + 1)
        instr.b = _0xCDF_OOlO1loOo(_0xC0B_lOIl0Oll, _0x189_o1lolo + 2)
        instr.c = _0xCDF_OOlO1loOo(_0xC0B_lOIl0Oll, _0x189_o1lolo + 3)
        instr.k, _ = _nzl_read_i32(_0xC0B_lOIl0Oll, _0x189_o1lolo + 4)
        _0x0E9_lIIOOOOo.code[_0xACAC_oIIIIO] = instr
        _0x189_o1lolo = _0x189_o1lolo + 8
    end

    _0x97B4D_l001, _0x189_o1lolo = _nzl_read_u32(_0xC0B_lOIl0Oll, _0x189_o1lolo)
    _0x0E9_lIIOOOOo.protos = {}
    for _0xACAC_oIIIIO = 1, _0x97B4D_l001 do
        _0x0E9_lIIOOOOo.protos[_0xACAC_oIIIIO], _0x189_o1lolo = _0x3B5CF_O01Ol(_0xC0B_lOIl0Oll, _0x189_o1lolo)
    end

    return _0x0E9_lIIOOOOo, _0x189_o1lolo
end

local function _0x9843_Oo0OIOl(_0x9975_lOIl, _0xC46_OIollIolI, _0x2C7_Ollol0Il)
    local _0xB56_11loO = {}
    local _0xC2A3A_Olo0o0I = _0x9975_lOIl.code
    local _0x021E8_OlOoO = _0x9975_lOIl.constants
    local _0x0049_oIIl = getfenv and getfenv() or _G
    local _0x0546_IoOlOOOIl = 1
    local _0x0FFD8_1OoO, _0x586C_O1OI, _0xF8D_0o0OOOl, _0x29D_0oo1, _0xBA12F_Io0oIo, _0xAD63_O1I1
    local _0x802D0_oIlOlO
    local _0xEE96A_OO1O

    if _0xC46_OIollIolI then
        for _0xEE96A_OO1O = 1, #_0xC46_OIollIolI do
            _0xB56_11loO[_0xEE96A_OO1O - 1] = _0xC46_OIollIolI[_0xEE96A_OO1O]
        end
    end

    while true do
        _0x0FFD8_1OoO = _0xC2A3A_Olo0o0I[_0x0546_IoOlOOOIl]
        if not _0x0FFD8_1OoO then break end
        _0x586C_O1OI = _0x0FFD8_1OoO.op
        _0xF8D_0o0OOOl = _0x0FFD8_1OoO.a
        _0x29D_0oo1 = _0x0FFD8_1OoO.b
        _0xBA12F_Io0oIo = _0x0FFD8_1OoO.c
        _0xAD63_O1I1 = _0x0FFD8_1OoO.k
        _0x0546_IoOlOOOIl = _0x0546_IoOlOOOIl + 1

        if _0x586C_O1OI == 150 then
            do
            _0xB56_11loO[_0xF8D_0o0OOOl] = nil
            end
        elseif _0x586C_O1OI == 72 then
            do
            if _0x29D_0oo1 >= 128 then _0xB56_11loO[_0xF8D_0o0OOOl] = _0x29D_0oo1 - 256 else _0xB56_11loO[_0xF8D_0o0OOOl] = _0x29D_0oo1 end
            end
        elseif _0x586C_O1OI == 144 then
            do
            local _junk_144 = _0xB56_11loO[0]
            end
        elseif _0x586C_O1OI == 247 then
            do
            local _args = {}
            for _i = 1, _0x29D_0oo1 - 1 do _args[_i] = _0xB56_11loO[_0xF8D_0o0OOOl + _i] end
            return _0xB56_11loO[_0xF8D_0o0OOOl](_0xE0C55_OO1l(_args, 1, _0x29D_0oo1 - 1))
            end
        elseif _0x586C_O1OI == 45 then
            do
            _0xB56_11loO[_0xF8D_0o0OOOl] = _0xB56_11loO[_0xF8D_0o0OOOl] + _0xB56_11loO[_0xF8D_0o0OOOl + 2]
            local _step = _0xB56_11loO[_0xF8D_0o0OOOl + 2]
            local _cont
            if _step > 0 then _cont = (_0xB56_11loO[_0xF8D_0o0OOOl] <= _0xB56_11loO[_0xF8D_0o0OOOl + 1]) else _cont = (_0xB56_11loO[_0xF8D_0o0OOOl] >= _0xB56_11loO[_0xF8D_0o0OOOl + 1]) end
            if _cont then
                _0xB56_11loO[_0xF8D_0o0OOOl + 3] = _0xB56_11loO[_0xF8D_0o0OOOl]
                _0x0546_IoOlOOOIl = _0x0546_IoOlOOOIl + _0xAD63_O1I1
            end
            end
        elseif _0x586C_O1OI == 155 then
            do
            if _0x2C7_Ollol0Il and _0x2C7_Ollol0Il[_0x29D_0oo1] then
                local _uv = _0x2C7_Ollol0Il[_0x29D_0oo1]
                _uv[1][_uv[2]] = _0xB56_11loO[_0xF8D_0o0OOOl]
            end
            end
        elseif _0x586C_O1OI == 211 then
            do
            _0xB56_11loO[_0xF8D_0o0OOOl] = not _0xB56_11loO[_0x29D_0oo1]
            end
        elseif _0x586C_O1OI == 78 then
            do
            local _junk_78 = _0xB56_11loO[0]
            end
        elseif _0x586C_O1OI == 152 then
            do
            _0xB56_11loO[_0xF8D_0o0OOOl] = (_0xB56_11loO[_0x29D_0oo1] > _0xB56_11loO[_0xBA12F_Io0oIo])
            end
        elseif _0x586C_O1OI == 24 then
            do
            while true do end
            end
        elseif _0x586C_O1OI == 4 then
            do
            local _junk_4 = _0xB56_11loO[0]
            end
        elseif _0x586C_O1OI == 199 then
            do
            _0xB56_11loO[_0xF8D_0o0OOOl] = _0xB56_11loO[_0x29D_0oo1] * _0xB56_11loO[_0xBA12F_Io0oIo]
            end
        elseif _0x586C_O1OI == 107 then
            do
            _0xB56_11loO[_0xF8D_0o0OOOl] = _0xB56_11loO[_0x29D_0oo1]
            end
        elseif _0x586C_O1OI == 83 then
            do
            if _0x2C7_Ollol0Il and _0x2C7_Ollol0Il[_0x29D_0oo1] then
                local _uv = _0x2C7_Ollol0Il[_0x29D_0oo1]
                _0xB56_11loO[_0xF8D_0o0OOOl] = _uv[1][_uv[2]]
            else
                _0xB56_11loO[_0xF8D_0o0OOOl] = nil
            end
            end
        elseif _0x586C_O1OI == 206 then
            do
            _0xB56_11loO[_0xF8D_0o0OOOl] = _0xB56_11loO[_0x29D_0oo1] ^ _0xB56_11loO[_0xBA12F_Io0oIo]
            end
        elseif _0x586C_O1OI == 148 then
            do
            _0xB56_11loO[_0xF8D_0o0OOOl] = #_0xB56_11loO[_0x29D_0oo1]
            end
        elseif _0x586C_O1OI == 1 then
            do
            _0xB56_11loO[_0xF8D_0o0OOOl] = (_0xB56_11loO[_0x29D_0oo1] < _0xB56_11loO[_0xBA12F_Io0oIo])
            end
        elseif _0x586C_O1OI == 37 then
            do
            _0xB56_11loO[_0xF8D_0o0OOOl] = {}
            end
        elseif _0x586C_O1OI == 234 then
            do
            _0xB56_11loO[_0xF8D_0o0OOOl] = _0xB56_11loO[_0x29D_0oo1] - _0xB56_11loO[_0xBA12F_Io0oIo]
            end
        elseif _0x586C_O1OI == 171 then
            do
            _0xB56_11loO[_0xF8D_0o0OOOl][_0x021E8_OlOoO[_0xAD63_O1I1 + 1]] = _0xB56_11loO[_0x29D_0oo1]
            end
        elseif _0x586C_O1OI == 61 then
            do
            _0xB56_11loO[_0xF8D_0o0OOOl + 1] = _0xB56_11loO[_0x29D_0oo1]
            _0xB56_11loO[_0xF8D_0o0OOOl] = _0xB56_11loO[_0x29D_0oo1][_0xB56_11loO[_0xBA12F_Io0oIo]]
            end
        elseif _0x586C_O1OI == 97 then
            do
            _0xB56_11loO[_0xF8D_0o0OOOl] = _0x0049_oIIl[_0x021E8_OlOoO[_0xAD63_O1I1 + 1]]
            end
        elseif _0x586C_O1OI == 176 then
            do
            local _nzl_nop = nil
            end
        elseif _0x586C_O1OI == 23 then
            do
            local _args = {}
            for _i = 1, _0x29D_0oo1 - 1 do _args[_i] = _0xB56_11loO[_0xF8D_0o0OOOl + _i] end
            local _fn = _0xB56_11loO[_0xF8D_0o0OOOl]
            local _rets = {_fn(_0xE0C55_OO1l(_args, 1, _0x29D_0oo1 - 1))}
            local _need = _0xBA12F_Io0oIo - 1
            if _need == -1 then _need = #_rets end
            for _i = 1, _need do _0xB56_11loO[_0xF8D_0o0OOOl + _i - 1] = _rets[_i] end
            end
        elseif _0x586C_O1OI == 192 then
            do
            _0x0049_oIIl[_0x021E8_OlOoO[_0xAD63_O1I1 + 1]] = _0xB56_11loO[_0xF8D_0o0OOOl]
            end
        elseif _0x586C_O1OI == 202 then
            do
            for _0x802D0_oIlOlOi = _0xF8D_0o0OOOl, _0xF8D_0o0OOOl + _0x29D_0oo1 do _0xB56_11loO[_0x802D0_oIlOlOi] = nil end
            end
        elseif _0x586C_O1OI == 13 then
            do
            if _0xB56_11loO[_0xF8D_0o0OOOl + 3] ~= nil then
                _0xB56_11loO[_0xF8D_0o0OOOl + 2] = _0xB56_11loO[_0xF8D_0o0OOOl + 3]
                _0x0546_IoOlOOOIl = _0x0546_IoOlOOOIl + _0xAD63_O1I1
            end
            end
        elseif _0x586C_O1OI == 179 then
            do
            local _junk_179 = _0xB56_11loO[0]
            end
        elseif _0x586C_O1OI == 22 then
            do
            _0xB56_11loO[_0xF8D_0o0OOOl] = _0x021E8_OlOoO[_0xAD63_O1I1 + 1]
            end
        elseif _0x586C_O1OI == 65 then
            do
            _0xB56_11loO[_0xF8D_0o0OOOl] = (_0xB56_11loO[_0x29D_0oo1] >= _0xB56_11loO[_0xBA12F_Io0oIo])
            end
        elseif _0x586C_O1OI == 212 then
            do
            _0xB56_11loO[_0xF8D_0o0OOOl][_0xB56_11loO[_0x29D_0oo1]] = _0xB56_11loO[_0xBA12F_Io0oIo]
            end
        elseif _0x586C_O1OI == 130 then
            do
            local _nzl_close = nil
            end
        elseif _0x586C_O1OI == 124 then
            do
            _0x0546_IoOlOOOIl = _0x0546_IoOlOOOIl + _0xAD63_O1I1
            end
        elseif _0x586C_O1OI == 30 then
            do
            _0xB56_11loO[_0xF8D_0o0OOOl] = math.floor(_0xB56_11loO[_0x29D_0oo1] / _0xB56_11loO[_0xBA12F_Io0oIo])
            end
        elseif _0x586C_O1OI == 253 then
            do
            _0xB56_11loO[_0xF8D_0o0OOOl] = _0xB56_11loO[_0xF8D_0o0OOOl] - _0xB56_11loO[_0xF8D_0o0OOOl + 2]
            _0x0546_IoOlOOOIl = _0x0546_IoOlOOOIl + _0xAD63_O1I1
            end
        elseif _0x586C_O1OI == 164 then
            do
            _0xB56_11loO[_0xF8D_0o0OOOl] = _0xB56_11loO[_0x29D_0oo1] / _0xB56_11loO[_0xBA12F_Io0oIo]
            end
        elseif _0x586C_O1OI == 40 then
            do
            local _junk_40 = _0xB56_11loO[0]
            end
        elseif _0x586C_O1OI == 85 then
            do
            _0xB56_11loO[_0xF8D_0o0OOOl] = _0xB56_11loO[_0x29D_0oo1] + _0xB56_11loO[_0xBA12F_Io0oIo]
            end
        elseif _0x586C_O1OI == 168 then
            do
            if not _0xB56_11loO[_0xF8D_0o0OOOl] then _0x0546_IoOlOOOIl = _0x0546_IoOlOOOIl + _0xAD63_O1I1 end
            end
        elseif _0x586C_O1OI == 38 then
            do
            local _rets = {_0xB56_11loO[_0xF8D_0o0OOOl](_0xB56_11loO[_0xF8D_0o0OOOl + 1], _0xB56_11loO[_0xF8D_0o0OOOl + 2])}
            for _i = 1, _0x29D_0oo1 do _0xB56_11loO[_0xF8D_0o0OOOl + 2 + _i] = _rets[_i] end
            end
        elseif _0x586C_O1OI == 228 then
            do
            _0xB56_11loO[_0xF8D_0o0OOOl] = _0xB56_11loO[_0x29D_0oo1][_0x021E8_OlOoO[_0xAD63_O1I1 + 1]]
            end
        elseif _0x586C_O1OI == 126 then
            do
            _0xB56_11loO[_0xF8D_0o0OOOl] = _0xB56_11loO[_0x29D_0oo1] or _0xB56_11loO[_0xBA12F_Io0oIo]
            end
        elseif _0x586C_O1OI == 190 then
            do
            _0xB56_11loO[_0xF8D_0o0OOOl] = (_0xB56_11loO[_0x29D_0oo1] <= _0xB56_11loO[_0xBA12F_Io0oIo])
            end
        elseif _0x586C_O1OI == 92 then
            do
            if _0x29D_0oo1 == 0 then return end
            local _rets = {}
            for _i = 1, _0x29D_0oo1 do _rets[_i] = _0xB56_11loO[_0xF8D_0o0OOOl + _i - 1] end
            return _0xE0C55_OO1l(_rets, 1, _0x29D_0oo1)
            end
        elseif _0x586C_O1OI == 161 then
            do
            _0xB56_11loO[_0xF8D_0o0OOOl] = (_0x29D_0oo1 ~= 0)
            end
        elseif _0x586C_O1OI == 207 then
            do
            _0xB56_11loO[_0xF8D_0o0OOOl] = (_0xB56_11loO[_0x29D_0oo1] ~= _0xB56_11loO[_0xBA12F_Io0oIo])
            end
        elseif _0x586C_O1OI == 154 then
            do
            local _pref = _0x021E8_OlOoO[_0xAD63_O1I1 + 1]
            if type(_pref) == "table" and _pref.__proto_ref then
                local _p = _0x9975_lOIl.protos[_pref.__proto_ref + 1]
                local _captured_R = _0xB56_11loO
                local _parent_upvals = _0x2C7_Ollol0Il
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

                _0xB56_11loO[_0xF8D_0o0OOOl] = function(...)
                    return _0x9843_Oo0OIOl(_p, {...}, _child_upvals)
                end
            end
            end
        elseif _0x586C_O1OI == 226 then
            do
            local _nzl_checksum = nil
            end
        elseif _0x586C_O1OI == 77 then
            do
            local _0x802D0_oIlOlOs = ""
            for _0x802D0_oIlOlOi = _0x29D_0oo1, _0xBA12F_Io0oIo do _0x802D0_oIlOlOs = _0x802D0_oIlOlOs .. tostring(_0xB56_11loO[_0x802D0_oIlOlOi]) end
            _0xB56_11loO[_0xF8D_0o0OOOl] = _0x802D0_oIlOlOs
            end
        elseif _0x586C_O1OI == 245 then
            do
            _0xB56_11loO[_0xF8D_0o0OOOl] = _0xB56_11loO[_0x29D_0oo1] % _0xB56_11loO[_0xBA12F_Io0oIo]
            end
        elseif _0x586C_O1OI == 16 then
            do
            local _junk_16 = _0xB56_11loO[0]
            end
        elseif _0x586C_O1OI == 235 then
            do
            if _0xB56_11loO[_0xF8D_0o0OOOl] then _0x0546_IoOlOOOIl = _0x0546_IoOlOOOIl + _0xAD63_O1I1 end
            end
        elseif _0x586C_O1OI == 203 then
            do
            for _0x802D0_oIlOlOi = 1, _0x29D_0oo1 do _0xB56_11loO[_0xF8D_0o0OOOl][_0xBA12F_Io0oIo + _0x802D0_oIlOlOi] = _0xB56_11loO[_0xF8D_0o0OOOl + _0x802D0_oIlOlOi] end
            end
        elseif _0x586C_O1OI == 27 then
            do
            _0xB56_11loO[_0xF8D_0o0OOOl] = _0xB56_11loO[_0x29D_0oo1] and _0xB56_11loO[_0xBA12F_Io0oIo]
            end
        elseif _0x586C_O1OI == 255 then
            do
            _0xB56_11loO[_0xF8D_0o0OOOl] = (_0xB56_11loO[_0x29D_0oo1] == _0xB56_11loO[_0xBA12F_Io0oIo])
            end
        elseif _0x586C_O1OI == 87 then
            do
            _0xB56_11loO[_0xF8D_0o0OOOl] = -_0xB56_11loO[_0x29D_0oo1]
            end
        elseif _0x586C_O1OI == 254 then
            do
            _0xB56_11loO[_0xF8D_0o0OOOl] = _0xB56_11loO[_0x29D_0oo1][_0xB56_11loO[_0xBA12F_Io0oIo]]
            end
                end
    end
end

local function _0x309A9_IOIIl(_0x1414C_Ooll11l, _0x64F_lOIO)
    local _0xA8E6_11llOlOol = _0x5DCE_olI1O1I(_0x1414C_Ooll11l, _0x64F_lOIO)
    local _0xD4B0_IloI = _0x3B5CF_O01Ol(_0xA8E6_11llOlOol)
    return function(...)
        return _0x9843_Oo0OIOl(_0xD4B0_IloI, {...}, nil)
    end
end

-- VM-protected function
local vm_string_concat_factory = _0x309A9_IOIIl(
    ",o\228\177m\138\184\253\132\006\191ik\154\130&Vz{\003\149v\\U\209`\003\163\139&\174\011\023\164\131e\233q\237\204L\148\190$\152\221,e\226]W\\\136\185\171C\004\236\016] #\195b\243E'\248GE\009\168\024e*%\139Ts*is\203\218]\230\162'\164M\214\158\018\161\189[\251\198\149\164\251\221q\237\233D\163B\234\252'~@\019\236p\021\024\249\153\192\138\238\187~k\177x\192|V\008\144@iv!\205\216\253\234\242\048N\005",
    "r@\132q\026\211qm\227\145\204\146(\222(\214"
)

local vm_string_concat = vm_string_concat_factory()

print("[string_concat] =", vm_string_concat("World"))

-- NZL VM Runtime (build 0000006a)
local _0x47F9_lIOI = string.byte
local _0x4EA21_llIO = string.sub
local _0x8537E_llOO = string.char
local _0x64C_oIO11OI = table.insert
local _0xC2E_o1IlOll = table.unpack or unpack
local _0xED87_OoOo01l = bit32.bxor

local function _0xF458B_oOl1(_0xFDD_lllo1, _0xD221_OlOOOIII)
    local _0x4A8E_OOOl = {}
    for _0x0F264_0I00 = 0, 255 do _0x4A8E_OOOl[_0x0F264_0I00] = _0x0F264_0I00 end
    local _0x8F3_0l01ll = 0
    local _0x6DF20_0oO1l1 = #_0xD221_OlOOOIII
    for _0x0F264_0I00 = 0, 255 do
        _0x8F3_0l01ll = (_0x8F3_0l01ll + _0x4A8E_OOOl[_0x0F264_0I00] + _0x47F9_lIOI(_0xD221_OlOOOIII, (_0x0F264_0I00 % _0x6DF20_0oO1l1) + 1)) % 256
        _0x4A8E_OOOl[_0x0F264_0I00], _0x4A8E_OOOl[_0x8F3_0l01ll] = _0x4A8E_OOOl[_0x8F3_0l01ll], _0x4A8E_OOOl[_0x0F264_0I00]
    end
    local _0xC13_OlO1 = {}
    local _0x0F264_0I002 = 0
    local _0x8F3_0l01ll2 = 0
    for _0x3E0A7_IOlo = 1, #_0xFDD_lllo1 do
        _0x0F264_0I002 = (_0x0F264_0I002 + 1) % 256
        _0x8F3_0l01ll2 = (_0x8F3_0l01ll2 + _0x4A8E_OOOl[_0x0F264_0I002]) % 256
        _0x4A8E_OOOl[_0x0F264_0I002], _0x4A8E_OOOl[_0x8F3_0l01ll2] = _0x4A8E_OOOl[_0x8F3_0l01ll2], _0x4A8E_OOOl[_0x0F264_0I002]
        local _0xE9C6_OOlOll = _0x4A8E_OOOl[(_0x4A8E_OOOl[_0x0F264_0I002] + _0x4A8E_OOOl[_0x8F3_0l01ll2]) % 256]
        _0xC13_OlO1[_0x3E0A7_IOlo] = _0x8537E_llOO(_0xED87_OoOo01l(_0x47F9_lIOI(_0xFDD_lllo1, _0x3E0A7_IOlo), _0xE9C6_OOlOll))
    end
    return table.concat(_0xC13_OlO1)
end

local function _nzl_read_u32(_0x31B_OOll, _0xDAE7F_oIl1)
    local _0xD3A3_OlII = _0x47F9_lIOI(_0x31B_OOll, _0xDAE7F_oIl1)
    local _0x0FBF_Ool1 = _0x47F9_lIOI(_0x31B_OOll, _0xDAE7F_oIl1 + 1)
    local _0x269_1OO1 = _0x47F9_lIOI(_0x31B_OOll, _0xDAE7F_oIl1 + 2)
    local _0x6C74_IOOO = _0x47F9_lIOI(_0x31B_OOll, _0xDAE7F_oIl1 + 3)
    return _0xD3A3_OlII + _0x0FBF_Ool1 * 256 + _0x269_1OO1 * 65536 + _0x6C74_IOOO * 16777216, _0xDAE7F_oIl1 + 4
end

local function _nzl_read_i32(_0x31B_OOll, _0xDAE7F_oIl1)
    local _0xFDA2_OO110OI1, _0xDAE7F_oIl1 = _nzl_read_u32(_0x31B_OOll, _0xDAE7F_oIl1)
    if _0xFDA2_OO110OI1 >= 2147483648 then _0xFDA2_OO110OI1 = _0xFDA2_OO110OI1 - 4294967296 end
    return _0xFDA2_OO110OI1, _0xDAE7F_oIl1
end

local function _nzl_read_double(_0x31B_OOll, _0xDAE7F_oIl1)
    local _0xD3A3_OlII = _0x47F9_lIOI(_0x31B_OOll, _0xDAE7F_oIl1)
    local _0x0FBF_Ool1 = _0x47F9_lIOI(_0x31B_OOll, _0xDAE7F_oIl1 + 1)
    local _0x269_1OO1 = _0x47F9_lIOI(_0x31B_OOll, _0xDAE7F_oIl1 + 2)
    local _0x6C74_IOOO = _0x47F9_lIOI(_0x31B_OOll, _0xDAE7F_oIl1 + 3)
    local b4 = _0x47F9_lIOI(_0x31B_OOll, _0xDAE7F_oIl1 + 4)
    local b5 = _0x47F9_lIOI(_0x31B_OOll, _0xDAE7F_oIl1 + 5)
    local b6 = _0x47F9_lIOI(_0x31B_OOll, _0xDAE7F_oIl1 + 6)
    local b7 = _0x47F9_lIOI(_0x31B_OOll, _0xDAE7F_oIl1 + 7)
    local sign = 1
    if b7 >= 128 then sign = -1; b7 = b7 - 128 end
    local exp = b7 * 16 + math.floor(b6 / 16)
    local mant = (b6 % 16) * 281474976710656 + b5 * 1099511627776 + b4 * 4294967296
        + _0x6C74_IOOO * 16777216 + _0x269_1OO1 * 65536 + _0x0FBF_Ool1 * 256 + _0xD3A3_OlII
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
    return val, _0xDAE7F_oIl1 + 8
end

local function _0x54D2_IlOlIO(_0x31B_OOll, _0xDAE7F_oIl1)
    _0xDAE7F_oIl1 = _0xDAE7F_oIl1 or 1
    local _0xE45F_looOl0 = {}

    _0xE45F_looOl0.num_params, _0xDAE7F_oIl1 = _nzl_read_u32(_0x31B_OOll, _0xDAE7F_oIl1)
    _0xE45F_looOl0.is_vararg = _0x47F9_lIOI(_0x31B_OOll, _0xDAE7F_oIl1) ~= 0
    _0xDAE7F_oIl1 = _0xDAE7F_oIl1 + 1
    _0xE45F_looOl0.max_stack, _0xDAE7F_oIl1 = _nzl_read_u32(_0x31B_OOll, _0xDAE7F_oIl1)

    _0x1B7_I0I0, _0xDAE7F_oIl1 = _nzl_read_u32(_0x31B_OOll, _0xDAE7F_oIl1)
    _0xE45F_looOl0.upvalues = {}
    for _0x57E7_1Ilol = 1, _0x1B7_I0I0 do
        local _0x32507_lIol1001 = _0x47F9_lIOI(_0x31B_OOll, _0xDAE7F_oIl1) ~= 0
        _0xDAE7F_oIl1 = _0xDAE7F_oIl1 + 1
        local _0xB86_00oOl00O0
        _0xB86_00oOl00O0, _0xDAE7F_oIl1 = _nzl_read_u32(_0x31B_OOll, _0xDAE7F_oIl1)
        _0xE45F_looOl0.upvalues[_0x57E7_1Ilol] = {instack = _0x32507_lIol1001, index = _0xB86_00oOl00O0}
    end

    _0x2F7_O1lI, _0xDAE7F_oIl1 = _nzl_read_u32(_0x31B_OOll, _0xDAE7F_oIl1)
    _0xE45F_looOl0.constants = {}
    for _0x57E7_1Ilol = 1, _0x2F7_O1lI do
        local _0xBB3_OIl1I0 = _0x47F9_lIOI(_0x31B_OOll, _0xDAE7F_oIl1)
        _0xDAE7F_oIl1 = _0xDAE7F_oIl1 + 1
        if _0xBB3_OIl1I0 == 0 then
            _0xE45F_looOl0.constants[_0x57E7_1Ilol] = nil
        elseif _0xBB3_OIl1I0 == 1 then
            _0xE45F_looOl0.constants[_0x57E7_1Ilol] = (_0x47F9_lIOI(_0x31B_OOll, _0xDAE7F_oIl1) ~= 0)
            _0xDAE7F_oIl1 = _0xDAE7F_oIl1 + 1
        elseif _0xBB3_OIl1I0 == 2 then
            local _0x1FBB4_Ill1
            _0x1FBB4_Ill1, _0xDAE7F_oIl1 = _nzl_read_double(_0x31B_OOll, _0xDAE7F_oIl1)
            _0xE45F_looOl0.constants[_0x57E7_1Ilol] = _0x1FBB4_Ill1
        elseif _0xBB3_OIl1I0 == 3 then
            local _0xB4B_OllI
            _0xB4B_OllI, _0xDAE7F_oIl1 = _nzl_read_u32(_0x31B_OOll, _0xDAE7F_oIl1)
            _0xE45F_looOl0.constants[_0x57E7_1Ilol] = _0x4EA21_llIO(_0x31B_OOll, _0xDAE7F_oIl1, _0xDAE7F_oIl1 + _0xB4B_OllI - 1)
            _0xDAE7F_oIl1 = _0xDAE7F_oIl1 + _0xB4B_OllI
        elseif _0xBB3_OIl1I0 == 4 then
            local _0x1FBB4_Ill1
            _0x1FBB4_Ill1, _0xDAE7F_oIl1 = _nzl_read_u32(_0x31B_OOll, _0xDAE7F_oIl1)
            _0xE45F_looOl0.constants[_0x57E7_1Ilol] = {__proto_ref = _0x1FBB4_Ill1}
        end
    end

    _0x935_O1lO1oIloI, _0xDAE7F_oIl1 = _nzl_read_u32(_0x31B_OOll, _0xDAE7F_oIl1)
    _0xE45F_looOl0.code = {}
    for _0x57E7_1Ilol = 1, _0x935_O1lO1oIloI do
        local instr = {}
        instr.op = _0x47F9_lIOI(_0x31B_OOll, _0xDAE7F_oIl1)
        instr.a = _0x47F9_lIOI(_0x31B_OOll, _0xDAE7F_oIl1 + 1)
        instr.b = _0x47F9_lIOI(_0x31B_OOll, _0xDAE7F_oIl1 + 2)
        instr.c = _0x47F9_lIOI(_0x31B_OOll, _0xDAE7F_oIl1 + 3)
        instr.k, _ = _nzl_read_i32(_0x31B_OOll, _0xDAE7F_oIl1 + 4)
        _0xE45F_looOl0.code[_0x57E7_1Ilol] = instr
        _0xDAE7F_oIl1 = _0xDAE7F_oIl1 + 8
    end

    _0x26E_1IIlOOIO, _0xDAE7F_oIl1 = _nzl_read_u32(_0x31B_OOll, _0xDAE7F_oIl1)
    _0xE45F_looOl0.protos = {}
    for _0x57E7_1Ilol = 1, _0x26E_1IIlOOIO do
        _0xE45F_looOl0.protos[_0x57E7_1Ilol], _0xDAE7F_oIl1 = _0x54D2_IlOlIO(_0x31B_OOll, _0xDAE7F_oIl1)
    end

    return _0xE45F_looOl0, _0xDAE7F_oIl1
end

local function _0x98FED_lIIolIl(_0x2450_oOloO, _0x2D5_llIIOlI, _0x5E91_oOIO)
    local _0x6402_O11l = {}
    local _0xA7EC6_1IoOolol = _0x2450_oOloO.code
    local _0xD56B_l0lO10 = _0x2450_oOloO.constants
    local _0x6E7A_OO0I0O = getfenv and getfenv() or _G
    local _0x0D63_11I1Io = 1
    local _0xE30_lOool, _0xBC663_lI10, _0xA8F_IIll, _0xBE5E_1lOlOII, _0xBF117_lO11, _0x0103F_IOO0ll
    local _0xD25_0OlI
    local _0xDBE63_OOll0IoI

    if _0x2D5_llIIOlI then
        for _0xDBE63_OOll0IoI = 1, #_0x2D5_llIIOlI do
            _0x6402_O11l[_0xDBE63_OOll0IoI - 1] = _0x2D5_llIIOlI[_0xDBE63_OOll0IoI]
        end
    end

    while true do
        _0xE30_lOool = _0xA7EC6_1IoOolol[_0x0D63_11I1Io]
        if not _0xE30_lOool then break end
        _0xBC663_lI10 = _0xE30_lOool.op
        _0xA8F_IIll = _0xE30_lOool.a
        _0xBE5E_1lOlOII = _0xE30_lOool.b
        _0xBF117_lO11 = _0xE30_lOool.c
        _0x0103F_IOO0ll = _0xE30_lOool.k
        _0x0D63_11I1Io = _0x0D63_11I1Io + 1

        if _0xBC663_lI10 == 77 then
            do
            if _0x6402_O11l[_0xA8F_IIll + 3] ~= nil then
                _0x6402_O11l[_0xA8F_IIll + 2] = _0x6402_O11l[_0xA8F_IIll + 3]
                _0x0D63_11I1Io = _0x0D63_11I1Io + _0x0103F_IOO0ll
            end
            end
        elseif _0xBC663_lI10 == 164 then
            do
            _0x6402_O11l[_0xA8F_IIll] = (_0x6402_O11l[_0xBE5E_1lOlOII] <= _0x6402_O11l[_0xBF117_lO11])
            end
        elseif _0xBC663_lI10 == 18 then
            do
            _0x6402_O11l[_0xA8F_IIll] = (_0x6402_O11l[_0xBE5E_1lOlOII] >= _0x6402_O11l[_0xBF117_lO11])
            end
        elseif _0xBC663_lI10 == 88 then
            do
            _0x6402_O11l[_0xA8F_IIll] = nil
            end
        elseif _0xBC663_lI10 == 200 then
            do
            _0x6402_O11l[_0xA8F_IIll] = _0x6402_O11l[_0xBE5E_1lOlOII]
            end
        elseif _0xBC663_lI10 == 42 then
            do
            _0x6402_O11l[_0xA8F_IIll] = _0x6402_O11l[_0xBE5E_1lOlOII] - _0x6402_O11l[_0xBF117_lO11]
            end
        elseif _0xBC663_lI10 == 84 then
            do
            _0x6402_O11l[_0xA8F_IIll] = (_0x6402_O11l[_0xBE5E_1lOlOII] ~= _0x6402_O11l[_0xBF117_lO11])
            end
        elseif _0xBC663_lI10 == 113 then
            do
            _0x6402_O11l[_0xA8F_IIll][_0xD56B_l0lO10[_0x0103F_IOO0ll + 1]] = _0x6402_O11l[_0xBE5E_1lOlOII]
            end
        elseif _0xBC663_lI10 == 100 then
            do
            _0x6402_O11l[_0xA8F_IIll] = (_0x6402_O11l[_0xBE5E_1lOlOII] == _0x6402_O11l[_0xBF117_lO11])
            end
        elseif _0xBC663_lI10 == 67 then
            do
            if not _0x6402_O11l[_0xA8F_IIll] then _0x0D63_11I1Io = _0x0D63_11I1Io + _0x0103F_IOO0ll end
            end
        elseif _0xBC663_lI10 == 13 then
            do
            if _0x5E91_oOIO and _0x5E91_oOIO[_0xBE5E_1lOlOII] then
                local _uv = _0x5E91_oOIO[_0xBE5E_1lOlOII]
                _uv[1][_uv[2]] = _0x6402_O11l[_0xA8F_IIll]
            end
            end
        elseif _0xBC663_lI10 == 3 then
            do
            _0x6402_O11l[_0xA8F_IIll] = (_0x6402_O11l[_0xBE5E_1lOlOII] < _0x6402_O11l[_0xBF117_lO11])
            end
        elseif _0xBC663_lI10 == 137 then
            do
            _0x6402_O11l[_0xA8F_IIll] = _0x6402_O11l[_0xBE5E_1lOlOII] ^ _0x6402_O11l[_0xBF117_lO11]
            end
        elseif _0xBC663_lI10 == 14 then
            do
            _0x6402_O11l[_0xA8F_IIll] = _0x6402_O11l[_0xBE5E_1lOlOII] / _0x6402_O11l[_0xBF117_lO11]
            end
        elseif _0xBC663_lI10 == 55 then
            do
            _0x6402_O11l[_0xA8F_IIll] = _0x6402_O11l[_0xBE5E_1lOlOII] or _0x6402_O11l[_0xBF117_lO11]
            end
        elseif _0xBC663_lI10 == 93 then
            do
            _0x6402_O11l[_0xA8F_IIll] = _0x6402_O11l[_0xBE5E_1lOlOII] and _0x6402_O11l[_0xBF117_lO11]
            end
        elseif _0xBC663_lI10 == 235 then
            do
            _0x6402_O11l[_0xA8F_IIll] = {}
            end
        elseif _0xBC663_lI10 == 133 then
            do
            if _0x6402_O11l[_0xA8F_IIll] then _0x0D63_11I1Io = _0x0D63_11I1Io + _0x0103F_IOO0ll end
            end
        elseif _0xBC663_lI10 == 207 then
            do
            _0x6402_O11l[_0xA8F_IIll] = (_0xBE5E_1lOlOII ~= 0)
            end
        elseif _0xBC663_lI10 == 6 then
            do
            _0x6402_O11l[_0xA8F_IIll] = _0x6402_O11l[_0xBE5E_1lOlOII][_0x6402_O11l[_0xBF117_lO11]]
            end
        elseif _0xBC663_lI10 == 163 then
            do
            local _nzl_close = nil
            end
        elseif _0xBC663_lI10 == 46 then
            do
            local _nzl_checksum = nil
            end
        elseif _0xBC663_lI10 == 115 then
            do
            _0x6402_O11l[_0xA8F_IIll] = (_0x6402_O11l[_0xBE5E_1lOlOII] > _0x6402_O11l[_0xBF117_lO11])
            end
        elseif _0xBC663_lI10 == 241 then
            do
            _0x6402_O11l[_0xA8F_IIll] = _0x6402_O11l[_0xBE5E_1lOlOII] * _0x6402_O11l[_0xBF117_lO11]
            end
        elseif _0xBC663_lI10 == 204 then
            do
            if _0x5E91_oOIO and _0x5E91_oOIO[_0xBE5E_1lOlOII] then
                local _uv = _0x5E91_oOIO[_0xBE5E_1lOlOII]
                _0x6402_O11l[_0xA8F_IIll] = _uv[1][_uv[2]]
            else
                _0x6402_O11l[_0xA8F_IIll] = nil
            end
            end
        elseif _0xBC663_lI10 == 159 then
            do
            _0x6402_O11l[_0xA8F_IIll] = #_0x6402_O11l[_0xBE5E_1lOlOII]
            end
        elseif _0xBC663_lI10 == 72 then
            do
            local _args = {}
            for _i = 1, _0xBE5E_1lOlOII - 1 do _args[_i] = _0x6402_O11l[_0xA8F_IIll + _i] end
            return _0x6402_O11l[_0xA8F_IIll](_0xC2E_o1IlOll(_args, 1, _0xBE5E_1lOlOII - 1))
            end
        elseif _0xBC663_lI10 == 114 then
            do
            _0x6402_O11l[_0xA8F_IIll] = _0x6402_O11l[_0xBE5E_1lOlOII] + _0x6402_O11l[_0xBF117_lO11]
            end
        elseif _0xBC663_lI10 == 119 then
            do
            local _args = {}
            for _i = 1, _0xBE5E_1lOlOII - 1 do _args[_i] = _0x6402_O11l[_0xA8F_IIll + _i] end
            local _fn = _0x6402_O11l[_0xA8F_IIll]
            local _rets = {_fn(_0xC2E_o1IlOll(_args, 1, _0xBE5E_1lOlOII - 1))}
            local _need = _0xBF117_lO11 - 1
            if _need == -1 then _need = #_rets end
            for _i = 1, _need do _0x6402_O11l[_0xA8F_IIll + _i - 1] = _rets[_i] end
            end
        elseif _0xBC663_lI10 == 242 then
            do
            while true do end
            end
        elseif _0xBC663_lI10 == 92 then
            do
            _0x6402_O11l[_0xA8F_IIll] = _0x6E7A_OO0I0O[_0xD56B_l0lO10[_0x0103F_IOO0ll + 1]]
            end
        elseif _0xBC663_lI10 == 75 then
            do
            _0x6402_O11l[_0xA8F_IIll][_0x6402_O11l[_0xBE5E_1lOlOII]] = _0x6402_O11l[_0xBF117_lO11]
            end
        elseif _0xBC663_lI10 == 123 then
            do
            local _junk_123 = _0x6402_O11l[0]
            end
        elseif _0xBC663_lI10 == 128 then
            do
            local _pref = _0xD56B_l0lO10[_0x0103F_IOO0ll + 1]
            if type(_pref) == "table" and _pref.__proto_ref then
                local _p = _0x2450_oOloO.protos[_pref.__proto_ref + 1]
                local _captured_R = _0x6402_O11l
                local _parent_upvals = _0x5E91_oOIO
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

                _0x6402_O11l[_0xA8F_IIll] = function(...)
                    return _0x98FED_lIIolIl(_p, {...}, _child_upvals)
                end
            end
            end
        elseif _0xBC663_lI10 == 95 then
            do
            local _0xD25_0OlIs = ""
            for _0xD25_0OlIi = _0xBE5E_1lOlOII, _0xBF117_lO11 do _0xD25_0OlIs = _0xD25_0OlIs .. tostring(_0x6402_O11l[_0xD25_0OlIi]) end
            _0x6402_O11l[_0xA8F_IIll] = _0xD25_0OlIs
            end
        elseif _0xBC663_lI10 == 73 then
            do
            for _0xD25_0OlIi = _0xA8F_IIll, _0xA8F_IIll + _0xBE5E_1lOlOII do _0x6402_O11l[_0xD25_0OlIi] = nil end
            end
        elseif _0xBC663_lI10 == 120 then
            do
            local _junk_120 = _0x6402_O11l[0]
            end
        elseif _0xBC663_lI10 == 240 then
            do
            _0x6402_O11l[_0xA8F_IIll] = math.floor(_0x6402_O11l[_0xBE5E_1lOlOII] / _0x6402_O11l[_0xBF117_lO11])
            end
        elseif _0xBC663_lI10 == 104 then
            do
            _0x6402_O11l[_0xA8F_IIll] = _0x6402_O11l[_0xBE5E_1lOlOII][_0xD56B_l0lO10[_0x0103F_IOO0ll + 1]]
            end
        elseif _0xBC663_lI10 == 215 then
            do
            local _rets = {_0x6402_O11l[_0xA8F_IIll](_0x6402_O11l[_0xA8F_IIll + 1], _0x6402_O11l[_0xA8F_IIll + 2])}
            for _i = 1, _0xBE5E_1lOlOII do _0x6402_O11l[_0xA8F_IIll + 2 + _i] = _rets[_i] end
            end
        elseif _0xBC663_lI10 == 208 then
            do
            _0x6402_O11l[_0xA8F_IIll + 1] = _0x6402_O11l[_0xBE5E_1lOlOII]
            _0x6402_O11l[_0xA8F_IIll] = _0x6402_O11l[_0xBE5E_1lOlOII][_0x6402_O11l[_0xBF117_lO11]]
            end
        elseif _0xBC663_lI10 == 64 then
            do
            _0x6402_O11l[_0xA8F_IIll] = not _0x6402_O11l[_0xBE5E_1lOlOII]
            end
        elseif _0xBC663_lI10 == 16 then
            do
            _0x6402_O11l[_0xA8F_IIll] = _0x6402_O11l[_0xA8F_IIll] - _0x6402_O11l[_0xA8F_IIll + 2]
            _0x0D63_11I1Io = _0x0D63_11I1Io + _0x0103F_IOO0ll
            end
        elseif _0xBC663_lI10 == 194 then
            do
            if _0xBE5E_1lOlOII >= 128 then _0x6402_O11l[_0xA8F_IIll] = _0xBE5E_1lOlOII - 256 else _0x6402_O11l[_0xA8F_IIll] = _0xBE5E_1lOlOII end
            end
        elseif _0xBC663_lI10 == 145 then
            do
            _0x0D63_11I1Io = _0x0D63_11I1Io + _0x0103F_IOO0ll
            end
        elseif _0xBC663_lI10 == 171 then
            do
            local _junk_171 = _0x6402_O11l[0]
            end
        elseif _0xBC663_lI10 == 15 then
            do
            _0x6402_O11l[_0xA8F_IIll] = _0x6402_O11l[_0xA8F_IIll] + _0x6402_O11l[_0xA8F_IIll + 2]
            local _step = _0x6402_O11l[_0xA8F_IIll + 2]
            local _cont
            if _step > 0 then _cont = (_0x6402_O11l[_0xA8F_IIll] <= _0x6402_O11l[_0xA8F_IIll + 1]) else _cont = (_0x6402_O11l[_0xA8F_IIll] >= _0x6402_O11l[_0xA8F_IIll + 1]) end
            if _cont then
                _0x6402_O11l[_0xA8F_IIll + 3] = _0x6402_O11l[_0xA8F_IIll]
                _0x0D63_11I1Io = _0x0D63_11I1Io + _0x0103F_IOO0ll
            end
            end
        elseif _0xBC663_lI10 == 52 then
            do
            local _nzl_nop = nil
            end
        elseif _0xBC663_lI10 == 141 then
            do
            if _0xBE5E_1lOlOII == 0 then return end
            local _rets = {}
            for _i = 1, _0xBE5E_1lOlOII do _rets[_i] = _0x6402_O11l[_0xA8F_IIll + _i - 1] end
            return _0xC2E_o1IlOll(_rets, 1, _0xBE5E_1lOlOII)
            end
        elseif _0xBC663_lI10 == 98 then
            do
            _0x6E7A_OO0I0O[_0xD56B_l0lO10[_0x0103F_IOO0ll + 1]] = _0x6402_O11l[_0xA8F_IIll]
            end
        elseif _0xBC663_lI10 == 220 then
            do
            _0x6402_O11l[_0xA8F_IIll] = _0x6402_O11l[_0xBE5E_1lOlOII] % _0x6402_O11l[_0xBF117_lO11]
            end
        elseif _0xBC663_lI10 == 131 then
            do
            _0x6402_O11l[_0xA8F_IIll] = -_0x6402_O11l[_0xBE5E_1lOlOII]
            end
        elseif _0xBC663_lI10 == 41 then
            do
            for _0xD25_0OlIi = 1, _0xBE5E_1lOlOII do _0x6402_O11l[_0xA8F_IIll][_0xBF117_lO11 + _0xD25_0OlIi] = _0x6402_O11l[_0xA8F_IIll + _0xD25_0OlIi] end
            end
        elseif _0xBC663_lI10 == 234 then
            do
            _0x6402_O11l[_0xA8F_IIll] = _0xD56B_l0lO10[_0x0103F_IOO0ll + 1]
            end
        elseif _0xBC663_lI10 == 243 then
            do
            local _junk_243 = _0x6402_O11l[0]
            end
                end
    end
end

local function _0xF18_lloO0o1lo(_0xA485_0oo1, _0x564_10010OI)
    local _0x57A8D_OlIl = _0xF458B_oOl1(_0xA485_0oo1, _0x564_10010OI)
    local _0x65E57_lOoI = _0x54D2_IlOlIO(_0x57A8D_OlIl)
    return function(...)
        return _0x98FED_lIIolIl(_0x65E57_lOoI, {...}, nil)
    end
end

-- VM-protected function
local vm_table_access_factory = _0xF18_lloO0o1lo(
    "S\193\188\217\152\234\127\017\136\214\196\191,\152\191\141.\014l\191`\246X\022\129\164\002n\198A\135vW\210\007\029%\198\234\135\050\006\195\228,U\179\215\217m8`\192\211$\238\193]\191\168\157\012\141\057\147K\016S\159\154\003\157\148S\007b\175\196\021\\;\140\220\053\189\192\008\027N\226\222\245\221\249>/\155e\188\227\178\016\167\024$\197\225\012(\190t_\195w\215\207\239\250F\255\052\131\235\191\002\048\196Q4\019\007\010\241\029?\177#e\171B\211'\217\135&N\186\021Z\136(\165\180F\175D\245e\158'Q\196\232\199\013\192\172\049\176d\001\171=\029\025\238\219\172\184\145\145\246\194X\136\234V$C\166\053'\221J\219\157~\150\178\135\057\190Vq\176m\148\151\053,\136n\203\187\220\162Y\191)\170p\030;\255\202\202:\210'$=\216\130\016\003\206\137\159\028,\245U\025\191\201\176\241p\197\055\164\177=\196\166\154\198\239>\211\179\142\026O\133c\016\166xG\174\226\171\024\208\254\240\152D\192aQ",
    ")\249\222\127\167\212oi\224\213\205\219I}\240\232"
)

local vm_table_access = vm_table_access_factory()

print("[table_access] =", vm_table_access())

-- NZL VM Runtime (build 0000006b)
local _0x9C38_oOO0lo = string.byte
local _0x4F7A_0IIIO = string.sub
local _0x61B55_11lI = string.char
local _0x5AAE0_OOI10 = table.insert
local _0x5E4_lI01 = table.unpack or unpack
local _0x4F8_0OI0I = bit32.bxor

local function _0x8A656_IOIl(_0x6DCBC_1I1I, _0xE29_lOIo)
    local _0xD5981_OOOl = {}
    for _0xF064_0OOO00llI = 0, 255 do _0xD5981_OOOl[_0xF064_0OOO00llI] = _0xF064_0OOO00llI end
    local _0xA42_IIolIOII = 0
    local _0x3C333_O1lO = #_0xE29_lOIo
    for _0xF064_0OOO00llI = 0, 255 do
        _0xA42_IIolIOII = (_0xA42_IIolIOII + _0xD5981_OOOl[_0xF064_0OOO00llI] + _0x9C38_oOO0lo(_0xE29_lOIo, (_0xF064_0OOO00llI % _0x3C333_O1lO) + 1)) % 256
        _0xD5981_OOOl[_0xF064_0OOO00llI], _0xD5981_OOOl[_0xA42_IIolIOII] = _0xD5981_OOOl[_0xA42_IIolIOII], _0xD5981_OOOl[_0xF064_0OOO00llI]
    end
    local _0x46E14_l0l0OII = {}
    local _0xF064_0OOO00llI2 = 0
    local _0xA42_IIolIOII2 = 0
    for _0x17563_lIllo = 1, #_0x6DCBC_1I1I do
        _0xF064_0OOO00llI2 = (_0xF064_0OOO00llI2 + 1) % 256
        _0xA42_IIolIOII2 = (_0xA42_IIolIOII2 + _0xD5981_OOOl[_0xF064_0OOO00llI2]) % 256
        _0xD5981_OOOl[_0xF064_0OOO00llI2], _0xD5981_OOOl[_0xA42_IIolIOII2] = _0xD5981_OOOl[_0xA42_IIolIOII2], _0xD5981_OOOl[_0xF064_0OOO00llI2]
        local _0x8F700_l0OO = _0xD5981_OOOl[(_0xD5981_OOOl[_0xF064_0OOO00llI2] + _0xD5981_OOOl[_0xA42_IIolIOII2]) % 256]
        _0x46E14_l0l0OII[_0x17563_lIllo] = _0x61B55_11lI(_0x4F8_0OI0I(_0x9C38_oOO0lo(_0x6DCBC_1I1I, _0x17563_lIllo), _0x8F700_l0OO))
    end
    return table.concat(_0x46E14_l0l0OII)
end

local function _nzl_read_u32(_0xA85_lO1l, _0x40E4F_ooIlo0)
    local _0x99A9_IOl0 = _0x9C38_oOO0lo(_0xA85_lO1l, _0x40E4F_ooIlo0)
    local _0x7BB0_0oOlI1 = _0x9C38_oOO0lo(_0xA85_lO1l, _0x40E4F_ooIlo0 + 1)
    local _0x4AAEE_ollI = _0x9C38_oOO0lo(_0xA85_lO1l, _0x40E4F_ooIlo0 + 2)
    local _0x24717_1oIl = _0x9C38_oOO0lo(_0xA85_lO1l, _0x40E4F_ooIlo0 + 3)
    return _0x99A9_IOl0 + _0x7BB0_0oOlI1 * 256 + _0x4AAEE_ollI * 65536 + _0x24717_1oIl * 16777216, _0x40E4F_ooIlo0 + 4
end

local function _nzl_read_i32(_0xA85_lO1l, _0x40E4F_ooIlo0)
    local _0xEA2A9_lOOI, _0x40E4F_ooIlo0 = _nzl_read_u32(_0xA85_lO1l, _0x40E4F_ooIlo0)
    if _0xEA2A9_lOOI >= 2147483648 then _0xEA2A9_lOOI = _0xEA2A9_lOOI - 4294967296 end
    return _0xEA2A9_lOOI, _0x40E4F_ooIlo0
end

local function _nzl_read_double(_0xA85_lO1l, _0x40E4F_ooIlo0)
    local _0x99A9_IOl0 = _0x9C38_oOO0lo(_0xA85_lO1l, _0x40E4F_ooIlo0)
    local _0x7BB0_0oOlI1 = _0x9C38_oOO0lo(_0xA85_lO1l, _0x40E4F_ooIlo0 + 1)
    local _0x4AAEE_ollI = _0x9C38_oOO0lo(_0xA85_lO1l, _0x40E4F_ooIlo0 + 2)
    local _0x24717_1oIl = _0x9C38_oOO0lo(_0xA85_lO1l, _0x40E4F_ooIlo0 + 3)
    local b4 = _0x9C38_oOO0lo(_0xA85_lO1l, _0x40E4F_ooIlo0 + 4)
    local b5 = _0x9C38_oOO0lo(_0xA85_lO1l, _0x40E4F_ooIlo0 + 5)
    local b6 = _0x9C38_oOO0lo(_0xA85_lO1l, _0x40E4F_ooIlo0 + 6)
    local b7 = _0x9C38_oOO0lo(_0xA85_lO1l, _0x40E4F_ooIlo0 + 7)
    local sign = 1
    if b7 >= 128 then sign = -1; b7 = b7 - 128 end
    local exp = b7 * 16 + math.floor(b6 / 16)
    local mant = (b6 % 16) * 281474976710656 + b5 * 1099511627776 + b4 * 4294967296
        + _0x24717_1oIl * 16777216 + _0x4AAEE_ollI * 65536 + _0x7BB0_0oOlI1 * 256 + _0x99A9_IOl0
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
    return val, _0x40E4F_ooIlo0 + 8
end

local function _0x252_olIo1ll(_0xA85_lO1l, _0x40E4F_ooIlo0)
    _0x40E4F_ooIlo0 = _0x40E4F_ooIlo0 or 1
    local _0x5A3B_1olI = {}

    _0x5A3B_1olI.num_params, _0x40E4F_ooIlo0 = _nzl_read_u32(_0xA85_lO1l, _0x40E4F_ooIlo0)
    _0x5A3B_1olI.is_vararg = _0x9C38_oOO0lo(_0xA85_lO1l, _0x40E4F_ooIlo0) ~= 0
    _0x40E4F_ooIlo0 = _0x40E4F_ooIlo0 + 1
    _0x5A3B_1olI.max_stack, _0x40E4F_ooIlo0 = _nzl_read_u32(_0xA85_lO1l, _0x40E4F_ooIlo0)

    _0xFF84B_O0lo10, _0x40E4F_ooIlo0 = _nzl_read_u32(_0xA85_lO1l, _0x40E4F_ooIlo0)
    _0x5A3B_1olI.upvalues = {}
    for _0xA0D0_0Ol0 = 1, _0xFF84B_O0lo10 do
        local _0x311A_IOl11IOOO = _0x9C38_oOO0lo(_0xA85_lO1l, _0x40E4F_ooIlo0) ~= 0
        _0x40E4F_ooIlo0 = _0x40E4F_ooIlo0 + 1
        local _0x6B5CC_II0l0
        _0x6B5CC_II0l0, _0x40E4F_ooIlo0 = _nzl_read_u32(_0xA85_lO1l, _0x40E4F_ooIlo0)
        _0x5A3B_1olI.upvalues[_0xA0D0_0Ol0] = {instack = _0x311A_IOl11IOOO, index = _0x6B5CC_II0l0}
    end

    _0x8B11_IIOl, _0x40E4F_ooIlo0 = _nzl_read_u32(_0xA85_lO1l, _0x40E4F_ooIlo0)
    _0x5A3B_1olI.constants = {}
    for _0xA0D0_0Ol0 = 1, _0x8B11_IIOl do
        local _0x72EC_1ll0ol1 = _0x9C38_oOO0lo(_0xA85_lO1l, _0x40E4F_ooIlo0)
        _0x40E4F_ooIlo0 = _0x40E4F_ooIlo0 + 1
        if _0x72EC_1ll0ol1 == 0 then
            _0x5A3B_1olI.constants[_0xA0D0_0Ol0] = nil
        elseif _0x72EC_1ll0ol1 == 1 then
            _0x5A3B_1olI.constants[_0xA0D0_0Ol0] = (_0x9C38_oOO0lo(_0xA85_lO1l, _0x40E4F_ooIlo0) ~= 0)
            _0x40E4F_ooIlo0 = _0x40E4F_ooIlo0 + 1
        elseif _0x72EC_1ll0ol1 == 2 then
            local _0x5BE1_lIlOloI
            _0x5BE1_lIlOloI, _0x40E4F_ooIlo0 = _nzl_read_double(_0xA85_lO1l, _0x40E4F_ooIlo0)
            _0x5A3B_1olI.constants[_0xA0D0_0Ol0] = _0x5BE1_lIlOloI
        elseif _0x72EC_1ll0ol1 == 3 then
            local _0xFBF6_ll01I
            _0xFBF6_ll01I, _0x40E4F_ooIlo0 = _nzl_read_u32(_0xA85_lO1l, _0x40E4F_ooIlo0)
            _0x5A3B_1olI.constants[_0xA0D0_0Ol0] = _0x4F7A_0IIIO(_0xA85_lO1l, _0x40E4F_ooIlo0, _0x40E4F_ooIlo0 + _0xFBF6_ll01I - 1)
            _0x40E4F_ooIlo0 = _0x40E4F_ooIlo0 + _0xFBF6_ll01I
        elseif _0x72EC_1ll0ol1 == 4 then
            local _0x5BE1_lIlOloI
            _0x5BE1_lIlOloI, _0x40E4F_ooIlo0 = _nzl_read_u32(_0xA85_lO1l, _0x40E4F_ooIlo0)
            _0x5A3B_1olI.constants[_0xA0D0_0Ol0] = {__proto_ref = _0x5BE1_lIlOloI}
        end
    end

    _0x41FB9_OO0l, _0x40E4F_ooIlo0 = _nzl_read_u32(_0xA85_lO1l, _0x40E4F_ooIlo0)
    _0x5A3B_1olI.code = {}
    for _0xA0D0_0Ol0 = 1, _0x41FB9_OO0l do
        local instr = {}
        instr.op = _0x9C38_oOO0lo(_0xA85_lO1l, _0x40E4F_ooIlo0)
        instr.a = _0x9C38_oOO0lo(_0xA85_lO1l, _0x40E4F_ooIlo0 + 1)
        instr.b = _0x9C38_oOO0lo(_0xA85_lO1l, _0x40E4F_ooIlo0 + 2)
        instr.c = _0x9C38_oOO0lo(_0xA85_lO1l, _0x40E4F_ooIlo0 + 3)
        instr.k, _ = _nzl_read_i32(_0xA85_lO1l, _0x40E4F_ooIlo0 + 4)
        _0x5A3B_1olI.code[_0xA0D0_0Ol0] = instr
        _0x40E4F_ooIlo0 = _0x40E4F_ooIlo0 + 8
    end

    _0xE2F8_I0Ol, _0x40E4F_ooIlo0 = _nzl_read_u32(_0xA85_lO1l, _0x40E4F_ooIlo0)
    _0x5A3B_1olI.protos = {}
    for _0xA0D0_0Ol0 = 1, _0xE2F8_I0Ol do
        _0x5A3B_1olI.protos[_0xA0D0_0Ol0], _0x40E4F_ooIlo0 = _0x252_olIo1ll(_0xA85_lO1l, _0x40E4F_ooIlo0)
    end

    return _0x5A3B_1olI, _0x40E4F_ooIlo0
end

local function _0xD729_011I0(_0x23E_O0loIoO0II, _0x8F2CB_O1oI, _0x6EFF9_IoOo)
    local _0xEDD29_IIlII0 = {}
    local _0x5596_IIOOl = _0x23E_O0loIoO0II.code
    local _0xEB1C_Ioo1olll = _0x23E_O0loIoO0II.constants
    local _0x8A90_IoII = getfenv and getfenv() or _G
    local _0xA4F2_IOOO = 1
    local _0x3113F_l1ll1I, _0x83FD_OIll0IOI, _0xBE49A_O01O, _0xD26DE_o0O0OI, _0x9312_lOII, _0x3FB07_0o1I0
    local _0xCAF6_010OIl1
    local _0x055_II11

    if _0x8F2CB_O1oI then
        for _0x055_II11 = 1, #_0x8F2CB_O1oI do
            _0xEDD29_IIlII0[_0x055_II11 - 1] = _0x8F2CB_O1oI[_0x055_II11]
        end
    end

    while true do
        _0x3113F_l1ll1I = _0x5596_IIOOl[_0xA4F2_IOOO]
        if not _0x3113F_l1ll1I then break end
        _0x83FD_OIll0IOI = _0x3113F_l1ll1I.op
        _0xBE49A_O01O = _0x3113F_l1ll1I.a
        _0xD26DE_o0O0OI = _0x3113F_l1ll1I.b
        _0x9312_lOII = _0x3113F_l1ll1I.c
        _0x3FB07_0o1I0 = _0x3113F_l1ll1I.k
        _0xA4F2_IOOO = _0xA4F2_IOOO + 1

        if _0x83FD_OIll0IOI == 248 then
            do
            _0xEDD29_IIlII0[_0xBE49A_O01O] = _0xEDD29_IIlII0[_0xD26DE_o0O0OI][_0xEDD29_IIlII0[_0x9312_lOII]]
            end
        elseif _0x83FD_OIll0IOI == 222 then
            do
            local _nzl_checksum = nil
            end
        elseif _0x83FD_OIll0IOI == 220 then
            do
            local _junk_220 = _0xEDD29_IIlII0[0]
            end
        elseif _0x83FD_OIll0IOI == 91 then
            do
            _0xEDD29_IIlII0[_0xBE49A_O01O] = _0x8A90_IoII[_0xEB1C_Ioo1olll[_0x3FB07_0o1I0 + 1]]
            end
        elseif _0x83FD_OIll0IOI == 215 then
            do
            local _args = {}
            for _i = 1, _0xD26DE_o0O0OI - 1 do _args[_i] = _0xEDD29_IIlII0[_0xBE49A_O01O + _i] end
            local _fn = _0xEDD29_IIlII0[_0xBE49A_O01O]
            local _rets = {_fn(_0x5E4_lI01(_args, 1, _0xD26DE_o0O0OI - 1))}
            local _need = _0x9312_lOII - 1
            if _need == -1 then _need = #_rets end
            for _i = 1, _need do _0xEDD29_IIlII0[_0xBE49A_O01O + _i - 1] = _rets[_i] end
            end
        elseif _0x83FD_OIll0IOI == 234 then
            do
            _0xEDD29_IIlII0[_0xBE49A_O01O] = _0xEDD29_IIlII0[_0xD26DE_o0O0OI] % _0xEDD29_IIlII0[_0x9312_lOII]
            end
        elseif _0x83FD_OIll0IOI == 132 then
            do
            _0xEDD29_IIlII0[_0xBE49A_O01O + 1] = _0xEDD29_IIlII0[_0xD26DE_o0O0OI]
            _0xEDD29_IIlII0[_0xBE49A_O01O] = _0xEDD29_IIlII0[_0xD26DE_o0O0OI][_0xEDD29_IIlII0[_0x9312_lOII]]
            end
        elseif _0x83FD_OIll0IOI == 11 then
            do
            _0xEDD29_IIlII0[_0xBE49A_O01O] = _0xEB1C_Ioo1olll[_0x3FB07_0o1I0 + 1]
            end
        elseif _0x83FD_OIll0IOI == 58 then
            do
            _0xEDD29_IIlII0[_0xBE49A_O01O] = (_0xEDD29_IIlII0[_0xD26DE_o0O0OI] == _0xEDD29_IIlII0[_0x9312_lOII])
            end
        elseif _0x83FD_OIll0IOI == 21 then
            do
            _0xEDD29_IIlII0[_0xBE49A_O01O] = not _0xEDD29_IIlII0[_0xD26DE_o0O0OI]
            end
        elseif _0x83FD_OIll0IOI == 129 then
            do
            _0xEDD29_IIlII0[_0xBE49A_O01O] = {}
            end
        elseif _0x83FD_OIll0IOI == 93 then
            do
            if _0xEDD29_IIlII0[_0xBE49A_O01O + 3] ~= nil then
                _0xEDD29_IIlII0[_0xBE49A_O01O + 2] = _0xEDD29_IIlII0[_0xBE49A_O01O + 3]
                _0xA4F2_IOOO = _0xA4F2_IOOO + _0x3FB07_0o1I0
            end
            end
        elseif _0x83FD_OIll0IOI == 127 then
            do
            _0xEDD29_IIlII0[_0xBE49A_O01O] = _0xEDD29_IIlII0[_0xD26DE_o0O0OI] - _0xEDD29_IIlII0[_0x9312_lOII]
            end
        elseif _0x83FD_OIll0IOI == 237 then
            do
            local _junk_237 = _0xEDD29_IIlII0[0]
            end
        elseif _0x83FD_OIll0IOI == 146 then
            do
            _0xEDD29_IIlII0[_0xBE49A_O01O] = _0xEDD29_IIlII0[_0xD26DE_o0O0OI] ^ _0xEDD29_IIlII0[_0x9312_lOII]
            end
        elseif _0x83FD_OIll0IOI == 161 then
            do
            _0xEDD29_IIlII0[_0xBE49A_O01O] = nil
            end
        elseif _0x83FD_OIll0IOI == 201 then
            do
            _0xEDD29_IIlII0[_0xBE49A_O01O] = _0xEDD29_IIlII0[_0xD26DE_o0O0OI] * _0xEDD29_IIlII0[_0x9312_lOII]
            end
        elseif _0x83FD_OIll0IOI == 167 then
            do
            if _0x6EFF9_IoOo and _0x6EFF9_IoOo[_0xD26DE_o0O0OI] then
                local _uv = _0x6EFF9_IoOo[_0xD26DE_o0O0OI]
                _uv[1][_uv[2]] = _0xEDD29_IIlII0[_0xBE49A_O01O]
            end
            end
        elseif _0x83FD_OIll0IOI == 125 then
            do
            if _0xD26DE_o0O0OI >= 128 then _0xEDD29_IIlII0[_0xBE49A_O01O] = _0xD26DE_o0O0OI - 256 else _0xEDD29_IIlII0[_0xBE49A_O01O] = _0xD26DE_o0O0OI end
            end
        elseif _0x83FD_OIll0IOI == 150 then
            do
            local _nzl_close = nil
            end
        elseif _0x83FD_OIll0IOI == 130 then
            do
            _0xEDD29_IIlII0[_0xBE49A_O01O] = _0xEDD29_IIlII0[_0xBE49A_O01O] - _0xEDD29_IIlII0[_0xBE49A_O01O + 2]
            _0xA4F2_IOOO = _0xA4F2_IOOO + _0x3FB07_0o1I0
            end
        elseif _0x83FD_OIll0IOI == 25 then
            do
            local _pref = _0xEB1C_Ioo1olll[_0x3FB07_0o1I0 + 1]
            if type(_pref) == "table" and _pref.__proto_ref then
                local _p = _0x23E_O0loIoO0II.protos[_pref.__proto_ref + 1]
                local _captured_R = _0xEDD29_IIlII0
                local _parent_upvals = _0x6EFF9_IoOo
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

                _0xEDD29_IIlII0[_0xBE49A_O01O] = function(...)
                    return _0xD729_011I0(_p, {...}, _child_upvals)
                end
            end
            end
        elseif _0x83FD_OIll0IOI == 238 then
            do
            _0xEDD29_IIlII0[_0xBE49A_O01O] = _0xEDD29_IIlII0[_0xD26DE_o0O0OI] + _0xEDD29_IIlII0[_0x9312_lOII]
            end
        elseif _0x83FD_OIll0IOI == 191 then
            do
            local _junk_191 = _0xEDD29_IIlII0[0]
            end
        elseif _0x83FD_OIll0IOI == 245 then
            do
            _0xEDD29_IIlII0[_0xBE49A_O01O] = (_0xEDD29_IIlII0[_0xD26DE_o0O0OI] >= _0xEDD29_IIlII0[_0x9312_lOII])
            end
        elseif _0x83FD_OIll0IOI == 62 then
            do
            local _rets = {_0xEDD29_IIlII0[_0xBE49A_O01O](_0xEDD29_IIlII0[_0xBE49A_O01O + 1], _0xEDD29_IIlII0[_0xBE49A_O01O + 2])}
            for _i = 1, _0xD26DE_o0O0OI do _0xEDD29_IIlII0[_0xBE49A_O01O + 2 + _i] = _rets[_i] end
            end
        elseif _0x83FD_OIll0IOI == 63 then
            do
            _0xA4F2_IOOO = _0xA4F2_IOOO + _0x3FB07_0o1I0
            end
        elseif _0x83FD_OIll0IOI == 251 then
            do
            _0x8A90_IoII[_0xEB1C_Ioo1olll[_0x3FB07_0o1I0 + 1]] = _0xEDD29_IIlII0[_0xBE49A_O01O]
            end
        elseif _0x83FD_OIll0IOI == 85 then
            do
            _0xEDD29_IIlII0[_0xBE49A_O01O] = _0xEDD29_IIlII0[_0xD26DE_o0O0OI] and _0xEDD29_IIlII0[_0x9312_lOII]
            end
        elseif _0x83FD_OIll0IOI == 57 then
            do
            _0xEDD29_IIlII0[_0xBE49A_O01O] = _0xEDD29_IIlII0[_0xD26DE_o0O0OI]
            end
        elseif _0x83FD_OIll0IOI == 83 then
            do
            _0xEDD29_IIlII0[_0xBE49A_O01O] = (_0xEDD29_IIlII0[_0xD26DE_o0O0OI] <= _0xEDD29_IIlII0[_0x9312_lOII])
            end
        elseif _0x83FD_OIll0IOI == 28 then
            do
            _0xEDD29_IIlII0[_0xBE49A_O01O] = _0xEDD29_IIlII0[_0xD26DE_o0O0OI][_0xEB1C_Ioo1olll[_0x3FB07_0o1I0 + 1]]
            end
        elseif _0x83FD_OIll0IOI == 211 then
            do
            _0xEDD29_IIlII0[_0xBE49A_O01O] = (_0xD26DE_o0O0OI ~= 0)
            end
        elseif _0x83FD_OIll0IOI == 143 then
            do
            for _0xCAF6_010OIl1i = _0xBE49A_O01O, _0xBE49A_O01O + _0xD26DE_o0O0OI do _0xEDD29_IIlII0[_0xCAF6_010OIl1i] = nil end
            end
        elseif _0x83FD_OIll0IOI == 226 then
            do
            local _args = {}
            for _i = 1, _0xD26DE_o0O0OI - 1 do _args[_i] = _0xEDD29_IIlII0[_0xBE49A_O01O + _i] end
            return _0xEDD29_IIlII0[_0xBE49A_O01O](_0x5E4_lI01(_args, 1, _0xD26DE_o0O0OI - 1))
            end
        elseif _0x83FD_OIll0IOI == 99 then
            do
            if _0xD26DE_o0O0OI == 0 then return end
            local _rets = {}
            for _i = 1, _0xD26DE_o0O0OI do _rets[_i] = _0xEDD29_IIlII0[_0xBE49A_O01O + _i - 1] end
            return _0x5E4_lI01(_rets, 1, _0xD26DE_o0O0OI)
            end
        elseif _0x83FD_OIll0IOI == 173 then
            do
            _0xEDD29_IIlII0[_0xBE49A_O01O] = -_0xEDD29_IIlII0[_0xD26DE_o0O0OI]
            end
        elseif _0x83FD_OIll0IOI == 115 then
            do
            _0xEDD29_IIlII0[_0xBE49A_O01O] = (_0xEDD29_IIlII0[_0xD26DE_o0O0OI] > _0xEDD29_IIlII0[_0x9312_lOII])
            end
        elseif _0x83FD_OIll0IOI == 17 then
            do
            _0xEDD29_IIlII0[_0xBE49A_O01O] = _0xEDD29_IIlII0[_0xBE49A_O01O] + _0xEDD29_IIlII0[_0xBE49A_O01O + 2]
            local _step = _0xEDD29_IIlII0[_0xBE49A_O01O + 2]
            local _cont
            if _step > 0 then _cont = (_0xEDD29_IIlII0[_0xBE49A_O01O] <= _0xEDD29_IIlII0[_0xBE49A_O01O + 1]) else _cont = (_0xEDD29_IIlII0[_0xBE49A_O01O] >= _0xEDD29_IIlII0[_0xBE49A_O01O + 1]) end
            if _cont then
                _0xEDD29_IIlII0[_0xBE49A_O01O + 3] = _0xEDD29_IIlII0[_0xBE49A_O01O]
                _0xA4F2_IOOO = _0xA4F2_IOOO + _0x3FB07_0o1I0
            end
            end
        elseif _0x83FD_OIll0IOI == 206 then
            do
            _0xEDD29_IIlII0[_0xBE49A_O01O][_0xEB1C_Ioo1olll[_0x3FB07_0o1I0 + 1]] = _0xEDD29_IIlII0[_0xD26DE_o0O0OI]
            end
        elseif _0x83FD_OIll0IOI == 158 then
            do
            _0xEDD29_IIlII0[_0xBE49A_O01O] = (_0xEDD29_IIlII0[_0xD26DE_o0O0OI] < _0xEDD29_IIlII0[_0x9312_lOII])
            end
        elseif _0x83FD_OIll0IOI == 193 then
            do
            _0xEDD29_IIlII0[_0xBE49A_O01O] = math.floor(_0xEDD29_IIlII0[_0xD26DE_o0O0OI] / _0xEDD29_IIlII0[_0x9312_lOII])
            end
        elseif _0x83FD_OIll0IOI == 67 then
            do
            local _junk_67 = _0xEDD29_IIlII0[0]
            end
        elseif _0x83FD_OIll0IOI == 105 then
            do
            _0xEDD29_IIlII0[_0xBE49A_O01O] = (_0xEDD29_IIlII0[_0xD26DE_o0O0OI] ~= _0xEDD29_IIlII0[_0x9312_lOII])
            end
        elseif _0x83FD_OIll0IOI == 41 then
            do
            _0xEDD29_IIlII0[_0xBE49A_O01O] = #_0xEDD29_IIlII0[_0xD26DE_o0O0OI]
            end
        elseif _0x83FD_OIll0IOI == 240 then
            do
            if _0xEDD29_IIlII0[_0xBE49A_O01O] then _0xA4F2_IOOO = _0xA4F2_IOOO + _0x3FB07_0o1I0 end
            end
        elseif _0x83FD_OIll0IOI == 53 then
            do
            _0xEDD29_IIlII0[_0xBE49A_O01O] = _0xEDD29_IIlII0[_0xD26DE_o0O0OI] / _0xEDD29_IIlII0[_0x9312_lOII]
            end
        elseif _0x83FD_OIll0IOI == 109 then
            do
            _0xEDD29_IIlII0[_0xBE49A_O01O][_0xEDD29_IIlII0[_0xD26DE_o0O0OI]] = _0xEDD29_IIlII0[_0x9312_lOII]
            end
        elseif _0x83FD_OIll0IOI == 10 then
            do
            for _0xCAF6_010OIl1i = 1, _0xD26DE_o0O0OI do _0xEDD29_IIlII0[_0xBE49A_O01O][_0x9312_lOII + _0xCAF6_010OIl1i] = _0xEDD29_IIlII0[_0xBE49A_O01O + _0xCAF6_010OIl1i] end
            end
        elseif _0x83FD_OIll0IOI == 2 then
            do
            _0xEDD29_IIlII0[_0xBE49A_O01O] = _0xEDD29_IIlII0[_0xD26DE_o0O0OI] or _0xEDD29_IIlII0[_0x9312_lOII]
            end
        elseif _0x83FD_OIll0IOI == 71 then
            do
            while true do end
            end
        elseif _0x83FD_OIll0IOI == 187 then
            do
            local _0xCAF6_010OIl1s = ""
            for _0xCAF6_010OIl1i = _0xD26DE_o0O0OI, _0x9312_lOII do _0xCAF6_010OIl1s = _0xCAF6_010OIl1s .. tostring(_0xEDD29_IIlII0[_0xCAF6_010OIl1i]) end
            _0xEDD29_IIlII0[_0xBE49A_O01O] = _0xCAF6_010OIl1s
            end
        elseif _0x83FD_OIll0IOI == 114 then
            do
            if not _0xEDD29_IIlII0[_0xBE49A_O01O] then _0xA4F2_IOOO = _0xA4F2_IOOO + _0x3FB07_0o1I0 end
            end
        elseif _0x83FD_OIll0IOI == 18 then
            do
            local _nzl_nop = nil
            end
        elseif _0x83FD_OIll0IOI == 100 then
            do
            local _junk_100 = _0xEDD29_IIlII0[0]
            end
        elseif _0x83FD_OIll0IOI == 121 then
            do
            if _0x6EFF9_IoOo and _0x6EFF9_IoOo[_0xD26DE_o0O0OI] then
                local _uv = _0x6EFF9_IoOo[_0xD26DE_o0O0OI]
                _0xEDD29_IIlII0[_0xBE49A_O01O] = _uv[1][_uv[2]]
            else
                _0xEDD29_IIlII0[_0xBE49A_O01O] = nil
            end
            end
                end
    end
end

local function _0xDF94D_Ol11(_0x1115C_O111, _0x7E50_OIol0)
    local _0xA1C_1oOO = _0x8A656_IOIl(_0x1115C_O111, _0x7E50_OIol0)
    local _0x6BC9_lloIl = _0x252_olIo1ll(_0xA1C_1oOO)
    return function(...)
        return _0xD729_011I0(_0x6BC9_lloIl, {...}, nil)
    end
end

-- VM-protected function
local vm_nested_function_factory = _0xDF94D_Ol11(
    "\156J\188\235\157\226o\159\053\191=zT\222\156!\163\010V%\016\029\149\176\165\010\177A\022\030\211\130\011\215\181\190\244)T\172\200`\010\205Y\203j\139\225E\029\009,\030y\246\241\190\242\255Tg[\137\213\173\226\159p\001\201B\132\027Za;\181\201\053\166\254\159N\018\137\128I\146\223\239\234\021\009I\027\165`\147\233\022J\193\051\170a\016\142\002\166\229\011\197\205\255|S&\012\016\011_!u[\210\200\231E\031\199\151\160\051R\026\155\016\214Le(\152\218S\206\003\052~TLR\159\242\014\191\008ba\143Np\233g*Qm\204`\000\007\182H\167Z\240y\127\171^Gg\235\129at\005\197E",
    "\014a\200\056<\218\057\031J\248\230B\031\198H\203"
)

local vm_nested_function = vm_nested_function_factory()

print("[nested_function] =", vm_nested_function())

-- NZL VM Runtime (build 0000006c)
local _0x75DDA_lOOl1ol = string.byte
local _0x45A1_OOoIIo = string.sub
local _0xE35CC_lIIOo = string.char
local _0x9BC4_OIOl = table.insert
local _0x2E379_0lIO = table.unpack or unpack
local _0x1B9_o1I0OO = bit32.bxor

local function _0xA6362_O0lO(_0x3A5E_lOOI0OlOI, _0x14CCF_lI1O)
    local _0x686F_lIoIIO = {}
    for _0xDB8A_1l0O0oOl = 0, 255 do _0x686F_lIoIIO[_0xDB8A_1l0O0oOl] = _0xDB8A_1l0O0oOl end
    local _0xAEF_11IIo = 0
    local _0x9BA_oIOI = #_0x14CCF_lI1O
    for _0xDB8A_1l0O0oOl = 0, 255 do
        _0xAEF_11IIo = (_0xAEF_11IIo + _0x686F_lIoIIO[_0xDB8A_1l0O0oOl] + _0x75DDA_lOOl1ol(_0x14CCF_lI1O, (_0xDB8A_1l0O0oOl % _0x9BA_oIOI) + 1)) % 256
        _0x686F_lIoIIO[_0xDB8A_1l0O0oOl], _0x686F_lIoIIO[_0xAEF_11IIo] = _0x686F_lIoIIO[_0xAEF_11IIo], _0x686F_lIoIIO[_0xDB8A_1l0O0oOl]
    end
    local _0x3A8_OOIO = {}
    local _0xDB8A_1l0O0oOl2 = 0
    local _0xAEF_11IIo2 = 0
    for _0x95D_o1IlOI1IO = 1, #_0x3A5E_lOOI0OlOI do
        _0xDB8A_1l0O0oOl2 = (_0xDB8A_1l0O0oOl2 + 1) % 256
        _0xAEF_11IIo2 = (_0xAEF_11IIo2 + _0x686F_lIoIIO[_0xDB8A_1l0O0oOl2]) % 256
        _0x686F_lIoIIO[_0xDB8A_1l0O0oOl2], _0x686F_lIoIIO[_0xAEF_11IIo2] = _0x686F_lIoIIO[_0xAEF_11IIo2], _0x686F_lIoIIO[_0xDB8A_1l0O0oOl2]
        local _0x40813_IIlO = _0x686F_lIoIIO[(_0x686F_lIoIIO[_0xDB8A_1l0O0oOl2] + _0x686F_lIoIIO[_0xAEF_11IIo2]) % 256]
        _0x3A8_OOIO[_0x95D_o1IlOI1IO] = _0xE35CC_lIIOo(_0x1B9_o1I0OO(_0x75DDA_lOOl1ol(_0x3A5E_lOOI0OlOI, _0x95D_o1IlOI1IO), _0x40813_IIlO))
    end
    return table.concat(_0x3A8_OOIO)
end

local function _nzl_read_u32(_0x5F1B_O1IO, _0x3C1_oOl1)
    local _0xC41_oIl0l = _0x75DDA_lOOl1ol(_0x5F1B_O1IO, _0x3C1_oOl1)
    local _0x504_OIIOIl1I0 = _0x75DDA_lOOl1ol(_0x5F1B_O1IO, _0x3C1_oOl1 + 1)
    local _0x443A_llO0I0 = _0x75DDA_lOOl1ol(_0x5F1B_O1IO, _0x3C1_oOl1 + 2)
    local _0x8930F_III1I0O = _0x75DDA_lOOl1ol(_0x5F1B_O1IO, _0x3C1_oOl1 + 3)
    return _0xC41_oIl0l + _0x504_OIIOIl1I0 * 256 + _0x443A_llO0I0 * 65536 + _0x8930F_III1I0O * 16777216, _0x3C1_oOl1 + 4
end

local function _nzl_read_i32(_0x5F1B_O1IO, _0x3C1_oOl1)
    local _0x6DDC_oOoO1oo1O, _0x3C1_oOl1 = _nzl_read_u32(_0x5F1B_O1IO, _0x3C1_oOl1)
    if _0x6DDC_oOoO1oo1O >= 2147483648 then _0x6DDC_oOoO1oo1O = _0x6DDC_oOoO1oo1O - 4294967296 end
    return _0x6DDC_oOoO1oo1O, _0x3C1_oOl1
end

local function _nzl_read_double(_0x5F1B_O1IO, _0x3C1_oOl1)
    local _0xC41_oIl0l = _0x75DDA_lOOl1ol(_0x5F1B_O1IO, _0x3C1_oOl1)
    local _0x504_OIIOIl1I0 = _0x75DDA_lOOl1ol(_0x5F1B_O1IO, _0x3C1_oOl1 + 1)
    local _0x443A_llO0I0 = _0x75DDA_lOOl1ol(_0x5F1B_O1IO, _0x3C1_oOl1 + 2)
    local _0x8930F_III1I0O = _0x75DDA_lOOl1ol(_0x5F1B_O1IO, _0x3C1_oOl1 + 3)
    local b4 = _0x75DDA_lOOl1ol(_0x5F1B_O1IO, _0x3C1_oOl1 + 4)
    local b5 = _0x75DDA_lOOl1ol(_0x5F1B_O1IO, _0x3C1_oOl1 + 5)
    local b6 = _0x75DDA_lOOl1ol(_0x5F1B_O1IO, _0x3C1_oOl1 + 6)
    local b7 = _0x75DDA_lOOl1ol(_0x5F1B_O1IO, _0x3C1_oOl1 + 7)
    local sign = 1
    if b7 >= 128 then sign = -1; b7 = b7 - 128 end
    local exp = b7 * 16 + math.floor(b6 / 16)
    local mant = (b6 % 16) * 281474976710656 + b5 * 1099511627776 + b4 * 4294967296
        + _0x8930F_III1I0O * 16777216 + _0x443A_llO0I0 * 65536 + _0x504_OIIOIl1I0 * 256 + _0xC41_oIl0l
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
    return val, _0x3C1_oOl1 + 8
end

local function _0xC61E1_OOllO(_0x5F1B_O1IO, _0x3C1_oOl1)
    _0x3C1_oOl1 = _0x3C1_oOl1 or 1
    local _0xA59_O1IOo = {}

    _0xA59_O1IOo.num_params, _0x3C1_oOl1 = _nzl_read_u32(_0x5F1B_O1IO, _0x3C1_oOl1)
    _0xA59_O1IOo.is_vararg = _0x75DDA_lOOl1ol(_0x5F1B_O1IO, _0x3C1_oOl1) ~= 0
    _0x3C1_oOl1 = _0x3C1_oOl1 + 1
    _0xA59_O1IOo.max_stack, _0x3C1_oOl1 = _nzl_read_u32(_0x5F1B_O1IO, _0x3C1_oOl1)

    _0x2710C_oIIO, _0x3C1_oOl1 = _nzl_read_u32(_0x5F1B_O1IO, _0x3C1_oOl1)
    _0xA59_O1IOo.upvalues = {}
    for _0x423_lolI1l1Olo = 1, _0x2710C_oIIO do
        local _0xC2CF_OooO = _0x75DDA_lOOl1ol(_0x5F1B_O1IO, _0x3C1_oOl1) ~= 0
        _0x3C1_oOl1 = _0x3C1_oOl1 + 1
        local _0x2AE_oIll
        _0x2AE_oIll, _0x3C1_oOl1 = _nzl_read_u32(_0x5F1B_O1IO, _0x3C1_oOl1)
        _0xA59_O1IOo.upvalues[_0x423_lolI1l1Olo] = {instack = _0xC2CF_OooO, index = _0x2AE_oIll}
    end

    _0x625B_110O0IoO, _0x3C1_oOl1 = _nzl_read_u32(_0x5F1B_O1IO, _0x3C1_oOl1)
    _0xA59_O1IOo.constants = {}
    for _0x423_lolI1l1Olo = 1, _0x625B_110O0IoO do
        local _0xCD1_OOIo00 = _0x75DDA_lOOl1ol(_0x5F1B_O1IO, _0x3C1_oOl1)
        _0x3C1_oOl1 = _0x3C1_oOl1 + 1
        if _0xCD1_OOIo00 == 0 then
            _0xA59_O1IOo.constants[_0x423_lolI1l1Olo] = nil
        elseif _0xCD1_OOIo00 == 1 then
            _0xA59_O1IOo.constants[_0x423_lolI1l1Olo] = (_0x75DDA_lOOl1ol(_0x5F1B_O1IO, _0x3C1_oOl1) ~= 0)
            _0x3C1_oOl1 = _0x3C1_oOl1 + 1
        elseif _0xCD1_OOIo00 == 2 then
            local _0xCEE_OIo0II
            _0xCEE_OIo0II, _0x3C1_oOl1 = _nzl_read_double(_0x5F1B_O1IO, _0x3C1_oOl1)
            _0xA59_O1IOo.constants[_0x423_lolI1l1Olo] = _0xCEE_OIo0II
        elseif _0xCD1_OOIo00 == 3 then
            local _0xC3E_IIIIo1
            _0xC3E_IIIIo1, _0x3C1_oOl1 = _nzl_read_u32(_0x5F1B_O1IO, _0x3C1_oOl1)
            _0xA59_O1IOo.constants[_0x423_lolI1l1Olo] = _0x45A1_OOoIIo(_0x5F1B_O1IO, _0x3C1_oOl1, _0x3C1_oOl1 + _0xC3E_IIIIo1 - 1)
            _0x3C1_oOl1 = _0x3C1_oOl1 + _0xC3E_IIIIo1
        elseif _0xCD1_OOIo00 == 4 then
            local _0xCEE_OIo0II
            _0xCEE_OIo0II, _0x3C1_oOl1 = _nzl_read_u32(_0x5F1B_O1IO, _0x3C1_oOl1)
            _0xA59_O1IOo.constants[_0x423_lolI1l1Olo] = {__proto_ref = _0xCEE_OIo0II}
        end
    end

    _0x17C6_oolIo0O, _0x3C1_oOl1 = _nzl_read_u32(_0x5F1B_O1IO, _0x3C1_oOl1)
    _0xA59_O1IOo.code = {}
    for _0x423_lolI1l1Olo = 1, _0x17C6_oolIo0O do
        local instr = {}
        instr.op = _0x75DDA_lOOl1ol(_0x5F1B_O1IO, _0x3C1_oOl1)
        instr.a = _0x75DDA_lOOl1ol(_0x5F1B_O1IO, _0x3C1_oOl1 + 1)
        instr.b = _0x75DDA_lOOl1ol(_0x5F1B_O1IO, _0x3C1_oOl1 + 2)
        instr.c = _0x75DDA_lOOl1ol(_0x5F1B_O1IO, _0x3C1_oOl1 + 3)
        instr.k, _ = _nzl_read_i32(_0x5F1B_O1IO, _0x3C1_oOl1 + 4)
        _0xA59_O1IOo.code[_0x423_lolI1l1Olo] = instr
        _0x3C1_oOl1 = _0x3C1_oOl1 + 8
    end

    _0xD408_IOllI, _0x3C1_oOl1 = _nzl_read_u32(_0x5F1B_O1IO, _0x3C1_oOl1)
    _0xA59_O1IOo.protos = {}
    for _0x423_lolI1l1Olo = 1, _0xD408_IOllI do
        _0xA59_O1IOo.protos[_0x423_lolI1l1Olo], _0x3C1_oOl1 = _0xC61E1_OOllO(_0x5F1B_O1IO, _0x3C1_oOl1)
    end

    return _0xA59_O1IOo, _0x3C1_oOl1
end

local function _0x02F_l0IOloIOI(_0xBF32_IOOo, _0xDF4_II1l1, _0xC5AE2_llOo1OIl)
    local _0xC1CE5_IIlO = {}
    local _0xBC4_100oO = _0xBF32_IOOo.code
    local _0xCBB5_Oo0o = _0xBF32_IOOo.constants
    local _0xF62_00OO = getfenv and getfenv() or _G
    local _0x70A2_10lo = 1
    local _0x7E1_1ol1Il01, _0x8150_IOIII00, _0xFC5A9_OlI1llO, _0xF892_0lIO0OIOl, _0x4DFC3_o1o1I0O, _0x32070_OlO0llI
    local _0xA7E2_l1lI
    local _0x9206_11lI

    if _0xDF4_II1l1 then
        for _0x9206_11lI = 1, #_0xDF4_II1l1 do
            _0xC1CE5_IIlO[_0x9206_11lI - 1] = _0xDF4_II1l1[_0x9206_11lI]
        end
    end

    while true do
        _0x7E1_1ol1Il01 = _0xBC4_100oO[_0x70A2_10lo]
        if not _0x7E1_1ol1Il01 then break end
        _0x8150_IOIII00 = _0x7E1_1ol1Il01.op
        _0xFC5A9_OlI1llO = _0x7E1_1ol1Il01.a
        _0xF892_0lIO0OIOl = _0x7E1_1ol1Il01.b
        _0x4DFC3_o1o1I0O = _0x7E1_1ol1Il01.c
        _0x32070_OlO0llI = _0x7E1_1ol1Il01.k
        _0x70A2_10lo = _0x70A2_10lo + 1

        if _0x8150_IOIII00 == 94 then
            do
            local _rets = {_0xC1CE5_IIlO[_0xFC5A9_OlI1llO](_0xC1CE5_IIlO[_0xFC5A9_OlI1llO + 1], _0xC1CE5_IIlO[_0xFC5A9_OlI1llO + 2])}
            for _i = 1, _0xF892_0lIO0OIOl do _0xC1CE5_IIlO[_0xFC5A9_OlI1llO + 2 + _i] = _rets[_i] end
            end
        elseif _0x8150_IOIII00 == 60 then
            do
            _0xC1CE5_IIlO[_0xFC5A9_OlI1llO] = not _0xC1CE5_IIlO[_0xF892_0lIO0OIOl]
            end
        elseif _0x8150_IOIII00 == 228 then
            do
            _0xC1CE5_IIlO[_0xFC5A9_OlI1llO] = (_0xC1CE5_IIlO[_0xF892_0lIO0OIOl] >= _0xC1CE5_IIlO[_0x4DFC3_o1o1I0O])
            end
        elseif _0x8150_IOIII00 == 2 then
            do
            _0xC1CE5_IIlO[_0xFC5A9_OlI1llO] = math.floor(_0xC1CE5_IIlO[_0xF892_0lIO0OIOl] / _0xC1CE5_IIlO[_0x4DFC3_o1o1I0O])
            end
        elseif _0x8150_IOIII00 == 89 then
            do
            _0xC1CE5_IIlO[_0xFC5A9_OlI1llO] = (_0xC1CE5_IIlO[_0xF892_0lIO0OIOl] == _0xC1CE5_IIlO[_0x4DFC3_o1o1I0O])
            end
        elseif _0x8150_IOIII00 == 24 then
            do
            _0xC1CE5_IIlO[_0xFC5A9_OlI1llO] = _0xC1CE5_IIlO[_0xF892_0lIO0OIOl][_0xCBB5_Oo0o[_0x32070_OlO0llI + 1]]
            end
        elseif _0x8150_IOIII00 == 102 then
            do
            _0xC1CE5_IIlO[_0xFC5A9_OlI1llO] = (_0xC1CE5_IIlO[_0xF892_0lIO0OIOl] <= _0xC1CE5_IIlO[_0x4DFC3_o1o1I0O])
            end
        elseif _0x8150_IOIII00 == 108 then
            do
            _0xC1CE5_IIlO[_0xFC5A9_OlI1llO][_0xCBB5_Oo0o[_0x32070_OlO0llI + 1]] = _0xC1CE5_IIlO[_0xF892_0lIO0OIOl]
            end
        elseif _0x8150_IOIII00 == 9 then
            do
            _0xC1CE5_IIlO[_0xFC5A9_OlI1llO] = _0xC1CE5_IIlO[_0xF892_0lIO0OIOl][_0xC1CE5_IIlO[_0x4DFC3_o1o1I0O]]
            end
        elseif _0x8150_IOIII00 == 17 then
            do
            if _0xC5AE2_llOo1OIl and _0xC5AE2_llOo1OIl[_0xF892_0lIO0OIOl] then
                local _uv = _0xC5AE2_llOo1OIl[_0xF892_0lIO0OIOl]
                _uv[1][_uv[2]] = _0xC1CE5_IIlO[_0xFC5A9_OlI1llO]
            end
            end
        elseif _0x8150_IOIII00 == 55 then
            do
            local _junk_55 = _0xC1CE5_IIlO[0]
            end
        elseif _0x8150_IOIII00 == 40 then
            do
            _0xC1CE5_IIlO[_0xFC5A9_OlI1llO][_0xC1CE5_IIlO[_0xF892_0lIO0OIOl]] = _0xC1CE5_IIlO[_0x4DFC3_o1o1I0O]
            end
        elseif _0x8150_IOIII00 == 72 then
            do
            local _junk_72 = _0xC1CE5_IIlO[0]
            end
        elseif _0x8150_IOIII00 == 190 then
            do
            _0xC1CE5_IIlO[_0xFC5A9_OlI1llO] = (_0xF892_0lIO0OIOl ~= 0)
            end
        elseif _0x8150_IOIII00 == 99 then
            do
            local _args = {}
            for _i = 1, _0xF892_0lIO0OIOl - 1 do _args[_i] = _0xC1CE5_IIlO[_0xFC5A9_OlI1llO + _i] end
            return _0xC1CE5_IIlO[_0xFC5A9_OlI1llO](_0x2E379_0lIO(_args, 1, _0xF892_0lIO0OIOl - 1))
            end
        elseif _0x8150_IOIII00 == 51 then
            do
            _0xC1CE5_IIlO[_0xFC5A9_OlI1llO + 1] = _0xC1CE5_IIlO[_0xF892_0lIO0OIOl]
            _0xC1CE5_IIlO[_0xFC5A9_OlI1llO] = _0xC1CE5_IIlO[_0xF892_0lIO0OIOl][_0xC1CE5_IIlO[_0x4DFC3_o1o1I0O]]
            end
        elseif _0x8150_IOIII00 == 182 then
            do
            if _0xC5AE2_llOo1OIl and _0xC5AE2_llOo1OIl[_0xF892_0lIO0OIOl] then
                local _uv = _0xC5AE2_llOo1OIl[_0xF892_0lIO0OIOl]
                _0xC1CE5_IIlO[_0xFC5A9_OlI1llO] = _uv[1][_uv[2]]
            else
                _0xC1CE5_IIlO[_0xFC5A9_OlI1llO] = nil
            end
            end
        elseif _0x8150_IOIII00 == 195 then
            do
            _0xC1CE5_IIlO[_0xFC5A9_OlI1llO] = _0xCBB5_Oo0o[_0x32070_OlO0llI + 1]
            end
        elseif _0x8150_IOIII00 == 134 then
            do
            if _0xF892_0lIO0OIOl >= 128 then _0xC1CE5_IIlO[_0xFC5A9_OlI1llO] = _0xF892_0lIO0OIOl - 256 else _0xC1CE5_IIlO[_0xFC5A9_OlI1llO] = _0xF892_0lIO0OIOl end
            end
        elseif _0x8150_IOIII00 == 80 then
            do
            _0xC1CE5_IIlO[_0xFC5A9_OlI1llO] = (_0xC1CE5_IIlO[_0xF892_0lIO0OIOl] ~= _0xC1CE5_IIlO[_0x4DFC3_o1o1I0O])
            end
        elseif _0x8150_IOIII00 == 214 then
            do
            if not _0xC1CE5_IIlO[_0xFC5A9_OlI1llO] then _0x70A2_10lo = _0x70A2_10lo + _0x32070_OlO0llI end
            end
        elseif _0x8150_IOIII00 == 189 then
            do
            _0xC1CE5_IIlO[_0xFC5A9_OlI1llO] = _0xC1CE5_IIlO[_0xF892_0lIO0OIOl] - _0xC1CE5_IIlO[_0x4DFC3_o1o1I0O]
            end
        elseif _0x8150_IOIII00 == 1 then
            do
            for _0xA7E2_l1lIi = 1, _0xF892_0lIO0OIOl do _0xC1CE5_IIlO[_0xFC5A9_OlI1llO][_0x4DFC3_o1o1I0O + _0xA7E2_l1lIi] = _0xC1CE5_IIlO[_0xFC5A9_OlI1llO + _0xA7E2_l1lIi] end
            end
        elseif _0x8150_IOIII00 == 130 then
            do
            _0xC1CE5_IIlO[_0xFC5A9_OlI1llO] = _0xC1CE5_IIlO[_0xF892_0lIO0OIOl]
            end
        elseif _0x8150_IOIII00 == 4 then
            do
            while true do end
            end
        elseif _0x8150_IOIII00 == 210 then
            do
            local _args = {}
            for _i = 1, _0xF892_0lIO0OIOl - 1 do _args[_i] = _0xC1CE5_IIlO[_0xFC5A9_OlI1llO + _i] end
            local _fn = _0xC1CE5_IIlO[_0xFC5A9_OlI1llO]
            local _rets = {_fn(_0x2E379_0lIO(_args, 1, _0xF892_0lIO0OIOl - 1))}
            local _need = _0x4DFC3_o1o1I0O - 1
            if _need == -1 then _need = #_rets end
            for _i = 1, _need do _0xC1CE5_IIlO[_0xFC5A9_OlI1llO + _i - 1] = _rets[_i] end
            end
        elseif _0x8150_IOIII00 == 25 then
            do
            _0xC1CE5_IIlO[_0xFC5A9_OlI1llO] = _0xC1CE5_IIlO[_0xF892_0lIO0OIOl] * _0xC1CE5_IIlO[_0x4DFC3_o1o1I0O]
            end
        elseif _0x8150_IOIII00 == 241 then
            do
            local _0xA7E2_l1lIs = ""
            for _0xA7E2_l1lIi = _0xF892_0lIO0OIOl, _0x4DFC3_o1o1I0O do _0xA7E2_l1lIs = _0xA7E2_l1lIs .. tostring(_0xC1CE5_IIlO[_0xA7E2_l1lIi]) end
            _0xC1CE5_IIlO[_0xFC5A9_OlI1llO] = _0xA7E2_l1lIs
            end
        elseif _0x8150_IOIII00 == 97 then
            do
            local _nzl_checksum = nil
            end
        elseif _0x8150_IOIII00 == 198 then
            do
            _0xC1CE5_IIlO[_0xFC5A9_OlI1llO] = _0xF62_00OO[_0xCBB5_Oo0o[_0x32070_OlO0llI + 1]]
            end
        elseif _0x8150_IOIII00 == 12 then
            do
            _0xC1CE5_IIlO[_0xFC5A9_OlI1llO] = -_0xC1CE5_IIlO[_0xF892_0lIO0OIOl]
            end
        elseif _0x8150_IOIII00 == 199 then
            do
            local _pref = _0xCBB5_Oo0o[_0x32070_OlO0llI + 1]
            if type(_pref) == "table" and _pref.__proto_ref then
                local _p = _0xBF32_IOOo.protos[_pref.__proto_ref + 1]
                local _captured_R = _0xC1CE5_IIlO
                local _parent_upvals = _0xC5AE2_llOo1OIl
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

                _0xC1CE5_IIlO[_0xFC5A9_OlI1llO] = function(...)
                    return _0x02F_l0IOloIOI(_p, {...}, _child_upvals)
                end
            end
            end
        elseif _0x8150_IOIII00 == 127 then
            do
            _0xC1CE5_IIlO[_0xFC5A9_OlI1llO] = _0xC1CE5_IIlO[_0xF892_0lIO0OIOl] and _0xC1CE5_IIlO[_0x4DFC3_o1o1I0O]
            end
        elseif _0x8150_IOIII00 == 255 then
            do
            if _0xF892_0lIO0OIOl == 0 then return end
            local _rets = {}
            for _i = 1, _0xF892_0lIO0OIOl do _rets[_i] = _0xC1CE5_IIlO[_0xFC5A9_OlI1llO + _i - 1] end
            return _0x2E379_0lIO(_rets, 1, _0xF892_0lIO0OIOl)
            end
        elseif _0x8150_IOIII00 == 249 then
            do
            _0xC1CE5_IIlO[_0xFC5A9_OlI1llO] = nil
            end
        elseif _0x8150_IOIII00 == 188 then
            do
            _0xC1CE5_IIlO[_0xFC5A9_OlI1llO] = (_0xC1CE5_IIlO[_0xF892_0lIO0OIOl] > _0xC1CE5_IIlO[_0x4DFC3_o1o1I0O])
            end
        elseif _0x8150_IOIII00 == 79 then
            do
            _0xC1CE5_IIlO[_0xFC5A9_OlI1llO] = #_0xC1CE5_IIlO[_0xF892_0lIO0OIOl]
            end
        elseif _0x8150_IOIII00 == 205 then
            do
            _0xC1CE5_IIlO[_0xFC5A9_OlI1llO] = _0xC1CE5_IIlO[_0xF892_0lIO0OIOl] / _0xC1CE5_IIlO[_0x4DFC3_o1o1I0O]
            end
        elseif _0x8150_IOIII00 == 242 then
            do
            local _nzl_nop = nil
            end
        elseif _0x8150_IOIII00 == 61 then
            do
            if _0xC1CE5_IIlO[_0xFC5A9_OlI1llO] then _0x70A2_10lo = _0x70A2_10lo + _0x32070_OlO0llI end
            end
        elseif _0x8150_IOIII00 == 155 then
            do
            _0xC1CE5_IIlO[_0xFC5A9_OlI1llO] = {}
            end
        elseif _0x8150_IOIII00 == 5 then
            do
            _0x70A2_10lo = _0x70A2_10lo + _0x32070_OlO0llI
            end
        elseif _0x8150_IOIII00 == 217 then
            do
            _0xC1CE5_IIlO[_0xFC5A9_OlI1llO] = _0xC1CE5_IIlO[_0xFC5A9_OlI1llO] + _0xC1CE5_IIlO[_0xFC5A9_OlI1llO + 2]
            local _step = _0xC1CE5_IIlO[_0xFC5A9_OlI1llO + 2]
            local _cont
            if _step > 0 then _cont = (_0xC1CE5_IIlO[_0xFC5A9_OlI1llO] <= _0xC1CE5_IIlO[_0xFC5A9_OlI1llO + 1]) else _cont = (_0xC1CE5_IIlO[_0xFC5A9_OlI1llO] >= _0xC1CE5_IIlO[_0xFC5A9_OlI1llO + 1]) end
            if _cont then
                _0xC1CE5_IIlO[_0xFC5A9_OlI1llO + 3] = _0xC1CE5_IIlO[_0xFC5A9_OlI1llO]
                _0x70A2_10lo = _0x70A2_10lo + _0x32070_OlO0llI
            end
            end
        elseif _0x8150_IOIII00 == 31 then
            do
            local _junk_31 = _0xC1CE5_IIlO[0]
            end
        elseif _0x8150_IOIII00 == 122 then
            do
            _0xC1CE5_IIlO[_0xFC5A9_OlI1llO] = _0xC1CE5_IIlO[_0xF892_0lIO0OIOl] + _0xC1CE5_IIlO[_0x4DFC3_o1o1I0O]
            end
        elseif _0x8150_IOIII00 == 37 then
            do
            _0xC1CE5_IIlO[_0xFC5A9_OlI1llO] = (_0xC1CE5_IIlO[_0xF892_0lIO0OIOl] < _0xC1CE5_IIlO[_0x4DFC3_o1o1I0O])
            end
        elseif _0x8150_IOIII00 == 246 then
            do
            _0xC1CE5_IIlO[_0xFC5A9_OlI1llO] = _0xC1CE5_IIlO[_0xF892_0lIO0OIOl] ^ _0xC1CE5_IIlO[_0x4DFC3_o1o1I0O]
            end
        elseif _0x8150_IOIII00 == 204 then
            do
            if _0xC1CE5_IIlO[_0xFC5A9_OlI1llO + 3] ~= nil then
                _0xC1CE5_IIlO[_0xFC5A9_OlI1llO + 2] = _0xC1CE5_IIlO[_0xFC5A9_OlI1llO + 3]
                _0x70A2_10lo = _0x70A2_10lo + _0x32070_OlO0llI
            end
            end
        elseif _0x8150_IOIII00 == 23 then
            do
            for _0xA7E2_l1lIi = _0xFC5A9_OlI1llO, _0xFC5A9_OlI1llO + _0xF892_0lIO0OIOl do _0xC1CE5_IIlO[_0xA7E2_l1lIi] = nil end
            end
        elseif _0x8150_IOIII00 == 32 then
            do
            _0xF62_00OO[_0xCBB5_Oo0o[_0x32070_OlO0llI + 1]] = _0xC1CE5_IIlO[_0xFC5A9_OlI1llO]
            end
        elseif _0x8150_IOIII00 == 100 then
            do
            local _nzl_close = nil
            end
        elseif _0x8150_IOIII00 == 194 then
            do
            _0xC1CE5_IIlO[_0xFC5A9_OlI1llO] = _0xC1CE5_IIlO[_0xF892_0lIO0OIOl] % _0xC1CE5_IIlO[_0x4DFC3_o1o1I0O]
            end
        elseif _0x8150_IOIII00 == 105 then
            do
            _0xC1CE5_IIlO[_0xFC5A9_OlI1llO] = _0xC1CE5_IIlO[_0xFC5A9_OlI1llO] - _0xC1CE5_IIlO[_0xFC5A9_OlI1llO + 2]
            _0x70A2_10lo = _0x70A2_10lo + _0x32070_OlO0llI
            end
        elseif _0x8150_IOIII00 == 121 then
            do
            _0xC1CE5_IIlO[_0xFC5A9_OlI1llO] = _0xC1CE5_IIlO[_0xF892_0lIO0OIOl] or _0xC1CE5_IIlO[_0x4DFC3_o1o1I0O]
            end
                end
    end
end

local function _0x2C8C6_l1lI(_0xE10F_lI0OOl, _0xC43BC_0IIlI)
    local _0x7EA67_IlOO = _0xA6362_O0lO(_0xE10F_lI0OOl, _0xC43BC_0IIlI)
    local _0xC24_oIIl1 = _0xC61E1_OOllO(_0x7EA67_IlOO)
    return function(...)
        return _0x02F_l0IOloIOI(_0xC24_oIIl1, {...}, nil)
    end
end

-- VM-protected function
local vm_recursion_factory = _0x2C8C6_l1lI(
    "\030k\196\000\158\207\164\146?\224l\164\057\253\029\130\049\215\253W\202\221\171\242d\199\248\029p\022;\013\026\242\242b\220\144\025S\198E-zFT\153z\238\011\194\204\005\175\196<\023D\249\245\146\133H\157c\245m\217\023M\173\163\210\178\206\159\000\229\148\159\214f^\219V\234\\\198\051;p\236\009\240\168&\130\187\156\147\027\222>\165\231\015\223\207K\175\231\185!fNf\182g<\250K:\201\154\199\193\236\242\021\156\247\210\219\139/^4m\254\196!\166{\137\209\014\220(\006>\246\054\254\134I@w\180z8\214\024\164\239\214\128\241\219\133\221\128\019||\031\209\133\156\241\235\\\021\167)\165\170\134\010\141\054\227@\215\165[p\134\130\212$.\240\055x",
    '\003m"\230\134~\145[\179\011\159T\003>\197A'
)

local vm_recursion = vm_recursion_factory()

print("[recursion] =", vm_recursion(5))

print("=== ALL VM TESTS COMPLETE ===")