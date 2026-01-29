set -e  # Exit on any error

# Handle stop command
if [ "$1" = "stop" ]; then
    echo "Stopping XCOM System..."
    docker compose down -v --remove-orphans >/dev/null 2>&1
    exit 0
fi
cd "$(dirname "$0")"

echo "Starting XCOM System..."

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
    echo "Then run this script again: ./start_xcom_tx.sh"
    echo ""
    exit 1
fi

echo "✓ Docker is running"

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
XCOM System is ready:

   Web UI: http://localhost:8000

   Commands:
   - View logs:    docker compose logs -f
   - Stop system:  ./start_xcom_tx.sh stop
"