<#
.SYNOPSIS
  Start the XCOM transmitter stack on Windows (PowerShell wrapper).

.DESCRIPTION
  This script is the PowerShell equivalent of the POSIX `start_xcom_tx.sh`.
  It checks Docker, optionally detects a serial STM32 device (COMx), sets
  `BRIDGE_ARGS` and `HOST_RECEIVED_DIR` environment variables for docker compose,
  and brings the compose stack up or down.

.USAGE
  # Start services (requires $env:STM32_IP to be set)
  $env:STM32_IP = '192.168.1.10'
  .\start_xcom_tx.ps1

  # Stop services
  .\start_xcom_tx.ps1 stop
#>

param(
    [Parameter(Position=0, HelpMessage='Optional: STM32 IP address; falls back to $env:STM32_IP')]
    [string]$Ip,
    [Parameter(Position=1, HelpMessage='Optional: STM32 TCP port (default 5000)')]
    [int]$Port = 5000,
    [Parameter(HelpMessage='Optional: Force a specific COM port (e.g. COM3)')]
    [string]$ComPort,
    [Parameter(HelpMessage='Optional: override BRIDGE_ARGS passed into container')]
    [string]$BridgeArgs,
    [Parameter(HelpMessage='Optional: override HOST_RECEIVED_DIR')]
    [string]$HostReceivedDir,
    [switch]$Stop
)

Set-StrictMode -Version Latest
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

function Write-Info($msg) { Write-Host $msg }
function Write-Err($msg) { Write-Host $msg -ForegroundColor Red }

# Handle stop command
if ($Stop) {
    Write-Info "Stopping XCOM System..."
    & docker compose down -v --remove-orphans 2>$null
    exit 0
}

# Ensure script runs from its directory
if ($PSScriptRoot) { Set-Location $PSScriptRoot }

Write-Info "Starting XCOM System..."

# If -Ip provided, set STM32_IP in this session (overrides env)
if ($Ip) { $env:STM32_IP = $Ip }

if (-not $env:STM32_IP -or $env:STM32_IP.Trim() -eq '') {
    Write-Err "`n❌ Error: STM32 IP is required. Provide -Ip or set `$env:STM32_IP`n"
    Write-Host "Usage examples:`n  .\start_xcom_tx.ps1 -Ip 192.168.1.10`n  `$env:STM32_IP = '192.168.1.10'; .\start_xcom_tx.ps1`n"
    exit 1
}

Write-Info "STM32 IP: $($env:STM32_IP)"

# Check Docker availability
try {
    & docker info >$null 2>&1
    if ($LASTEXITCODE -ne 0) { throw 'docker not available' }
} catch {
    Write-Err "`n❌ Docker is not running or not on PATH`n"
    Write-Host "To start Docker:`n  Docker Desktop -> Start (or ensure 'docker' is on PATH)`n"
    exit 1
}

Write-Info "✓ Docker is running"

# Clean up existing containers (non-fatal)
Write-Info "Cleaning up existing containers..."
try { & docker compose down --remove-orphans >$null 2>&1 } catch { }

# Detect STM32 device on Windows (COM ports) or use provided -ComPort
Write-Info "Looking for STM32 device..."
$stm32Port = $null
if ($ComPort) {
    $stm32Port = $ComPort
} else {
    try {
        $serialPorts = [System.IO.Ports.SerialPort]::GetPortNames()
        if ($serialPorts -and $serialPorts.Length -gt 0) { $stm32Port = $serialPorts[0] }
    } catch { }
}

if ($stm32Port) {
    Write-Info "Found STM32 device at: $stm32Port"
    # If user supplied BridgeArgs explicitly, use that; otherwise build default
    if ($BridgeArgs) { $env:BRIDGE_ARGS = $BridgeArgs } else { $env:BRIDGE_ARGS = "--port $stm32Port --baud 115200 --ws-port 8765" }
} else {
    Write-Info "No STM32 device found. Starting in simulation mode..."
    if ($BridgeArgs) { $env:BRIDGE_ARGS = $BridgeArgs } else { $env:BRIDGE_ARGS = $env:BRIDGE_ARGS -or "" }
}

# Ensure host-side received_files exists and export into environment (or honor override)
if ($HostReceivedDir) {
    $env:HOST_RECEIVED_DIR = $HostReceivedDir
} else {
    $receivedDir = Join-Path -Path (Get-Location) -ChildPath 'received_files'
    if (-not (Test-Path $receivedDir)) { New-Item -ItemType Directory -Path $receivedDir | Out-Null }
    $env:HOST_RECEIVED_DIR = $receivedDir
}

Write-Info "Building and starting services..."
try {
    & docker compose up --build -d --quiet-pull 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw 'compose up failed'
    }
} catch {
    Write-Err "❌ Error: Failed to start services"
    Write-Host "--- Recent logs ---"
    & docker compose logs --tail 10
    exit 1
}

Write-Host ""
Write-Host "XCOM System is ready:"
Write-Host ""
Write-Host "   STM32 IP: $($env:STM32_IP)"
Write-Host "   Web UI: http://localhost:8000"
Write-Host ""
Write-Host "   Commands:"
Write-Host '   - View logs:    docker compose logs -f'
Write-Host '   - Stop system:  .\start_xcom_tx.ps1 stop'
Write-Host ""
