<#
.SYNOPSIS
  PowerShell version of start_xcom_rx.sh — starts/stops the RX bridge locally or via Docker.
#>

param(
    [string]$Action = 'start'
)

# --- Helper Functions ---
function Write-Info($msg){ Write-Host "[INFO] $msg" -ForegroundColor Cyan }
function Write-ErrorMsg($msg){ Write-Host "[ERROR] $msg" -ForegroundColor Red }
function Write-Warn($msg){ Write-Host "[WARN] $msg" -ForegroundColor Yellow }

# Set Working Directory
$scriptPath = Split-Path -Path $MyInvocation.MyCommand.Definition -Parent
Push-Location -Path $scriptPath

# --- Handle STOP Action ---
if ($Action -eq 'stop'){
    Write-Info "Stopping XCOM RX System..."
    
    # Kill local processes if PIDs exist
    foreach ($pidFile in @("./bridge.pid", "./ftdi_poster.pid")) {
        if (Test-Path $pidFile){
            try {
                $pId = Get-Content $pidFile -Raw | Out-String
                $pId = $pId.Trim()
                if ($pId -and (Get-Process -Id $pId -ErrorAction SilentlyContinue)){
                    Write-Info "Stopping process $pId ($pidFile)"
                    Stop-Process -Id $pId -Force -ErrorAction SilentlyContinue
                }
                Remove-Item -Path $pidFile -ErrorAction SilentlyContinue
            } catch {
                Write-Warn "Failed to stop process from $pidFile"
            }
        }
    }

    # Try Docker stop
    if (Get-Command docker -ErrorAction SilentlyContinue){
        Write-Info "Bringing down Docker Compose services..."
        try { docker compose down -v --remove-orphans } catch { }
    }

    Pop-Location
    exit 0
}

# --- Handle START Action ---
Write-Info "Starting XCOM RX System..."

# 1. Ensure directories exist
if (-not (Test-Path ./received_files)){
    New-Item -ItemType Directory -Path ./received_files | Out-Null
}

# 2. Locate Python (Compatibility fix for PS 5.1)
$pythonCmd = ""
if (Get-Command python3 -ErrorAction SilentlyContinue) {
    $pythonCmd = (Get-Command python3).Source
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $pythonCmd = (Get-Command python).Source
}

if (-not $pythonCmd){
    Write-ErrorMsg "Python not found. Please install Python 3.8+."
    Pop-Location
    exit 1
}

# 3. Setup Virtual Environment
$VENV_DIR = Join-Path (Get-Location) '.venv'
if (-not (Test-Path $VENV_DIR)){
    Write-Info "Creating virtualenv..."
    & $pythonCmd -m venv $VENV_DIR
}

$pipExe = Join-Path $VENV_DIR 'Scripts\pip.exe'
$pythonExe = Join-Path $VENV_DIR 'Scripts\python.exe'

# 4. Install Requirements
Write-Info "Installing dependencies..."
try {
    & $pipExe install --upgrade pip | Out-Null
    & $pipExe install -r requirements.txt
} catch {
    Write-ErrorMsg "Failed to install requirements."
    Pop-Location
    exit 1
}

# 5. Build Arguments
$BRIDGE_ARGS = "--ws-port 8766 --web-port 8001 --host 0.0.0.0"
if ($env:ADAFRUIT_PORT){
    $BRIDGE_ARGS = "$BRIDGE_ARGS --adafruit-port $($env:ADAFRUIT_PORT)"
}

# 6. Start Bridge (Avoid using reserved $args variable)
Write-Info "Starting bridge.py..."
$ftdiIdx = if ($env:FTDI_INDEX) { $env:FTDI_INDEX } else { "2" }
$bridgeParams = @("./bridge/bridge.py")
$bridgeParams += $BRIDGE_ARGS.Split(" ")
$bridgeParams += "--enable-ftdi"
$bridgeParams += "--ftdi-index"
$bridgeParams += $ftdiIdx

$startInfo = @{
    FilePath = $pythonExe
    ArgumentList = $bridgeParams
    NoNewWindow = $true
    RedirectStandardOutput = "bridge.log"
    RedirectStandardError  = "bridge.log"
}

$proc = Start-Process @startInfo -PassThru
if ($proc -and $proc.Id){
    $proc.Id | Out-File -FilePath ./bridge.pid -Encoding ascii
    Write-Info "Bridge started (pid: $($proc.Id)). Web UI: http://localhost:8001"
}

Write-Info "Start sequence complete. To stop run: .\start_xcom_rx.ps1 stop"
Pop-Location