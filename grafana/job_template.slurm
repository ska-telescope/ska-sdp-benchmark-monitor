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

# Navigate to benchmon directory
cd "${BENCHMON_HOME}/grafana"

# Start services (only on first node automatically)
echo "📊 Starting monitoring services..."
benchmark-start-grafana

# Wait for services to be fully ready
sleep 15

# Get the actual ports used (from first node)


# Run monitoring with InfluxDB3 integration
./exec/benchmon-run \
    --system \
    --grafana \
    --grafana-url "${INFLUXDB3_URL}" \
    --grafana-token "" \
    --no-csv \
    --duration 3600  # Run for 1 hour

echo "✅ Monitoring completed on $(hostname)"

# Only stop services from the first node
if [ "$CURRENT_NODE" == "$FIRST_NODE" ]; then
    echo "🛑 Stopping services from first node..."
    benchmon-stop-grafana
    # Clean up service info
fi

echo "🎉 Job completed on $(hostname) at $(date)"