#!/bin/bash

# SKA SDP Benchmark Monitor - Local Services Startup
# Start InfluxDB3 and Grafana locally (no Docker)

set -e

# Configuration
INSTALL_DIR="${HOME}/benchmon-stack"
GRAFANA_DIR="${INSTALL_DIR}/grafana"
INFLUXDB3_DIR="${INSTALL_DIR}/influxdb3"
LOG_DIR="${HOME}/benchmon-logs"
CONFIG_DIR="$(dirname "$0")/configs"

# Create log directory
mkdir -p "${LOG_DIR}"

# SLURM cluster configuration
if [ -n "$SLURM_JOB_ID" ]; then
    # Running in SLURM environment
    NODE_ID=$(hostname -s)
    SLURM_NODELIST=${SLURM_JOB_NODELIST}
    SLURM_PROCID=${SLURM_PROCID:-0}
    
    # Get first node from SLURM_NODELIST for services
    FIRST_NODE=$(scontrol show hostname $SLURM_NODELIST | head -n1)
    CURRENT_NODE=$(hostname -s)
    
    echo "   SLURM Environment Detected"
    echo "   Job ID: ${SLURM_JOB_ID}"
    echo "   Current Node: ${CURRENT_NODE}"
    echo "   First Node: ${FIRST_NODE}"
    echo "   Process ID: ${SLURM_PROCID}"
else
    # Running locally
    NODE_ID=$(hostname -s)
    FIRST_NODE=${NODE_ID}
    CURRENT_NODE=${NODE_ID}
fi

echo "Starting Local Benchmark Monitor Services on ${NODE_ID}"
echo "InfluxDB3: ${INFLUXDB3_DIR}"
echo "Grafana: ${GRAFANA_DIR}"

# Function to find available port starting from a base port
find_available_port() {
    local base_port=$1
    local max_attempts=${2:-50}  # Try up to 50 ports
    local port=$base_port
    
    for ((i=0; i<max_attempts; i++)); do
        if ! (netstat -tuln 2>/dev/null | grep -q ":${port} " || ss -tuln 2>/dev/null | grep -q ":${port} "); then
            echo "$port"
            return 0
        fi
        port=$((port + 1))
    done
    
    echo "Could not find available port starting from $base_port after $max_attempts attempts"
    return 1
}

# Function to check if port is available
check_port() {
    local port=$1
    if netstat -tuln 2>/dev/null | grep -q ":${port} " || ss -tuln 2>/dev/null | grep -q ":${port} "; then
        echo "Port ${port} is already in use"
        return 1
    fi
    return 0
}

# Function to start InfluxDB3
start_influxdb3() {
    # Only start InfluxDB3 on the first node in SLURM cluster
    if [ -n "$SLURM_JOB_ID" ] && [ "$CURRENT_NODE" != "$FIRST_NODE" ]; then
        echo "InfluxDB3 will run on first node: $FIRST_NODE (current: $CURRENT_NODE)"
        echo "   Waiting for InfluxDB3 to be available..."
        
        # Wait for InfluxDB3 to be available on first node
        for i in {1..60}; do
            if curl -s http://${FIRST_NODE}:${INFLUXDB3_PORT}/health > /dev/null 2>&1; then
                echo "InfluxDB3 is available on $FIRST_NODE:$INFLUXDB3_PORT"
                return 0
            fi
            sleep 2
            echo -n "."
        done
        
        echo "InfluxDB3 not available on $FIRST_NODE after 120 seconds"
        return 1
    fi
    
    echo "Starting InfluxDB3 on first node..."
    
    # Find available port for InfluxDB3
    INFLUXDB3_PORT=$(find_available_port 8181)
    if [ $? -ne 0 ]; then
        echo "Could not find available port for InfluxDB3"
        return 1
    fi
    
    echo "   Using port: $INFLUXDB3_PORT"
    
    # Save port to file for other processes
    echo "$INFLUXDB3_PORT" > "${LOG_DIR}/influxdb3.port"
    
    cd "${INFLUXDB3_DIR}"
    
    # Start InfluxDB3 in background
    echo "Starting InfluxDB3 with node-id: ${NODE_ID}"
    nohup ./influxdb3 serve \
        --node-id "${NODE_ID}" \
        --object-store file \
        --data-dir data \
        --http-bind 0.0.0.0:$INFLUXDB3_PORT \
        --without-auth \
        > "${LOG_DIR}/influxdb3.log" 2>&1 &

    # --admin-token-file "${INFLUXDB3_DIR}/admin_token.json" \

    local influxdb_pid=$!
    echo "${influxdb_pid}" > "${LOG_DIR}/influxdb3.pid"
    
    echo "InfluxDB3 started with PID: ${influxdb_pid}"
    
    # Wait for InfluxDB3 to be ready
    echo "Waiting for InfluxDB3 to be ready..."
    for i in {1..30}; do
        if curl -s http://localhost:$INFLUXDB3_PORT/health > /dev/null 2>&1; then
            echo "InfluxDB3 is ready on port $INFLUXDB3_PORT!"
            return 0
        fi
        sleep 2
        echo -n "."
    done
    
    echo "InfluxDB3 failed to start within 60 seconds"
    return 1
}

# Function to start Grafana
start_grafana() {
    # Only start Grafana on the first node in SLURM cluster
    if [ -n "$SLURM_JOB_ID" ] && [ "$CURRENT_NODE" != "$FIRST_NODE" ]; then
        echo "Grafana will run on first node: $FIRST_NODE (current: $CURRENT_NODE)"
        echo "   Waiting for Grafana to be available..."
        
        # Wait for Grafana to be available on first node
        for i in {1..60}; do
            if curl -s http://${FIRST_NODE}:${GRAFANA_PORT}/api/health > /dev/null 2>&1; then
                echo "Grafana is available on $FIRST_NODE:$GRAFANA_PORT"
                return 0
            fi
            sleep 2
            echo -n "."
        done
        
        echo "Grafana not available on $FIRST_NODE after 120 seconds"
        return 1
    fi
    
    echo "Starting Grafana on first node..."
    
    # Find available port for Grafana
    GRAFANA_PORT=$(find_available_port 3000)
    if [ $? -ne 0 ]; then
        echo "Could not find available port for Grafana"
        return 1
    fi
    
    echo "   Using port: $GRAFANA_PORT"
    
    # Save port to file for other processes
    echo "$GRAFANA_PORT" > "${LOG_DIR}/grafana.port"
    
    cd "${GRAFANA_DIR}"
    
    # Copy configuration if available and update port
    if [ -f "${CONFIG_DIR}/grafana.ini" ]; then
        echo "Using custom Grafana configuration"
        cp "${CONFIG_DIR}/grafana.ini" conf/
        # Update port in configuration
        sed -i "s/http_port = .*/http_port = $GRAFANA_PORT/" conf/grafana.ini
    else
        # Create basic configuration with dynamic port
        cat > conf/grafana.ini << EOF
[server]
http_port = $GRAFANA_PORT
domain = localhost

[security]
admin_user = admin
admin_password = admin123

[users]
allow_sign_up = false
EOF
    fi
    
    # 生成Grafana InfluxDB数据源配置 (直接在 Bash 中生成)
    DATASOURCE_DIR="${GRAFANA_DIR}/conf/provisioning/datasources"
    mkdir -p "$DATASOURCE_DIR"
    cat > "$DATASOURCE_DIR/influxdb3.yml" <<EOF
apiVersion: 1
datasources:
  - name: InfluxDB v3 SQL
    uid: influxdb-v3-sql
    type: influxdb
    access: proxy
    url: http://localhost:${INFLUXDB3_PORT}
    isDefault: true
    editable: true
    jsonData:
      dbName: metrics
      version: Sql
      httpMode: GET
      tlsSkipVerify: true
    secureJsonData: {}
EOF
    
    # Start Grafana in background
    nohup ./bin/grafana server \
        --config conf/grafana.ini \
        --homepath . \
        > "${LOG_DIR}/grafana.log" 2>&1 &
    
    local grafana_pid=$!
    echo "${grafana_pid}" > "${LOG_DIR}/grafana.pid"
    
    echo "Grafana started with PID: ${grafana_pid}"
    
    # Wait for Grafana to be ready
    echo "Waiting for Grafana to be ready..."
    for i in {1..30}; do
        if curl -s http://localhost:$GRAFANA_PORT/api/health > /dev/null 2>&1; then
            echo "Grafana is ready on port $GRAFANA_PORT!"
            return 0
        fi
        sleep 2
        echo -n "."
    done
    
    echo "Grafana failed to start within 60 seconds"
    return 1
}

# Function to deploy dashboards
deploy_dashboards() {
    # Only deploy dashboards on the first node
    if [ -n "$SLURM_JOB_ID" ] && [ "$CURRENT_NODE" != "$FIRST_NODE" ]; then
        echo "Dashboard deployment will be handled by first node: $FIRST_NODE"
        return 0
    fi
    
    echo "Deploying Grafana dashboards..."
    echo "Current Directory: $(pwd)"
    echo "   Waiting for Grafana to be fully ready..."
    # Wait a bit more for Grafana to fully initialize
    sleep 10
        
    # Read the actual ports used
    if [ -f "${LOG_DIR}/grafana.port" ]; then
        GRAFANA_PORT=$(cat "${LOG_DIR}/grafana.port")
    else
        GRAFANA_PORT=3000  # fallback
    fi
    
    if [ -f "deploy_dashboard.py" ]; then
        echo "Deploying all dashboards to http://localhost:${GRAFANA_PORT}..."
        python3 deploy_dashboard.py --deploy-all --grafana-url "http://localhost:${GRAFANA_PORT}" --overwrite
        echo "Dashboard deployment completed"
    else
        echo "Dashboard deployment script not found"
    fi
}

# Main execution
main() {
    # Check if installation exists
    if [ ! -d "${INSTALL_DIR}" ]; then
        echo "Benchmark stack not found at ${INSTALL_DIR}"
        echo "Please install the standalone stack first:"
        echo "  ./install_standalone.sh"
        exit 1
    fi
    
    # Start services
    if start_influxdb3 && start_grafana; then
        # Read the actual ports used
        if [ -f "${LOG_DIR}/influxdb3.port" ]; then
            INFLUXDB3_PORT=$(cat "${LOG_DIR}/influxdb3.port")
        else
            INFLUXDB3_PORT=8086  # fallback
        fi
        
        if [ -f "${LOG_DIR}/grafana.port" ]; then
            GRAFANA_PORT=$(cat "${LOG_DIR}/grafana.port")
        else
            GRAFANA_PORT=3000  # fallback
        fi
        
        echo ""
        echo "Services started successfully!"
        echo ""
        if [ -n "$SLURM_JOB_ID" ]; then
            echo "InfluxDB3: http://${FIRST_NODE}:${INFLUXDB3_PORT}"
            echo "Grafana:   http://${FIRST_NODE}:${GRAFANA_PORT} (admin/admin123)"
            echo ""
            echo "Access from login node:"
            echo "   ssh -L ${GRAFANA_PORT}:${FIRST_NODE}:${GRAFANA_PORT} -L ${INFLUXDB3_PORT}:${FIRST_NODE}:${INFLUXDB3_PORT} $USER@login-node"
            echo "   Then open: http://localhost:${GRAFANA_PORT}"
        else
            echo "InfluxDB3: http://localhost:${INFLUXDB3_PORT}"
            echo "Grafana:   http://localhost:${GRAFANA_PORT} (admin/admin123)"
        fi
        echo ""
        echo "Logs directory: ${LOG_DIR}"
        echo "PIDs saved in: ${LOG_DIR}/*.pid"
        echo "Ports saved in: ${LOG_DIR}/*.port"
        echo ""
        
        # Deploy dashboards
        deploy_dashboards
        
        echo "System is ready for monitoring!"
        echo "To stop services, run: ./stop_local_services.sh"
    else
        echo "Failed to start one or more services"
        exit 1
    fi
}

main "$@"