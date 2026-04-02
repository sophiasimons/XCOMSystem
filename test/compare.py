import sys
import os

def compare_binary_files(file1_path, file2_path, max_errors=15):
    print(f"[*] Comparing:\n    1: {file1_path}\n    2: {file2_path}\n")

    try:
        size1 = os.path.getsize(file1_path)
        size2 = os.path.getsize(file2_path)
    except FileNotFoundError as e:
        print(f"[!] Error: {e}")
        return

    # Check for dropped or duplicated bytes
    if size1 != size2:
        print(f"[!] WARNING: File sizes do not match!")
        print(f"    File 1: {size1} bytes")
        print(f"    File 2: {size2} bytes")
        print(f"    Difference: {abs(size1 - size2)} bytes")
        print("-" * 40)

    errors_found = 0
    offset = 0

    with open(file1_path, 'rb') as f1, open(file2_path, 'rb') as f2:
        while True:
            b1 = f1.read(1)
            b2 = f2.read(1)

            # End of file(s)
            if not b1 and not b2:
                break
            
            # One file ended before the other
            if not b1 or not b2:
                print(f"[!] Reached EOF on one file at offset {hex(offset)} ({offset})")
                break

            if b1 != b2:
                if errors_found == 0:
                    print(f"Mismatch Details:")
                    print(f"{'Offset (Hex)':<15} | {'Offset (Dec)':<15} | {'File 1':<10} | {'File 2':<10}")
                    print("-" * 55)

                if errors_found < max_errors:
                    print(f"{hex(offset):<15} | {offset:<15} | 0x{b1.hex().upper():<8} | 0x{b2.hex().upper():<8}")
                elif errors_found == max_errors:
                    print(f"... and more (suppressing further output)")
                
                errors_found += 1

            offset += 1

    print("-" * 40)
    if errors_found == 0 and size1 == size2:
        print("[+] SUCCESS: The files are 100% bit-for-bit identical!")
    else:
        print(f"[!] FAILED: Found {errors_found} byte mismatches.")

if __name__ == "__main__":
    # Change these to your actual test payload and received file
    ORIGINAL_FILE = "optical_payload_cleaned2.bin" 
    RECEIVED_FILE = "10mb_file.bin"

    compare_binary_files(ORIGINAL_FILE, RECEIVED_FILE)