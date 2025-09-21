#!/bin/bash

# Set permissions for all scripts

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Setting up script permissions in ${SCRIPT_DIR}..."

# Make all shell scripts executable
for script in *.sh; do
    if [ -f "$script" ]; then
        chmod +x "$script"
        echo "  $script is now executable"
    fi
done

# Make Python scripts executable
for script in *.py; do
    if [ -f "$script" ]; then
        chmod +x "$script"
        echo "  $script is now executable"
    fi
done

echo ""
echo "All scripts are now ready to use!"
echo ""
echo "Available scripts:"
echo "   start_local_services.sh  - Start InfluxDB3 and Grafana (SLURM aware)"
echo "   stop_local_services.sh   - Stop all services"
echo "   slurm_job_template.sh    - SLURM job template for multi-node monitoring"
echo "   port_utils.sh           - Port management utilities"
echo "   test_slurm_setup.sh     - Test SLURM environment setup"
echo "   deploy_dashboard.py     - Deploy Grafana dashboards"
echo ""
echo "Quick start for SLURM:"
echo "   ./test_slurm_setup.sh    # Test environment"
echo "   sbatch slurm_job_template.sh  # Submit monitoring job"