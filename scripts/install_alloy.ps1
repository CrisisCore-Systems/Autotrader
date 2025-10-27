# Grafana Alloy Installation Script for Windows
# Multiple methods with automatic fallback

Write-Host "🔧 Grafana Alloy Installation Script" -ForegroundColor Cyan
Write-Host "====================================" -ForegroundColor Cyan
Write-Host ""

$alloyVersion = "v1.4.2"  # Latest stable version
$downloadUrl = "https://github.com/grafana/alloy/releases/download/$alloyVersion/alloy-installer-windows-amd64.exe"
$zipUrl = "https://github.com/grafana/alloy/releases/download/$alloyVersion/alloy-windows-amd64.exe.zip"
$tempDir = $env:TEMP
$installDir = "$env:ProgramFiles\GrafanaLabs\Alloy"

# Check if already installed
Write-Host "🔍 Checking if Alloy is already installed..." -ForegroundColor Yellow
$existing = Get-Command alloy -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "✅ Alloy is already installed at: $($existing.Source)" -ForegroundColor Green
    Write-Host ""
    & alloy --version
    Write-Host ""
    Write-Host "To reinstall, uninstall first or run with -Force flag" -ForegroundColor Yellow
    exit 0
}

Write-Host "📦 Alloy not found. Proceeding with installation..." -ForegroundColor Yellow
Write-Host ""

# Method 1: Try Chocolatey
Write-Host "Method 1: Trying Chocolatey..." -ForegroundColor Cyan
$choco = Get-Command choco -ErrorAction SilentlyContinue
if ($choco) {
    Write-Host "   Chocolatey found! Installing Alloy..." -ForegroundColor Green
    try {
        choco install grafana-alloy -y
        if ($LASTEXITCODE -eq 0) {
            Write-Host "   ✅ Successfully installed via Chocolatey!" -ForegroundColor Green
            & alloy --version
            exit 0
        }
    } catch {
        Write-Host "   ❌ Chocolatey installation failed: $_" -ForegroundColor Red
    }
} else {
    Write-Host "   ⚠️  Chocolatey not found. Skipping." -ForegroundColor Yellow
}
Write-Host ""

# Method 2: Try downloading ZIP (more reliable than installer)
Write-Host "Method 2: Downloading standalone executable..." -ForegroundColor Cyan
$zipPath = Join-Path $tempDir "alloy.exe.zip"
$exePath = Join-Path $tempDir "alloy.exe"

try {
    Write-Host "   📥 Downloading from: $zipUrl" -ForegroundColor Yellow
    
    # Use .NET WebClient (more reliable than Invoke-WebRequest for large files)
    $webClient = New-Object System.Net.WebClient
    $webClient.DownloadFile($zipUrl, $zipPath)
    
    Write-Host "   ✅ Download complete!" -ForegroundColor Green
    
    # Extract ZIP
    Write-Host "   📂 Extracting archive..." -ForegroundColor Yellow
    Expand-Archive -Path $zipPath -DestinationPath $tempDir -Force
    
    # Create installation directory
    Write-Host "   📁 Creating installation directory..." -ForegroundColor Yellow
    if (-not (Test-Path $installDir)) {
        New-Item -ItemType Directory -Path $installDir -Force | Out-Null
    }
    
    # Move executable
    Write-Host "   🚀 Installing Alloy to: $installDir" -ForegroundColor Yellow
    $finalExePath = Join-Path $installDir "alloy.exe"
    Move-Item -Path $exePath -Destination $finalExePath -Force
    
    # Add to PATH
    Write-Host "   🔧 Adding to system PATH..." -ForegroundColor Yellow
    $currentPath = [Environment]::GetEnvironmentVariable("Path", "Machine")
    if ($currentPath -notlike "*$installDir*") {
        [Environment]::SetEnvironmentVariable("Path", "$currentPath;$installDir", "Machine")
        $env:Path += ";$installDir"
    }
    
    Write-Host ""
    Write-Host "   ✅ Successfully installed Alloy!" -ForegroundColor Green
    Write-Host ""
    Write-Host "   📍 Location: $finalExePath" -ForegroundColor Cyan
    Write-Host "   ⚡ You may need to restart your terminal for PATH updates" -ForegroundColor Yellow
    Write-Host ""
    
    # Test installation
    & $finalExePath --version
    
    # Cleanup
    Remove-Item $zipPath -Force -ErrorAction SilentlyContinue
    
    exit 0
    
} catch {
    Write-Host "   ❌ Download/extraction failed: $_" -ForegroundColor Red
}
Write-Host ""

# Method 3: Manual download instructions
Write-Host "Method 3: Manual Installation" -ForegroundColor Cyan
Write-Host "   ⚠️  Automated installation failed. Please install manually:" -ForegroundColor Yellow
Write-Host ""
Write-Host "   1. Visit: https://github.com/grafana/alloy/releases/latest" -ForegroundColor White
Write-Host "   2. Download: alloy-windows-amd64.exe.zip" -ForegroundColor White
Write-Host "   3. Extract the ZIP file" -ForegroundColor White
Write-Host "   4. Rename alloy-windows-amd64.exe to alloy.exe" -ForegroundColor White
Write-Host "   5. Move to: $installDir" -ForegroundColor White
Write-Host "   6. Add $installDir to your PATH" -ForegroundColor White
Write-Host ""
Write-Host "   Or try Docker:" -ForegroundColor Cyan
Write-Host "   docker run -v ${PWD}/configs:/etc/alloy grafana/alloy:latest run /etc/alloy/alloy-config.river" -ForegroundColor White
Write-Host ""

exit 1
