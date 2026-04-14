<#
.SYNOPSIS
  PowerShell version of start_xcom_rx.sh — starts/stops the RX bridge locally (not Docker)

USAGE
  # Start
  .\start_xcom_rx.ps1

  # Stop
  .\start_xcom_rx.ps1 stop

NOTES
  - This script prefers PowerShell 7+ but will work in Windows PowerShell 5.1 for basic features.
  - Uses Write-Host for terminal output to avoid "Write-Object"/Write-Output confusion.
  - Creates a virtualenv at .\.venv and installs Python requirements from requirements.txt.
  - Starts bridge/bridge.py with --enable-ftdi by default. To avoid starting the integrated FTDI reader,
    set the environment variable START_HOST_POSTER=1 to launch the external poster instead.

  Execution policy: if you cannot run this script, run PowerShell as Administrator and execute:
    Set-ExecutionPolicy RemoteSigned -Scope CurrentUser

#>

param(
    [string]$Action = 'start'
)

function Write-Info($msg){ Write-Host "[INFO] $msg" -ForegroundColor Cyan }
function Write-ErrorMsg($msg){ Write-Host "[ERROR] $msg" -ForegroundColor Red }
function Write-Warn($msg){ Write-Host "[WARN] $msg" -ForegroundColor Yellow }

Push-Location -Path (Split-Path -Path $MyInvocation.MyCommand.Definition -Parent)

if ($Action -eq 'stop'){
    Write-Info "Stopping XCOM RX System..."
    if (Test-Path ./bridge.pid){
        try{
            $pid = Get-Content ./bridge.pid | Out-String | Trim
            if ($pid -and (Get-Process -Id $pid -ErrorAction SilentlyContinue)){
                Write-Info "Stopping local bridge (pid $pid)"
                Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
            }
            Remove-Item -Path ./bridge.pid -ErrorAction SilentlyContinue
        } catch {
            Write-Warn "Failed to stop bridge process: $_"
        }
    }

    if (Test-Path ./ftdi_poster.pid){
        try{
            $pid = Get-Content ./ftdi_poster.pid | Out-String | Trim
            if ($pid -and (Get-Process -Id $pid -ErrorAction SilentlyContinue)){
                Write-Info "Stopping FTDI poster (pid $pid)"
                Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
            }
            Remove-Item -Path ./ftdi_poster.pid -ErrorAction SilentlyContinue
        } catch {
            Write-Warn "Failed to stop ftdi_poster process: $_"
        }
    }

    # If Docker is present, try to bring down compose services as well
    if (Get-Command docker -ErrorAction SilentlyContinue){
        Write-Info "Bringing down Docker Compose services (if any)"
        try{ docker compose down -v --remove-orphans } catch { }
    }

    Pop-Location
    exit 0
}

Write-Info "Starting XCOM RX System (PowerShell)..."

# Ensure working directory has received_files
if (-not (Test-Path ./received_files)){
    New-Item -ItemType Directory -Path ./received_files | Out-Null
}

# Build BRIDGE_ARGS
$BRIDGE_ARGS = "--ws-port 8766 --web-port 8001 --host 0.0.0.0"
if ($env:ADAFRUIT_PORT){
    $BRIDGE_ARGS = "$BRIDGE_ARGS --adafruit-port $($env:ADAFRUIT_PORT)"
}

# Locate Python
$pythonCmd = (Get-Command python3 -ErrorAction SilentlyContinue) ? (Get-Command python3).Source : (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $pythonCmd){
    Write-ErrorMsg "python3 or python not found in PATH. Please install Python 3.8+ and re-run this script."
    Pop-Location
    exit 1
}

$VENV_DIR = Join-Path (Get-Location) '.venv'
if (-not (Test-Path $VENV_DIR)){
    Write-Info "Creating virtualenv in $VENV_DIR"
    & $pythonCmd -m venv $VENV_DIR
}

$pipExe = Join-Path $VENV_DIR 'Scripts\pip.exe'
$pythonExe = Join-Path $VENV_DIR 'Scripts\python.exe'
if (-not (Test-Path $pipExe)){
    Write-ErrorMsg "pip not found in venv. Ensure venv creation succeeded or run: $pythonCmd -m venv .venv"
    Pop-Location
    exit 1
}

Write-Info "Installing Python dependencies into venv (this may take a few minutes)..."
& $pipExe install --upgrade pip | Out-Null
try{
    & $pipExe install -r requirements.txt 2>&1 | ForEach-Object { Write-Host $_ }
} catch {
    Write-ErrorMsg "Failed to install Python requirements. See output above."
    Pop-Location
    exit 1
}

Write-Info "Checking for FTDI bindings..."
try{
    & $pythonExe -c "import ftd2xx" 2>$null
    Write-Info "ftd2xx available in venv (D2XX) — ensure native libftd2xx is installed on the host if you expect D2XX support."
} catch {
    Write-Warn "ftd2xx not importable in venv. pyftdi (libusb) may still work if libusb is installed."
}

# Start bridge
Write-Info "Starting bridge.py in background (log: ./bridge.log)"
$args = "$BRIDGE_ARGS --enable-ftdi --ftdi-index $($env:FTDI_INDEX -or 2)"
$startInfo = @{
    FilePath = $pythonExe
    ArgumentList = "./bridge/bridge.py", $args
    NoNewWindow = $true
    RedirectStandardOutput = "bridge.log"
    RedirectStandardError  = "bridge.log"
}
$proc = Start-Process @startInfo -PassThru
if ($proc -and $proc.Id){
    $proc.Id | Out-File -FilePath ./bridge.pid -Encoding ascii
    Write-Info "Bridge started (pid: $($proc.Id)). Web UI: http://localhost:8001"
} else {
    Write-ErrorMsg "Failed to start bridge process"
    Pop-Location
    exit 1
}

# Optionally start host poster if requested via env var START_HOST_POSTER=1
if ($env:START_HOST_POSTER -eq '1'){
    Write-Info "Starting host ftdi_poster (poster will POST to bridge)..."
    $posterArgs = "$($env:FTDI_INDEX -or 2)"
    $posterExe = $pythonExe
    $posterProc = Start-Process -FilePath $posterExe -ArgumentList "./bridge/ftdi_poster.py", $posterArgs -NoNewWindow -RedirectStandardOutput "ftdi_poster.log" -RedirectStandardError "ftdi_poster.log" -PassThru
    if ($posterProc -and $posterProc.Id){
        $posterProc.Id | Out-File -FilePath ./ftdi_poster.pid -Encoding ascii
        Write-Info "FTDI poster started (log: ./ftdi_poster.log, pid: $($posterProc.Id))"
    } else {
        Write-Warn "Failed to start ftdi_poster.py"
    }
}

Write-Info "Start sequence complete. To stop run: .\start_xcom_rx.ps1 stop"

Pop-Location

exit 0
<#
.SYNOPSIS
  PowerShell wrapper to start the XCOM RX stack (Windows / pwsh friendly).

.DESCRIPTION
  This is a PowerShell equivalent of `start_xcom_rx.sh`.
  It prepares environment variables (`BRIDGE_ARGS`, `HOST_RECEIVED_DIR`),
  attempts to detect an FPGA at `$env:FPGA_IP`, creates the host received_files
  folder, and brings up the Docker Compose stack. Informational output lines
  (Write-Host / Write-Info) are commented out per request.
#>

param(
    [switch]$Stop
)

Set-StrictMode -Version Latest
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# function wrappers (kept as comments per request)
function Write-Info($msg) { # Write-Host $msg
}
function Write-Err($msg) { # Write-Host $msg -ForegroundColor Red
}

# Handle "stop" positional argument as well as -Stop switch
if ($Stop -or ($args.Count -gt 0 -and $args[0] -eq 'stop')) {
    # Write-Info "Stopping XCOM RX System..."
    & docker compose down -v --remove-orphans 2>$null
    exit 0
}

# Ensure script runs from its directory
if ($PSScriptRoot) { Set-Location $PSScriptRoot } else { Set-Location (Split-Path -Path $MyInvocation.MyCommand.Definition -Parent) }

# Write-Info "Starting XCOM RX System..."

# Check Docker availability
try {
    & docker info >$null 2>&1
    if ($LASTEXITCODE -ne 0) { throw 'docker not available' }
} catch {
    # Write-Err "`n❌ Docker is not running or not on PATH`n"
    # Write-Host "To start Docker:`n  macOS: Open Docker Desktop from Applications`n  Linux: sudo systemctl start docker`n  Windows: Start Docker Desktop from Start Menu`n"
    exit 1
}

# Write-Info "✓ Docker is running"

# Clean up any existing containers (non-fatal)
# Write-Info "Cleaning up existing containers..."
try { & docker compose down --remove-orphans >$null 2>&1 } catch { }

# Detect Adafruit board (prefer ADAFRUIT_IP env if provided)
$ADAFRUIT_CONNECTED = $false
if ($env:ADAFRUIT_IP) {
    # Write-Info "Checking for Adafruit at $env:ADAFRUIT_IP..."
    try {
        if (Test-Connection -Quiet -Count 1 -ComputerName $env:ADAFRUIT_IP -TimeoutSeconds 1) {
            # Write-Info "Found Adafruit at $env:ADAFRUIT_IP"
            $ADAFRUIT_CONNECTED = $true
        } else {
            # Write-Info "Adafruit at $env:ADAFRUIT_IP not reachable"
        }
    } catch { }
} else {
    # Write-Info "ADAFRUIT_IP not set; starting without Adafruit connection. To enable, set `\$env:ADAFRUIT_IP`."
}

# Build BRIDGE_ARGS (will be exported into the compose environment)
$BRIDGE_ARGS = "--ws-port 8766 --web-port 8001 --host 0.0.0.0"
if ($ADAFRUIT_CONNECTED) {
    if (-not $env:ADAFRUIT_PORT) { $env:ADAFRUIT_PORT = '5001' }
    if (-not $env:ADAFRUIT_BITPACKED) { $env:ADAFRUIT_BITPACKED = '0' }
    if (-not $env:ADAFRUIT_BITORDER) { $env:ADAFRUIT_BITORDER = 'msb' }
    $BRIDGE_ARGS = "$BRIDGE_ARGS --adafruit-port $env:ADAFRUIT_PORT"
    if ($env:ADAFRUIT_BITPACKED -ne '0') { $BRIDGE_ARGS = "$BRIDGE_ARGS --adafruit-bitpacked" }
    $BRIDGE_ARGS = "$BRIDGE_ARGS --adafruit-bitorder $env:ADAFRUIT_BITORDER"
}
$env:BRIDGE_ARGS = $BRIDGE_ARGS

# Ensure host-side received_files exists and export path
$receivedDir = Join-Path -Path (Get-Location) -ChildPath 'received_files'
if (-not (Test-Path $receivedDir)) { New-Item -ItemType Directory -Path $receivedDir | Out-Null }
$env:HOST_RECEIVED_DIR = $receivedDir

# Build and start services
# Write-Info "Building and starting services..."
try {
    & docker compose up --build -d --quiet-pull 2>$null
    if ($LASTEXITCODE -ne 0) { throw 'compose up failed' }
} catch {
    # Write-Err "❌ Error: Failed to start services"
    # Write-Host "--- Recent logs ---"
    & docker compose logs --tail 10
    exit 1
}

# Success message (commented out)
# Write-Host "`nXCOM RX System is ready:`n`n   Web UI: http://localhost:8001`n`n   Commands:`n   - View logs:    docker compose logs -f`n   - Stop system:  .\start_xcom_rx.ps1 -Stop`n"
