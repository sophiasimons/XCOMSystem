import socket
import time

# Configuration
NUCLEO_IP = '192.168.0.10'
PORT = 5000
CHUNK_SIZE = 1024        # 1 KB payload
TARGET_MBPS = 10         # Target speed in Mbit/s

# Calculate delay to maintain target bitrate
# (Bits per second) / 8 = Bytes per second
BYTES_PER_SEC = (TARGET_MBPS * 1_000_000) / 8
PACKETS_PER_SEC = BYTES_PER_SEC / CHUNK_SIZE
DELAY = 1.0 / PACKETS_PER_SEC

print(f"Targeting {TARGET_MBPS} Mbit/s")
print(f"Delay between packets: {DELAY*1000:.3f} ms")

# Generate dummy data
payload = bytes([0xAA] * CHUNK_SIZE) # 0xAA is easy to see on Logic Analyzer (10101010)

try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((NUCLEO_IP, PORT))
    print("Connected! Streaming...")

    while True:
        start_time = time.time()
        
        sock.sendall(payload)
        
        # Compensate for execution time to stay accurate
        elapsed = time.time() - start_time
        sleep_time = DELAY - elapsed
        
        if sleep_time > 0:
            time.sleep(sleep_time)

except KeyboardInterrupt:
    print("Stopped by user.")
except Exception as e:
    print(f"Error: {e}")
finally:
    sock.close()