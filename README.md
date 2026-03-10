# XCOMSystem

ECE3906 Capstone project 2025-26

## Table of Contents

- [Introduction](#introduction)
    - [Terms Used in this Documentation](#terms-used-in-this-documentation)
- [Software Prerequisites/Set-Up](#section-1)
    - [Cloning this Repository](#cloning-this-repository)
    - [Required Software](#required-software)
    - [Verifying Installation](#verifying-installation)
    - [Establishing Ethernet/STM32 connection](#establising-ethernet/stm32-connection)
- [Transmitting UI](#transmitting-UI)
    - [TX Set-Up](#tx-set-up)
    - [Transmitting Your Data](#transmitting-your-data)
- [Receiving UI](#receiving-ui)
    - [RX Set-Up](#rx-set-up)
    - [Receiving Your Data](#receiving-your-data)
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


# Software Prerequisites/Set-Up

Before setting up the XCOM system, ensure you complete the following sections **on BOTH TX and RX laptops**:

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
   - Check version: `docker --version`
   - Check Docker service: `docker info`
   - Download: [Docker Desktop](https://www.docker.com/products/docker-desktop/)

4. **Docker Compose**
   - Check version: `docker-compose --version`
   - Usually comes with Docker Desktop installation

5. **Git**
   - Check version: `git --version`
   - Download: [Git SCM](https://git-scm.com/downloads)

### Python Dependencies
Install the required Python packages:
```bash
pip install websockets pyserial
```

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

# Verify Docker is running
docker ps
```
### Establishing Ethernet/STM32 Connection

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

5. If it still does not work, change the STM32’s IP to `192.168.5.10` and try
   pinging `192.168.1.10` again to verify your laptop can see the STM32.

    If that still fails, confirm your Ethernet adapter is connected and that
    your laptop is on the same subnet as the STM32.

    **The IP address that works with your laptop will be used as an input for the**
    **start up scripts, so copy this IP address to use later.**

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
3. Run the `start_xcom_tx.sh` script to begin building the transmitter:
    ```bash
    STM32_IP=<your-working-ip> ./start_xcom_tx.sh
    ```
    To stop:
    ```bash
    ./start_xcom_tx.sh stop
    ```
    NOTE: You must stop the container running when you are finished using the XCOM system in order to smoothly restart the system at another time. 

4. Open http://localhost:8000 in your browser to view

### Transmitting Your Data

1. Ensure the STM32 Microcontroller is connected to the TX laptop: The system will only allow you to send while the laptop detects the microcontroller connected. You can track this status at the top right corner of the webpage.
2. Choose a file: Select the 'Choose File' button to open your laptop's File Manager, select a file and press 'Open'
3. Send File: It's as easy as clicking `SEND DATA`! 


# Receiving UI

### RX Set-Up

1. Cd into the **host-ui-rx** folder: 
    ```bash
    cd host-ui-rx
    ```

2. Start Docker based on your OS:

    **MacOS:** Open the app on your laptop, searching in Applications for "Docker"
   
    **Windows:** Start Docker Desktop from the Start Menu

    **Linux:** Run this command in your terminal:
    ```bash   
    sudo systemctl start docker
    ```
3. Run the `start_xcom_rx.sh` script to begin building the transmitter:
    ```bash
    ./start_xcom_rx.sh
    ```
    To stop:
    ```bash
    ./start_xcom_rx.sh stop
    ```
    NOTE: You must stop the container running when you are finished using the XCOM system in order to smoothly restart the system at another time. 
    
4. Open http://localhost:8000 in your browser to view

    Stuff on how to select a file and send it yada yada

### Receiving Your Data

1. Ensure the FPGA is connected to the RX laptop:
2. Ensure data has been sent from the TX laptop:
3. Receive Data:



# Physical Design

The team has decided to use OnShape for version control and sharing the CAD work done for the LED hood. The OnShape document can be accessed by following [this](https://cad.onshape.com/documents/160594215cd894a2421d9008/w/7cbc5794dcd9044259dca69f/e/757ea2b3c66a400e93fe81c9?renderMode=0&uiState=690cc312c9d051bd86b585a4) link.
