# ngrok local API -> print public URLs (optional: update .env)
param(
    [switch]$UpdateEnv
)

$ErrorActionPreference = "Stop"
$ScriptDir = $PSScriptRoot
if (-not $ScriptDir) {
    $ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
}
$Root = Split-Path -Parent $ScriptDir
$EnvFile = Join-Path $Root ".env"

try {
    $tunnels = Invoke-RestMethod -Uri "http://127.0.0.1:4040/api/tunnels" -TimeoutSec 3
} catch {
    Write-Host "[NG] ngrok is not running."
    Write-Host "     Run: .\scripts\run_ngrok.ps1"
    exit 1
}

$httpsTunnel = $tunnels.tunnels | Where-Object { $_.public_url -like "https://*" } | Select-Object -First 1
if (-not $httpsTunnel) {
    Write-Host "[NG] HTTPS tunnel not found."
    exit 1
}

$BaseUrl = $httpsTunnel.public_url.TrimEnd("/")
$WebhookUrl = "$BaseUrl/api/v1/line/webhook"
$OAuthCallback = "$BaseUrl/api/v1/oauth/google/callback"
$OAuthStartExample = "$BaseUrl/api/v1/oauth/google/start?user_id=<users.id>"

Write-Host "=== ngrok URLs ==="
Write-Host ""
Write-Host "PUBLIC_BASE_URL=$BaseUrl"
Write-Host "GOOGLE_OAUTH_REDIRECT_URI=$OAuthCallback"
Write-Host ""
Write-Host "LINE Webhook (set in LINE Developers Console):"
Write-Host "  $WebhookUrl"
Write-Host ""
Write-Host "Gmail OAuth start example:"
Write-Host "  $OAuthStartExample"
Write-Host ""
Write-Host "Health check:"
Write-Host "  $BaseUrl/health"
Write-Host ""

if ($UpdateEnv) {
    if (-not (Test-Path $EnvFile)) {
        Write-Host "[NG] .env not found: $EnvFile"
        exit 1
    }

    $content = Get-Content -LiteralPath $EnvFile -Raw -Encoding UTF8
    $content = $content -replace "(?m)^PUBLIC_BASE_URL=.*$", "PUBLIC_BASE_URL=$BaseUrl"
    $content = $content -replace "(?m)^GOOGLE_OAUTH_REDIRECT_URI=.*$", "GOOGLE_OAUTH_REDIRECT_URI=$OAuthCallback"
    [System.IO.File]::WriteAllText($EnvFile, $content, [System.Text.UTF8Encoding]::new($false))

    Write-Host "[OK] .env updated. Restart API (run_api.ps1)."
    Write-Host ""
    Write-Host "Add this redirect URI in Google Cloud Console:"
    Write-Host "  $OAuthCallback"
}
