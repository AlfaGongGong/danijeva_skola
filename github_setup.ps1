# ══════════════════════════════════════════════════════════════════
#  github_setup.ps1 — Kreira GitHub repo i pusha projekt
#  Projekt: Danijeva E-Školica
#
#  Potrebno:
#    - Git instaliran (https://git-scm.com)
#    - GitHub Personal Access Token s "repo" permisijom
#      Kreiraj na: https://github.com/settings/tokens/new
#      (Classic token, označi: repo ✓)
#
#  Pokretanje iz root direktorija projekta:
#    powershell -ExecutionPolicy Bypass -File github_setup.ps1
# ══════════════════════════════════════════════════════════════════

$ErrorActionPreference = "Stop"

function Log { param($m) Write-Host "  OK  $m" -ForegroundColor Green }
function Warn { param($m) Write-Host "  !!  $m" -ForegroundColor Yellow }
function Info { param($m) Write-Host "  >>  $m" -ForegroundColor Cyan }
function Err { param($m) Write-Host "  XX  $m" -ForegroundColor Red; Read-Host "Pritisni Enter za izlaz"; exit 1 }
function Ask {
    param($prompt, $default = "")
    if ($default) { Write-Host "  ?   $prompt [$default]: " -ForegroundColor Magenta -NoNewline }
    else { Write-Host "  ?   $prompt`: " -ForegroundColor Magenta -NoNewline }
    $val = Read-Host
    if ($val -eq "" -and $default -ne "") { return $default }
    return $val
}

Clear-Host
Write-Host ""
Write-Host "  ================================================" -ForegroundColor Cyan
Write-Host "    GitHub Setup -- Danijeva E-Skolica" -ForegroundColor Cyan
Write-Host "  ================================================" -ForegroundColor Cyan
Write-Host ""

# ── 1. Provjera da smo u pravom direktoriju ──────────────
if (-not (Test-Path "config.py") -and -not (Test-Path "test.py")) {
    Err "Nije pronađen config.py. Pokreni skriptu iz root direktorija projekta."
}
Log "Direktorij: $(Get-Location)"

# ── 2. Provjera gita ──────────────────────────────────────
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Err "Git nije instaliran. Instaliraj s https://git-scm.com i pokušaj ponovo."
}
Log "Git: $(git --version)"

# ── 3. GitHub token i username ───────────────────────────
Write-Host ""
Write-Host "  Trebas GitHub Personal Access Token." -ForegroundColor Yellow
Write-Host "  Kreiraj na: https://github.com/settings/tokens/new" -ForegroundColor Yellow
Write-Host "  (Classic token, oznaci: repo)" -ForegroundColor Yellow
Write-Host ""

$GH_TOKEN = Ask "GitHub Personal Access Token (ghp_...)"
$GH_USER = Ask "GitHub korisnicko ime"
$REPO_NAME = Ask "Naziv novog repozitorija" "danijeva-e-skolica"
$REPO_DESC = Ask "Opis repozitorija" "Flask e-learning app s AI generiranjem lekcija i gamifikacijom"
$REPO_PRIVATE = Ask "Privatan repozitorij? (y/N)" "y"

if (-not $GH_TOKEN -or -not $GH_USER) {
    Err "Token i korisnicko ime su obavezni."
}

$isPrivate = ($REPO_PRIVATE -match '^[Yy]$')

# ── 4. Kreiranje repozitorija putem GitHub API-ja ─────────
Write-Host ""
Info "Kreiram GitHub repozitorij '$REPO_NAME'..."

$headers = @{
    "Authorization" = "token $GH_TOKEN"
    "Accept"        = "application/vnd.github.v3+json"
    "User-Agent"    = "PowerShell-GitHubSetup"
}

$body = @{
    name        = $REPO_NAME
    description = $REPO_DESC
    private     = $isPrivate
    auto_init   = $false
} | ConvertTo-Json

try {
    $response = Invoke-RestMethod `
        -Uri "https://api.github.com/user/repos" `
        -Method POST `
        -Headers $headers `
        -Body $body `
        -ContentType "application/json"

    $REPO_URL = $response.clone_url
    $REPO_HTML_URL = $response.html_url
    Log "Repozitorij kreiran: $REPO_HTML_URL"
}
catch {
    $statusCode = $_.Exception.Response.StatusCode.value__
    if ($statusCode -eq 422) {
        Warn "Repozitorij '$REPO_NAME' vec postoji na GitHub-u."
        $REPO_URL = "https://github.com/$GH_USER/$REPO_NAME.git"
        Info "Koristit cu postojeci: $REPO_URL"
    }
    elseif ($statusCode -eq 401) {
        Err "Token nije validan ili nema 'repo' permisiju. Provjeri na https://github.com/settings/tokens"
    }
    else {
        Err "GitHub API greska ($statusCode): $_"
    }
}

# ── 5. Kreiranje .gitignore ───────────────────────────────
Write-Host ""
Info "Kreiram .gitignore..."

if (Test-Path ".gitignore") {
    $ts = Get-Date -Format "yyyyMMdd_HHmmss"
    Copy-Item ".gitignore" ".gitignore.bak.$ts"
    Warn "Postojeci .gitignore backupiran kao .gitignore.bak.$ts"
}

@'
# Python
__pycache__/
*.py[cod]
*.pyo
*.pyd
*.so
*.egg
*.egg-info/
dist/
build/
.eggs/

# Virtualna okruženja
venv/
.venv/
env/
ENV/

# Baza podataka
*.db
*.sqlite
*.sqlite3

# Tajni podaci
.env
*.env
!.env.example

# Logovi i izvještaji učenika
izvjestaji/
*.log
process_audit.log

# Legacy stats
ucenik_stats.json

# Atlas slike (435 PNG-ova, ~150MB)
atlas_processed/images/

# Atlas index (15 MB JSON)
atlas_processed/atlas_index.json

# Sobotta PDF (prevelik za git)
*.pdf

# Windows
Thumbs.db
desktop.ini
ehthumbs.db

# macOS
.DS_Store

# IDE
.idea/
.vscode/
*.code-workspace
*.swp
*.swo

# Testing
.pytest_cache/
.mypy_cache/
.coverage
htmlcov/
.tox/

# Ngrok
ngrok.log
ngrok.yml
'@ | Set-Content ".gitignore" -Encoding UTF8

Log ".gitignore kreiran"

# ── 6. Kreiranje .env.example ─────────────────────────────
if (-not (Test-Path ".env.example")) {
    @'
# Kopiraj ovaj fajl u .env i popuni vrijednosti

# Google Gemini API
GOOGLE_API_KEY=your_google_api_key_here

# Ngrok (za remote pristup)
NGROK_AUTH_TOKEN=your_ngrok_token_here
NGROK_DOMAIN=your_ngrok_domain_here

# Lozinke
ACCESS_PASSWORD=your_student_password
ADMIN_PASSWORD=your_admin_password

# OCR alati (za atlas.py)
TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
POPPLER_PATH=C:\Program Files\poppler-24\Library\bin
'@ | Set-Content ".env.example" -Encoding UTF8
    Log ".env.example kreiran"
}
else {
    Info ".env.example vec postoji, preskacam"
}

# ── 7. Git init ───────────────────────────────────────────
if (-not (Test-Path ".git")) {
    git init
    Log "Git repozitorij inicijaliziran"
}
else {
    Info "Git repozitorij vec postoji"
}

# ── 8. Git identitet ──────────────────────────────────────
$gitEmail = git config --global user.email 2>$null
$gitName = git config --global user.name  2>$null

if (-not $gitEmail) {
    $gitEmail = Ask "Git email"
    git config --global user.email $gitEmail
}
if (-not $gitName) {
    $gitName = Ask "Git ime/prezime"
    git config --global user.name $gitName
}
Log "Git identitet: $gitName <$gitEmail>"

# ── 9. Remote ─────────────────────────────────────────────
$existingRemote = git remote get-url origin 2>$null
if ($existingRemote) {
    git remote set-url origin $REPO_URL
    Info "Remote ažuriran: $REPO_URL"
}
else {
    git remote add origin $REPO_URL
    Log "Remote dodan: $REPO_URL"
}

# Postavi credentials u URL da ne pita za lozinku
$REPO_URL_WITH_TOKEN = $REPO_URL -replace "https://", "https://$GH_USER`:$GH_TOKEN@"
git remote set-url origin $REPO_URL_WITH_TOKEN

# ── 10. Čišćenje git cachea ───────────────────────────────
Info "Cistim git cache..."
git rm -r --cached . -q 2>$null
Log "Git cache ociscen"

# ── 11. Stage ─────────────────────────────────────────────
git add .
$staged = (git diff --cached --name-only | Measure-Object -Line).Lines
Log "Stagean $staged fajl(ova)"

# ── 12. Sigurnosna provjera ───────────────────────────────
$stagedFiles = git diff --cached --name-only
if ($stagedFiles -contains ".env") {
    # Ukloni .env i prekini
    git reset HEAD .env | Out-Null
    Err ".env je bio stagean! Uklonjen, ali provjeri .gitignore. Pokusaj ponovo."
}
Log "Sigurnosna provjera prosla (.env nije u commitu)"

# ── 13. Commit ────────────────────────────────────────────
$commitMsg = "Danijeva E-Skolica v1`n`n- Flask backend s AI generiranjem lekcija (Gemini)`n- Gamifikacija: XP, rankovi, medalje, telemetrija`n- Anatomski atlas s OCR indeksom (Sobotta)`n- SQLite baza: lekcije, pitanja, statistika`n- gitignore: iskljuceni DB, slike, logovi, PDF"

git commit -m $commitMsg
Log "Commit kreiran"

# ── 14. Branch → main ─────────────────────────────────────
git branch -M main
Log "Branch: main"

# ── 15. Push ─────────────────────────────────────────────
Write-Host ""
Info "Pusham na GitHub..."
git push -u origin main

# Vrati remote URL bez tokena (sigurnost)
git remote set-url origin $REPO_URL
Log "Token uklonjen iz remote URL-a"

# ── 16. Gotovo ────────────────────────────────────────────
Write-Host ""
Write-Host "  ================================================" -ForegroundColor Green
Write-Host "    Projekt je na GitHubu!" -ForegroundColor Green
Write-Host "  ================================================" -ForegroundColor Green
Write-Host ""
Write-Host "  URL: $REPO_HTML_URL" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Sljedeci korak: kopiraj .env.example u .env" -ForegroundColor Yellow
Write-Host "  i popuni API kljuceve." -ForegroundColor Yellow
Write-Host ""
Read-Host "  Pritisni Enter za izlaz"
