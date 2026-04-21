# XCOMSystem

ECE4905 Capstone Project 2025-2026

## Table of Contents

- [Introduction](#introduction)
    - [Terms Used in this Documentation](#terms-used-in-this-documentation)
- [Software Set-Up](#software-set-up)
    - [Cloning this Repository](#cloning-this-repository)
    - [Required Software](#required-software)
    - [Verifying Installation](#verifying-installation)
    - [Establishing Ethernet/STM32 connection](#establishing-ethernet-to-stm32-connection)
- [Transmitting UI](#transmitting-ui)
    - [TX Set-Up](#tx-set-up)
    - [Transmitting Your Data](#transmitting-your-data)
- [Receiving UI](#receiving-ui)
    - [RX Set-Up](#rx-set-up)
    - [Receiving Your Data](#receiving-your-data)
- [FPGA Setup](#fpga-setup)
    - [Programming The FPGA](#programming-the-fpga)
    - [Tuning the Comparator](#tuning-the-comparator-with-the-fpga)
- [Physcial Design](#physical-design)
    - [OnShape Project]
# Introduction

### Terms Used in this Documentation:

| Term | Definition |
|------|------------|
|  RX    |   Receiving Side   |
|  TX    |   Transmitting Side   |
|  UI   |   User Interface (the web app in this case)   |
|      |            |


## Software Set-Up

Before using the XCOM system, ensure you complete the following sections **on BOTH TX and RX laptops (unless otherwise stated, it is not needed)**:


### Cloning this Repository

To get a copy of this project on your local machine:

1. Click the green "Code" button near the top of the page

2. In the dropdown menu, you have several options:
   - For HTTPS: Copy the HTTPS URL (preferred)
   - For SSH: Click SSH and copy the SSH URL (if you have SSH keys set up)

3. Complete these steps in your terminal with the copied URL from Step 3:
```bash
# Navigate to where you want to store the project
cd desired/location

# Clone the repository
git clone <paste-the-copied-url>
```

Alternatively, to download as a ZIP file:
   - Click "Download ZIP"
   - Extract the ZIP file to your desired location


### Required Software
1. **Python 3.7+**
   - Check version: `python --version` or `python3 --version`
   - Download: [Python Official Website](https://www.python.org/downloads/)

2. **pip (Python package manager)**
   - Check version: `pip --version` or `pip3 --version`
   - Usually comes with Python installation

3. **Docker**
   - Download: [Docker Desktop](https://www.docker.com/products/docker-desktop/)
   - Check version: `docker --version`
   - Check Docker service: `docker info`

4. **Docker Compose**
   - Check version: `docker-compose --version`
   - Usually comes with Docker Desktop installation

5. **Git**
   - Check version: `git --version`
   - Download: [Git SCM](https://git-scm.com/downloads)

### Python Dependencies
Install the required Python packages:
```bash
# Install dependencies used by the bridge and host-side helpers.
# The repository includes requirements files for the RX bridge. Prefer
# installing from those so package versions stay consistent.

# For the RX bridge and host helpers (recommended):
python3 -m pip install --user -r host-ui-rx/bridge/requirements.txt

# For the TX bridge (if you plan to run the transmitter bridge locally):
if [ -f host-ui-tx/bridge/requirements.txt ]; then
    python3 -m pip install --user -r host-ui-tx/bridge/requirements.txt
else
    # fallback: common packages used across the project
    python3 -m pip install --user websockets pyserial requests
fi
```

### Host FTDI (Adafruit / FT232H) requirements (RECEIVING LAPTOP ONLY)

- FTDI D2XX driver download and instructions (find readme file with instructions in donwload):
    https://ftdichip.com/drivers/d2xx-drivers/

- macOS / Windows:
    1. Download and install the D2XX driver package from FTDI's site.
    2. Install the Python binding (may require a platform wheel):

```bash
# macOS example (after installing the FTDI driver):
python3 -m pip install --user ftd2xx requests
# Alternatively, to use libusb/pyftdi instead of D2XX (recommended on Linux/macOS
# if you prefer open-source stack), first install libusb then install pyftdi:
# macOS (Homebrew):
#   brew install libusb
#   python3 -m pip install --user pyftdi requests
# Linux (Debian/Ubuntu):
#   sudo apt-get install libusb-1.0-0-dev
#   python3 -m pip install --user pyftdi requests
```

- Linux:
    - If using the FTDI-provided D2XX driver, follow the FTDI Linux instructions
        linked above. Alternately, many Linux setups use libftdi/pyftdi, but the
        `ftdi_poster.py` expects the `ftd2xx` package unless you adapt it.

Notes:
- The host-side `ftdi_poster.py` (or the bridge's integrated FTDI reader) is
    intended to run on the host (outside of Docker) so it can access the system's
    native USB stack and drivers. On macOS Docker runs inside a VM and USB
    passthrough is unreliable; running the bridge locally avoids these issues.
- If you cannot install `ftd2xx`, you can use `pyftdi` (libusb) as an
    alternative after installing `libusb` on the host.


### Verifying Installation
Run these commands to ensure all required software is properly installed:
```bash
# Check Python
python --version

# Check pip
pip --version

# Check Docker
docker --version
docker-compose --version

# Check Git
git --version

# Verify Docker is running (TX laptop)
docker ps

```
### Establishing Ethernet to STM32 Connection

1. Connect the STM32 to your laptop via Ethernet and power it on.

2. Open a terminal and try to ping the default STM32 IP address:

    ```bash
    ping 192.168.1.10
    ```

3. If the ping succeeds, your Ethernet link is working and you can proceed.

    **Example of a successful ping (macOS/Linux):**
    ```
    PING 192.168.1.10 (192.168.1.10): 56 data bytes
    64 bytes from 192.168.1.10: icmp_seq=0 ttl=64 time=0.845 ms
    64 bytes from 192.168.1.10: icmp_seq=1 ttl=64 time=0.781 ms
    64 bytes from 192.168.1.10: icmp_seq=2 ttl=64 time=0.802 ms
    
    --- 192.168.1.10 ping statistics ---
    3 packets transmitted, 3 packets received, 0.0% packet loss
    ```

4. If the ping does **not** succeed, open your network settings and set the
   STM32’s IP to `192.168.1.10`, then try the ping again.

5. If it still does not work, change the STM32’s IP to `192.168.1.50` (or any other value for the last two digits of the IP) and try
   pinging `192.168.1.10` again to verify your laptop can see the STM32.

    If that still fails, confirm your Ethernet adapter is connected and that
    your laptop is on the same subnet as the STM32 (255.255.255.0).


# Transmitting UI

### TX Set-Up

1. Cd into the **host-ui-tx** folder: 
    ```bash
    cd host-ui-tx
    ```
2. Start Docker based on your OS:

    **MacOS:** Open the app on your laptop, searching in Applications for "Docker"
   
    **Windows:** Start Docker Desktop from the Start Menu

    **Linux:** Run this command in your terminal:
    ```bash   
    sudo systemctl start docker
    ```
3. Run the start script to begin building the transmitter. Choose the instruction that matches your OS:

   macOS / Linux (bash / zsh)

    ```bash
    STM32_IP=192.168.1.10 ./start_xcom_tx.sh
    ```

   Windows (PowerShell)

    If you're on Windows use the PowerShell wrapper `start_xcom_tx.ps1` (recommended) or run via `pwsh`:

    ```powershell

    powershell.exe -ExecutionPolicy Bypass -File "start_xcom_tx.ps1" -Ip <your-working-ip>
    ```

   Alternative (use PowerShell Core from other shells):

    ```bash
    # from Git Bash, WSL, macOS, etc. if pwsh is installed
    pwsh -NoProfile -File ./host-ui-tx/start_xcom_tx.ps1 -Ip <your-working-ip>
    ```

   To stop the services:
    ```bash
    # on Mac/Linux
    ./start_xcom_tx.sh stop

    # on Windows PowerShell
    .\start_xcom_tx.ps1 -Stop
    ```

    NOTE: You must stop the container running when you are finished using the XCOM system in order to smoothly restart the system at another time. 

4. Open http://localhost:8000 in your browser to view

### Transmitting Your Data

1. Ensure the STM32 Microcontroller is connected to the TX laptop: The system will only allow you to send while the laptop detects the microcontroller connected. You can track this status at the top right corner of the webpage.
2. Choose a file: Select the 'Choose File' button to open your laptop's File Manager, select a file and press 'Open'
3. Send File: It's as easy as clicking `SEND DATA`! 


# Receiving UI

## RX LAPTOP: Connect Adafruit (USB/FTDI) and Start Receiver

### RX Set-Up

1. Cd into the **host-ui-rx** folder:
    ```bash
    cd host-ui-rx
    ```

2. Start Docker based on your OS:

    **MacOS:** Open Docker Desktop from Applications

    **Windows:** Start Docker Desktop from the Start Menu

    **Linux:** Run this command in your terminal:
    ```bash
    sudo systemctl start docker
    ```

3. Run the `start_xcom_rx.sh` script to build and start the receiver. The script will
   automatically start the host FTDI poster if the `ftd2xx` Python binding is available
   on the host. No environment variables are required for the USB (FTDI) workflow.

     macOS / Linux (bash / zsh)

        ```bash
        cd host-ui-rx
        ./start_xcom_rx.sh
        ```

     Windows (PowerShell)

        ```powershell
        # run from the host-ui-rx folder
        powershell.exe -ExecutionPolicy Bypass -File "start_xcom_rx.ps1"
        ```
       If this doesn't work, check you have everything installed. Or run the bridge manually by running the bridge.py file. 

     To stop the bridge and any host helper processes:
        ```bash
        # on Mac/Linux
        ./start_xcom_rx.sh stop

        # on Windows PowerShell
        .\start_xcom_rx.ps1 stop
        ```

     Notes:
     - The script creates a Python virtual environment in `host-ui-rx/.venv` and
         installs required Python packages.
     - The bridge will start with its integrated FTDI reader (if available) and
         will also accept notifications from the host poster `ftdi_poster.py`.
     - If you prefer Docker for other parts of the project, you can still run
         services in containers, but the receiver/FTDI workflow works best when
         the bridge runs directly on the host.

3. Open the web UI at: http://localhost:8001

### Receiving Your Data

1. Ensure the Adafruit/FPGA is connected to the RX laptop over USB (FTDI/FT232H).
2. Ensure data has been sent from the TX laptop.
3. The host-side `ftdi_poster.py` will capture frames from the FTDI device and
    post notifications to the bridge so files appear in the Received files list.
4. Click the "Open" button in the UI to view or download received files. 
5. Optional: To check BER, you can select the `BER` button next to the file name and upload a       manually downloaded copy of the same file.


# FPGA Setup

## Programming the FPGA
There are two options available to the user for programming the FPGA.
1. Download the Optical Receiver zip files and import this project into Vivado 2025.2, this will allow you to connect to the FPGA via USB and program the Nexys A7.
2. Use the MicroSD card and adjust the onboard jumpers for the Nexys A7 to flash the MicroSD card's .bit file onto the board on startup.

## Tuning the Comparator with the FPGA
In order to properly recover the transmitted data the comparator must be tuned so that the output seen on the FPGA is correct. To tune the comparator the current method is to adjust the potentiometer while examining the waveform generated by the integrated logic analyzer on the FPGA.
If you have utilized the MicroSD card tuning will need to be done via oscilloscope and you will want to probe in JA2.

Attached is an image of the correct waveform for a properly tuned comparator:
<img width="700" height="78" alt="Screenshot 2026-04-15 163518" src="https://github.com/user-attachments/assets/3be1121b-b01d-46f4-9032-a27c1f4178fa" />




# Physical Design
 All hardware design files are located [here](https://github.com/sophiasimons/XCOMSystem/tree/main/hardware).
