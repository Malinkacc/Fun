local function ____8_0__(l1II0O1IlOll0lO, _0xE3C_lO1Oll, Illl01oOIOO)
    if Illl01oOIOO == 1 then
        local _II0l00o = {}
        for _O01llOlo0o = 0, 255 do _II0l00o[_O01llOlo0o] = _O01llOlo0o end
        local _lOO100OlIOo = 0
        for _O01llOlo0o = 0, 255 do
            _lOO100OlIOo = (_lOO100OlIOo + _II0l00o[_O01llOlo0o] + string.byte(_0xE3C_lO1Oll, (_O01llOlo0o % #_0xE3C_lO1Oll) + 1)) % 256
            _II0l00o[_O01llOlo0o], _II0l00o[_lOO100OlIOo] = _II0l00o[_lOO100OlIOo], _II0l00o[_O01llOlo0o]
        end
        local llIOlIo01OlO = {}
        _O01llOlo0o = 0
        _lOO100OlIOo = 0
        for _0185_7_4214 = 1, #l1II0O1IlOll0lO do
            _O01llOlo0o = (_O01llOlo0o + 1) % 256
            _lOO100OlIOo = (_lOO100OlIOo + _II0l00o[_O01llOlo0o]) % 256
            _II0l00o[_O01llOlo0o], _II0l00o[_lOO100OlIOo] = _II0l00o[_lOO100OlIOo], _II0l00o[_O01llOlo0o]
            local k = _II0l00o[(_II0l00o[_O01llOlo0o] + _II0l00o[_lOO100OlIOo]) % 256]
            llIOlIo01OlO[_0185_7_4214] = string.char(bit32.bxor(string.byte(l1II0O1IlOll0lO, _0185_7_4214), k))
        end
        return table.concat(llIOlIo01OlO)
    elseif Illl01oOIOO == 3 then
        local __5__393 = {}
        local _0x33D_O00oIlI0 = string.byte(_0xE3C_lO1Oll, 1)
        local _1__6_18_813_ = string.byte(_0xE3C_lO1Oll, 2)
        local _2__89__4__1_182 = _0x33D_O00oIlI0
        for _O01llOlo0o = 1, #l1II0O1IlOll0lO do
            __5__393[_O01llOlo0o] = string.char(bit32.bxor(string.byte(l1II0O1IlOll0lO, _O01llOlo0o), _2__89__4__1_182))
            _2__89__4__1_182 = (_2__89__4__1_182 + _1__6_18_813_) % 256
        end
        return table.concat(__5__393)
    elseif Illl01oOIOO == 2 then
        local __5__393 = {}
        local _2_6836583__30_ = #_0xE3C_lO1Oll
        for _O01llOlo0o = 1, #l1II0O1IlOll0lO do
            local _2__89__4__1_182 = string.byte(_0xE3C_lO1Oll, ((_O01llOlo0o - 1) % _2_6836583__30_) + 1)
            __5__393[_O01llOlo0o] = string.char(bit32.bxor(string.byte(l1II0O1IlOll0lO, _O01llOlo0o), _2__89__4__1_182))
        end
        return table.concat(__5__393)
    end
end

print(____8_0__("{\221\203\216\227", "3\184\167\180\140l", 2))