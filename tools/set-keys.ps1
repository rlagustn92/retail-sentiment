# Finnhub·FRED 키를 GitHub 저장소 Secrets(FINNHUB_KEY, FRED_KEY)에 넣어요.
# 키 값은 화면에 안 보이고 어디에도 기록되지 않아요. 실행: 저장소 폴더의 "키등록.cmd"를 더블클릭
$repo = 'rlagustn92/retail-sentiment'

if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    Write-Host 'gh(GitHub CLI)가 없어요. winget install GitHub.cli 로 설치한 뒤 다시 실행하세요.'
    exit 1
}

$items = @(
    @{ Name = 'FINNHUB_KEY'; Label = 'Finnhub API 키' },
    @{ Name = 'FRED_KEY';    Label = 'FRED API 키 (이 대시보드용으로 새로 받은 키)' }
)
foreach ($it in $items) {
    Write-Host ''
    $sec = Read-Host -AsSecureString "$($it.Label)를 붙여넣고 Enter (마우스 오른쪽 클릭 = 붙여넣기, 건너뛰려면 그냥 Enter)"
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec)
    try { $val = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr).Trim() }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr) }
    if (-not $val) { Write-Host "  -> $($it.Name) 건너뜀"; continue }
    $out = & gh secret set $it.Name --repo $repo --body $val 2>&1
    $code = $LASTEXITCODE
    $val = $null
    if ($code -eq 0) {
        Write-Host "  -> $($it.Name) 저장 완료"
    } else {
        Write-Host "  -> $($it.Name) 저장 실패. gh가 알려준 내용:"
        $out | ForEach-Object { Write-Host "     $_" }
    }
}

Write-Host ''
Write-Host '지금 저장소에 들어 있는 키 이름 (값은 안 보여요):'
& gh secret list --repo $repo 2>&1 | ForEach-Object { Write-Host "  $_" }
