# XCOM Test Programs

Cross-platform test utilities for TX and RX STM32 Ethernet connectivity.

## Files

- `test_connection.c` - Tests sending data to TX STM32
- `test_receive.c` - Tests receiving data from RX STM32
- `txtFile.txt` - Sample text file for testing

## Building

### macOS/Linux

```bash
# Option 1: Use build script
chmod +x build.sh
./build.sh

# Option 2: Manual compilation
gcc -o test_connection test_connection.c
gcc -o test_receive test_receive.c
```

### Windows

#### Option 1: Visual Studio (MSVC)

1. Open "Developer Command Prompt for VS"
2. Navigate to this directory
3. Run:
   ```cmd
   build.bat
   ```

Or manually compile:
```cmd
cl /Fe:test_connection.exe test_connection.c /link ws2_32.lib
cl /Fe:test_receive.exe test_receive.c /link ws2_32.lib
```

#### Option 2: MinGW-w64

1. Install MinGW-w64 or MSYS2
2. Run:
   ```cmd
   build_mingw.bat
   ```

Or manually compile:
```cmd
gcc -o test_connection.exe test_connection.c -lws2_32
gcc -o test_receive.exe test_receive.c -lws2_32
```

## Running Tests

### Test TX STM32 (Sending)

**macOS/Linux:**
```bash
./test_connection 192.168.1.100 5000
```

**Windows:**
```cmd
test_connection.exe 192.168.1.100 5000
```

This will:
1. Ping the TX STM32
2. Test TCP connection
3. Send `txtFile.txt` to the STM32

### Test RX STM32 (Receiving)

**macOS/Linux:**
```bash
./test_receive 192.168.1.101 5000
```

**Windows:**
```cmd
test_receive.exe 192.168.1.101 5000
```

This will:
1. Ping the RX STM32
2. Test TCP connection
3. Wait to receive data (30 second timeout)
4. Save received data to timestamped file

## End-to-End Test

**Terminal 1 (RX side):**
```bash
# macOS/Linux
./test_receive 192.168.1.101 5000

# Windows
test_receive.exe 192.168.1.101 5000
```

**Terminal 2 (TX side):**
```bash
# macOS/Linux
./test_connection 192.168.1.100 5000

# Windows
test_connection.exe 192.168.1.100 5000
```

## Troubleshooting

### Windows Compilation Errors

**"'cl' is not recognized"**
- Install Visual Studio or Build Tools
- Use "Developer Command Prompt for VS"
- Or use MinGW with `build_mingw.bat`

**"'gcc' is not recognized"**
- Install MinGW-w64: https://www.mingw-w64.org/
- Or install MSYS2: https://www.msys2.org/

**Winsock errors**
- Make sure `ws2_32.lib` is linked (handled by build scripts)
- The code already includes proper Windows socket initialization

### Network Issues

**Ping fails:**
- Check Ethernet cable connection
- Verify IP address matches STM32 configuration
- Ensure firewall allows ICMP (ping)

**TCP connection fails:**
- Verify STM32 is powered on and running code
- Check STM32 IP configuration in .ioc file
- Ensure firewall allows port 5000
- Verify tx_main.c or rx_main.c is flashed to STM32

**Data transfer fails:**
- Make sure `txtFile.txt` exists in current directory
- Check STM32 has enough RAM for file buffer
- Verify LwIP is properly configured in STM32CubeIDE

### File Permissions (macOS/Linux)

If you get "Permission denied":
```bash
chmod +x build.sh
chmod +x test_connection
chmod +x test_receive
```

## IP Configuration

Default IPs (modify in .ioc file or command line):
- TX STM32: `192.168.1.100:5000`
- RX STM32: `192.168.1.101:5000`

To use different IPs, pass as arguments:
```bash
./test_connection 192.168.0.10 5000
./test_receive 192.168.0.11 5000
```
