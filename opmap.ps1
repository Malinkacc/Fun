# NZL STUDIO - Sprint 6 (slices 4+5) quick verification runner
# Runs in SECONDS: self-tests + STATIC opcode map + LIFT of real VM frames.
# No sandbox execution, no network. Usage:
#   powershell -ExecutionPolicy Bypass -File opmap.ps1
$env:PYTHONIOENCODING = "utf-8"
Set-Location -Path $PSScriptRoot
$fail = 0

Write-Host "== STEP 1: vm_opcodes self-test (expect 'Result: 9/9' + '[OK] ALL PASSED')"
py -m obfuscator.deobfuscator.luraph.vm_opcodes --test
if ($LASTEXITCODE -ne 0) { $fail = 1; Write-Host "[XX] vm_opcodes self-test FAILED" } else { Write-Host "[OK] vm_opcodes self-test passed" }

Write-Host ""
Write-Host "== STEP 2: static opcode map of the real sample (instant, pure AST)"
$sample = "obfuscator\deobfuscator\samples\luraph\v14.6_sample1.lua"
if (-not (Test-Path $sample)) {
    Write-Host "[XX] sample not found: $sample"
    Write-Host "[XX] update the tree first (ZIP step), then rerun"
    exit 1
}
New-Item -ItemType Directory -Force -Path "out" | Out-Null
$o2 = py -m obfuscator.deobfuscator.luraph.vm_opcodes $sample --static --static-json "out\v146map.json" --report "out\v146map.txt" 2>&1
$c2 = $LASTEXITCODE
$o2 | Select-Object -First 1
if ($c2 -ne 0) { $fail = 1; Write-Host "[XX] static map FAILED"; $o2 | Select-Object -Last 5 } else { Write-Host "[OK] static map written: out\v146map.json + out\v146map.txt" }

Write-Host ""
Write-Host "== STEP 3: vm_lift self-test (expect 'Result: 9/9' + '[OK] ALL PASSED')"
py -m obfuscator.deobfuscator.luraph.vm_lift --test
if ($LASTEXITCODE -ne 0) { $fail = 1; Write-Host "[XX] vm_lift self-test FAILED" } else { Write-Host "[OK] vm_lift self-test passed" }

Write-Host ""
Write-Host "== STEP 4: lift real VM frames of the sample (instant; first 12 lines shown)"
$o4 = py -m obfuscator.deobfuscator.luraph.vm_lift --demo --max 3 --out "out\lifted.txt" 2>&1
$c4 = $LASTEXITCODE
$o4 | Select-Object -First 12
if ($c4 -ne 0) { $fail = 1; Write-Host "[XX] demo lift FAILED"; $o4 | Select-Object -Last 5 } else { Write-Host "[OK] lifted code written: out\lifted.txt" }

Write-Host ""
Write-Host "== STEP 5: dynamic_decrypt self-test (expect 'Result: 5/5' + '[OK] ALL PASSED')"
$o5 = py -m obfuscator.deobfuscator.dynamic_decrypt --test 2>&1
$c5 = $LASTEXITCODE
$o5 | Select-Object -Last 2
if ($c5 -ne 0) { $fail = 1; Write-Host "[XX] dynamic_decrypt self-test FAILED"; $o5 | Select-Object -Last 6 } else { Write-Host "[OK] dynamic_decrypt self-test passed" }

Write-Host ""
Write-Host "== STEP 6: moonsec string_harvest self-test (expect 'Result: 5/5' + '[OK] ALL PASSED')"
$o6 = py -m obfuscator.deobfuscator.moonsec.string_harvest --test 2>&1
$c6 = $LASTEXITCODE
$o6 | Select-Object -Last 2
if ($c6 -ne 0) { $fail = 1; Write-Host "[XX] string_harvest self-test FAILED"; $o6 | Select-Object -Last 6 } else { Write-Host "[OK] string_harvest self-test passed" }

Write-Host ""
Write-Host "== STEP 7: moonveil vm_trace self-test (expect 'Result: 6/6' + '[OK] ALL PASSED')"
$o7 = py -m obfuscator.deobfuscator.moonveil.vm_trace --test 2>&1
$c7 = $LASTEXITCODE
$o7 | Select-Object -Last 2
if ($c7 -ne 0) { $fail = 1; Write-Host "[XX] vm_trace self-test FAILED"; $o7 | Select-Object -Last 6 } else { Write-Host "[OK] vm_trace self-test passed" }

Write-Host ""
Write-Host "== STEP 8: moonveil vm_state self-test (expect 'Result: 6/6' + '[OK] ALL PASSED')"
$o8 = py -m obfuscator.deobfuscator.moonveil.vm_state --test 2>&1
$c8 = $LASTEXITCODE
$o8 | Select-Object -Last 2
if ($c8 -ne 0) { $fail = 1; Write-Host "[XX] vm_state self-test FAILED"; $o8 | Select-Object -Last 6 } else { Write-Host "[OK] vm_state self-test passed" }

Write-Host ""
Write-Host "== STEP 9: moonveil stream_assemble self-test (expect 'Result: 5/5' + '[OK] ALL PASSED')"
$o9 = py -m obfuscator.deobfuscator.moonveil.stream_assemble --test 2>&1
$c9 = $LASTEXITCODE
$o9 | Select-Object -Last 2
if ($c9 -ne 0) { $fail = 1; Write-Host "[XX] stream_assemble self-test FAILED"; $o9 | Select-Object -Last 6 } else { Write-Host "[OK] stream_assemble self-test passed" }

Write-Host ""
Write-Host "== STEP 10: moonveil vm_phase self-test (expect 'Result: 5/5' + '[OK] ALL PASSED')"
$o10 = py -m obfuscator.deobfuscator.moonveil.vm_phase --test 2>&1
$c10 = $LASTEXITCODE
$o10 | Select-Object -Last 2
if ($c10 -ne 0) { $fail = 1; Write-Host "[XX] vm_phase self-test FAILED"; $o10 | Select-Object -Last 6 } else { Write-Host "[OK] vm_phase self-test passed" }

Write-Host ""
Write-Host "== STEP 11: moonveil vm_tables self-test (expect 'Result: 5/5' + '[OK] ALL PASSED')"
$o11 = py -m obfuscator.deobfuscator.moonveil.vm_tables --test 2>&1
$c11 = $LASTEXITCODE
$o11 | Select-Object -Last 2
if ($c11 -ne 0) { $fail = 1; Write-Host "[XX] vm_tables self-test FAILED"; $o11 | Select-Object -Last 6 } else { Write-Host "[OK] vm_tables self-test passed" }

Write-Host ""
Write-Host "== STEP 12: moonveil vm_lift self-test (expect 'Result: 6/6' + '[OK] ALL PASSED')"
$o12 = py -m obfuscator.deobfuscator.moonveil.vm_lift --test 2>&1
$c12 = $LASTEXITCODE
$o12 | Select-Object -Last 2
if ($c12 -ne 0) { $fail = 1; Write-Host "[XX] vm_lift(moonveil) self-test FAILED"; $o12 | Select-Object -Last 6 } else { Write-Host "[OK] moonveil vm_lift self-test passed" }

Write-Host ""
Write-Host "== STEP 13: wearedevs array_trace self-test (expect 'Result: 5/5' + '[OK] ALL PASSED')"
$o13 = py -m obfuscator.deobfuscator.wearedevs.array_trace --test 2>&1
$c13 = $LASTEXITCODE
$o13 | Select-Object -Last 2
if ($c13 -ne 0) { $fail = 1; Write-Host "[XX] array_trace self-test FAILED"; $o13 | Select-Object -Last 6 } else { Write-Host "[OK] array_trace self-test passed" }

Write-Host ""
Write-Host "== STEP 14: sprint7 round-trip (emitters vs decoders, expect 'Result: 5/5')"
$o14 = py -m obfuscator.deobfuscator.sprint7_roundtrip --test 2>&1
$c14 = $LASTEXITCODE
$o14 | Select-Object -Last 2
if ($c14 -ne 0) { $fail = 1; Write-Host "[XX] sprint7 round-trip FAILED"; $o14 | Select-Object -Last 8 } else { Write-Host "[OK] sprint7 round-trip passed" }

Write-Host ""
Write-Host "== EXPECTED: STEP2 'leaves=157'; STEP4 lines like 'function vmfn1(...)' and r12[...]=..."
if ($fail -eq 0) { Write-Host "[OK] ALL STEPS PASSED" } else { Write-Host "[XX] FAILURES PRESENT - send me the full output" }
exit $fail
