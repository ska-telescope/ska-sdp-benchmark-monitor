#!/bin/bash

# Test local services startup and shutdown

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Testing Local Services Management"

# Test 1: Check if scripts exist
echo "1. Checking script files..."
for script in start_local_services.sh stop_local_services.sh; do
    if [ -f "${SCRIPT_DIR}/${script}" ]; then
        echo "  ${script} exists"
    else
        echo "  ${script} missing"
        exit 1
    fi
done

# Test 2: Check if installation directory exists
echo "2. Checking installation..."
INSTALL_DIR="${HOME}/benchmon-stack"
if [ -d "${INSTALL_DIR}" ]; then
    echo "  Installation directory exists: ${INSTALL_DIR}"
    if [ -x "${INSTALL_DIR}/grafana/bin/grafana" ]; then
        echo "  Grafana binary found"
    else
        echo "  Grafana binary not found or not executable"
    fi
    
    if [ -x "${INSTALL_DIR}/influxdb3/influxdb3" ]; then
        echo "  InfluxDB3 binary found"
    else
        echo "  InfluxDB3 binary not found or not executable"
    fi
else
    echo "  Installation directory not found: ${INSTALL_DIR}"
    echo "    Run install_standalone.sh first to install the stack"
fi

# Test 3: Check port availability
echo "3. Checking port availability..."
for port in 3000 8086; do
    if netstat -tuln 2>/dev/null | grep -q ":${port} " || ss -tuln 2>/dev/null | grep -q ":${port} "; then
        echo "  Port ${port} is in use"
    else
        echo "  Port ${port} is available"
    fi
done

# Test 4: Test script permissions
echo "4. Checking script permissions..."
for script in start_local_services.sh stop_local_services.sh; do
    if [ -x "${SCRIPT_DIR}/${script}" ]; then
        echo "  ${script} is executable"
    else
        echo "  Making ${script} executable..."
        chmod +x "${SCRIPT_DIR}/${script}"
    fi
done

echo ""
echo "Test Summary:"
echo "   Installation: ${INSTALL_DIR}"
echo "   Logs will be in: ${HOME}/benchmon-logs"
echo ""
echo "To start services: ./start_local_services.sh"
echo "To stop services:  ./stop_local_services.sh"
echo ""

# Optional: Quick service test if installation exists
if [ -d "${INSTALL_DIR}" ] && [ -x "${INSTALL_DIR}/grafana/bin/grafana" ] && [ -x "${INSTALL_DIR}/influxdb3/influxdb3" ]; then
    echo "Installation looks complete!"
    echo "   You can now start the services."
else
    echo "Installation incomplete. Please run:"
    echo "   ./install_standalone.sh"
fi