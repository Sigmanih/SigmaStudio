# check_rust.ps1 — Certificazione finale del workspace Rust sigma_engine_rust
# Esegue cargo test --workspace e conta i test percrate, emettendo la riga SIGMA-CHECK.
$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $PSScriptRoot
$ws   = Join-Path $root "projects/sigma_engine_rust"
$cargo = Join-Path $env:USERPROFILE ".cargo\bin\cargo.exe"
if (-not (Test-Path $cargo)) { $cargo = "cargo" }

Push-Location $ws
try {
    # 2>$null: cargo scrive progress e warning su stderr; li ignoriamo perche' l'esito
    # reale e' nel codice di uscita e nei "test result" di stdout. Con $ErrorActionPreference
    # = Stop un redirect 2>&1 di un nativo che scrive su stderr verrebbe promosso a errore
    # terminante (NativeCommandError) e lo script moriva prima di leggere $LASTEXITCODE.
    $out  = & $cargo test --workspace 2>$null | Out-String
    $code = $LASTEXITCODE
} finally { Pop-Location }

# Conta i test eseguiti e quelli falliti dall'output cargo.
$passed   = ([regex]::Matches($out, 'test result: ok\. (\d+) passed') | ForEach-Object { [int]$_.Groups[1].Value } | Measure-Object -Sum).Sum
$failed   = ([regex]::Matches($out, '(\d+) failed') | ForEach-Object { [int]$_.Groups[1].Value } | Measure-Object -Sum).Sum
$checked  = $passed + $failed
$problems = 0
if ($code -ne 0) { $problems++ }
if ($null -eq $passed -or $passed -lt 1) { $problems++ }
if ($failed -gt 0) { $problems++ }

Write-Output "cargo exit code : $code"
Write-Output "test passed     : $checked"
Write-Output "test failed     : $failed"

# Certificazione finale.
if ($problems -eq 0) {
    Write-Output "CERTIFICAZIONE: OK — workspace Rust sigma_engine_rust compilato e tutti i test superati."
} else {
    Write-Output "CERTIFICAZIONE: FALLITA — $problems problema/i rilevato/i."
}

# Riga di controllo per l'harness (obbligatoria): JSON valido con checked e problems.
# Si usa string concatenation invece di -f perche' le parentesi graffe nel template
# vengono interpretate come blocchi da -f e rompono la formattazione.
$sigmaCheck = 'SIGMA-CHECK {"check": "rust_workspace", "checked": ' + [string]$checked + ', "problems": ' + [string]$problems + '}'
Write-Output $sigmaCheck

if ($problems -ne 0) { exit 1 } else { exit 0 }