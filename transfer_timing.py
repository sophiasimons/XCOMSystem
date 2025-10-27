#!/usr/bin/env python3
import os
import sys
import math

# Configuration
CHUNK_SIZE = 16 * 1024  # 16KB chunks
BAUD_RATES = {
    '9600': 9600,
    '19200': 19200,
    '38400': 38400,
    '57600': 57600,
    '115200': 115200,
    '230400': 230400,
    '460800': 460800,
    '921600': 921600
}

# Protocol overhead per chunk (example values)
HEADER_SIZE = 4  # 4 bytes for size header
CHUNK_HEADER = 2  # 2 bytes per chunk for sequence number
CHUNK_FOOTER = 2  # 2 bytes for chunk checksum
PROCESSING_TIME_MS = 5  # Estimated MCU processing time per chunk in milliseconds

def calculate_transfer_time(file_size, baud_rate):
    # Calculate number of chunks
    num_chunks = math.ceil(file_size / CHUNK_SIZE)
    
    # Calculate total protocol overhead
    total_overhead = HEADER_SIZE + (num_chunks * (CHUNK_HEADER + CHUNK_FOOTER))
    
    # Total bytes to transfer including overhead
    total_bytes = file_size + total_overhead
    
    # Calculate raw transfer time (in seconds)
    # For UART: 1 start bit + 8 data bits + 1 stop bit = 10 bits per byte
    bits_to_transfer = total_bytes * 10
    transfer_time_s = bits_to_transfer / baud_rate
    
    # Add processing time for each chunk
    total_processing_time_s = (num_chunks * PROCESSING_TIME_MS) / 1000
    
    # Total time including processing
    total_time_s = transfer_time_s + total_processing_time_s
    
    return {
        'file_size_bytes': file_size,
        'num_chunks': num_chunks,
        'protocol_overhead_bytes': total_overhead,
        'total_bytes': total_bytes,
        'raw_transfer_time_s': transfer_time_s,
        'processing_time_s': total_processing_time_s,
        'total_time_s': total_time_s
    }

def format_size(size_bytes):
    for unit in ['B', 'KB', 'MB']:
        if size_bytes < 1024:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.2f} GB"

def format_time(seconds):
    if seconds < 1:
        return f"{seconds*1000:.2f} ms"
    elif seconds < 60:
        return f"{seconds:.2f} seconds"
    else:
        minutes = int(seconds // 60)
        remaining_seconds = seconds % 60
        return f"{minutes} minutes {remaining_seconds:.2f} seconds"

def main():
    if len(sys.argv) != 2:
        print("Usage: ./transfer_timing.py <file_path>")
        sys.exit(1)
        
    file_path = sys.argv[1]
    
    try:
        file_size = os.path.getsize(file_path)
        print(f"\nAnalyzing transfer time for: {file_path}")
        print(f"File size: {format_size(file_size)}")
        print("\nTransfer time estimates for different baud rates:")
        print("-" * 80)
        print(f"{'Baud Rate':<12} {'Transfer Time':<20} {'Protocol Overhead':<20} {'Chunks':<10}")
        print("-" * 80)
        
        for baud_name, baud_rate in sorted(BAUD_RATES.items()):
            result = calculate_transfer_time(file_size, baud_rate)
            
            print(f"{baud_name:<12} "
                  f"{format_time(result['total_time_s']):<20} "
                  f"{format_size(result['protocol_overhead_bytes']):<20} "
                  f"{result['num_chunks']:<10}")
        
        # Detailed analysis for common baud rate
        print("\nDetailed analysis at 115200 baud:")
        result = calculate_transfer_time(file_size, 115200)
        print(f"Raw transfer time: {format_time(result['raw_transfer_time_s'])}")
        print(f"Processing time:   {format_time(result['processing_time_s'])}")
        print(f"Total time:       {format_time(result['total_time_s'])}")
        print(f"Data efficiency:  {(file_size / result['total_bytes'] * 100):.1f}%")
        
    except FileNotFoundError:
        print(f"Error: File '{file_path}' not found")
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    main()