$ErrorActionPreference='Stop'
. "$PSScriptRoot/workflow.ps1" -Library
$count=0
function Assert($Condition,$Label){if(-not $Condition){throw "FAIL $Label"};$script:count++;Write-Output "PASS $Label"}
function Initialize-Fixture($Name) {
    $dir=Join-Path $PSScriptRoot $Name
    New-Item -ItemType Directory -Force "$dir/input","$dir/checkpoints" | Out-Null
    Copy-Item "$PSScriptRoot/input/books.csv","$PSScriptRoot/input/queue.csv","$PSScriptRoot/input/projects.csv","$PSScriptRoot/input/evidence.csv" "$dir/input" -Force
    Get-ChildItem "$dir/checkpoints" -File | Remove-Item -Force
    return $dir
}
$dir=Initialize-Fixture 'workflow-test-sandbox'
$a='DEMO-A-CASH-2026'; $b='DEMO-B-MISA-2026'
$queued=Invoke-SyntheticWorkflow $a $dir -LegacyRegressionTest -Quota EXHAUSTED
Assert ($queued.status -eq 'QUEUED' -and (Test-Path "$dir/checkpoints/workflow-$a.json") -and -not (Test-Path "$dir/checkpoints/$a.json")) 'quota persists QUEUED without routing'
$threw=$false; try {Invoke-SyntheticWorkflow $b $dir -LegacyRegressionTest -Fault AFTER_ROUTING | Out-Null} catch {$threw=$_.Exception.Message -match 'SIMULATED_INTERRUPT_AFTER_ROUTING'}
Assert ($threw -and (Test-Path "$dir/checkpoints/$b.json") -and -not (Test-Path "$dir/checkpoints/timeline-$b.json")) 'interrupt after routing preserved checkpoint'
$bres=Invoke-SyntheticWorkflow $b $dir -LegacyRegressionTest
Assert ($bres.status -eq 'VERIFIED' -and $bres.record_count -eq 1) 'resume B after routing'
$threw=$false; try {Invoke-SyntheticWorkflow $a $dir -LegacyRegressionTest -Fault AFTER_TIMELINE | Out-Null} catch {$threw=$_.Exception.Message -match 'SIMULATED_INTERRUPT_AFTER_TIMELINE'}
Assert ($threw -and (Test-Path "$dir/checkpoints/timeline-$a.json")) 'interrupt after timeline retained records'
$before=(Get-FileHash "$dir/checkpoints/timeline-$a.json").Hash; $ares=Invoke-SyntheticWorkflow $a $dir -LegacyRegressionTest; $after=(Get-FileHash "$dir/checkpoints/timeline-$a.json").Hash
Assert ($ares.status -eq 'VERIFIED' -and $ares.record_count -eq 6 -and $ares.transaction_count -eq 4 -and $before -eq $after) 'resume A without processing again'
$again=Invoke-SyntheticWorkflow $a $dir -LegacyRegressionTest; Assert ($again.record_count -eq 6 -and $again.transaction_count -eq 4) 'completed workflow retry keeps counts'
$p=@(Import-Csv "$dir/input/projects.csv"); $p[0].STATUS='CHANGED'; $p | Export-Csv "$dir/input/projects.csv" -Encoding UTF8 -NoTypeInformation
$threw=$false; try {Invoke-SyntheticWorkflow $a $dir -LegacyRegressionTest | Out-Null} catch {$threw=$_.Exception.Message -match 'INVALID_WORKFLOW_PROJECT|WORKFLOW_INPUT_CHANGED'}
Assert $threw 'changed project cannot resume stale workflow'
$bres=Invoke-SyntheticWorkflow $b $dir -LegacyRegressionTest; Assert ($bres.status -eq 'VERIFIED') 'project error A does not block B'
Copy-Item "$PSScriptRoot/input/projects.csv" "$dir/input/projects.csv" -Force
$jobs=@(Import-Csv "$dir/input/queue.csv"); ($jobs | Where-Object BOOK_ID -CEQ $a).SOURCE_SNAPSHOT_ID='SYN_A_CHANGED'; $jobs | Export-Csv "$dir/input/queue.csv" -Encoding UTF8 -NoTypeInformation
$threw=$false; try {Invoke-SyntheticWorkflow $a $dir -LegacyRegressionTest | Out-Null} catch {$threw=$_.Exception.Message -match 'WORKFLOW_INPUT_CHANGED'}; Assert $threw 'changed snapshot label cannot resume stale workflow'
Copy-Item "$PSScriptRoot/input/queue.csv" "$dir/input/queue.csv" -Force
$events=@(Import-Csv "$dir/input/evidence.csv"); $events[0].AMOUNT='101'; $events | Export-Csv "$dir/input/evidence.csv" -Encoding UTF8 -NoTypeInformation
$threw=$false; try {Invoke-SyntheticWorkflow $a $dir -LegacyRegressionTest | Out-Null} catch {$threw=$_.Exception.Message -match 'WORKFLOW_INPUT_CHANGED'}; Assert $threw 'changed evidence cannot resume stale workflow'
$missingDir=Initialize-Fixture 'workflow-test-final-loss'
$threw=$false; try {Invoke-SyntheticWorkflow $a $missingDir -LegacyRegressionTest -Fault AFTER_FINAL | Out-Null} catch {$threw=$_.Exception.Message -match 'SIMULATED_RESPONSE_LOST_AFTER_FINAL'}
$final=Invoke-SyntheticWorkflow $a $missingDir -LegacyRegressionTest
Assert ($threw -and $final.status -eq 'VERIFIED' -and $final.record_count -eq 6) 'lost final response retry is idempotent'
Remove-Item -LiteralPath "$missingDir/checkpoints/timeline-$a.json"
$threw=$false; try {Invoke-SyntheticWorkflow $a $missingDir -LegacyRegressionTest | Out-Null} catch {$threw=$_.Exception.Message -match 'WORKFLOW_CHECKPOINT_MISSING'}; Assert $threw 'missing child checkpoint fails closed'
$parallel=Initialize-Fixture 'workflow-test-concurrent'
$workflowPath=Join-Path $PSScriptRoot 'workflow.ps1'
$fn={param($path,$sandbox,$id) $result=& powershell -NoProfile -ExecutionPolicy Bypass -File $path -BookId $id -WorkflowRoot $sandbox -LegacyRegressionTest; [pscustomobject]@{exit=$LASTEXITCODE;result=(($result -join "`n") | ConvertFrom-Json)}}
$ja=Start-Job -ScriptBlock $fn -ArgumentList $workflowPath,$parallel,$a; $jb=Start-Job -ScriptBlock $fn -ArgumentList $workflowPath,$parallel,$b
Wait-Job $ja,$jb | Out-Null; $ra=Receive-Job $ja; $rb=Receive-Job $jb; Remove-Job $ja,$jb
Assert ($ra.exit -eq 0 -and $rb.exit -eq 0 -and $ra.result.status -eq 'VERIFIED' -and $rb.result.status -eq 'VERIFIED' -and $ra.result.record_count -eq 6 -and $rb.result.record_count -eq 1) 'two full workflows run concurrently'
Write-Output "TOTAL $count"
