#!/bin/bash
set -e  # Exit on any error

# Handle stop command
if [ "$1" = "stop" ]; then
    echo "Stopping XCOM RX System..."
    docker compose down -v --remove-orphans >/dev/null 2>&1
    # Kill host helper processes if they were started
    if [ -f ./ftdi_poster.pid ]; then
        pid=$(cat ./ftdi_poster.pid)
        echo "Stopping FTDI poster (pid $pid)"
        kill "$pid" >/dev/null 2>&1 || true
        rm -f ./ftdi_poster.pid
    fi
    if [ -f ./adafruit_forward.pid ]; then
        pid=$(cat ./adafruit_forward.pid)
        echo "Stopping Adafruit forward (pid $pid)"
        kill "$pid" >/dev/null 2>&1 || true
        rm -f ./adafruit_forward.pid
    fi
    # remove logs if desired (keep for debugging)
    # rm -f ./ftdi_poster.log ./adafruit_forward.log
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


# Build BRIDGE_ARGS so the container will start the bridge.
# By default we do not require any Adafruit network configuration because
# the recommended mode is USB/FTDI. If you do want the bridge to listen for
# an Adafruit TCP client, set ADAFRUIT_PORT before running this script.
BRIDGE_ARGS="--ws-port 8766 --web-port 8001 --host 0.0.0.0"
# If user explicitly set ADAFRUIT_PORT, pass it through so the bridge listens
if [ -n "$ADAFRUIT_PORT" ]; then
    BRIDGE_ARGS="$BRIDGE_ARGS --adafruit-port $ADAFRUIT_PORT"
    export ADAFRUIT_PORT
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

# If an FTDI device and Python bindings are present on the host, start the FTDI poster
# which will read framed files from the FT232H and notify the bridge via HTTP.
echo "Checking for FTDI (ftd2xx) support on the host..."
if python3 -c "import ftd2xx" >/dev/null 2>&1; then
    echo "Found ftd2xx Python binding. Starting host FTDI poster..."
    # Start in background, log to file. Use nohup so it survives if terminal closes.
    nohup python3 ./bridge/ftdi_poster.py ${FTDI_INDEX:-2} > ./ftdi_poster.log 2>&1 &
    echo $! > ./ftdi_poster.pid
    sleep 0.5
    echo "FTDI poster started (log: ./ftdi_poster.log, pid: $(cat ./ftdi_poster.pid))"
else
    echo "ftd2xx Python binding not found on host; skipping FTDI poster."
    echo "If you want FTDI integration, install ftd2xx on the host and re-run this script."
fi

# Show success message
echo "
XCOM RX System is ready:

   Web UI: http://localhost:8001

   Commands:
   - View logs:    docker compose logs -f
   - Stop system:  ./start_xcom_rx.sh stop
"