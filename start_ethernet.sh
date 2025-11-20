#!/bin/bash
# Quick start script for Ethernet-based XCOM system

set -e

# Default configuration
STM32_IP=${STM32_IP:-"192.168.1.100"}
STM32_PORT=${STM32_PORT:-"5000"}

echo "=== XCOM Ethernet File Transfer System ==="
echo ""
echo "Configuration:"
echo "  STM32 IP:   $STM32_IP"
echo "  STM32 Port: $STM32_PORT"
echo "  Web UI:     http://127.0.0.1:8000"
echo "  WebSocket:  ws://127.0.0.1:8765"
echo ""

# Check if STM32 is reachable
echo "Testing connection to STM32..."
if ping -c 1 -W 2 $STM32_IP >/dev/null 2>&1; then
    echo "✓ STM32 is reachable at $STM32_IP"
else
    echo "⚠ Warning: Cannot ping $STM32_IP"
    echo "  Make sure:"
    echo "  - STM32 is powered on"
    echo "  - Ethernet cable is connected"
    echo "  - Both devices are on same network"
    echo "  - IP address is correct"
    echo ""
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo ""
echo "Starting bridge..."

# Start the bridge with Python
cd "$(dirname "$0")/host-ui-tx/bridge"

if [ -f "venv/bin/activate" ]; then
    echo "Using virtual environment..."
    source venv/bin/activate
fi

python bridge.py \
    --stm32-ip "$STM32_IP" \
    --stm32-port "$STM32_PORT" \
    --ws-port 8765 \
    --web-port 8000 \
    --host 0.0.0.0

