# XCOMSystem

ECE3906 Capstone project 2025-26

## Table of Contents

- [Introduction](#introduction)
    - [Software Installation](#section-1)
- [Transmitting Software UI Set-up](#transmitting-software-ui-set-up)
- [Section 3](#section-3)
- [Section 4](#section-4)

# Introduction

# Software Installation

## Transmitting Software UI Setup

1. Cd into the host-ui folder: 
    `cd host-ui`
2. Run the `start_xcom.sh` script to begin building the transmitter:
    `./start_xcom.sh`
    To stop:
    `./start_xcom.sh stop`
4. Open http://localhost:8000 in your browser to view

    Stuff on how to select a file and send it yada yada



To connect STM32:
1. Start bridge with correct serial port:
`python bridge.py --port /dev/tty.usbserial-XXXX --baud 115200 --ws-port 8765`
 (need serial port where usbserial-xxxx is)
NOTE: need to have data cable, not just charging (longer prongs on inside)

## Section 3

## Section 4
