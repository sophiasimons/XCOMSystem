import sys

def clean_bin(input_file, output_file):
    # The exact hex sequence leaking from your FPGA (0x4A followed by 0xB5)
    target_sequence = b'\x4a\xb5'

    try:
        # Read the raw binary data
        with open(input_file, 'rb') as f_in:
            data = f_in.read()

        # Scrub the sequence from the data
        # NOTE: If you meant removing *individual* bytes regardless of order, 
        # change this to: data = data.replace(b'\x4a', b'').replace(b'\xb5', b'')
        cleaned_data = data.replace(target_sequence, b'')

        # Write the cleaned data to a new file
        with open(output_file, 'wb') as f_out:
            f_out.write(cleaned_data)

        occurrences = (len(data) - len(cleaned_data)) // len(target_sequence)
        
        print(f"[+] Successfully cleaned '{input_file}'")
        print(f"    Original size: {len(data)} bytes")
        print(f"    Cleaned size:  {len(cleaned_data)} bytes")
        print(f"    Removed {occurrences} occurrences of 0x4A 0xB5.")
        print(f"[+] Saved payload to '{output_file}'")

    except FileNotFoundError:
        print(f"[!] Error: Could not find '{input_file}'. Check the filename.")
    except Exception as e:
        print(f"[!] An error occurred: {e}")

if __name__ == "__main__":
    # Change these strings to match your actual filenames!
    INPUT_FILENAME = "optical_payload.bin"
    OUTPUT_FILENAME = "optical_payload_cleaned.bin"
    
    clean_bin(INPUT_FILENAME, OUTPUT_FILENAME)