#!/bin/bash

# XCOM System Startup Script
echo "Starting XCOM System"

# Function to find STM32 device port
find_stm32_port() {
    # Try different possible patterns for STM32 device
    for pattern in "/dev/tty.usbmodem*" "/dev/ttyACM*" "/dev/tty.usb*" "/dev/ttyUSB*"; do
        port=$(ls $pattern 2>/dev/null | head -n 1)
        if [ ! -z "$port" ]; then
            echo "$port"
            return 0
        fi
    done
    echo ""
    return 1
}

# Check if Docker is running
if ! docker info >/dev/null 2>&1; then
    echo "Error: Docker is not running. Please start Docker first."
    exit 1
fi

# Clean up any existing containers
echo "Cleaning up existing containers..."
docker-compose down --remove-orphans >/dev/null 2>&1

# Find STM32 device
echo "Looking for STM32 device..."
STM32_PORT=$(find_stm32_port)

if [ -z "$STM32_PORT" ]; then
    echo "Warning: No STM32 device found. Will start in simulation mode."
    BRIDGE_ARGS="--ws-port 8765"
else
    echo "Found STM32 device at: $STM32_PORT"
    BRIDGE_ARGS="--port $STM32_PORT --baud 115200 --ws-port 8765"
fi

# Export the bridge arguments for docker-compose
export BRIDGE_ARGS

# Build and start the containers
echo "🏗️  Building containers..."
docker-compose build

echo "Starting services..."
docker-compose up -d

# Show status and instructions
echo "
XCOM System is ready.

Web UI: http://localhost:8000
Bridge: ws://localhost:8765

To view logs:
  docker-compose logs -f

To stop:
  ./start_xcom.sh stop

"

# Handle stop command
if [ "$1" = "stop" ]; then
    echo "🛑 Stopping XCOM System..."
    docker-compose down
    echo "✅ Stopped"
    exit 0
fi