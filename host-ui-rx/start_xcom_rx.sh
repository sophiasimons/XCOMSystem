#!/bin/bash
set -e  # Exit on any error

# Handle stop command
if [ "$1" = "stop" ]; then
    echo "Stopping XCOM RX System..."
    docker compose down -v --remove-orphans >/dev/null 2>&1
    exit 0
fi

cd "$(dirname "$0")"

echo "Starting XCOM RX System..."

# Check if Docker is available and running
if ! docker info >/dev/null 2>&1; then
    echo ""
    echo "❌ Docker is not running"
    echo ""
    echo "To start Docker:"
    echo "  macOS:   Open Docker Desktop from Applications"
    echo "  Linux:   sudo systemctl start docker"
    echo "  Windows: Start Docker Desktop from Start Menu"
    echo ""
    echo "Then run this script again: ./start_xcom_rx.sh"
    echo ""
    exit 1
fi

echo "✓ Docker is running"

# Clean up any existing containers
echo "Cleaning up existing containers..."
docker compose down --remove-orphans >/dev/null 2>&1 || true


# detect FPGA board (prefer FPGA_IP env if provided)
FPGA_CONNECTED=0
if [ -n "$FPGA_IP" ]; then
    echo "Checking for FPGA at $FPGA_IP..."
    if ping -c 1 -W 1 "$FPGA_IP" >/dev/null 2>&1; then
        echo "Found FPGA at $FPGA_IP"
        FPGA_CONNECTED=1
        export FPGA_IP
    else
        echo "FPGA at $FPGA_IP not reachable"
    fi
else
    echo "FPGA_IP not set; starting without FPGA connection. To enable, set FPGA_IP environment variable."
fi

# Build BRIDGE_ARGS so the container will start the bridge with FPGA listener when present.
# If an FPGA was detected, include --fpga-port and optional flags; otherwise use defaults.
BRIDGE_ARGS="--ws-port 8766 --web-port 8001 --host 0.0.0.0"
if [ "$FPGA_CONNECTED" -eq 1 ]; then
    : "${FPGA_PORT:=5001}"
    : "${FPGA_BITPACKED:=0}"
    : "${FPGA_BITORDER:=msb}"
    BRIDGE_ARGS="$BRIDGE_ARGS --fpga-port $FPGA_PORT"
    if [ "$FPGA_BITPACKED" != "0" ]; then
        BRIDGE_ARGS="$BRIDGE_ARGS --fpga-bitpacked"
    fi
    BRIDGE_ARGS="$BRIDGE_ARGS --fpga-bitorder $FPGA_BITORDER"
    export FPGA_PORT FPGA_BITPACKED FPGA_BITORDER
fi
export BRIDGE_ARGS

# Ensure host-side received_files exists and export path so container knows host path
mkdir -p "$(pwd)/received_files"
export HOST_RECEIVED_DIR="$(pwd)/received_files"

# Build and start services. If the user wants a custom STM32 host port mapping, they
# can export STM32_PORT beforehand (e.g. STM32_PORT=5010 ./start_xcom_rx.sh).
echo "Building and starting services..."
if ! docker compose up --build -d --quiet-pull >/dev/null 2>&1; then
    echo "❌ Error: Failed to start services"
    docker compose logs --tail 10 || true
    exit 1
fi

# Show success message
echo "
XCOM RX System is ready:

   Web UI: http://localhost:8001

   Commands:
   - View logs:    docker compose logs -f
   - Stop system:  ./start_xcom_rx.sh stop
"