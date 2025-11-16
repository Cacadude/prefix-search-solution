# Скрипт подготовки проекта к отправке
# Использование: .\prepare_for_submission.ps1

Write-Host "=== Подготовка проекта к отправке ===" -ForegroundColor Cyan
Write-Host ""

# Переход в директорию проекта
$projectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectDir

Write-Host "1. Остановка Docker контейнеров..." -ForegroundColor Yellow
try {
    docker compose down -v 2>$null | Out-Null
    Write-Host "   ✓ Контейнеры остановлены" -ForegroundColor Green
} catch {
    Write-Host "   ⚠ Контейнеры не были запущены" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "2. Очистка временных файлов..." -ForegroundColor Yellow

# Удаление __pycache__
$pycacheCount = (Get-ChildItem -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue | Measure-Object).Count
if ($pycacheCount -gt 0) {
    Get-ChildItem -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "   ✓ Удалено $pycacheCount папок __pycache__" -ForegroundColor Green
} else {
    Write-Host "   ✓ Нет папок __pycache__" -ForegroundColor Green
}

# Удаление .pyc файлов
$pycCount = (Get-ChildItem -Recurse -Filter "*.pyc" -ErrorAction SilentlyContinue | Measure-Object).Count
if ($pycCount -gt 0) {
    Get-ChildItem -Recurse -Filter "*.pyc" -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue
    Write-Host "   ✓ Удалено $pycCount файлов .pyc" -ForegroundColor Green
} else {
    Write-Host "   ✓ Нет файлов .pyc" -ForegroundColor Green
}

# Удаление .pyo файлов
$pyoCount = (Get-ChildItem -Recurse -Filter "*.pyo" -ErrorAction SilentlyContinue | Measure-Object).Count
if ($pyoCount -gt 0) {
    Get-ChildItem -Recurse -Filter "*.pyo" -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue
    Write-Host "   ✓ Удалено $pyoCount файлов .pyo" -ForegroundColor Green
}

Write-Host ""
Write-Host "3. Проверка необходимых файлов..." -ForegroundColor Yellow

$requiredFiles = @(
    "src\load_catalog.py",
    "src\search_api.py",
    "tools\evaluate.py",
    "data\catalog_products.xml",
    "data\prefix_queries.csv",
    "docker-compose.yml",
    "Dockerfile",
    "requirements.txt",
    "README.md"
)

$missingFiles = @()
foreach ($file in $requiredFiles) {
    if (Test-Path $file) {
        Write-Host "   ✓ $file" -ForegroundColor Green
    } else {
        Write-Host "   ✗ $file - ОТСУТСТВУЕТ!" -ForegroundColor Red
        $missingFiles += $file
    }
}

if ($missingFiles.Count -gt 0) {
    Write-Host ""
    Write-Host "ОШИБКА: Отсутствуют необходимые файлы!" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "4. Создание архива..." -ForegroundColor Yellow

$date = Get-Date -Format "yyyy-MM-dd"
$archiveName = "prefix-search-solution-$date.zip"
$archivePath = Join-Path (Split-Path -Parent $projectDir) $archiveName

# Исключаемые паттерны
$excludePatterns = @(
    "__pycache__",
    "*.pyc",
    "*.pyo",
    ".git",
    "es_data",
    "*.log"
)

# Создание временной папки для архивации
$tempDir = Join-Path $env:TEMP "prefix-search-temp-$(Get-Random)"
New-Item -ItemType Directory -Path $tempDir -Force | Out-Null

# Копирование файлов (исключая ненужные)
Write-Host "   Копирование файлов..." -ForegroundColor Gray
Get-ChildItem -Path $projectDir -Recurse | Where-Object {
    $item = $_
    $relativePath = $item.FullName.Substring($projectDir.Length + 1)
    
    # Проверка исключений
    $shouldExclude = $false
    foreach ($pattern in $excludePatterns) {
        if ($relativePath -like "*\$pattern" -or $relativePath -like "$pattern\*" -or $relativePath -eq $pattern) {
            $shouldExclude = $true
            break
        }
    }
    
    # Исключаем также скрытые файлы и папки
    if ($item.Name -like ".*" -and $item.Name -ne ".gitignore") {
        $shouldExclude = $true
    }
    
    return -not $shouldExclude
} | ForEach-Object {
    $relativePath = $_.FullName.Substring($projectDir.Length + 1)
    $destPath = Join-Path $tempDir $relativePath
    $destDir = Split-Path -Parent $destPath
    if (-not (Test-Path $destDir)) {
        New-Item -ItemType Directory -Path $destDir -Force | Out-Null
    }
    Copy-Item $_.FullName -Destination $destPath -Force
}

# Создание архива
Write-Host "   Сжатие архива..." -ForegroundColor Gray
if (Test-Path $archivePath) {
    Remove-Item $archivePath -Force
}
Compress-Archive -Path "$tempDir\*" -DestinationPath $archivePath -Force

# Удаление временной папки
Remove-Item -Recurse -Force $tempDir

$archiveSize = (Get-Item $archivePath).Length / 1MB
Write-Host "   ✓ Архив создан: $archivePath" -ForegroundColor Green
Write-Host "   ✓ Размер: $([math]::Round($archiveSize, 2)) MB" -ForegroundColor Green

Write-Host ""
Write-Host "=== Готово! ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "Архив для отправки: $archivePath" -ForegroundColor Green
Write-Host ""
Write-Host "Следующие шаги:" -ForegroundColor Yellow
Write-Host "1. Проверьте архив, распаковав его" -ForegroundColor White
Write-Host "2. Отправьте архив на artem.kruglov@diginetica.com" -ForegroundColor White
Write-Host "   или загрузите в Git репозиторий" -ForegroundColor White
Write-Host ""
