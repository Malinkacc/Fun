"""
NZL Studio Obfuscator — Engine v5

Simple: source → encrypt → base85 → loadstring → execute
Works in ALL Roblox executors (Xeno, Potassium, Delta, Solara, Volt, Wave)
"""

import sys
import os
import time
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class Obfuscator:
    def __init__(self, seed: Optional[int] = None, **kwargs):
        if seed is None:
            seed = int(time.time() * 1000) & 0xFFFFFFFF
        self.seed = seed

    def obfuscate(self, source: str, **kwargs) -> str:
        from obfuscator.symbiote_obf import obfuscate_script
        return obfuscate_script(source, seed=self.seed)


def obfuscate(source: str, seed: Optional[int] = None) -> str:
    obf = Obfuscator(seed=seed)
    return obf.obfuscate(source)
