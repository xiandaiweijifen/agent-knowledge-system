param(
    [string]$BaseUrl = "http://127.0.0.1:8000",
    [switch]$Recover
)

$requestBody = @{
    question = "Search docs for RAG and create a high severity ticket for payment-service"
    debug_fault_injection = @{
        tool_execution_failures = @(
            @{
                tool_name = "ticketing"
                action = "create"
                fail_count = 2
                message = "demo injected persistent failure"
            }
        )
    }
}

Write-Host "Creating recoverable workflow failure..." -ForegroundColor Cyan
$sourceRun = Invoke-RestMethod `
    -Method Post `
    -Uri "$BaseUrl/api/query/agent" `
    -ContentType "application/json" `
    -Body ($requestBody | ConvertTo-Json -Depth 6)

Write-Host ""
Write-Host "Source Run" -ForegroundColor Yellow
Write-Host "  Run Id: $($sourceRun.run_id)"
Write-Host "  Status: $($sourceRun.workflow_status)"
Write-Host "  Retry State: $($sourceRun.retry_state)"
Write-Host "  Recommended Recovery: $($sourceRun.recommended_recovery_action)"
Write-Host "  Available Recovery Actions: $([string]::Join(', ', $sourceRun.available_recovery_actions))"

if (-not $Recover) {
    Write-Host ""
    Write-Host "Recovery not executed. Re-run with -Recover to continue the flow." -ForegroundColor DarkYellow
    exit 0
}

Write-Host ""
Write-Host "Recovering workflow run..." -ForegroundColor Cyan
$recoverBody = @{
    run_id = $sourceRun.run_id
}

$recoveredRun = Invoke-RestMethod `
    -Method Post `
    -Uri "$BaseUrl/api/query/agent/recover" `
    -ContentType "application/json" `
    -Body ($recoverBody | ConvertTo-Json -Depth 4)

Write-Host ""
Write-Host "Recovered Run" -ForegroundColor Green
Write-Host "  Run Id: $($recoveredRun.run_id)"
Write-Host "  Status: $($recoveredRun.workflow_status)"
Write-Host "  Recovered Via: $($recoveredRun.recovered_via_action)"
Write-Host "  Resume Strategy: $($recoveredRun.resume_strategy)"
Write-Host "  Root Run Id: $($recoveredRun.root_run_id)"
Write-Host "  Source Run Id: $($recoveredRun.source_run_id)"
Write-Host "  Recovery Depth: $($recoveredRun.recovery_depth)"

if ($recoveredRun.reused_step_indices) {
    Write-Host "  Reused Steps: $([string]::Join(', ', $recoveredRun.reused_step_indices))"
}
