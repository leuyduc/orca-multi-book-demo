param([switch]$Library)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
function Field($Object,[string]$Name) {
    if ($null -eq $Object -or $null -eq $Object.PSObject.Properties[$Name]) { return '' }
    return [string]$Object.$Name
}
function Resolve-FixtureProject($Projects,[string]$Entity,[string]$BookId) {
    $candidates=@($Projects | Where-Object { (Field $_ 'LEGAL_ENTITY_ID') -ceq $Entity -and (Field $_ 'BOOK_ID') -ceq $BookId -and (Field $_ 'STATUS') -ceq 'DU_THAO_GIA' })
    if ($candidates.Count -ne 1 -or [string]::IsNullOrWhiteSpace((Field $candidates[0] 'PROJECT_ID'))) { return '' }
    return (Field $candidates[0] 'PROJECT_ID')
}
function Test-Registry($Ticket,$Books,$SourceBooks,$Projects) {
    $problems=[Collections.Generic.List[string]]::new()
    foreach($field in @('JOB_ID','LEGAL_ENTITY_ID','BRANCH_ID','BOOK_ID','PERIOD','PROJECT_ID','SOURCE_SNAPSHOT_ID','ACTION','PERMISSION_SCOPE','EXPECTED_OUTPUT','REVIEWER')) {
        if ([string]::IsNullOrWhiteSpace((Field $Ticket $field))) { $problems.Add("MISSING_JOB_$field") }
    }
    if ((Field $Ticket 'ACTION') -cne 'REVIEW_DEMO_REGISTRY' -or (Field $Ticket 'PERMISSION_SCOPE') -cne 'SYNTHETIC_ONLY') { $problems.Add('UNSAFE_JOB_SCOPE') }
    $bookId=Field $Ticket 'BOOK_ID'; $matches=@($Books | Where-Object { (Field $_ 'BOOK_ID') -ceq $bookId })
    $sourceMatches=@($SourceBooks | Where-Object { (Field $_ 'BOOK_ID') -ceq $bookId })
    if ($matches.Count -ne 1) { $problems.Add('BOOK_NOT_UNIQUE_IN_STAGING') }
    if ($sourceMatches.Count -ne 1) { $problems.Add('BOOK_NOT_UNIQUE_IN_SOURCE') }
    if ($matches.Count -eq 1) {
        $book=$matches[0]
        foreach($field in @('BOOK_ID','LEGAL_ENTITY_ID','BRANCH_ID','PERIOD','BOOK_KIND','SOURCE_SYSTEM','READ_SCOPE','WRITE_SCOPE','STATUS')) {
            if ([string]::IsNullOrWhiteSpace((Field $book $field))) { $problems.Add("MISSING_BOOK_$field") }
        }
        foreach($field in @('LEGAL_ENTITY_ID','BRANCH_ID','PERIOD')) {
            if ((Field $book $field) -cne (Field $Ticket $field)) { $problems.Add("MISMATCH_BOOK_$field") }
        }
        if ((Field $book 'READ_SCOPE') -cne 'SYNTHETIC_ONLY' -or (Field $book 'WRITE_SCOPE') -cne 'NONE') { $problems.Add('UNSAFE_BOOK_SCOPE') }
        if ($sourceMatches.Count -eq 1) {
            foreach($field in @('BOOK_ID','LEGAL_ENTITY_ID','BRANCH_ID','PERIOD','BOOK_KIND','SOURCE_SYSTEM','READ_SCOPE','WRITE_SCOPE','STATUS')) {
                if ((Field $book $field) -cne (Field $sourceMatches[0] $field)) { $problems.Add("SOURCE_MISMATCH_$field") }
            }
        }
    }
    $projectId=Field $Ticket 'PROJECT_ID'; $projectMatches=@($Projects | Where-Object { (Field $_ 'PROJECT_ID') -ceq $projectId })
    if ($projectMatches.Count -ne 1) { $problems.Add('PROJECT_NOT_UNIQUE_OR_MISSING') }
    else {
        foreach($field in @('LEGAL_ENTITY_ID','BOOK_ID')) {
            if ((Field $projectMatches[0] $field) -cne (Field $Ticket $field)) { $problems.Add("MISMATCH_PROJECT_$field") }
        }
        if ((Field $projectMatches[0] 'STATUS') -cne 'DU_THAO_GIA') { $problems.Add('PROJECT_NOT_SYNTHETIC_DRAFT') }
    }
    [pscustomobject]@{status=if($problems.Count){'BLOCKED'}else{'VERIFIED_DEMO'}; problems=@($problems.ToArray() | Sort-Object -Unique)}
}
if (-not $Library) {
    $root=Split-Path $PSScriptRoot -Parent
    $books=@(Import-Csv "$root/input/books.csv"); $source=@(Import-Csv "$root/../../data_gia/books.csv"); $projects=@(Import-Csv "$root/input/projects.csv")
    $project=Resolve-FixtureProject $projects 'DEMO_A' 'DEMO-A-CASH-2026'
    $ticket=[pscustomobject]@{JOB_ID='M1-REG-A-001';LEGAL_ENTITY_ID='DEMO_A';BRANCH_ID='NA';BOOK_ID='DEMO-A-CASH-2026';PERIOD='2026-11';PROJECT_ID=$project;SOURCE_SNAPSHOT_ID='SYN_A_001';ACTION='REVIEW_DEMO_REGISTRY';PERMISSION_SCOPE='SYNTHETIC_ONLY';EXPECTED_OUTPUT='DANH_MUC_NHAP_A';REVIEWER='OWNER'}
    $result=Test-Registry $ticket $books $source $projects
    $matched=@($books | Where-Object { (Field $_ 'BOOK_ID') -ceq 'DEMO-A-CASH-2026' })
    $missing=@(foreach($field in @('FISCAL_YEAR','SOURCE_REF','OWNER','LAST_SNAPSHOT')) { if($matched.Count -ne 1 -or [string]::IsNullOrWhiteSpace((Field $matched[0] $field))){$field} })
    [pscustomobject]@{identity_status=$result.status;problems=$result.problems;ticket_project_label='DEMO_PROJECT_A';fixture_project_id=$project;metadata_status=if($missing.Count){'INCOMPLETE_UNCLASSIFIED'}else{'PRESENT_NOT_INDEPENDENTLY_VERIFIED'};missing_metadata=$missing} | ConvertTo-Json -Depth 5
}
