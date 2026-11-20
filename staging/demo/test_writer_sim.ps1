$ErrorActionPreference='Stop'
. "$PSScriptRoot/writer_sim.ps1" -Library
$script:WriterRoot=Join-Path $PSScriptRoot 'writer-test-sandbox'
New-Item -ItemType Directory -Force "$script:WriterRoot/writer-state" | Out-Null
Get-ChildItem "$script:WriterRoot/writer-state" -File | Remove-Item -Force
$count=0
function Assert($Condition,$Label) {if(-not $Condition){throw "FAIL $Label"}; $script:count++; Write-Output "PASS $Label"}
Initialize-Writer 'DEMO-A-CASH-2026' 'DEMO_A' '2026-11'
Initialize-Writer 'DEMO-B-MISA-2026' 'DEMO_B' '2026-11'
$a=[pscustomobject]@{BOOK_ID='DEMO-A-CASH-2026';LEGAL_ENTITY_ID='DEMO_A';PERIOD='2026-11';KEY='DEMO-K-1';TX='DEMO-T-1';AMOUNT='100';EXPECTED_VERSION=0;QUOTA='AVAILABLE';APPROVAL_BOOK='DEMO-A-CASH-2026';APPROVAL_PERIOD='2026-11';APPROVAL_ACTION='SYNTHETIC_WRITE';APPROVED='YES'}
$b=[pscustomobject]@{BOOK_ID='DEMO-B-MISA-2026';LEGAL_ENTITY_ID='DEMO_B';PERIOD='2026-11';KEY='DEMO-K-1';TX='DEMO-T-1';AMOUNT='70';EXPECTED_VERSION=0;QUOTA='AVAILABLE';APPROVAL_BOOK='DEMO-B-MISA-2026';APPROVAL_PERIOD='2026-11';APPROVAL_ACTION='SYNTHETIC_WRITE';APPROVED='YES'}
$threw=$false; try {Invoke-SyntheticWrite $a -LoseResponse | Out-Null} catch {$threw=$_.Exception.Message -match 'SIMULATED_RESPONSE_LOST_AFTER_COMMIT'}
Assert $threw 'lost response after committed local write'
$retry=Invoke-SyntheticWrite $a; $state=Get-Content -Raw "$script:WriterRoot/writer-state/DEMO-A-CASH-2026.json" | ConvertFrom-Json
Assert ($retry.status -eq 'ALREADY_APPLIED' -and $state.rows.Count -eq 1 -and $state.version -eq 1) 'B07 retry idempotent after lost response'
$changed=$a.PSObject.Copy(); $changed.AMOUNT='101'; $threw=$false; try {Invoke-SyntheticWrite $changed | Out-Null} catch {$threw=$_.Exception.Message -match 'IDEMPOTENCY_CONFLICT'}; Assert $threw 'same idempotency key with altered content rejected'
$stale=$a.PSObject.Copy(); $stale.KEY='DEMO-K-2'; $stale.TX='DEMO-T-2'; $conflict=Invoke-SyntheticWrite $stale
Assert ($conflict.status -eq 'BLOCKED' -and $conflict.reason -eq 'VERSION_CONFLICT') 'B08 stale version blocks write'
$stale.EXPECTED_VERSION=1; $stale.TX='DEMO-T-1'; $duplicate=Invoke-SyntheticWrite $stale; Assert ($duplicate.reason -eq 'DUPLICATE_TRANSACTION') 'different key cannot duplicate transaction'
$lock=[IO.File]::Open("$script:WriterRoot/writer-state/DEMO-A-CASH-2026.json.lock",'OpenOrCreate','ReadWrite','None')
try {
    $job=Start-Job -ScriptBlock { param($scriptFile,$root,$request) . $scriptFile -Library; $script:WriterRoot=$root; try {Invoke-SyntheticWrite $request | Out-Null; 'NOT_BLOCKED'} catch {'LOCKED'} } -ArgumentList "$PSScriptRoot/writer_sim.ps1",$script:WriterRoot,$a
    Wait-Job $job | Out-Null; $result=Receive-Job $job; Remove-Job $job
    Assert ($result -eq 'LOCKED') 'B02 second process blocked by exclusive lock'
    $out=Invoke-SyntheticWrite $b; Assert ($out.status -eq 'APPLIED') 'B01 locked A does not block B'
} finally {$lock.Dispose()}
$wrong=$b.PSObject.Copy(); $wrong.KEY='DEMO-K-2'; $wrong.TX='DEMO-T-2'; $wrong.EXPECTED_VERSION=1; $wrong.APPROVAL_BOOK='DEMO-A-CASH-2026'; $out=Invoke-SyntheticWrite $wrong
Assert ($out.status -eq 'BLOCKED' -and $out.reason -eq 'APPROVAL_SCOPE') 'B11 approval cannot cross book'
$wrong.APPROVAL_BOOK='DEMO-B-MISA-2026'; $wrong.QUOTA='EXHAUSTED'; $out=Invoke-SyntheticWrite $wrong
Assert ($out.status -eq 'QUEUED' -and $out.reason -eq 'QUOTA') 'B12 quota preserves queued status'
$next=$a.PSObject.Copy(); $next.KEY='DEMO-K-3'; $next.TX='DEMO-T-3'; $next.EXPECTED_VERSION=1; $out=Invoke-SyntheticWrite $next
Assert ($out.status -eq 'APPLIED') 'B06 quota B does not stop A'
$before=Get-Content -Raw "$script:WriterRoot/writer-state/DEMO-B-MISA-2026.json" | ConvertFrom-Json
Assert ($before.rows.Count -eq 1 -and $before.version -eq 1) 'blocked and quota requests did not write'
Assert ($before.pending.Count -eq 1 -and $before.pending[0].status -eq 'QUEUED') 'quota persists queued item'
$conflicting=$wrong.PSObject.Copy(); $conflicting.AMOUNT='71'; $threw=$false; try {Invoke-SyntheticWrite $conflicting | Out-Null} catch {$threw=$_.Exception.Message -match 'PENDING_INTENT_CONFLICT'}; Assert $threw 'queued key cannot change intent'
$wrong.QUOTA='AVAILABLE'; $out=Invoke-SyntheticWrite $wrong; $after=Get-Content -Raw "$script:WriterRoot/writer-state/DEMO-B-MISA-2026.json" | ConvertFrom-Json
Assert ($out.status -eq 'APPLIED' -and $after.rows.Count -eq 2 -and $after.pending.Count -eq 0) 'queued item resumes once and clears queue'
$rows=@([pscustomobject]@{ID='R2';DATE='2026-11-02';LINK='demo://two';FORMULA='=SUM(C2:D2)';VALUE=20},[pscustomobject]@{ID='R1';DATE='2026-11-01';LINK='demo://one';FORMULA='=SUM(C1:D1)';VALUE=10})
$sorted=@(Sort-SyntheticRows $rows)
Assert ($sorted.Count -eq 2 -and $sorted[0].ID -eq 'R1' -and $sorted[0].LINK -eq 'demo://one' -and $sorted[0].FORMULA -eq '=SUM(C1:D1)' -and $sorted[0].VALUE -eq 10 -and $sorted[1].ID -eq 'R2' -and $sorted[1].LINK -eq 'demo://two' -and $sorted[1].FORMULA -eq '=SUM(C2:D2)') 'A08 sort entire object retains link and formula text'
Write-Output "TOTAL $count"
