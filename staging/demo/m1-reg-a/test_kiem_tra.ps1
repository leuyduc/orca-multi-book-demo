$ErrorActionPreference='Stop'
. "$PSScriptRoot/kiem_tra.ps1" -Library
$root=Split-Path $PSScriptRoot -Parent
$books=@(Import-Csv "$root/input/books.csv"); $source=@(Import-Csv "$root/../../data_gia/books.csv"); $projects=@(Import-Csv "$root/input/projects.csv")
$ticket=[pscustomobject]@{JOB_ID='M1-REG-A-001';LEGAL_ENTITY_ID='DEMO_A';BRANCH_ID='NA';BOOK_ID='DEMO-A-CASH-2026';PERIOD='2026-11';PROJECT_ID='DEMO_PROJECT_A';SOURCE_SNAPSHOT_ID='SYN_A_001';ACTION='REVIEW_DEMO_REGISTRY';PERMISSION_SCOPE='SYNTHETIC_ONLY';EXPECTED_OUTPUT='DANH_MUC_NHAP_A';REVIEWER='OWNER'}
$script:count=0
function Assert($Condition,$Label){ if(-not $Condition){throw "FAIL $Label"}; $script:count++; Write-Output "PASS $Label" }
$actual=Test-Registry $ticket $books $source $projects
Assert ($actual.status -eq 'BLOCKED' -and $actual.problems -contains 'PROJECT_NOT_UNIQUE_OR_MISSING') 'ticket label remains distinct from fixture ID'
$selected=Resolve-FixtureProject $projects 'DEMO_A' 'DEMO-A-CASH-2026'
Assert ($selected -ceq 'DEMO-PROJECT-A') 'fixture project selected by entity book and draft status'
$reference=$ticket.PSObject.Copy(); $reference.PROJECT_ID=$selected
$result=Test-Registry $reference $books $source $projects
Assert ($result.status -eq 'VERIFIED_DEMO') 'approved fixture ID verifies scoped synthetic identity'
$extra=[pscustomobject]@{PROJECT_ID='DEMO-PROJECT-OTHER';LEGAL_ENTITY_ID='DEMO_A';BOOK_ID='DEMO-A-CASH-2026';STATUS='DU_THAO_GIA'}
Assert ((Resolve-FixtureProject (@($projects)+@($extra)) 'DEMO_A' 'DEMO-A-CASH-2026') -ceq '') 'ambiguous project candidates not selected'
Assert ((Resolve-FixtureProject @() 'DEMO_A' 'DEMO-A-CASH-2026') -ceq '') 'missing project candidate not selected'
foreach($field in @('JOB_ID','LEGAL_ENTITY_ID','BRANCH_ID','BOOK_ID','PERIOD','PROJECT_ID','SOURCE_SNAPSHOT_ID','ACTION','PERMISSION_SCOPE','EXPECTED_OUTPUT','REVIEWER')) {
    $bad=$reference.PSObject.Copy(); $bad.$field=''; $out=Test-Registry $bad $books $source $projects
    Assert ($out.status -eq 'BLOCKED' -and $out.problems -contains "MISSING_JOB_$field") "missing $field blocked"
}
$book=@($books | Where-Object BOOK_ID -CEQ 'DEMO-A-CASH-2026')[0]
$out=Test-Registry $reference (@($books)+@($book)) $source $projects
Assert ($out.problems -contains 'BOOK_NOT_UNIQUE_IN_STAGING') 'duplicate staging book blocked'
$src=@($source | Where-Object BOOK_ID -CEQ 'DEMO-A-CASH-2026')[0]
$out=Test-Registry $reference $books (@($source)+@($src)) $projects
Assert ($out.problems -contains 'BOOK_NOT_UNIQUE_IN_SOURCE') 'duplicate source book blocked'
$project=@($projects | Where-Object PROJECT_ID -CEQ 'DEMO-PROJECT-A')[0]
$out=Test-Registry $reference $books $source (@($projects)+@($project))
Assert ($out.problems -contains 'PROJECT_NOT_UNIQUE_OR_MISSING') 'duplicate project blocked'
$wrong=$book.PSObject.Copy(); $wrong.PERIOD='2026-10'; $modified=@($books | Where-Object BOOK_ID -CNE 'DEMO-A-CASH-2026')+@($wrong)
$out=Test-Registry $reference $modified $source $projects
Assert (($out.problems -contains 'MISMATCH_BOOK_PERIOD') -and ($out.problems -contains 'SOURCE_MISMATCH_PERIOD')) 'wrong period and drift blocked'
$wrong=$project.PSObject.Copy(); $wrong.LEGAL_ENTITY_ID='DEMO_WRONG'; $modified=@($projects | Where-Object PROJECT_ID -CNE 'DEMO-PROJECT-A')+@($wrong)
$out=Test-Registry $reference $books $source $modified
Assert ($out.problems -contains 'MISMATCH_PROJECT_LEGAL_ENTITY_ID') 'wrong project entity blocked'
$wrong=$reference.PSObject.Copy(); $wrong.PERMISSION_SCOPE='LIVE'; $out=Test-Registry $wrong $books $source $projects
Assert ($out.problems -contains 'UNSAFE_JOB_SCOPE') 'live scope blocked'
Write-Output "TOTAL $script:count"
