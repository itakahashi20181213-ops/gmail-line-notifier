# プロジェクト .venv で API を起動（conda の uvicorn は使わない）
$ScriptDir = $PSScriptRoot
if (-not $ScriptDir) {
    $ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
}
if ($ScriptDir) {
    $Root = Split-Path -Parent $ScriptDir
} else {
    $Root = (Get-Location).Path
}

if (-not (Test-Path (Join-Path $Root ".venv\Scripts\uvicorn.exe"))) {
    $cwd = (Get-Location).Path
    if (Test-Path (Join-Path $cwd ".venv\Scripts\uvicorn.exe")) {
        $Root = $cwd
    }
}

Set-Location -LiteralPath $Root

$Uvicorn = Join-Path $Root ".venv\Scripts\uvicorn.exe"

if (-not (Test-Path -LiteralPath $Uvicorn)) {
    Write-Error ".venv がありません ($Root)。先に: python -m venv .venv; .\.venv\Scripts\pip install -r requirements.txt"
    exit 1
}

Write-Host "起動: $Uvicorn (cwd: $Root)"
& $Uvicorn app.main:app --reload @args
