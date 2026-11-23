# Finnhub·FRED·KRX 키를 GitHub 저장소 Secrets(FINNHUB_KEY, FRED_KEY, KRX_KEY)에 넣어요.
# 붙여넣기 대신 클립보드에서 바로 읽어요 (검은 창에서 Ctrl+V는 키가 아니라 글자 하나로 들어가요).
# 키 값은 앞뒤 2글자만 보여주고, 저장한 뒤 클립보드를 비워요. 실행: 저장소 폴더의 "키등록.cmd" 더블클릭
$repo = 'rlagustn92/retail-sentiment'

if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    Write-Host 'gh(GitHub CLI)가 없어요. winget install GitHub.cli 로 설치한 뒤 다시 실행하세요.'
    exit 1
}

$items = @(
    @{ Name = 'FINNHUB_KEY'; Label = 'Finnhub API key'; Where = 'finnhub.io 로그인 > Dashboard 의 "API key" 칸' },
    @{ Name = 'FRED_KEY';    Label = 'FRED API 키';     Where = 'fredaccount.stlouisfed.org/apikeys 에서 이 대시보드용으로 새로 받은 키 (32자)' },
    @{ Name = 'KRX_KEY';     Label = 'KRX Open API 인증키'; Where = 'openapi.krx.co.kr 로그인 > 마이페이지 > API 인증키 (승인된 뒤에 보여요)' }
)

foreach ($it in $items) {
    Write-Host ''
    Write-Host "=== $($it.Label) ===" -ForegroundColor Cyan
    Write-Host "1) $($it.Where) 를 복사하세요 (마우스로 긁어서 Ctrl+C)"
    while ($true) {
        $ans = Read-Host '2) 복사했으면 그냥 Enter / 이 키는 건너뛰려면 s 입력 후 Enter'
        if ($ans -eq 's') { Write-Host "  -> $($it.Name) 건너뜀"; break }
        $val = ''
        try { $val = [string](Get-Clipboard -Raw) } catch { $val = '' }
        $val = $val.Trim()
        if ($val -notmatch '^[A-Za-z0-9_\-]{10,80}$') {
            Write-Host "  클립보드에 키가 아닌 값이 있어요 (길이 $($val.Length)자, 띄어쓰기·줄바꿈이 섞였거나 비어 있음)." -ForegroundColor Yellow
            Write-Host '  키 한 줄만 다시 복사한 뒤 Enter 를 눌러주세요.'
            continue
        }
        $mask = $val.Substring(0, 2) + ('*' * ($val.Length - 4)) + $val.Substring($val.Length - 2)
        $ok = Read-Host "  읽은 값: $mask ($($val.Length)자) — 맞으면 Enter, 다시 복사하려면 n"
        if ($ok -eq 'n') { continue }
        $out = & gh secret set $it.Name --repo $repo --body $val 2>&1
        $code = $LASTEXITCODE
        $val = $null
        try { Set-Clipboard -Value ' ' } catch { }
        if ($code -eq 0) {
            Write-Host "  -> $($it.Name) 저장 완료 (클립보드는 비웠어요)" -ForegroundColor Green
        } else {
            Write-Host "  -> $($it.Name) 저장 실패. gh가 알려준 내용:" -ForegroundColor Red
            $out | ForEach-Object { Write-Host "     $_" }
        }
        break
    }
}

Write-Host ''
Write-Host '지금 저장소에 들어 있는 키 이름 (값은 안 보여요):'
& gh secret list --repo $repo 2>&1 | ForEach-Object { Write-Host "  $_" }
