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
    echo "❌ Error: Docker is not available"
    echo "Please ensure Docker Desktop is installed and running"
    echo "Get Docker Desktop from: https://www.docker.com/products/docker-desktop"
    exit 1
fi

# Clean up any existing containers
echo "Cleaning up existing containers..."
docker compose down --remove-orphans >/dev/null 2>&1

# Check for STM32 device
echo "Looking for STM32 device..."
STM32_PORT=$(ls /dev/tty.usbmodem* /dev/ttyACM* /dev/tty.usb* /dev/ttyUSB* 2>/dev/null | head -n 1)
if [ -n "$STM32_PORT" ]; then
    echo "Found STM32 device at: $STM32_PORT"
    export BRIDGE_ARGS="--port $STM32_PORT --baud 115200 --ws-port 8765"
else
    echo "No STM32 device found. Starting in simulation mode..."
fi

# Build and start services
echo "Building and starting services..."
if ! docker compose up --build -d --quiet-pull >/dev/null 2>&1; then
    echo "❌ Error: Failed to start services"
    docker compose logs --tail 10
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