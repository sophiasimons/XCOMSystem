@echo off
REM Build script for Windows

echo Building test programs for Windows...
echo.

REM Check if compiler is available
where cl >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Microsoft Visual C++ compiler not found
    echo.
    echo Please install one of the following:
    echo   1. Visual Studio (Community Edition is free)
    echo   2. Build Tools for Visual Studio
    echo   3. MinGW-w64 (use build_mingw.bat instead)
    echo.
    echo Or open "Developer Command Prompt for VS" and run this script again
    pause
    exit /b 1
)

REM Build test_connection
echo Compiling test_connection.c...
cl /Fe:test_connection.exe test_connection.c /link ws2_32.lib
if %ERRORLEVEL% EQU 0 (
    echo [OK] test_connection compiled successfully
) else (
    echo [FAIL] Failed to compile test_connection
    exit /b 1
)

echo.

REM Build test_receive
echo Compiling test_receive.c...
cl /Fe:test_receive.exe test_receive.c /link ws2_32.lib
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
