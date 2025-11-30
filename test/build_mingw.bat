@echo off
REM Build script for Windows using MinGW

echo Building test programs for Windows (MinGW)...
echo.

REM Check if MinGW gcc is available
where gcc >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: GCC not found in PATH
    echo.
    echo Please install MinGW-w64 from:
    echo   https://www.mingw-w64.org/
    echo.
    echo Or use MSYS2 and install with:
    echo   pacman -S mingw-w64-x86_64-gcc
    echo.
    pause
    exit /b 1
)

REM Build test_connection
echo Compiling test_connection.c...
gcc -o test_connection.exe test_connection.c -lws2_32
if %ERRORLEVEL% EQU 0 (
    echo [OK] test_connection compiled successfully
) else (
    echo [FAIL] Failed to compile test_connection
    exit /b 1
)

echo.

REM Build test_receive
echo Compiling test_receive.c...
gcc -o test_receive.exe test_receive.c -lws2_32
if %ERRORLEVEL% EQU 0 (
    echo [OK] test_receive compiled successfully
) else (
    echo [FAIL] Failed to compile test_receive
    exit /b 1
)

echo.
echo Build complete! Run tests with:
echo   test_connection.exe [ip] [port]
echo   test_receive.exe [ip] [port]
echo.
pause
