[CmdletBinding()]
param([string]$BookId,[string]$WorkflowRoot,[switch]$Library)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$workflowLibrary=$Library; $workflowBook=$BookId; $workflowDirectory=$WorkflowRoot
. "$PSScriptRoot/demo.ps1" -Library
. "$PSScriptRoot/timeline.ps1" -Library
$script:WorkflowBase=$PSScriptRoot



function Assert-WorkflowInputGate([string]$Id,[string]$Directory) {
    # Production-like entry has NO unsealed regression switch.
    # This is still a DEMO and does not grant access to real books.
    $full=[IO.Path]::GetFullPath($Directory).TrimEnd('\')
    $stage=[IO.Path]::GetFullPath($script:WorkflowBase).TrimEnd('\')+'\'
    if(-not $full.StartsWith($stage,[StringComparison]::OrdinalIgnoreCase)) {throw 'WORKFLOW_OUTSIDE_DEMO'}
    $p=[IO.DirectoryInfo]::new($full)
    while($p -and $p.FullName.TrimEnd('\') -cne $script:WorkflowBase.TrimEnd('\')) {
        if(-not $p.Exists -or (($p.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0)) {throw 'WORKFLOW_REPARSE_POINT_FORBIDDEN'}
        $p=$p.Parent
    }
    if([IO.Path]::GetFileName($full) -cne $Id -or
       -not (Test-Path -LiteralPath "$full/p1_document.json") -or
       -not (Test-Path -LiteralPath "$full/p1-manifest/source_manifest.json")) {
        throw 'P1_SEALED_SNAPSHOT_REQUIRED'
    }
    $args=@("$($script:WorkflowBase)/p1-manifest/manifest_demo.py",'verify',
        '--document',"$full/p1_document.json",
        '--source-root',"$full/input",
        '--output-dir',"$full/p1-manifest")
    $result=& python @args
    if($LASTEXITCODE -ne 0 -or @($result).Count -ne 1) {throw 'P1_VERIFICATION_BLOCKED'}
    try { $proof=($result | ConvertFrom-Json -ErrorAction Stop) }
    catch { throw 'P1_VERIFICATION_BLOCKED' }
    if($proof.status -cne 'VERIFIED_SYNTHETIC_ONLY' -or $proof.live_authorized -ne $false) {throw 'P1_VERIFICATION_BLOCKED'}
}

function Invoke-SyntheticWorkflow([string]$Id,[string]$Directory,[string]$Quota='AVAILABLE',[string]$Fault='NONE') {
    $Id=Get-SafeId $Id
    $base=[IO.Path]::GetFullPath($script:WorkflowBase).TrimEnd('\')+'\'
    $dir=[IO.Path]::GetFullPath($Directory).TrimEnd('\')
    if (-not $dir.StartsWith($base,[StringComparison]::OrdinalIgnoreCase) -or -not (Test-Path -LiteralPath "$dir/input") -or -not (Test-Path -LiteralPath "$dir/checkpoints")) { throw 'INVALID_WORKFLOW_DIRECTORY' }
    Assert-WorkflowInputGate $Id $dir
    if ($Quota -cnotin @('AVAILABLE','EXHAUSTED') -or $Fault -cnotin @('NONE','AFTER_ROUTING','AFTER_TIMELINE','AFTER_FINAL')) {throw 'INVALID_SIMULATION_OPTION'}
    $script:Root=$dir; $script:TimelineRoot=$dir
    $books=@(Import-Csv "$dir/input/books.csv" | Where-Object BOOK_ID -CEQ $Id)
    $jobs=@(Import-Csv "$dir/input/queue.csv" | Where-Object BOOK_ID -CEQ $Id)
    if ($books.Count -ne 1 -or $jobs.Count -ne 1) { throw 'AMBIGUOUS_WORKFLOW_SCOPE' }
    $job=$jobs[0]; $book=$books[0]
    if (@(Test-Job $job $books).Count -or -not $job.PROJECT_ID) {throw 'INVALID_WORKFLOW_JOB'}
    $projects=@(Import-Csv "$dir/input/projects.csv" | Where-Object PROJECT_ID -CEQ $job.PROJECT_ID)
    if ($projects.Count -ne 1 -or $projects[0].BOOK_ID -cne $Id -or $projects[0].LEGAL_ENTITY_ID -cne $job.LEGAL_ENTITY_ID -or $projects[0].STATUS -cne 'DU_THAO_GIA') {throw 'INVALID_WORKFLOW_PROJECT'}
    $events=@(Import-Csv "$dir/input/evidence.csv" | Where-Object BOOK_ID -CEQ $Id)
    if (-not $events.Count -or @($events | Where-Object { $_.PROJECT_ID -cne $job.PROJECT_ID -or $_.LEGAL_ENTITY_ID -cne $job.LEGAL_ENTITY_ID -or $_.BRANCH_ID -cne $job.BRANCH_ID -or $_.PERIOD -cne $job.PERIOD }).Count) {throw 'INVALID_WORKFLOW_EVIDENCE_SCOPE'}
    $input=[pscustomobject]@{book=$book;job=$job;project=$projects[0];events=$events} | ConvertTo-Json -Compress -Depth 12
    $sha=[Security.Cryptography.SHA256]::Create(); try {$inputHash=([BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($input)))).Replace('-','')} finally {$sha.Dispose()}
    $checkpoint="$dir/checkpoints/workflow-$Id.json"; $lock=[IO.File]::Open("$dir/checkpoints/workflow-$Id.lock",'OpenOrCreate','ReadWrite','None')
    try {
        $state=if(Test-Path $checkpoint){Get-Content -Raw -Encoding UTF8 $checkpoint | ConvertFrom-Json}else{[pscustomobject]@{book_id=$Id;job_id=$job.JOB_ID;period=$job.PERIOD;snapshot_label=$job.SOURCE_SNAPSHOT_ID;input_fingerprint=$inputHash;status='QUEUED';record_count=0;transaction_count=0}}
        if ($state.book_id -cne $Id -or $state.job_id -cne $job.JOB_ID -or $state.period -cne $job.PERIOD -or $state.input_fingerprint -cne $inputHash) {throw 'WORKFLOW_INPUT_CHANGED'}
        if ($state.status -ceq 'VERIFIED') {
            if (-not (Test-Path "$dir/checkpoints/$Id.json") -or -not (Test-Path "$dir/checkpoints/timeline-$Id.json")) { throw 'WORKFLOW_CHECKPOINT_MISSING' }
            $routing=@(Invoke-DemoBook $Id); $timeline=Invoke-Timeline $Id
            if ($routing.Count -ne 1 -or $routing[0].status -cne 'VERIFIED' -or $timeline.records.Count -ne $state.record_count -or $timeline.transactions.Count -ne $state.transaction_count) {throw 'WORKFLOW_CHECKPOINT_MISMATCH'}
            return $state
        }
        if($Quota -ceq 'EXHAUSTED') { $state.status='QUEUED'; Save-WorkflowState $checkpoint $state; return $state }
        $routing=@(Invoke-DemoBook $Id)
        if($routing.Count -ne 1 -or $routing[0].status -cne 'VERIFIED') {throw 'ROUTING_BLOCKED'}
        $state.status='VALIDATING'; Save-WorkflowState $checkpoint $state
        if($Fault -ceq 'AFTER_ROUTING'){throw 'SIMULATED_INTERRUPT_AFTER_ROUTING'}
        $timeline=Invoke-Timeline $Id
        if($Fault -ceq 'AFTER_TIMELINE'){throw 'SIMULATED_INTERRUPT_AFTER_TIMELINE'}
        $state.record_count=$timeline.records.Count; $state.transaction_count=$timeline.transactions.Count; $state.status='VERIFIED'
        Save-WorkflowState $checkpoint $state
        if($Fault -ceq 'AFTER_FINAL'){throw 'SIMULATED_RESPONSE_LOST_AFTER_FINAL'}
        return $state
    } finally {$lock.Dispose()}
}
function Save-WorkflowState($Path,$State) {
    $tmp="$Path.tmp"; $bak="$Path.bak"; $State | ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 $tmp
    if(Test-Path $Path){if(Test-Path $bak){Remove-Item -LiteralPath $bak -Force};[IO.File]::Replace($tmp,$Path,$bak);Remove-Item -LiteralPath $bak -Force}else{[IO.File]::Move($tmp,$Path)}
}
if(-not $workflowLibrary) {if(-not $workflowBook -or -not $workflowDirectory){throw 'BookId and WorkflowRoot required'}; Invoke-SyntheticWorkflow $workflowBook $workflowDirectory | ConvertTo-Json -Depth 8}
