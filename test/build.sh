#!/bin/bash
# Build script for macOS/Linux

echo "Building test programs for macOS/Linux..."

# Build test_connection
echo "Compiling test_connection.c..."
gcc -o test_connection test_connection.c
if [ $? -eq 0 ]; then
    echo "✓ test_connection compiled successfully"
else
    echo "✗ Failed to compile test_connection"
    exit 1
fi

# Build test_receive
echo "Compiling test_receive.c..."
gcc -o test_receive test_receive.c
if [ $? -eq 0 ]; then
    echo "✓ test_receive compiled successfully"
else
    echo "✗ Failed to compile test_receive"
    exit 1
fi

echo ""
echo "Build complete! Run tests with:"
echo "  ./test_connection [ip] [port]"
echo "  ./test_receive [ip] [port]"
