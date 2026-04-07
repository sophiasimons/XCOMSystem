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

# Detect FPGA board (prefer FPGA_IP env if provided)
$FPGA_CONNECTED = $false
if ($env:FPGA_IP) {
    # Write-Info "Checking for FPGA at $env:FPGA_IP..."
    try {
        if (Test-Connection -Quiet -Count 1 -ComputerName $env:FPGA_IP -TimeoutSeconds 1) {
            # Write-Info "Found FPGA at $env:FPGA_IP"
            $FPGA_CONNECTED = $true
        } else {
            # Write-Info "FPGA at $env:FPGA_IP not reachable"
        }
    } catch { }
} else {
    # Write-Info "FPGA_IP not set; starting without FPGA connection. To enable, set `\$env:FPGA_IP`."
}

# Build BRIDGE_ARGS (will be exported into the compose environment)
$BRIDGE_ARGS = "--ws-port 8766 --web-port 8001 --host 0.0.0.0"
if ($FPGA_CONNECTED) {
    if (-not $env:FPGA_PORT) { $env:FPGA_PORT = '5001' }
    if (-not $env:FPGA_BITPACKED) { $env:FPGA_BITPACKED = '0' }
    if (-not $env:FPGA_BITORDER) { $env:FPGA_BITORDER = 'msb' }
    $BRIDGE_ARGS = "$BRIDGE_ARGS --fpga-port $env:FPGA_PORT"
    if ($env:FPGA_BITPACKED -ne '0') { $BRIDGE_ARGS = "$BRIDGE_ARGS --fpga-bitpacked" }
    $BRIDGE_ARGS = "$BRIDGE_ARGS --fpga-bitorder $env:FPGA_BITORDER"
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
