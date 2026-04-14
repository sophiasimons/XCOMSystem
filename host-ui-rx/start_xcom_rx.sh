#!/bin/bash
set -e  # Exit on any error

# Handle stop command
if [ "$1" = "stop" ]; then
    echo "Stopping XCOM RX System..."
    # Try to stop local bridge if running
    if [ -f ./bridge.pid ]; then
        pid=$(cat ./bridge.pid)
        echo "Stopping local bridge (pid $pid)"
        kill "$pid" >/dev/null 2>&1 || true
        rm -f ./bridge.pid
    fi
    # If Docker was used, stop containers
    docker compose down -v --remove-orphans >/dev/null 2>&1 || true
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

# By default run the bridge locally (not in Docker) so native FTDI drivers
# and direct USB access work. To run with Docker instead set USE_DOCKER=1.
if [ "${USE_DOCKER:-0}" != "1" ]; then
    echo "Running bridge locally (not using Docker)."

    # Build BRIDGE_ARGS similar to the container case
    BRIDGE_ARGS="--ws-port 8766 --web-port 8001 --host 0.0.0.0"
    if [ -n "$ADAFRUIT_PORT" ]; then
        BRIDGE_ARGS="$BRIDGE_ARGS --adafruit-port $ADAFRUIT_PORT"
        export ADAFRUIT_PORT
    fi
    export BRIDGE_ARGS

    # Ensure host-side received_files exists and export path
    mkdir -p "$(pwd)/received_files"
    export HOST_RECEIVED_DIR="$(pwd)/received_files"

    # Ensure Python venv and dependencies
    VENV_DIR=".venv"
    PYTHON_BIN="python3"
    if ! command -v $PYTHON_BIN >/dev/null 2>&1; then
        echo "❌ python3 not found. Please install Python 3.8+ and re-run this script."
        exit 1
    fi

    if [ ! -d "$VENV_DIR" ]; then
        echo "Creating virtualenv in $VENV_DIR..."
        $PYTHON_BIN -m venv "$VENV_DIR"
    fi

    echo "Activating virtualenv and installing Python dependencies..."
    # Use pip from the venv so system packages aren't modified
    "$VENV_DIR/bin/pip" install --upgrade pip >/dev/null 2>&1 || true
    "$VENV_DIR/bin/pip" install -r requirements.txt || {
        echo "Failed to install Python requirements. Please inspect the output above and install dependencies manually.";
        exit 1;
    }

    # Quick checks for native FTDI driver availability
    echo "Checking for FTDI native driver availability (ftd2xx)..."
    if "$VENV_DIR/bin/python" -c "import ftd2xx" >/dev/null 2>&1; then
        echo "ftd2xx Python binding available in venv. If using D2XX driver make sure libftd2xx is installed on the host."
    else
        echo "ftd2xx not importable in venv. You may still be able to use pyftdi (libusb) if libusb is installed."
        echo "If you want D2XX (FTDI) support, install the D2XX driver from FTDI and then reinstall the 'ftd2xx' Python package into .venv."
    fi

    # Start the bridge locally
    echo "Bridge started (pid: $(cat ./bridge.pid)). Web UI: http://localhost:8001"

    # Optionally, if the user still wants the host-side poster (separate process that reads FTDI and POSTS)
    if [ "${START_HOST_POSTER:-0}" = "1" ]; then
        echo "Starting host ftdi_poster (poster will POST to bridge)..."
        BRIDGE_NOTIFY_URL=http://localhost:8001/api/notify_new_file nohup "$VENV_DIR/bin/python" ./bridge/ftdi_poster.py ${FTDI_INDEX:-2} > ./ftdi_poster.log 2>&1 &
        echo $! > ./ftdi_poster.pid
        echo "FTDI poster started (log: ./ftdi_poster.log, pid: $(cat ./ftdi_poster.pid))"
    fi

    echo "To stop: ./start_xcom_rx.sh stop"
    exit 0
else
    echo "USE_DOCKER=1 set; falling back to Docker compose startup."
    echo "Cleaning up existing containers..."
    docker compose down --remove-orphans >/dev/null 2>&1 || true

    echo "Building and starting services via Docker Compose..."
    if ! docker compose up --build -d --quiet-pull >/dev/null 2>&1; then
        echo "❌ Error: Failed to start services via Docker Compose"
        docker compose logs --tail 10 || true
        exit 1
    fi
fi