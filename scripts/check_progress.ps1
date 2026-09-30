<#
Shows progress for the currently-running multi-chapter build (ch04, ch05, ch06).
Prints the last progress line for each chapter's timing.csv that exists, and
marks whichever one was written to most recently as ACTIVE.

    powershell -ExecutionPolicy Bypass -File scripts\check_progress.ps1
#>

$targets = @(
    @{ Chapter = "ch04"; Path = "output\ch04full\step_04\chapters\ch04\timing.csv" },
    @{ Chapter = "ch05"; Path = "output\final2\step_04\chapters\ch05\timing.csv" },
    @{ Chapter = "ch06"; Path = "output\final2\step_04\chapters\ch06\timing.csv" }
)

$mostRecent = $null
foreach ($t in $targets) {
    if (-not (Test-Path $t.Path)) {
        Write-Host "$($t.Chapter): not started yet" -ForegroundColor DarkGray
        continue
    }
    $file = Get-Item $t.Path
    $last = Get-Content $t.Path -Tail 1
    $parts = $last -split ","
    if ($parts.Count -lt 5) { continue }
    $n, $itemSec, $elapsedSec, $avgSec, $etaSec = $parts

    if (-not $mostRecent -or $file.LastWriteTime -gt $mostRecent) { $mostRecent = $file.LastWriteTime }
    $isActive = ((Get-Date) - $file.LastWriteTime).TotalSeconds -lt 30

    $etaMin = [math]::Round([double]$etaSec / 60, 1)
    $elapsedMin = [math]::Round([double]$elapsedSec / 60, 1)
    $label = if ($isActive) { "ACTIVE" } else { "done / idle" }

    Write-Host "$($t.Chapter): clip $n  |  $($elapsedMin)min elapsed  |  ~$($etaMin)min remaining  [$label]" `
        -ForegroundColor $(if ($isActive) { "Green" } else { "Yellow" })
}

Write-Host "`n(tip: add -Wait to `"Get-Content <path> -Tail 5 -Wait`" to watch one chapter live)"
