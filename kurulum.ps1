# e-Fatura kurulum betiği
# Yaptıkları: Python ve Tesseract'ı kurar, Türkçe OCR dosyalarını indirir, programın bağımlılıklarını kurar,
# masaüstüne kısayol koyar, bilgisayar açılınca programın arka planda başlamasını sağlar,
# güvenlik duvarında yerel ağa izin verir ve isterseniz Tailscale'i (dışarıdan güvenli erişim) kurar.

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$Klasor = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Klasor

# --- Yönetici olarak yeniden başlat (güvenlik duvarı ve program kurulumu için)
$yonetici = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $yonetici) {
    Start-Process powershell -Verb RunAs -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$($MyInvocation.MyCommand.Path)`""
    exit
}

function Baslik($m) { Write-Host ""; Write-Host "==> $m" -ForegroundColor Cyan }
function Tamam($m)  { Write-Host "    $m" -ForegroundColor Green }
function Uyari($m)  { Write-Host "    $m" -ForegroundColor Yellow }
function Bitir($kod) { Write-Host ""; Read-Host "Kapatmak için Enter'a basın"; exit $kod }

trap {
    Write-Host ""
    Write-Host "HATA: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "Bu ekranın fotoğrafını çekip gönderirseniz sorunu birlikte çözeriz." -ForegroundColor Red
    Bitir 1
}

Write-Host "e-Fatura kurulumu başlıyor. İnternet bağlantısı gerekir; 5-10 dakika sürebilir." -ForegroundColor White
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$winget = Get-Command winget -ErrorAction SilentlyContinue

function Yenile-Path {
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
}

function Python-Bul {
    Yenile-Path
    $adaylar = @()
    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) { try { $adaylar += (& py -3 -c "import sys; print(sys.executable)" 2>$null) } catch {} }
    $p = Get-Command python -ErrorAction SilentlyContinue
    if ($p -and $p.Source -notlike "*WindowsApps*") { $adaylar += $p.Source }
    $adaylar += Get-ChildItem "$env:LOCALAPPDATA\Programs\Python\Python3*\python.exe", "$env:ProgramFiles\Python3*\python.exe" -ErrorAction SilentlyContinue | ForEach-Object FullName
    foreach ($a in $adaylar) {
        if (-not $a -or -not (Test-Path $a)) { continue }
        $surum = & $a -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null
        if ($surum -and [version]$surum -ge [version]"3.10") { return $a }
    }
    return $null
}

# --- 1) Python
Baslik "Python kontrol ediliyor"
$python = Python-Bul
if (-not $python) {
    if ($winget) {
        Uyari "Python kuruluyor (winget)..."
        winget install -e --id Python.Python.3.12 --scope machine --silent --accept-package-agreements --accept-source-agreements | Out-Host
    } else {
        Uyari "Python indiriliyor..."
        $kurucu = Join-Path $env:TEMP "python-kurulum.exe"
        Invoke-WebRequest "https://www.python.org/ftp/python/3.12.7/python-3.12.7-amd64.exe" -OutFile $kurucu
        Start-Process $kurucu -ArgumentList "/quiet InstallAllUsers=1 PrependPath=1 Include_test=0" -Wait
    }
    $python = Python-Bul
    if (-not $python) { throw "Python kurulamadı. python.org adresinden Python 3.12 kurup (Add to PATH işaretli) bu dosyayı tekrar çalıştırın." }
}
Tamam "Python hazır: $python"

# --- 2) Tesseract (OCR)
Baslik "Tesseract (irsaliye okuma) kontrol ediliyor"
$tesseract = @("$env:ProgramFiles\Tesseract-OCR\tesseract.exe", "${env:ProgramFiles(x86)}\Tesseract-OCR\tesseract.exe",
               "$env:LOCALAPPDATA\Programs\Tesseract-OCR\tesseract.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $tesseract -and $winget) {
    Uyari "Tesseract kuruluyor (winget)..."
    winget install -e --id UB-Mannheim.TesseractOCR --scope machine --silent --accept-package-agreements --accept-source-agreements | Out-Host
    $tesseract = @("$env:ProgramFiles\Tesseract-OCR\tesseract.exe", "$env:LOCALAPPDATA\Programs\Tesseract-OCR\tesseract.exe") |
        Where-Object { Test-Path $_ } | Select-Object -First 1
}
if ($tesseract) { Tamam "Tesseract hazır: $tesseract" }
else { Uyari "Tesseract otomatik kurulamadı. Program çalışır ama fotoğraf okuma olmaz. Kılavuzdaki elle kurulum adımını yapın." }

# --- 3) Türkçe OCR dosyaları (program klasörüne; yönetici izni gerektirmez, Tesseract sürümünden bağımsız)
Baslik "Türkçe OCR dil dosyaları indiriliyor"
$tessdata = Join-Path $Klasor "tessdata"
New-Item -ItemType Directory -Force -Path $tessdata | Out-Null
foreach ($dil in @("tur", "eng", "osd")) {
    $hedef = Join-Path $tessdata "$dil.traineddata"
    if (-not (Test-Path $hedef) -or (Get-Item $hedef).Length -lt 100000) {
        Invoke-WebRequest "https://github.com/tesseract-ocr/tessdata/raw/main/$dil.traineddata" -OutFile $hedef
    }
}
Tamam "Dil dosyaları hazır."

# --- 4) Programın bağımlılıkları
Baslik "Program bileşenleri kuruluyor"
$venv = Join-Path $Klasor ".venv"
if (-not (Test-Path "$venv\Scripts\python.exe")) { & $python -m venv $venv }
& "$venv\Scripts\python.exe" -m pip install --upgrade pip --quiet --disable-pip-version-check
& "$venv\Scripts\python.exe" -m pip install -r (Join-Path $Klasor "requirements.txt") --quiet --disable-pip-version-check
if ($LASTEXITCODE -ne 0) { throw "Program bileşenleri kurulamadı (pip)." }
Tamam "Bileşenler hazır."

# --- 5) Kısayollar
Baslik "Kısayollar oluşturuluyor"
$kabuk = New-Object -ComObject WScript.Shell
$masaustu = [Environment]::GetFolderPath("Desktop")
$k = $kabuk.CreateShortcut((Join-Path $masaustu "e-Fatura.lnk"))
$k.TargetPath = Join-Path $Klasor "baslat.bat"
$k.WorkingDirectory = $Klasor
$k.WindowStyle = 7
$k.Description = "e-Fatura programını aç"
$k.Save()
Tamam "Masaüstüne 'e-Fatura' kısayolu kondu."

# Eski sürümün başlangıç kısayolu varsa kaldır (artık sistem görevi kullanılıyor)
Remove-Item (Join-Path ([Environment]::GetFolderPath("Startup")) "e-Fatura (arka plan).lnk") -ErrorAction SilentlyContinue

Baslik "Program sistem görevi olarak kaydediliyor"
# Bilgisayar açılınca, kimse oturum açmasa bile başlar; kapanırsa 1 dakika içinde yeniden başlatılır.
New-Item -ItemType Directory -Force -Path (Join-Path $Klasor "veri") | Out-Null
$py = Join-Path $venv "Scripts\python.exe"
$log = Join-Path $Klasor "veri\sunucu.log"
$eylem = New-ScheduledTaskAction -Execute "cmd.exe" -WorkingDirectory $Klasor `
    -Argument "/c `"`"$py`" -m uvicorn app.main:app --host 0.0.0.0 --port 8000 >> `"$log`" 2>&1`""
$tetik = New-ScheduledTaskTrigger -AtStartup
$ayar = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
    -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero)
$kim = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
Register-ScheduledTask -TaskName "e-Fatura" -Action $eylem -Trigger $tetik -Settings $ayar -Principal $kim -Force | Out-Null
Stop-ScheduledTask -TaskName "e-Fatura" -ErrorAction SilentlyContinue
Start-ScheduledTask -TaskName "e-Fatura"
Tamam "Program arka planda çalışıyor ve bilgisayar her açıldığında kendiliğinden başlayacak."

# --- 6) Güvenlik duvarı: sadece yerel ağ (ofis Wi-Fi'ı) için izin
Baslik "Güvenlik duvarı ayarlanıyor"
Get-NetFirewallRule -DisplayName "e-Fatura" -ErrorAction SilentlyContinue | Remove-NetFirewallRule
New-NetFirewallRule -DisplayName "e-Fatura" -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow -Profile Private | Out-Null
Tamam "Yerel ağdan (telefon aynı Wi-Fi'dayken) erişime izin verildi."
$ag = Get-NetConnectionProfile -ErrorAction SilentlyContinue | Where-Object NetworkCategory -eq "Public"
if ($ag) { Uyari "Ofis ağınız 'Ortak (Public)' görünüyor. Telefondan bağlanmak için Windows Ayarlar > Ağ bölümünden ağı 'Özel (Private)' yapın." }

# --- 7) Tailscale (isteğe bağlı): dışarıdan güvenli erişim
$cevap = Read-Host "Telefondan ofis dışından da erişmek için Tailscale kurulsun mu? [e/H]"
if ($cevap -match '^[eEyY]') {
    Baslik "Tailscale kuruluyor"
    if ($winget) {
        winget install -e --id Tailscale.Tailscale --silent --accept-package-agreements --accept-source-agreements | Out-Host
        Tamam "Tailscale kuruldu. Sağ alttaki Tailscale simgesinden giriş yapın (Google hesabıyla olabilir)."
        Read-Host "Giriş yaptıktan sonra Enter'a basın"
        Yenile-Path
        $ts = "$env:ProgramFiles\Tailscale\tailscale.exe"
        if (Test-Path $ts) {
            try { & $ts serve --bg 8000 | Out-Host; Tamam "Güvenli adres (https) açıldı. Adres, programda Ayarlar > Telefondan erişim bölümünde görünür." }
            catch { Uyari "tailscale serve çalıştırılamadı. Kılavuzdaki adımı elle yapın." }
        }
    } else {
        Uyari "winget bulunamadı. tailscale.com/download adresinden Windows sürümünü kurun."
    }
}

Baslik "Kurulum tamamlandı"
Tamam "Masaüstündeki 'e-Fatura' kısayoluyla programı açabilirsiniz."
Start-Sleep -Seconds 5
Start-Process "http://localhost:8000"
Bitir 0
