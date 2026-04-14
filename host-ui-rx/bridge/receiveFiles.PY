import ftd2xx as ftd
import time
import sys

def main():
    # 1. Connect to the FT232H
    try:
        dev = ftd.open(0)
        print(f"[+] Connected to: {dev.getDeviceInfo()['description'].decode()}")
    except ftd.ftd2xx.DeviceError:
        print("[!] ERROR: FT232H not found. Check USB connection.")
        sys.exit(1)

    dev.resetDevice()
    dev.setUSBParameters(65536, 65536)
    dev.setTimeouts(1000, 1000)
    
    # 1. Force the chip to clear any previous Sync states
    dev.setBitMode(0x00, 0x00) 
    
    dev.purge(ftd.defines.PURGE_RX | ftd.defines.PURGE_TX)
    print("[+] Async Mode Active. Listening for data...")

    print("[+] Listening for 10 Mbps optical data...")
    print("[+] Press Ctrl+C to stop recording.\n")

    bytes_received = 0
    start_time = time.time()

    # 3. Open a binary file and start draining the hardware buffer
    try:
        with open("optical_payload.bin", "wb") as f:
            while True:
                # Ask the silicon exactly how many bytes are currently waiting
                rx_queue = dev.getQueueStatus()
                
                if rx_queue > 0:
                    # Read the exact chunk size available with zero overhead
                    chunk = dev.read(rx_queue)
                    f.write(chunk)
                    bytes_received += len(chunk)
                
                # 4. Bandwidth Monitor (Updates every 1 second)
                current_time = time.time()
                if current_time - start_time >= 1.0:
                    megabits_per_sec = (bytes_received * 8) / 1_000_000
                    print(f"Bandwidth: {megabits_per_sec:.2f} Mbps | Total Saved: {f.tell() / 1024:.1f} KB")
                    
                    bytes_received = 0
                    start_time = current_time

    except KeyboardInterrupt:
        print("\n[!] Transfer stopped by user.")
    finally:
        dev.close()
        print("[+] Device closed. Data safely written to optical_payload.bin")

if __name__ == "__main__":
    main()