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
py -m obfuscator.deobfuscator.luraph.vm_opcodes $sample --static --static-json "out\v146map.json" --report "out\v146map.txt" | Select-Object -First 1
if ($LASTEXITCODE -ne 0) { $fail = 1; Write-Host "[XX] static map FAILED" } else { Write-Host "[OK] static map written: out\v146map.json + out\v146map.txt" }

Write-Host ""
Write-Host "== STEP 3: vm_lift self-test (expect 'Result: 9/9' + '[OK] ALL PASSED')"
py -m obfuscator.deobfuscator.luraph.vm_lift --test
if ($LASTEXITCODE -ne 0) { $fail = 1; Write-Host "[XX] vm_lift self-test FAILED" } else { Write-Host "[OK] vm_lift self-test passed" }

Write-Host ""
Write-Host "== STEP 4: lift real VM frames of the sample (instant; first 12 lines shown)"
py -m obfuscator.deobfuscator.luraph.vm_lift --demo --max 3 --out "out\lifted.txt" | Select-Object -First 12
if ($LASTEXITCODE -ne 0) { $fail = 1; Write-Host "[XX] demo lift FAILED" } else { Write-Host "[OK] lifted code written: out\lifted.txt" }

Write-Host ""
Write-Host "== EXPECTED: STEP2 'leaves=157'; STEP4 lines like 'function vmfn1(...)' and r12[...]=..."
if ($fail -eq 0) { Write-Host "[OK] ALL STEPS PASSED" } else { Write-Host "[XX] FAILURES PRESENT - send me the full output" }
exit $fail
