# NZL STUDIO - Sprint 6 (slice 4) quick verification runner
# Runs in SECONDS: python self-test + STATIC opcode map (no sandbox execution).
# Usage:  powershell -ExecutionPolicy Bypass -File opmap.ps1
$env:PYTHONIOENCODING = "utf-8"
Set-Location -Path $PSScriptRoot
$fail = 0

Write-Host "== STEP 1: vm_opcodes self-test (expect 'Result: 9/9' + '[OK] ALL PASSED')"
py -m obfuscator.deobfuscator.luraph.vm_opcodes --test
if ($LASTEXITCODE -ne 0) { $fail = 1; Write-Host "[XX] self-test FAILED" } else { Write-Host "[OK] self-test passed" }

Write-Host ""
Write-Host "== STEP 2: static opcode map of the real sample (instant, pure AST)"
$sample = "obfuscator\deobfuscator\samples\luraph\v14.6_sample1.lua"
if (-not (Test-Path $sample)) {
    Write-Host "[XX] sample not found: $sample"
    Write-Host "[XX] update the tree first (ZIP step), then rerun"
    exit 1
}
New-Item -ItemType Directory -Force -Path "out" | Out-Null
py -m obfuscator.deobfuscator.luraph.vm_opcodes $sample --static --static-json "out\v146map.json" --report "out\v146map.txt"
if ($LASTEXITCODE -ne 0) { $fail = 1; Write-Host "[XX] static map FAILED" } else { Write-Host "[OK] static map written: out\v146map.json + out\v146map.txt" }

Write-Host ""
Write-Host "== EXPECTED STEP 2 LINE: dispatcher vars: q=q t=t E=E; root_if=True; leaves=157"
if ($fail -eq 0) { Write-Host "[OK] ALL STEPS PASSED" } else { Write-Host "[XX] FAILURES PRESENT - send me the full output" }
exit $fail
