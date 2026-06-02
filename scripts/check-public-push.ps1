# Проверка перед публичным git push. Запуск из корня репозитория.
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root

$fail = @()

function Add-Fail($msg) { $script:fail += $msg }

Write-Host "== Public push check: $root ==" -ForegroundColor Cyan

# 1) Запрещённые пути в индексе git
$tracked = git ls-files 2>$null
if (-not $tracked) {
    Add-Fail "git ls-files failed or repo empty"
} else {
    foreach ($line in $tracked) {
        if ($line -match '\.env$' -and $line -notmatch '\.env\.example$' -and $line -notmatch 'paths\.example\.env$') {
            Add-Fail "Tracked secret env file: $line"
            continue
        }
        if ($line -match 'rag_index|[/\\]chroma[/\\]|dzen-rag-snapshot|00docs[/\\]_') {
            Add-Fail "Tracked forbidden path: $line"
        }
        if ($line -match 'backend[/\\]\.venv') {
            Add-Fail "Tracked venv: $line"
        }
    }
}

# 2) Секреты в отслеживаемых файлах
$textFiles = $tracked | Where-Object { $_ -match '\.(md|py|js|html|json|env\.example|example\.env|bat|ps1|txt|yml|yaml)$' }
foreach ($rel in $textFiles) {
    $full = Join-Path $root $rel
    if (-not (Test-Path $full)) { continue }
    $content = Get-Content -Path $full -Raw -ErrorAction SilentlyContinue
    if ($content -match 'DEEPSEEK_API_KEY\s*=\s*sk-[a-zA-Z0-9]') {
        Add-Fail "API key pattern in tracked file: $rel"
    }
    if ($content -match '(?i)(api[_-]?key|secret|password)\s*=\s*[^\s#]{8,}' -and $rel -notmatch '\.example') {
        if ($content -notmatch 'DEEPSEEK_API_KEY=\s*$' -and $content -notmatch 'DEEPSEEK_API_KEY=\s*\r?\n') {
            # только если не пустой placeholder — грубая эвристика
            if ($content -match '=\s*sk-') {
                Add-Fail "Possible secret in: $rel"
            }
        }
    }
}

# 3) .env не должен существовать в staging
$stagedEnv = git diff --cached --name-only 2>$null | Where-Object { $_ -match '\.env$' -and $_ -notmatch '\.example' }
foreach ($e in $stagedEnv) { Add-Fail "Staged .env file: $e" }

# 4) Неотслеживаемый .env в backend — предупреждение, не fail
$localEnv = Join-Path $root "02modules\dzen-rag\backend\.env"
if (Test-Path $localEnv) {
    Write-Host "OK: local backend/.env exists (gitignored)" -ForegroundColor DarkGray
}

if ($fail.Count -gt 0) {
    Write-Host "`nFAILED ($($fail.Count) issue(s)):" -ForegroundColor Red
    $fail | ForEach-Object { Write-Host "  - $_" -ForegroundColor Red }
    Write-Host "`nFix before public push. See PUBLIC_RELEASE.md" -ForegroundColor Yellow
    exit 1
}

Write-Host "`nPASSED: safe to push public code (keep secrets and index local)." -ForegroundColor Green
exit 0
