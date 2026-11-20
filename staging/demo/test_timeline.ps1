$ErrorActionPreference='Stop'
. "$PSScriptRoot/timeline.ps1" -Library
$script:TimelineRoot=Join-Path $PSScriptRoot 'timeline-test-sandbox'
New-Item -ItemType Directory -Force "$script:TimelineRoot/input", "$script:TimelineRoot/checkpoints" | Out-Null
Copy-Item "$PSScriptRoot/input/books.csv", "$PSScriptRoot/input/projects.csv", "$PSScriptRoot/input/evidence.csv" "$script:TimelineRoot/input" -Force
$testEvidence=@(Import-Csv "$script:TimelineRoot/input/evidence.csv")
foreach($row in $testEvidence) {$row | Add-Member NoteProperty RELATED_ADVANCE_ID ''}
($testEvidence | Where-Object RECORD_ID -CEQ 'DEMO-R-A6').RELATED_ADVANCE_ID='DEMO-T-A3'
$testEvidence | Export-Csv "$script:TimelineRoot/input/evidence.csv" -NoTypeInformation -Encoding UTF8
Get-ChildItem "$script:TimelineRoot/checkpoints" -File | Remove-Item -Force
$count=0
function Assert($Condition,$Name){ if(-not $Condition){throw "FAIL $Name"}; $script:count++; Write-Output "PASS $Name" }
$partial=Invoke-Timeline 'DEMO-A-CASH-2026' -MaxNew 2
Assert ($partial.records.Count -eq 2 -and $partial.transactions.Count -eq 1) 'B10 partial checkpoint'
$a=Invoke-Timeline 'DEMO-A-CASH-2026'; $b=Invoke-Timeline 'DEMO-B-MISA-2026'
Assert ($a.records.Count -eq 6 -and $b.records.Count -eq 1) 'B01 independent book records'
$tx=@($a.transactions | Where-Object transaction_id -EQ 'DEMO-T-A1')[0]
Assert ($tx.record_ids.Count -eq 3 -and $tx.amount_out -eq 100 -and $a.records[2].duplicate_of -eq 'DEMO-R-A1') 'A01 repeated image keeps record and no second expense'
Assert ($a.records[0].transaction_id -eq $a.records[1].transaction_id -and $tx.kinds.Count -eq 2) 'A02 bill and transfer linked by explicit evidence'
Assert ($a.transactions.Count -eq 4 -and $a.transactions[1].amount_out -eq 100) 'A03 equal amount distinct reference stays separate'
Assert ($a.transactions[2].amount_out -eq 500 -and $a.transactions[2].settled_cost -eq 0 -and $a.transactions[3].amount_out -eq 0 -and $a.transactions[3].settled_cost -eq 420 -and $a.transactions[3].related_advance_id -eq 'DEMO-T-A3') 'A04 linked cash advance and settlement remain separate'
Assert ($a.records[0].source_date -eq '2026-11-03' -and $a.records[0].transaction_date -eq '2026-11-02') 'A06 separate source and transaction date'
Assert ($b.transactions[0].transaction_id -eq $tx.transaction_id -and $b.transactions[0].amount_out -eq 70) 'B05 identical transaction and hash across books separate'
$again=Invoke-Timeline 'DEMO-A-CASH-2026'
Assert ($again.records.Count -eq 6 -and $again.transactions[0].amount_out -eq 100) 'B07 checkpoint retry without append'
$bookRows=@(Import-Csv "$script:TimelineRoot/input/books.csv"); $changedBooks=@($bookRows | ForEach-Object {$_.PSObject.Copy()})
($changedBooks | Where-Object BOOK_ID -CEQ 'DEMO-A-CASH-2026').SOURCE_SYSTEM='SYNTHETIC_OTHER'
$changedBooks | Export-Csv "$script:TimelineRoot/input/books.csv" -NoTypeInformation -Encoding UTF8
$threw=$false; try {Invoke-Timeline 'DEMO-A-CASH-2026' | Out-Null} catch {$threw=$_.Exception.Message -match 'REGISTRY_CHANGED_SINCE_CHECKPOINT'}
Assert $threw 'changed timeline book rejected on resume'
$other=Invoke-Timeline 'DEMO-B-MISA-2026'; Assert ($other.records.Count -eq 1) 'other timeline unaffected by book change'
$bookRows | Export-Csv "$script:TimelineRoot/input/books.csv" -NoTypeInformation -Encoding UTF8
$projectRows=@(Import-Csv "$script:TimelineRoot/input/projects.csv"); $changedProjects=@($projectRows | ForEach-Object {$_.PSObject.Copy()})
($changedProjects | Where-Object PROJECT_ID -CEQ 'DEMO-PROJECT-A').LEGAL_ENTITY_ID='DEMO_WRONG'
$changedProjects | Export-Csv "$script:TimelineRoot/input/projects.csv" -NoTypeInformation -Encoding UTF8
$threw=$false; try {Invoke-Timeline 'DEMO-A-CASH-2026' | Out-Null} catch {$threw=$_.Exception.Message -match 'MISMATCH_PROJECT|PROJECT_CHANGED_SINCE_CHECKPOINT'}
Assert $threw 'changed project mapping rejected on resume'
$other=Invoke-Timeline 'DEMO-B-MISA-2026'; Assert ($other.records.Count -eq 1) 'other timeline unaffected by project change'
$projectRows | Export-Csv "$script:TimelineRoot/input/projects.csv" -NoTypeInformation -Encoding UTF8
$timelinePath="$script:TimelineRoot/checkpoints/timeline-DEMO-A-CASH-2026.json"; $saved=Get-Content -Raw -Encoding UTF8 $timelinePath; $legacy=$saved | ConvertFrom-Json; $legacy.PSObject.Properties.Remove('book_fingerprint'); $legacy | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $timelinePath
$threw=$false; try {Invoke-Timeline 'DEMO-A-CASH-2026' | Out-Null} catch {$threw=$_.Exception.Message -match 'LEGACY_TIMELINE_REQUIRES_REVALIDATION'}
Assert $threw 'legacy timeline without source fingerprint fails closed'; $saved | Set-Content -Encoding UTF8 $timelinePath
$rows=@(Import-Csv "$script:TimelineRoot/input/evidence.csv"); $rows[0].AMOUNT='101'; $rows | Export-Csv "$script:TimelineRoot/input/evidence.csv" -NoTypeInformation -Encoding UTF8
$threw=$false; try {Invoke-Timeline 'DEMO-A-CASH-2026' | Out-Null} catch {$threw=$_.Exception.Message -match 'SOURCE_CHANGED'}
Assert $threw 'B08 changed source rejected on resume'
$b=Invoke-Timeline 'DEMO-B-MISA-2026'; Assert ($b.records.Count -eq 1) 'B06 failure isolated to A'
$testEvidence | Export-Csv "$script:TimelineRoot/input/evidence.csv" -NoTypeInformation -Encoding UTF8
$rows=@(Import-Csv "$script:TimelineRoot/input/evidence.csv"); $extra=$rows[0].PSObject.Copy(); $extra.RECORD_ID='DEMO-R-A7'; $extra.RAW_SHA256='ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff'; $extra.EVIDENCE_REF='DEMO-E-OTHER'; $rows+=$extra; $rows | Export-Csv "$script:TimelineRoot/input/evidence.csv" -NoTypeInformation -Encoding UTF8
$threw=$false; try {Invoke-Timeline 'DEMO-A-CASH-2026' | Out-Null} catch {$threw=$_.Exception.Message -match 'TRANSACTION_EVIDENCE_CONFLICT'}
Assert $threw 'conflicting evidence cannot merge'
$extra.EVIDENCE_REF='DEMO-E-A1'; $rows[-1]=$extra; $rows | Export-Csv "$script:TimelineRoot/input/evidence.csv" -NoTypeInformation -Encoding UTF8
$threw=$false; try {Invoke-Timeline 'DEMO-A-CASH-2026' | Out-Null} catch {$threw=$_.Exception.Message -match 'MULTIPLE_CASH_OUT'}
Assert $threw 'second distinct payment cannot double expense'
$extra.LEGAL_ENTITY_ID='DEMO_B'; $rows[-1]=$extra; $rows | Export-Csv "$script:TimelineRoot/input/evidence.csv" -NoTypeInformation -Encoding UTF8
$threw=$false; try {Invoke-Timeline 'DEMO-A-CASH-2026' | Out-Null} catch {$threw=$_.Exception.Message -match 'MISMATCH_SCOPE'}
Assert $threw 'B03 wrong entity blocked before checkpoint'
$extra.LEGAL_ENTITY_ID='DEMO_A'; $extra.PERIOD='2026-10'; $rows[-1]=$extra; $rows | Export-Csv "$script:TimelineRoot/input/evidence.csv" -NoTypeInformation -Encoding UTF8
$threw=$false; try {Invoke-Timeline 'DEMO-A-CASH-2026' | Out-Null} catch {$threw=$_.Exception.Message -match 'MISMATCH_SCOPE'}
Assert $threw 'B04 wrong period blocked before checkpoint'
$lock=[IO.File]::Open("$script:TimelineRoot/checkpoints/timeline-DEMO-A-CASH-2026.lock",'OpenOrCreate','ReadWrite','None')
try { $threw=$false; try {Invoke-Timeline 'DEMO-A-CASH-2026' | Out-Null} catch {$threw=$true}; Assert $threw 'B02 exclusive checkpoint writer'; $b=Invoke-Timeline 'DEMO-B-MISA-2026'; Assert ($b.records.Count -eq 1) 'locked A does not block B' } finally {$lock.Dispose()}
$materials=@([pscustomobject]@{ITEM='IRON';UNIT='kg';QUANTITY=2},[pscustomobject]@{ITEM='IRON';UNIT='kg';QUANTITY=3},[pscustomobject]@{ITEM='IRON';UNIT='bar';QUANTITY=4})
$totals=@(Get-MaterialTotals $materials)
Assert ($totals.Count -eq 2 -and (@($totals | Where-Object unit -EQ 'kg')[0].quantity -eq 5) -and (@($totals | Where-Object unit -EQ 'bar')[0].quantity -eq 4)) 'A05 material grouped by item and unit'
$req=[pscustomobject]@{PERSON='DEMO-PERSON';DOCUMENT='DEMO-DOC';BOOK_ID='DEMO-A-CASH-2026';PERIOD='2026-11';ACTION='REVIEW'}
$approval=[pscustomobject]@{PERSON='DEMO-PERSON';DOCUMENT='DEMO-DOC';BOOK_ID='DEMO-A-CASH-2026';PERIOD='2026-11';ACTION='REVIEW';AUTHORIZED='YES'}
Assert ((Test-DemoApproval $req $approval) -eq 'APPROVED_DEMO') 'A07 exact approval scope accepted in simulation'
$approval.PERSON='OTHER'; Assert ((Test-DemoApproval $req $approval) -eq 'NEEDS_REVIEW') 'A07 wrong person needs review'
$approval.PERSON='DEMO-PERSON'; $approval.BOOK_ID='DEMO-B-MISA-2026'; Assert ((Test-DemoApproval $req $approval) -eq 'NEEDS_REVIEW') 'B11 approval not inherited across books'
$left=[pscustomobject]@{book_id='DEMO-A-CASH-2026';transaction_id='DEMO-T-X';amount=50;period='2026-11'}
$right=[pscustomobject]@{book_id='DEMO-B-MISA-2026';transaction_id='DEMO-T-Y';amount=50;period='2026-11'}
$link=New-DemoCrossBookLink $left $right 'DEMO-E-LINK'
Assert ($link.status -eq 'NEEDS_REVIEW' -and $left.amount -eq 50 -and $right.amount -eq 50) 'B09 link preserves both records'
$testEvidence | Export-Csv "$script:TimelineRoot/input/evidence.csv" -NoTypeInformation -Encoding UTF8
$rows=@(Import-Csv "$script:TimelineRoot/input/evidence.csv"); $rows[1..($rows.Count-1)] | Export-Csv "$script:TimelineRoot/input/evidence.csv" -NoTypeInformation -Encoding UTF8
$threw=$false; try {Invoke-Timeline 'DEMO-A-CASH-2026' | Out-Null} catch {$threw=$_.Exception.Message -match 'SOURCE_REMOVED'}; Assert $threw 'removed source detected'
$oldRoot=$script:TimelineRoot; $linkRoot=Join-Path $PSScriptRoot 'timeline-link-test-sandbox'
New-Item -ItemType Directory -Force "$linkRoot/input","$linkRoot/checkpoints" | Out-Null
Get-ChildItem "$linkRoot/checkpoints" -File | Remove-Item -Force
Copy-Item "$PSScriptRoot/input/books.csv","$PSScriptRoot/input/projects.csv" "$linkRoot/input" -Force
$invalid=@($testEvidence | ForEach-Object {$_.PSObject.Copy()}); ($invalid | Where-Object RECORD_ID -CEQ 'DEMO-R-A6').RELATED_ADVANCE_ID='DEMO-T-FOREIGN'
$invalid | Export-Csv "$linkRoot/input/evidence.csv" -NoTypeInformation -Encoding UTF8
$script:TimelineRoot=$linkRoot
$threw=$false; try {Invoke-Timeline 'DEMO-A-CASH-2026' | Out-Null} catch {$threw=$_.Exception.Message -match 'INVALID_ADVANCE_LINK'}; Assert $threw 'settlement cannot link missing advance'
$script:TimelineRoot=$oldRoot
Write-Output "TOTAL $count"
