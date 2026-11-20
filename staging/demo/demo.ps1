param([string]$BookId, [switch]$Library)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$script:Root = $PSScriptRoot

function Get-SafeId([string]$Value) {
    if ($Value -notmatch '^DEMO-[A-Z0-9-]+$') { throw 'INVALID_DEMO_ID' }
    return $Value
}
function Test-Job($Job, $Books) {
    $errors = [System.Collections.Generic.List[string]]::new()
    foreach ($field in @('JOB_ID','BOOK_ID','LEGAL_ENTITY_ID','BRANCH_ID','PERIOD','SOURCE_SNAPSHOT_ID','TRANSACTION_ID','VERSION','ACTION','PERMISSION_SCOPE','EXPECTED_OUTPUT','REVIEWER')) {
        if (-not $Job.$field) { $errors.Add("MISSING_$field") }
    }
    $matched = @($Books | Where-Object BOOK_ID -EQ $Job.BOOK_ID)
    if ($matched.Count -ne 1) { $errors.Add('UNKNOWN_OR_AMBIGUOUS_BOOK') }
    else {
        foreach ($field in @('LEGAL_ENTITY_ID','BRANCH_ID','PERIOD')) {
            if ($Job.$field -cne $matched[0].$field) { $errors.Add("MISMATCH_$field") }
        }
        if ($matched[0].READ_SCOPE -cne 'SYNTHETIC_ONLY' -or $matched[0].WRITE_SCOPE -cne 'NONE') { $errors.Add('UNSAFE_SCOPE') }
    }
    if ($Job.ACTION -cnotin @('RECONCILE_READ_ONLY','GENERATE_REPORT_OFFLINE','VALIDATE_SYNTHETIC')) { $errors.Add('ACTION_NOT_ALLOWED') }
    if ($Job.PERMISSION_SCOPE -cne 'SYNTHETIC_ONLY') { $errors.Add('UNSAFE_JOB_SCOPE') }
    return $errors.ToArray()
}
function Invoke-DemoBook([string]$Id) {
    $Id = Get-SafeId $Id
    $books = @(Import-Csv (Join-Path $script:Root 'input/books.csv'))
    $jobs = @(Import-Csv (Join-Path $script:Root 'input/queue.csv') | Where-Object BOOK_ID -CEQ $Id)
    $bookMatches = @($books | Where-Object BOOK_ID -CEQ $Id)
    if ($bookMatches.Count -ne 1) { throw 'UNKNOWN_OR_AMBIGUOUS_BOOK' }
    $bookJson = $bookMatches[0] | ConvertTo-Json -Compress
    $sha = [Security.Cryptography.SHA256]::Create()
    try { $bookFingerprint = ([BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($bookJson)))).Replace('-','') } finally { $sha.Dispose() }
    $path = Join-Path $script:Root "checkpoints/$Id.json"
    $lockPath = Join-Path $script:Root "checkpoints/$Id.lock"
    $lock = [IO.File]::Open($lockPath, 'OpenOrCreate', 'ReadWrite', 'None')
    try {
        $checkpoint = if (Test-Path $path) { Get-Content -Raw -Encoding UTF8 $path | ConvertFrom-Json } else { [pscustomobject]@{book_id=$Id; results=@()} }
        if ($checkpoint.book_id -cne $Id) { throw 'CHECKPOINT_SCOPE_MISMATCH' }
        $results = [System.Collections.Generic.List[object]]::new()
        foreach ($old in $checkpoint.results) { $results.Add($old) }
        foreach ($old in $results) {
            if (-not $old.PSObject.Properties['book_fingerprint'] -or -not $old.book_fingerprint) { throw 'LEGACY_CHECKPOINT_REQUIRES_REVALIDATION' }
            if ($old.book_fingerprint -cne $bookFingerprint) { throw 'REGISTRY_CHANGED_SINCE_CHECKPOINT' }
            $current = @($jobs | Where-Object JOB_ID -CEQ $old.job_id)
            if ($current.Count -ne 1 -or ($current[0] | ConvertTo-Json -Compress) -cne $old.fingerprint) { throw 'JOB_CHANGED_SINCE_CHECKPOINT' }
            if ($old.status -ceq 'VERIFIED' -and @(Test-Job $current[0] $books).Count) { throw 'JOB_NO_LONGER_VALID' }
        }
        foreach ($job in $jobs) {
            $errors = @(Test-Job $job $books)
            $prior = @($results | Where-Object job_id -CEQ $job.JOB_ID)
            $fingerprint = ($job | ConvertTo-Json -Compress)
            if ($prior.Count) {
                if ($prior.Count -ne 1 -or $prior[0].fingerprint -cne $fingerprint) { throw 'JOB_CHANGED_SINCE_CHECKPOINT' }
                continue
            }
            if (@($results | Where-Object { $_.job_id -cne $job.JOB_ID -and $_.intent -ceq "$($job.BOOK_ID)|$($job.TRANSACTION_ID)|$($job.VERSION)|$($job.ACTION)" -and $_.status -ceq 'VERIFIED' }).Count) { $errors += 'DUPLICATE_INTENT' }
            $status = if ($errors.Count) { 'BLOCKED' } else { 'VERIFIED' }
            $results.Add([pscustomobject]@{job_id=$job.JOB_ID; book_id=$Id; period=$job.PERIOD; snapshot=$job.SOURCE_SNAPSHOT_ID; intent="$($job.BOOK_ID)|$($job.TRANSACTION_ID)|$($job.VERSION)|$($job.ACTION)"; fingerprint=$fingerprint; book_fingerprint=$bookFingerprint; status=$status; errors=@($errors)})
            $newState = [pscustomobject]@{book_id=$Id; results=@($results.ToArray())}
            $tmp = "$path.tmp"
            $newState | ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 $tmp
            if (Test-Path $path) {
                $backup = "$path.bak"
                if (Test-Path $backup) { Remove-Item -LiteralPath $backup -Force }
                [IO.File]::Replace($tmp,$path,$backup)
                Remove-Item -LiteralPath $backup -Force
            } else { [IO.File]::Move($tmp,$path) }
        }
        return $results.ToArray()
    } finally { $lock.Dispose() }
}
if (-not $Library) {
    if (-not $BookId) { throw 'BookId required' }
    Invoke-DemoBook $BookId | ConvertTo-Json -Depth 8
}
