#!/bin/bash

# SKA SDP Benchmark Monitor - Local Services Stopper

LOG_DIR="${HOME}/benchmon-logs"

echo "Stopping Local Benchmark Monitor Services"

# Function to stop service by PID file
stop_service() {
    local service_name=$1
    local pid_file="${LOG_DIR}/${service_name}.pid"
    
    if [ -f "${pid_file}" ]; then
        local pid=$(cat "${pid_file}")
        echo "Stopping ${service_name} (PID: ${pid})"
        
        if kill -0 "${pid}" 2>/dev/null; then
            # Send TERM signal first for graceful shutdown
            kill -TERM "${pid}"
            
            # Wait up to 10 seconds for graceful shutdown
            for i in {1..10}; do
                if ! kill -0 "${pid}" 2>/dev/null; then
                    echo "  ${service_name} stopped gracefully"
                    rm -f "${pid_file}"
                    return 0
                fi
                sleep 1
            done
            
            # Force kill if still running
            if kill -0 "${pid}" 2>/dev/null; then
                echo "Force stopping ${service_name}"
                kill -KILL "${pid}"
                sleep 2
            fi
        fi
        
        rm -f "${pid_file}"
        echo "  ${service_name} stopped"
    else
        echo "  No PID file found for ${service_name}"
        
        # Try to find and stop by process name
        case "${service_name}" in
            "grafana")
                pkill -f "grafana.*server" 2>/dev/null && echo "  Killed grafana processes"
                ;;
            "influxdb3")
                pkill -f "influxdb3.*serve" 2>/dev/null && echo "  Killed influxdb3 processes"
                ;;
        esac
    fi
}

# Stop services in reverse order
stop_service "grafana"
stop_service "influxdb3"

# Clean up any remaining processes
echo "Cleaning up any remaining processes..."
pkill -f "grafana.*server" 2>/dev/null || true
pkill -f "influxdb3.*serve" 2>/dev/null || true

# Verify ports are free
echo "Checking if ports are free..."
sleep 2

if netstat -tuln 2>/dev/null | grep -q ":3000 " || ss -tuln 2>/dev/null | grep -q ":3000 "; then
    echo "  Port 3000 still in use"
else
    echo "  Port 3000 is free"
fi

if netstat -tuln 2>/dev/null | grep -q ":8181 " || ss -tuln 2>/dev/null | grep -q ":8181 "; then
    echo "  Port 8181 still in use"
else
    echo "  Port 8181 is free"
fi

echo "All services stopped"