#!/bin/bash
#SBATCH --job-name=benchmon-stack
#SBATCH --nodes=2
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G
#SBATCH --time=02:00:00
#SBATCH --output=%j-benchmon.out
#SBATCH --error=%j-benchmon.err

# SKA SDP Benchmark Monitor - SLURM Job Script
# This script runs InfluxDB3 and Grafana on compute nodes

echo "🚀 Starting SKA SDP Benchmark Monitor in SLURM"
echo "Job ID: ${SLURM_JOB_ID}"
echo "Node List: ${SLURM_JOB_NODELIST}"
echo "Current Node: $(hostname)"
echo "Start time: $(date)"

# Get first node for services
FIRST_NODE=$(scontrol show hostname $SLURM_JOB_NODELIST | head -n1)
CURRENT_NODE=$(hostname -s)

echo "First Node (services): ${FIRST_NODE}"
echo "Current Node: ${CURRENT_NODE}"

# Set environment variables
export BENCHMON_HOME="${HOME}/ska-sdp-benchmark-monitor"
export BENCHMON_STACK="${HOME}/benchmon-stack"

# Load required modules (adjust for your cluster)
# module load python/3.9
# module load curl

# Navigate to benchmon directory
cd "${BENCHMON_HOME}/grafana"

# Start services (only on first node automatically)
echo "📊 Starting monitoring services..."
./start_local_services.sh

# Wait for services to be fully ready
sleep 15

# Get the actual ports used (from first node)
INFLUXDB3_PORT=8086  # default fallback
GRAFANA_PORT=3000    # default fallback

if [ "$CURRENT_NODE" == "$FIRST_NODE" ]; then
    # We're on the first node, read the actual ports
    if [ -f "${HOME}/benchmon-logs/influxdb3.port" ]; then
        INFLUXDB3_PORT=$(cat "${HOME}/benchmon-logs/influxdb3.port")
    fi
    if [ -f "${HOME}/benchmon-logs/grafana.port" ]; then
        GRAFANA_PORT=$(cat "${HOME}/benchmon-logs/grafana.port")
    fi
    
    echo "🔗 Service URLs on first node:"
    echo "   InfluxDB3: http://${FIRST_NODE}:${INFLUXDB3_PORT}"
    echo "   Grafana:   http://${FIRST_NODE}:${GRAFANA_PORT}"
    
    # Write service info to shared location
    cat > "${HOME}/benchmon-logs/service_info.env" << EOF
INFLUXDB3_HOST=${FIRST_NODE}
INFLUXDB3_PORT=${INFLUXDB3_PORT}
GRAFANA_HOST=${FIRST_NODE}
GRAFANA_PORT=${GRAFANA_PORT}
EOF
else
    # We're on a worker node, wait for service info
    echo "⏳ Waiting for service information from first node..."
    for i in {1..60}; do
        if [ -f "${HOME}/benchmon-logs/service_info.env" ]; then
            source "${HOME}/benchmon-logs/service_info.env"
            echo "✅ Got service info: InfluxDB3 at ${INFLUXDB3_HOST}:${INFLUXDB3_PORT}"
            break
        fi
        sleep 2
    done
fi

# Deploy dashboards (only on first node)
if [ "$CURRENT_NODE" == "$FIRST_NODE" ]; then
    echo "📈 Deploying Grafana dashboards..."
    python3 deploy_dashboard.py --deploy-all --grafana-url "http://localhost:${GRAFANA_PORT}"
fi

# Start benchmark monitoring on all nodes
echo "🔍 Starting system monitoring on $(hostname)..."
cd "${BENCHMON_HOME}"

# Determine InfluxDB3 URL for this node
if [ "$CURRENT_NODE" == "$FIRST_NODE" ]; then
    INFLUXDB3_URL="http://localhost:${INFLUXDB3_PORT}"
else
    INFLUXDB3_URL="http://${FIRST_NODE}:${INFLUXDB3_PORT}"
fi

echo "📊 Using InfluxDB3 URL: ${INFLUXDB3_URL}"

# Run monitoring with InfluxDB3 integration
./exec/benchmon-run \
    --system \
    --grafana \
    --grafana-url "${INFLUXDB3_URL}" \
    --grafana-token "" \
    --grafana-org "benchmon" \
    --grafana-bucket "metrics" \
    --duration 3600  # Run for 1 hour

echo "✅ Monitoring completed on $(hostname)"

# Only stop services from the first node
if [ "$CURRENT_NODE" == "$FIRST_NODE" ]; then
    echo "🛑 Stopping services from first node..."
    cd "${BENCHMON_HOME}/grafana"
    ./stop_local_services.sh
    
    # Clean up service info
    rm -f "${HOME}/benchmon-logs/service_info.env"
fi

echo "🎉 Job completed on $(hostname) at $(date)"