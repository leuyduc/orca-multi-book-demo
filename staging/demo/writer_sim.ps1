param([switch]$Library)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$script:WriterRoot=$PSScriptRoot

function Get-WriterPath([string]$BookId) {
    if ($BookId -cnotmatch '^DEMO-[A-Z0-9-]+$') { throw 'INVALID_BOOK' }
    return "$script:WriterRoot/writer-state/$BookId.json"
}
function Save-WriterState($Path,$State) {
    $tmp="$Path.tmp"; $bak="$Path.bak"
    $State | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $tmp
    if (Test-Path $Path) { if(Test-Path $bak){Remove-Item -LiteralPath $bak -Force}; [IO.File]::Replace($tmp,$Path,$bak); Remove-Item -LiteralPath $bak -Force } else { [IO.File]::Move($tmp,$Path) }
}
function Initialize-Writer($BookId,$Entity,$Period) {
    $path=Get-WriterPath $BookId
    if (Test-Path $path) { throw 'ALREADY_INITIALIZED' }
    Save-WriterState $path ([pscustomobject]@{book_id=$BookId;entity=$Entity;period=$Period;version=0;rows=@();intents=@();pending=@()})
}
function Invoke-SyntheticWrite($Request,[switch]$LoseResponse) {
    $path=Get-WriterPath $Request.BOOK_ID
    $lock=[IO.File]::Open("$path.lock",'OpenOrCreate','ReadWrite','None')
    try {
        if (-not (Test-Path $path)) { throw 'UNKNOWN_BOOK' }
        $state=Get-Content -Raw -Encoding UTF8 $path | ConvertFrom-Json
        if ($state.book_id -cne $Request.BOOK_ID -or $state.entity -cne $Request.LEGAL_ENTITY_ID -or $state.period -cne $Request.PERIOD) { throw 'SCOPE_MISMATCH' }
        if ($Request.KEY -cnotmatch '^DEMO-K-[A-Z0-9-]+$' -or $Request.TX -cnotmatch '^DEMO-T-[A-Z0-9-]+$' -or [decimal]$Request.AMOUNT -le 0) { throw 'INVALID_REQUEST' }
        $intent="$($Request.BOOK_ID)|$($Request.PERIOD)|$($Request.TX)|$($Request.AMOUNT)"
        $pending=@($state.pending | Where-Object key -CEQ $Request.KEY)
        if ($pending.Count -and ($pending.Count -ne 1 -or $pending[0].intent -cne $intent)) { throw 'PENDING_INTENT_CONFLICT' }
        if ($Request.APPROVAL_BOOK -cne $state.book_id -or $Request.APPROVAL_PERIOD -cne $state.period -or $Request.APPROVAL_ACTION -cne 'SYNTHETIC_WRITE' -or $Request.APPROVED -cne 'YES') { return [pscustomobject]@{status='BLOCKED';reason='APPROVAL_SCOPE';version=$state.version} }
        $prior=@($state.intents | Where-Object key -CEQ $Request.KEY)
        if ($prior.Count) {
            if ($prior.Count -ne 1 -or $prior[0].intent -cne $intent) { throw 'IDEMPOTENCY_CONFLICT' }
            return [pscustomobject]@{status='ALREADY_APPLIED';version=$state.version}
        }
        if ($Request.QUOTA -cne 'AVAILABLE') {
            if (-not $pending.Count) {
                $state.pending=@($state.pending)+@([pscustomobject]@{key=$Request.KEY;intent=$intent;status='QUEUED';reason='QUOTA'})
                Save-WriterState $path $state
            }
            return [pscustomobject]@{status='QUEUED';reason='QUOTA';version=$state.version}
        }
        if ([int]$Request.EXPECTED_VERSION -ne [int]$state.version) { return [pscustomobject]@{status='BLOCKED';reason='VERSION_CONFLICT';version=$state.version} }
        if (@($state.rows | Where-Object tx -CEQ $Request.TX).Count) { return [pscustomobject]@{status='BLOCKED';reason='DUPLICATE_TRANSACTION';version=$state.version} }
        $state.rows=@($state.rows)+@([pscustomobject]@{tx=$Request.TX;amount=[decimal]$Request.AMOUNT})
        $state.intents=@($state.intents)+@([pscustomobject]@{key=$Request.KEY;intent=$intent})
        $state.pending=@($state.pending | Where-Object key -CNE $Request.KEY)
        $state.version=[int]$state.version+1
        Save-WriterState $path $state
        if ($LoseResponse) { throw 'SIMULATED_RESPONSE_LOST_AFTER_COMMIT' }
        return [pscustomobject]@{status='APPLIED';version=$state.version}
    } finally { $lock.Dispose() }
}
function Sort-SyntheticRows($Rows) {
    $ids=@{}; foreach($row in $Rows) { if(-not $row.ID -or $ids.ContainsKey($row.ID)) {throw 'INVALID_ROW_ID'}; $ids[$row.ID]=$true }
    return @($Rows | Sort-Object DATE,ID)
}
