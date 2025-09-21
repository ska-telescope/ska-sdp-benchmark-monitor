#!/bin/bash

set -e

# 支持传入项目目录参数
if [ -n "$1" ]; then
    PROJECT_DIR="$1"
else
    PROJECT_DIR="${HOME}/work/ska-sdp-benchmark-monitor"
fi

INSTALL_DIR="${HOME}/benchmon-stack"
GRAFANA_VERSION="12.1.1"
GRAFANA_TAR="grafana_${GRAFANA_VERSION}_16903967602_linux_amd64.tar.gz"
GRAFANA_URL="https://dl.grafana.com/grafana/release/${GRAFANA_VERSION}/${GRAFANA_TAR}"

INFLUXDB3_VERSION="3.4.2"
INFLUXDB3_TAR="influxdb3-core-${INFLUXDB3_VERSION}_linux_amd64.tar.gz"
INFLUXDB3_URL="https://dl.influxdata.com/influxdb/releases/${INFLUXDB3_TAR}"
INFLUXDB3_PORT=8081

echo "Creating install directory: $INSTALL_DIR"
mkdir -p "$INSTALL_DIR"
cd "$INSTALL_DIR"

# Download and extract Grafana
if [ ! -d "grafana" ]; then
    echo "Downloading Grafana..."
    echo "URL:" $GRAFANA_URL
    wget -c "$GRAFANA_URL"
    echo "Extracting Grafana..."
    tar -zxvf "$GRAFANA_TAR"
    GRAFANA_DIR=$(tar -tf "$GRAFANA_TAR" | head -1 | cut -f1 -d"/")
    mv "$GRAFANA_DIR" grafana
    rm -f "$GRAFANA_TAR"
else
    echo "Grafana already installed."
fi

# Download and extract InfluxDB3
if [ ! -d "influxdb3" ]; then
    echo "Downloading InfluxDB3..."
    wget -c "$INFLUXDB3_URL"
    echo "Extracting InfluxDB3..."
    tar -zxvf "$INFLUXDB3_TAR"
    INFLUXDB3_DIR=$(tar -tf "$INFLUXDB3_TAR" | head -1 | cut -f1 -d"/")
    mv "$INFLUXDB3_DIR" influxdb3
    rm -f "$INFLUXDB3_TAR"
else
    echo "InfluxDB3 already installed."
fi

# Create data directories if not exist
mkdir -p "$INSTALL_DIR/influxdb3/data"
mkdir -p "$INSTALL_DIR/grafana/data"
mkdir -p "$INSTALL_DIR/grafana/logs"

# 创建admin token json文件，供InfluxDB3启动时导入
ADMIN_TOKEN_FILE="$INSTALL_DIR/influxdb3/admin_token.json"
echo '{
  "token": "apiv3_admin123",
  "name": "_admin"
}' > "$ADMIN_TOKEN_FILE"
echo "Admin token file created at $ADMIN_TOKEN_FILE (token: apiv3_admin123)"

echo "Install Grafana Dashboards and Scripts"

# 拷贝项目grafana目录下的deploy_dashboard.py和dashboards
PROJECT_GRAFANA_DIR="$PROJECT_DIR/grafana"
TARGET_GRAFANA_DIR="$INSTALL_DIR/grafana"

echo "$PROJECT_GRAFANA_DIR/deploy_dashboard.py"
if [ -f "$PROJECT_GRAFANA_DIR/deploy_dashboard.py" ]; then
    echo "Copying deploy_dashboard.py to $TARGET_GRAFANA_DIR"
    cp -f -a "$PROJECT_GRAFANA_DIR/deploy_dashboard.py" "$TARGET_GRAFANA_DIR/"
fi
if [ -d "$PROJECT_GRAFANA_DIR/dashboards" ]; then
    echo "Copying dashboards directory to $TARGET_GRAFANA_DIR"
    cp -f -a -r "$PROJECT_GRAFANA_DIR/dashboards" "$TARGET_GRAFANA_DIR/"
fi

# 可选：拷贝其它grafana相关脚本
for f in start_local_services.sh stop_local_services.sh setup_permissions.sh port_utils.sh test_local_setup.sh slurm_job_template.sh; do
    if [ -f "$PROJECT_GRAFANA_DIR/$f" ]; then
        echo "Copying $f to $TARGET_GRAFANA_DIR"
        cp -a "$PROJECT_GRAFANA_DIR/$f" "$TARGET_GRAFANA_DIR/"
    fi
done

echo "Installation complete!"
echo "Grafana:   $INSTALL_DIR/grafana"
echo "InfluxDB3: $INSTALL_DIR/influxdb3"