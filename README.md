# XCOMSystem

ECE3906 Capstone project 2025-26

## Table of Contents

- [Introduction](#introduction)
    - [Terms Used in this Documentation](#terms-used-in-this-documentation)
- [Software Prerequisites/Set-Up](#section-1)
    - [Cloning this Repository](#cloning-this-repository)
    - [Required Software](#required-software)
    - [Verifying Installation](#verifying-installation)
- [Transmitting UI](#transmitting-UI)
    - [TX Set-up](#tx-set-up)
- [Section 3](#section-3)
- [Section 4](#section-4)

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

# Transmitting UI

### TX Set-Up

1. Cd into the host-ui folder: 
    ```bash
    cd host-ui-tx
    ```
2. Run the `start_xcom.sh` script to begin building the transmitter:
    ```bash
    ./start_xcom.sh
    ```
    To stop:
    ```bash
    ./start_xcom_tx.sh stop
    ```
3. Open http://localhost:8000 in your browser to view

    Stuff on how to select a file and send it yada yada

### Transmitting Your Data

1. Ensure the STM32 Microcontroller is connected to the TX laptop:
2. Choose a file:
3. Send File:



## Section 3

## Section 4
