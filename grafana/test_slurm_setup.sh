#!/bin/bash

# Test SLURM environment setup

echo "🧪 Testing SLURM Environment Setup"

# Test 1: Check SLURM commands
echo "1️⃣ Testing SLURM commands..."
if command -v scontrol &> /dev/null; then
    echo "✅ scontrol command available"
    scontrol show config | grep ClusterName || echo "⚠️  Could not get cluster name"
else
    echo "❌ scontrol command not found - not in SLURM environment"
fi

if command -v squeue &> /dev/null; then
    echo "✅ squeue command available"
else
    echo "❌ squeue command not found"
fi

# Test 2: Check script files
echo "2️⃣ Checking script files..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

for script in start_local_services.sh stop_local_services.sh slurm_job_template.sh port_utils.sh; do
    if [ -f "${SCRIPT_DIR}/${script}" ]; then
        if [ -x "${SCRIPT_DIR}/${script}" ]; then
            echo "✅ ${script} exists and is executable"
        else
            echo "🔧 ${script} exists but not executable, fixing..."
            chmod +x "${SCRIPT_DIR}/${script}"
        fi
    else
        echo "❌ ${script} missing"
    fi
done

# Test 3: Test port utilities
echo "3️⃣ Testing port utilities..."
source "${SCRIPT_DIR}/port_utils.sh"

echo "   Testing port availability check..."
if check_port_available 99999; then
    echo "✅ Port availability check works (port 99999 should be free)"
else
    echo "⚠️  Port 99999 appears to be in use (very unusual)"
fi

echo "   Testing port finding..."
AVAILABLE_PORT=$(find_available_port 8080 5)
if [ $? -eq 0 ] && [ -n "$AVAILABLE_PORT" ]; then
    echo "✅ Port finding works (found port: $AVAILABLE_PORT)"
else
    echo "❌ Port finding failed"
fi

# Test 4: Check installation
echo "4️⃣ Checking installation..."
INSTALL_DIR="${HOME}/benchmon-stack"
if [ -d "${INSTALL_DIR}" ]; then
    echo "✅ Installation directory exists: ${INSTALL_DIR}"
    
    # Check binaries
    if [ -x "${INSTALL_DIR}/grafana/bin/grafana" ]; then
        echo "✅ Grafana binary found and executable"
        GRAFANA_VERSION=$("${INSTALL_DIR}/grafana/bin/grafana" --version 2>/dev/null | head -1 || echo "unknown")
        echo "   Version: ${GRAFANA_VERSION}"
    else
        echo "❌ Grafana binary not found or not executable"
    fi
    
    if [ -x "${INSTALL_DIR}/influxdb3/influxdb3" ]; then
        echo "✅ InfluxDB3 binary found and executable"
        # InfluxDB3 might not have a --version flag, try to get version info
        INFLUXDB3_VERSION=$("${INSTALL_DIR}/influxdb3/influxdb3" --help 2>&1 | head -1 || echo "unknown")
        echo "   Info: ${INFLUXDB3_VERSION}"
    else
        echo "❌ InfluxDB3 binary not found or not executable"
    fi
    
else
    echo "❌ Installation directory not found: ${INSTALL_DIR}"
    echo "   Please run installation script first"
fi

# Test 5: Check environment
echo "5️⃣ Checking environment..."
echo "   Home directory: ${HOME}"
echo "   Current user: $(whoami)"
echo "   Current node: $(hostname)"

if [ -n "$SLURM_JOB_ID" ]; then
    echo "✅ Running in SLURM job environment"
    echo "   Job ID: ${SLURM_JOB_ID}"
    echo "   Node list: ${SLURM_JOB_NODELIST}"
    FIRST_NODE=$(scontrol show hostname $SLURM_JOB_NODELIST | head -n1)
    echo "   First node: ${FIRST_NODE}"
else
    echo "ℹ️  Not running in SLURM job (this is OK for testing)"
fi

# Test 6: Check network utilities
echo "6️⃣ Testing network utilities..."
if command -v curl &> /dev/null; then
    echo "✅ curl available"
else
    echo "❌ curl not found - required for health checks"
fi

if command -v netstat &> /dev/null; then
    echo "✅ netstat available"
elif command -v ss &> /dev/null; then
    echo "✅ ss available (alternative to netstat)"
else
    echo "❌ Neither netstat nor ss found - required for port checking"
fi

echo ""
echo "📋 Test Summary:"
echo "   Scripts: ${SCRIPT_DIR}"
echo "   Installation: ${INSTALL_DIR}"
echo "   Logs will be in: ${HOME}/benchmon-logs"
echo ""

# Final recommendation
if [ -d "${INSTALL_DIR}" ] && [ -x "${INSTALL_DIR}/grafana/bin/grafana" ] && [ -x "${INSTALL_DIR}/influxdb3/influxdb3" ]; then
    echo "🎉 Environment looks ready for SLURM deployment!"
    echo ""
    echo "📝 Next steps:"
    echo "   1. Review and customize slurm_job_template.sh"
    echo "   2. Submit job: sbatch slurm_job_template.sh"
    echo "   3. Monitor job: squeue -u \$USER"
    echo "   4. Check logs: tail -f \$HOME/benchmon-logs/*.log"
else
    echo "⚠️  Environment needs setup. Please:"
    echo "   1. Install the standalone stack"
    echo "   2. Ensure all binaries are executable"
    echo "   3. Re-run this test"
fi