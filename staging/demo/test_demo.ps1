$ErrorActionPreference = 'Stop'
. "$PSScriptRoot/demo.ps1" -Library
$script:Root = Join-Path $PSScriptRoot 'test-sandbox'
New-Item -ItemType Directory -Force "$script:Root/input", "$script:Root/checkpoints" | Out-Null
Copy-Item "$PSScriptRoot/input/books.csv" "$script:Root/input/books.csv" -Force
Copy-Item "$PSScriptRoot/input/queue.csv" "$script:Root/input/queue.csv" -Force
Get-ChildItem "$script:Root/checkpoints" -File | Remove-Item -Force
$count = 0
function Assert($Condition, $Message) { if (-not $Condition) { throw "FAIL: $Message" }; $script:count++; Write-Output "PASS $Message" }
$books = @(Import-Csv "$script:Root/input/books.csv")
$jobs = @(Import-Csv "$script:Root/input/queue.csv")
Assert (@(Test-Job $jobs[0] $books).Count -eq 0) 'valid synthetic job'
$bad = $jobs[0].PSObject.Copy(); $bad.LEGAL_ENTITY_ID='DEMO_B'
Assert (@(Test-Job $bad $books) -contains 'MISMATCH_LEGAL_ENTITY_ID') 'wrong entity blocked'
$bad = $jobs[1].PSObject.Copy(); $bad.BRANCH_ID='NA'; $bad.PERIOD='2026-10'
$errors = @(Test-Job $bad $books)
Assert (($errors -contains 'MISMATCH_BRANCH_ID') -and ($errors -contains 'MISMATCH_PERIOD')) 'wrong branch and period blocked'
$bad = $jobs[0].PSObject.Copy(); $bad.SOURCE_SNAPSHOT_ID=''; $bad.ACTION='WRITE_LIVE'
$errors = @(Test-Job $bad $books)
Assert (($errors -contains 'MISSING_SOURCE_SNAPSHOT_ID') -and ($errors -contains 'ACTION_NOT_ALLOWED')) 'missing snapshot and live write blocked'
$first = @(Invoke-DemoBook 'DEMO-A-CASH-2026'); $second = @(Invoke-DemoBook 'DEMO-A-CASH-2026')
Assert (($first.Count -eq 1) -and ($second.Count -eq 1) -and ($second[0].status -eq 'VERIFIED')) 'resume does not append twice'
$other = @(Invoke-DemoBook 'DEMO-B-MISA-2026')
Assert (($other.Count -eq 1) -and ($other[0].book_id -eq 'DEMO-B-MISA-2026')) 'independent book checkpoint'
$pathA="$script:Root/checkpoints/DEMO-A-CASH-2026.json"
$originalCheckpoint=Get-Content -Raw -Encoding UTF8 $pathA
$legacy=Get-Content -Raw -Encoding UTF8 $pathA | ConvertFrom-Json
$legacy.results[0].PSObject.Properties.Remove('book_fingerprint')
$legacy | ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 $pathA
$threw=$false; try {Invoke-DemoBook 'DEMO-A-CASH-2026' | Out-Null} catch {$threw=$_.Exception.Message -match 'LEGACY_CHECKPOINT_REQUIRES_REVALIDATION'}
Assert $threw 'legacy checkpoint without registry fingerprint fails closed'
$originalCheckpoint | Set-Content -Encoding UTF8 $pathA
$fixtureBooks=@(Import-Csv "$script:Root/input/books.csv")
$changedBooks=@($fixtureBooks | ForEach-Object { $_.PSObject.Copy() })
($changedBooks | Where-Object BOOK_ID -CEQ 'DEMO-A-CASH-2026').PERIOD='2026-10'
$changedBooks | Export-Csv "$script:Root/input/books.csv" -NoTypeInformation -Encoding UTF8
$threw=$false; try {Invoke-DemoBook 'DEMO-A-CASH-2026' | Out-Null} catch {$threw=$_.Exception.Message -match 'REGISTRY_CHANGED_SINCE_CHECKPOINT'}
Assert $threw 'changed registry scope refuses old verified result'
$other=@(Invoke-DemoBook 'DEMO-B-MISA-2026'); Assert ($other[0].status -eq 'VERIFIED') 'changed A registry does not block B'
$changedBooks=@($fixtureBooks | ForEach-Object { $_.PSObject.Copy() })
($changedBooks | Where-Object BOOK_ID -CEQ 'DEMO-B-MISA-2026').SOURCE_SYSTEM='SYNTHETIC_OTHER'
$changedBooks | Export-Csv "$script:Root/input/books.csv" -NoTypeInformation -Encoding UTF8
$threw=$false; try {Invoke-DemoBook 'DEMO-B-MISA-2026' | Out-Null} catch {$threw=$_.Exception.Message -match 'REGISTRY_CHANGED_SINCE_CHECKPOINT'}
Assert $threw 'registry change without scope mismatch is detected'
$first=@(Invoke-DemoBook 'DEMO-A-CASH-2026'); Assert ($first[0].status -eq 'VERIFIED') 'changed B registry does not block A'
$fixtureBooks | Export-Csv "$script:Root/input/books.csv" -NoTypeInformation -Encoding UTF8
@($jobs | Where-Object BOOK_ID -CEQ 'DEMO-B-MISA-2026') | Export-Csv "$script:Root/input/queue.csv" -NoTypeInformation -Encoding UTF8
$threw=$false; try {Invoke-DemoBook 'DEMO-A-CASH-2026' | Out-Null} catch {$threw=$_.Exception.Message -match 'JOB_CHANGED_SINCE_CHECKPOINT'}
Assert $threw 'removed job fails closed on resume'
$jobs | Export-Csv "$script:Root/input/queue.csv" -NoTypeInformation -Encoding UTF8
$duplicate = $jobs[0].PSObject.Copy(); $duplicate.JOB_ID='DEMO-J-003'
$sameOtherBook = $jobs[1].PSObject.Copy(); $sameOtherBook.JOB_ID='DEMO-J-004'; $sameOtherBook.TRANSACTION_ID=$jobs[0].TRANSACTION_ID
@($jobs) + @($duplicate,$sameOtherBook) | Export-Csv "$script:Root/input/queue.csv" -NoTypeInformation -Encoding UTF8
$aResults=@(Invoke-DemoBook 'DEMO-A-CASH-2026'); $bResults=@(Invoke-DemoBook 'DEMO-B-MISA-2026')
Assert (($aResults[-1].status -eq 'BLOCKED') -and ($aResults[-1].errors -contains 'DUPLICATE_INTENT')) 'same-book duplicate intent blocked'
Assert ($bResults[-1].status -eq 'VERIFIED') 'same transaction ID across books stays separate'
$jobs[0].PERIOD='2026-10'; @($jobs) + @($duplicate,$sameOtherBook) | Export-Csv "$script:Root/input/queue.csv" -NoTypeInformation -Encoding UTF8
$threw = $false; try { Invoke-DemoBook 'DEMO-A-CASH-2026' } catch { $threw = $_.Exception.Message -match 'JOB_CHANGED_SINCE_CHECKPOINT' }
Assert $threw 'changed job stopped on resume'
$lock = [IO.File]::Open("$script:Root/checkpoints/DEMO-A-CASH-2026.lock",'OpenOrCreate','ReadWrite','None')
try { $threw=$false; try { Invoke-DemoBook 'DEMO-A-CASH-2026' } catch { $threw=$true }; Assert $threw 'same book lock prevents concurrent writer'; $other=@(Invoke-DemoBook 'DEMO-B-MISA-2026'); Assert ($other[0].status -eq 'VERIFIED') 'book A lock does not block B' } finally { $lock.Dispose() }
$threw=$false; try { Invoke-DemoBook '../outside' } catch { $threw=$true }; Assert $threw 'unsafe path rejected'
Write-Output "TOTAL $count"
