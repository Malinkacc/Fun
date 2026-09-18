"""
NZL Studio Obfuscator — ULTRA Protection Pipeline

Применяет ВСЕ доступные трансформации в правильном порядке:
1. String array extraction
2. String encryption
3. Number obfuscation (aggressive)
4. Variable renaming (luraph style)
5. Control flow flattening
6. State machine obfuscation
7. VM protection (Luraph-style bytecode)
8. Anti-tamper (CRC, honeypots, traps)
9. Environment checks
10. Dead code injection
11. Opaque predicates
12. Symbiote-style wrapping
13. Watermark
"""

from __future__ import annotations

import sys
import os
from typing import Optional

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from obfuscator.lexer import Lexer
from obfuscator.parser import Parser
from obfuscator.ast_unparser import unparse
from obfuscator.utils.random_gen import make_rng, NameGenerator


def ultra_obfuscate(source: str, seed: Optional[int] = None) -> str:
    """
    ULTRA obfuscation pipeline — applies ALL available protections.
    """
    if seed is None:
        import time
        seed = int(time.time() * 1000) & 0xFFFFFFFF
    
    rng = make_rng(seed)
    name_gen = NameGenerator(rng, style='luraph')
    
    # Parse
    ast = Parser(Lexer(source).tokenize()).parse()
    
    # Stage 1: String array extraction
    try:
        from obfuscator.transformers.string_array import StringArrayConfig, obfuscate_string_array
        result = obfuscate_string_array(ast, rng=make_rng(seed ^ 0x5A17A7), config=StringArrayConfig.aggressive())
        ast = result[0] if isinstance(result, tuple) else result
    except Exception:
        pass
    
    # Stage 2: String encryption
    try:
        from obfuscator.transformers.string_encryptor import encrypt_strings_in_chunk
        result = encrypt_strings_in_chunk(ast, rng=make_rng(seed ^ 0xDEADBEEF), name_gen=name_gen, enable_chunking=True)
        ast = result[0] if isinstance(result, tuple) else result
    except Exception:
        pass
    
    # Stage 3: Number obfuscation (aggressive)
    try:
        from obfuscator.transformers.number_obfuscator import obfuscate_numbers_in_chunk, NumberObfuscatorConfig
        result = obfuscate_numbers_in_chunk(ast, rng=make_rng(seed ^ 0xCAFEBABE), config=NumberObfuscatorConfig.aggressive())
        ast = result[0] if isinstance(result, tuple) else result
    except Exception:
        pass
    
    # Stage 4: Variable renaming
    try:
        from obfuscator.transformers.variable_renamer import VariableRenamer
        renamer = VariableRenamer(rng=make_rng(seed ^ 0x12345678), style='luraph')
        result = renamer.rename(ast)
        ast = result[0] if isinstance(result, tuple) else result
    except Exception:
        pass
    
    # Stage 5: Control flow flattening
    try:
        from obfuscator.transformers.control_flow import ControlFlowFlattener
        flattener = ControlFlowFlattener(rng=make_rng(seed ^ 0xABCD1234))
        result = flattener.flatten(ast)
        ast = result[0] if isinstance(result, tuple) else result
    except Exception:
        pass
    
    # Stage 6: State machine obfuscation
    try:
        from obfuscator.transformers.state_machine import StateMachineConfig, obfuscate_state_machine
        result = obfuscate_state_machine(ast, rng=make_rng(seed ^ 0x57A7E), config=StateMachineConfig.aggressive())
        ast = result[0] if isinstance(result, tuple) else result
    except Exception:
        pass
    
    # Unparse to get Lua code
    lua_code = unparse(ast, minified=False)
    
    # Stage 7: VM protection (wrap in LuraphVM)
    try:
        from obfuscator.luraph_vm import obfuscate_script
        lua_code = obfuscate_script(lua_code, seed=seed ^ 0xABCDEF12)
    except Exception:
        pass
    
    # Stage 8-12: Add protection layers
    protection_code = _build_protection_layers(seed)
    
    # Combine
    final = protection_code + "\n" + lua_code
    
    # Stage 13: Watermark
    try:
        from obfuscator.protection.watermark import WatermarkGenerator
        wm = WatermarkGenerator(seed, owner_id=582821107065683971)
        final = wm.apply_watermarks(final, username="NZL Studio", num_inline=5)
    except Exception:
        pass
    
    return final


def _build_protection_layers(seed: int) -> str:
    """Build anti-tamper, environment checks, dead code, opaque predicates"""
    rng = make_rng(seed ^ 0x5AFE1234)
    layers = []
    
    # Anti-tamper
    try:
        from obfuscator.protection.anti_tamper import generate_anti_tamper
        layers.append(generate_anti_tamper(seed=seed ^ 0xA1171234))
    except Exception:
        pass
    
    # Environment checks
    try:
        from obfuscator.protection.environment import generate_environment_checks
        layers.append(generate_environment_checks(seed=seed ^ 0xE11E1234))
    except Exception:
        pass
    
    # Dead code injection
    dead_code = _generate_dead_code(rng)
    layers.append(dead_code)
    
    # Opaque predicates
    opaque = _generate_opaque_predicates(rng)
    layers.append(opaque)
    
    return "\n".join(layers)


def _generate_dead_code(rng) -> str:
    """Generate dead code blocks that never execute"""
    blocks = []
    for i in range(rng.randint(3, 8)):
        cond = rng.choice([
            "false",
            "0==1",
            "nil",
            "1>2",
            "''=='x'",
            "type(1)=='string'",
        ])
        body = rng.choice([
            "local _ = 1",
            "error('trap')",
            "while true do end",
            "return nil",
        ])
        blocks.append(f"if {cond} then {body} end")
    return "\n".join(blocks)


def _generate_opaque_predicates(rng) -> str:
    """Generate opaque predicates that always evaluate to known values"""
    preds = []
    for i in range(rng.randint(2, 5)):
        # Always true
        a = rng.randint(1, 100)
        b = rng.randint(1, 100)
        c = a + b
        preds.append(f"local _op{i} = ({a}+{b}=={c}) and true or false")
    return "\n".join(preds)


if __name__ == '__main__':
    if '--test' in sys.argv:
        test = '''
local x = 10
local y = 20
print(x + y)
'''
        result = ultra_obfuscate(test, seed=42)
        print(f"Generated {len(result)} chars")
        print(result[:500])
