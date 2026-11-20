param([string]$BookId, [switch]$Library)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$script:TimelineRoot=$PSScriptRoot

function Get-TimelineHash($Object) {
    $json=$Object | ConvertTo-Json -Compress
    $sha=[Security.Cryptography.SHA256]::Create()
    try { return ([BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($json)))).Replace('-','') } finally { $sha.Dispose() }
}
function Get-ProjectHash($Projects,$Event,$BookId) {
    $matched=@($Projects | Where-Object { $_.PROJECT_ID -ceq $Event.PROJECT_ID })
    if ($matched.Count -ne 1 -or $matched[0].BOOK_ID -cne $BookId -or $matched[0].LEGAL_ENTITY_ID -cne $Event.LEGAL_ENTITY_ID -or $matched[0].STATUS -cne 'DU_THAO_GIA') { throw 'MISMATCH_PROJECT' }
    return Get-TimelineHash $matched[0]
}
function Get-MaterialTotals($Rows) {
    foreach($row in $Rows) { if (-not $row.UNIT -or -not $row.ITEM -or $row.QUANTITY -lt 0) { throw 'INVALID_MATERIAL' } }
    foreach($group in @($Rows | Group-Object ITEM,UNIT)) {
        [pscustomobject]@{item=$group.Group[0].ITEM; unit=$group.Group[0].UNIT; quantity=($group.Group | Measure-Object QUANTITY -Sum).Sum}
    }
}
function Test-DemoApproval($Request,$Approval) {
    if ($Approval.PERSON -cne $Request.PERSON -or $Approval.DOCUMENT -cne $Request.DOCUMENT -or $Approval.BOOK_ID -cne $Request.BOOK_ID -or $Approval.PERIOD -cne $Request.PERIOD -or $Approval.ACTION -cne $Request.ACTION -or $Approval.AUTHORIZED -cne 'YES') { return 'NEEDS_REVIEW' }
    return 'APPROVED_DEMO'
}
function New-DemoCrossBookLink($Left,$Right,$Evidence) {
    if ($Left.book_id -ceq $Right.book_id -or -not $Evidence -or $Left.amount -ne $Right.amount -or $Left.period -cne $Right.period) { throw 'INVALID_CROSS_BOOK_LINK' }
    return [pscustomobject]@{left_book=$Left.book_id;left_tx=$Left.transaction_id;right_book=$Right.book_id;right_tx=$Right.transaction_id;amount=$Left.amount;evidence=$Evidence;status='NEEDS_REVIEW'}
}
function Invoke-Timeline([string]$BookId, [int]$MaxNew=2147483647) {
    if ($BookId -cnotmatch '^DEMO-[A-Z0-9-]+$') { throw 'INVALID_BOOK' }
    $books=@(Import-Csv "$script:TimelineRoot/input/books.csv" | Where-Object BOOK_ID -CEQ $BookId)
    if ($books.Count -ne 1 -or $books[0].READ_SCOPE -cne 'SYNTHETIC_ONLY' -or $books[0].WRITE_SCOPE -cne 'NONE') { throw 'INVALID_BOOK_SCOPE' }
    $book=$books[0]
    $bookHash=Get-TimelineHash $book
    $projects=@(Import-Csv "$script:TimelineRoot/input/projects.csv")
    $events=@(Import-Csv "$script:TimelineRoot/input/evidence.csv" | Where-Object BOOK_ID -CEQ $BookId)
    $path="$script:TimelineRoot/checkpoints/timeline-$BookId.json"
    $lock=[IO.File]::Open("$script:TimelineRoot/checkpoints/timeline-$BookId.lock",'OpenOrCreate','ReadWrite','None')
    try {
        $state=if (Test-Path $path) { Get-Content -Raw -Encoding UTF8 $path | ConvertFrom-Json } else { [pscustomobject]@{schema_version=2; book_id=$BookId; period=$book.PERIOD; book_fingerprint=$bookHash; records=@(); transactions=@()} }
        if ($state.book_id -cne $BookId -or $state.period -cne $book.PERIOD) { throw 'CHECKPOINT_SCOPE_MISMATCH' }
        if (-not $state.PSObject.Properties['schema_version'] -or $state.schema_version -ne 2) { throw 'LEGACY_TIMELINE_REQUIRES_REVALIDATION' }
        if (-not $state.PSObject.Properties['book_fingerprint'] -or -not $state.book_fingerprint) { throw 'LEGACY_TIMELINE_REQUIRES_REVALIDATION' }
        if ($state.book_fingerprint -cne $bookHash) { throw 'REGISTRY_CHANGED_SINCE_CHECKPOINT' }
        $records=[Collections.Generic.List[object]]::new(); foreach($r in $state.records){$records.Add($r)}
        $transactions=[Collections.Generic.List[object]]::new(); foreach($t in $state.transactions){$transactions.Add($t)}
        $ids=@{}; foreach($e in $events) { if($ids.ContainsKey($e.RECORD_ID)) { throw 'DUPLICATE_RECORD_ID' }; $ids[$e.RECORD_ID]=$true }
        foreach($r in $records) {
            if(-not $ids.ContainsKey($r.record_id)) { throw 'SOURCE_REMOVED' }
            $current=@($events | Where-Object RECORD_ID -CEQ $r.record_id)
            if ($current.Count -ne 1 -or ($current[0] | ConvertTo-Json -Compress) -cne $r.fingerprint) { throw 'SOURCE_CHANGED' }
            if (-not $r.PSObject.Properties['project_fingerprint'] -or -not $r.project_fingerprint) { throw 'LEGACY_TIMELINE_REQUIRES_REVALIDATION' }
            if ((Get-ProjectHash $projects $current[0] $BookId) -cne $r.project_fingerprint) { throw 'PROJECT_CHANGED_SINCE_CHECKPOINT' }
        }
        $count=0
        foreach($e in $events) {
            $fingerprint=$e | ConvertTo-Json -Compress
            $prior=@($records | Where-Object record_id -CEQ $e.RECORD_ID)
            if ($prior.Count) { if ($prior.Count -ne 1 -or $prior[0].fingerprint -cne $fingerprint) { throw 'SOURCE_CHANGED' }; continue }
            if ($count -ge $MaxNew) { break }
            if ($e.RECORD_ID -cnotmatch '^DEMO-R-[A-Z0-9-]+$' -or $e.TRANSACTION_ID -cnotmatch '^DEMO-T-[A-Z0-9-]+$' -or $e.RAW_SHA256 -cnotmatch '^[a-f0-9]{64}$') { throw 'INVALID_RECORD' }
            if ($e.LEGAL_ENTITY_ID -cne $book.LEGAL_ENTITY_ID -or $e.BRANCH_ID -cne $book.BRANCH_ID -or $e.PERIOD -cne $book.PERIOD) { throw 'MISMATCH_SCOPE' }
            $projectHash=Get-ProjectHash $projects $e $BookId
            if ($e.EVIDENCE_REF -cnotmatch '^DEMO-E-[A-Z0-9-]+$' -or $e.KIND -cnotin @('PAYMENT','BILL','ADVANCE','SETTLEMENT')) { throw 'INVALID_EVIDENCE' }
            $d=[datetime]::MinValue
            if (-not [datetime]::TryParseExact($e.SOURCE_DATE,'yyyy-MM-dd',[Globalization.CultureInfo]::InvariantCulture,[Globalization.DateTimeStyles]::None,[ref]$d)) { throw 'INVALID_SOURCE_DATE' }
            if (-not [datetime]::TryParseExact($e.TRANSACTION_DATE,'yyyy-MM-dd',[Globalization.CultureInfo]::InvariantCulture,[Globalization.DateTimeStyles]::None,[ref]$d) -or $e.TRANSACTION_DATE.Substring(0,7) -cne $book.PERIOD) { throw 'INVALID_TRANSACTION_DATE' }
            $amount=[decimal]0
            if (-not [decimal]::TryParse($e.AMOUNT,[Globalization.NumberStyles]::AllowDecimalPoint,[Globalization.CultureInfo]::InvariantCulture,[ref]$amount) -or $amount -le 0) { throw 'INVALID_AMOUNT' }
            $dups=@($records | Where-Object raw_sha256 -CEQ $e.RAW_SHA256)
            $txs=@($transactions | Where-Object transaction_id -CEQ $e.TRANSACTION_ID)
            $refs=@($transactions | Where-Object evidence_ref -CEQ $e.EVIDENCE_REF)
            if ($dups.Count -and @($dups | Where-Object { $_.transaction_id -cne $e.TRANSACTION_ID -or $_.evidence_ref -cne $e.EVIDENCE_REF -or $_.kind -cne $e.KIND -or $_.amount -ne $amount }).Count) { throw 'CONFLICTING_DUPLICATE' }
            if ($refs.Count -and $refs[0].transaction_id -cne $e.TRANSACTION_ID) { throw 'EVIDENCE_REF_CONFLICT' }
            if ($txs.Count -and ($txs[0].evidence_ref -cne $e.EVIDENCE_REF -or $txs[0].amount -ne $amount)) { throw 'TRANSACTION_EVIDENCE_CONFLICT' }
            if (-not $txs.Count) {
                $tx=[pscustomobject]@{transaction_id=$e.TRANSACTION_ID; evidence_ref=$e.EVIDENCE_REF; amount=$amount; amount_out=[decimal]0; settled_cost=[decimal]0; related_advance_id=''; kinds=@(); record_ids=@()}
                $transactions.Add($tx)
            } else { $tx=$txs[0] }
            $advanceId=if($e.PSObject.Properties['RELATED_ADVANCE_ID']){[string]$e.RELATED_ADVANCE_ID}else{''}
            if ($advanceId) {
                if ($e.KIND -cne 'SETTLEMENT' -or $advanceId -ceq $e.TRANSACTION_ID) {throw 'INVALID_ADVANCE_LINK'}
                $advance=@($transactions | Where-Object { $_.transaction_id -ceq $advanceId -and $_.kinds -ccontains 'ADVANCE' })
                $advanceEvents=@($events | Where-Object { $_.TRANSACTION_ID -ceq $advanceId -and $_.PROJECT_ID -ceq $e.PROJECT_ID -and $_.KIND -ceq 'ADVANCE' })
                if ($advance.Count -ne 1 -or $advanceEvents.Count -lt 1) {throw 'INVALID_ADVANCE_LINK'}
                if ($tx.related_advance_id -and $tx.related_advance_id -cne $advanceId) {throw 'INVALID_ADVANCE_LINK'}
                $tx.related_advance_id=$advanceId
            } elseif ($dups.Count -and $tx.related_advance_id) {throw 'CONFLICTING_DUPLICATE'}
            $duplicateOf=if($dups.Count){$dups[0].record_id}else{''}
            if (-not $duplicateOf) {
                if ($e.KIND -in @('PAYMENT','ADVANCE')) {
                    if (@($tx.kinds | Where-Object { $_ -in @('PAYMENT','ADVANCE') }).Count) { throw 'MULTIPLE_CASH_OUT' }
                    $tx.amount_out=$amount
                }
                if ($e.KIND -ceq 'SETTLEMENT') { if (@($tx.kinds | Where-Object { $_ -ceq 'SETTLEMENT' }).Count) { throw 'MULTIPLE_SETTLEMENT' }; $tx.settled_cost=$amount }
                $tx.kinds=@($tx.kinds)+@($e.KIND)
            }
            $tx.record_ids=@($tx.record_ids)+@($e.RECORD_ID)
            $records.Add([pscustomobject]@{record_id=$e.RECORD_ID; transaction_id=$e.TRANSACTION_ID; evidence_ref=$e.EVIDENCE_REF; raw_sha256=$e.RAW_SHA256; kind=$e.KIND; amount=$amount; source_date=$e.SOURCE_DATE; transaction_date=$e.TRANSACTION_DATE; duplicate_of=$duplicateOf; fingerprint=$fingerprint; project_fingerprint=$projectHash})
            $new=[pscustomobject]@{schema_version=2; book_id=$BookId; period=$book.PERIOD; book_fingerprint=$bookHash; records=@($records.ToArray()); transactions=@($transactions.ToArray())}
            $tmp="$path.tmp"; $backup="$path.bak"; $new | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $tmp
            if (Test-Path $path) { if(Test-Path $backup){Remove-Item -LiteralPath $backup -Force}; [IO.File]::Replace($tmp,$path,$backup); Remove-Item -LiteralPath $backup -Force } else { [IO.File]::Move($tmp,$path) }
            $count++
        }
        return [pscustomobject]@{book_id=$BookId; period=$book.PERIOD; records=@($records.ToArray()); transactions=@($transactions.ToArray())}
    } finally { $lock.Dispose() }
}
if (-not $Library) { if(-not $BookId){throw 'BookId required'}; Invoke-Timeline $BookId | ConvertTo-Json -Depth 10 }
