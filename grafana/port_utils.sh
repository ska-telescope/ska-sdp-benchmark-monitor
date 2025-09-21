#!/bin/bash

# Port management utilities for SLURM environment

# Function to find available port starting from a base port
find_available_port() {
    local base_port=$1
    local max_attempts=${2:-50}
    local port=$base_port
    
    echo "Searching for available port starting from $base_port..." >&2
    
    for ((i=0; i<max_attempts; i++)); do
        if ! (netstat -tuln 2>/dev/null | grep -q ":${port} " || ss -tuln 2>/dev/null | grep -q ":${port} "); then
            echo "Found available port: $port" >&2
            echo "$port"
            return 0
        fi
        echo "   Port $port is busy, trying next..." >&2
        port=$((port + 1))
    done
    
    echo "Could not find available port starting from $base_port after $max_attempts attempts" >&2
    return 1
}

# Function to check if a specific port is available
check_port_available() {
    local port=$1
    if netstat -tuln 2>/dev/null | grep -q ":${port} " || ss -tuln 2>/dev/null | grep -q ":${port} "; then
        return 1  # Port is busy
    else
        return 0  # Port is available
    fi
}

# Function to wait for service to be available on a specific host:port
wait_for_service() {
    local host=$1
    local port=$2
    local service_name=$3
    local max_wait=${4:-60}
    
    echo "Waiting for $service_name to be available on $host:$port..." >&2
    
    for ((i=1; i<=max_wait; i++)); do
        if curl -s --max-time 5 "http://${host}:${port}/health" > /dev/null 2>&1 || \
           curl -s --max-time 5 "http://${host}:${port}/api/health" > /dev/null 2>&1; then
            echo "$service_name is ready on $host:$port" >&2
            return 0
        fi
        sleep 2
        if [ $((i % 10)) -eq 0 ]; then
            echo "   Still waiting... (${i}/${max_wait})" >&2
        fi
    done
    
    echo "$service_name failed to become available on $host:$port after $((max_wait * 2)) seconds" >&2
    return 1
}

# Function to get service info from shared location
get_service_info() {
    local info_file="${HOME}/benchmon-logs/service_info.env"
    
    if [ -f "$info_file" ]; then
        source "$info_file"
        echo "InfluxDB3: ${INFLUXDB3_HOST}:${INFLUXDB3_PORT}" >&2
        echo "Grafana: ${GRAFANA_HOST}:${GRAFANA_PORT}" >&2
        return 0
    else
        echo "Service info file not found: $info_file" >&2
        return 1
    fi
}

# Function to show all listening ports on current node
show_listening_ports() {
    echo "Listening ports on $(hostname):" >&2
    echo "TCP Ports:" >&2
    netstat -tuln 2>/dev/null | grep ":.*LISTEN" | awk '{print $4}' | sed 's/.*://' | sort -n | uniq >&2
    echo "" >&2
}

# Function to cleanup port files
cleanup_port_files() {
    local log_dir="${HOME}/benchmon-logs"
    echo "Cleaning up port files..." >&2
    rm -f "${log_dir}"/*.port
    rm -f "${log_dir}/service_info.env"
    echo "Port files cleaned up" >&2
}

# Main script logic if called directly
if [ "${BASH_SOURCE[0]}" == "${0}" ]; then
    case "${1:-help}" in
        "find")
            find_available_port "${2:-8080}" "${3:-50}"
            ;;
        "check")
            if check_port_available "${2:-8080}"; then
                echo "Port ${2:-8080} is available"
                exit 0
            else
                echo "Port ${2:-8080} is busy"
                exit 1
            fi
            ;;
        "wait")
            wait_for_service "${2:-localhost}" "${3:-8080}" "${4:-service}" "${5:-60}"
            ;;
        "info")
            get_service_info
            ;;
        "show")
            show_listening_ports
            ;;
        "cleanup")
            cleanup_port_files
            ;;
        "help"|*)
            echo "Port Management Utilities"
            echo ""
            echo "Usage: $0 <command> [args...]"
            echo ""
            echo "Commands:"
            echo "  find <base_port> [max_attempts]  - Find available port starting from base_port"
            echo "  check <port>                     - Check if specific port is available"
            echo "  wait <host> <port> <name> [max]  - Wait for service to be ready"
            echo "  info                             - Show service info from shared file"
            echo "  show                             - Show all listening ports"
            echo "  cleanup                          - Clean up port files"
            echo "  help                             - Show this help"
            echo ""
            echo "Examples:"
            echo "  $0 find 8081 20     # Find port starting from 8081, try 20 ports"
            echo "  $0 check 3000       # Check if port 3000 is available"
            echo "  $0 wait node01 8081 InfluxDB3 30  # Wait for InfluxDB3 on node01:8081"
            ;;
    esac
fi