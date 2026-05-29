# ローカル API (port 8000) を ngrok で公開する
# 別ターミナルで scripts\run_api.ps1 を先に起動しておくこと
param(
    [int]$Port = 8000
)

$Ngrok = Get-Command ngrok -ErrorAction SilentlyContinue
if (-not $Ngrok) {
    Write-Error "ngrok が見つかりません。winget install Ngrok.Ngrok でインストールしてください。"
    exit 1
}

Write-Host "ngrok を起動します (localhost:$Port → 公開 URL)"
Write-Host "停止: Ctrl+C"
Write-Host ""
Write-Host "公開 URL の確認:"
Write-Host "  .\scripts\ngrok_urls.ps1"
Write-Host ""
Write-Host "LINE Webhook 例:"
Write-Host "  https://<ngrok-url>/api/v1/line/webhook"
Write-Host ""

& ngrok http $Port
