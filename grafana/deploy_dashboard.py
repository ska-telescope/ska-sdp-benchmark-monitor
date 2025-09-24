#!/usr/bin/env python3

"""
Grafana Dashboard Deployment Tool for Local Services
Deploys dashboards to local Grafana instance (no Docker dependency)
"""

import argparse
import json
import logging
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

import requests
from requests.auth import HTTPBasicAuth


class GrafanaDashboardManager:
    """Manage Grafana dashboards for local services"""
    
    def __init__(
        self,
        grafana_url: str = "http://localhost:3000",
        username: str = "admin",
        password: str = "admin123",
        timeout: float = 30.0
    ):
        self.grafana_url = grafana_url.rstrip('/')
        self.username = username
        self.password = password
        self.timeout = timeout
        self.session = requests.Session()
        self.session.auth = HTTPBasicAuth(username, password)
        self.logger = logging.getLogger(__name__)

    def test_connection(self) -> bool:
        """Test connection to local Grafana"""
        try:
            response = self.session.get(
                f"{self.grafana_url}/api/health",
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                self.logger.info("✅ Connected to Grafana successfully")
                return True
            else:
                self.logger.error(
                    f"❌ Grafana health check failed: {response.status_code}"
                )
                return False
                
        except requests.exceptions.RequestException as e:
            self.logger.error(f"❌ Cannot connect to Grafana: {e}")
            self.logger.info("💡 Make sure Grafana is running on localhost:3000")
            return False

    def ensure_datasource(self, ds_name: str = "InfluxDB v3 SQL", ds_uid: str = "influxdb-v3-sql", influx_url: str = "http://localhost:8181", db: str = "metrics") -> bool:
        """Ensure datasource exists or create/update it"""
        payload = {
            "name": ds_name,
            "type": "influxdb",
            "uid": ds_uid,
            "access": "proxy",
            "url": influx_url,
            "basicAuth": False,
            "isDefault": True,
            "jsonData": {
                "dbName": db,
                "queryLanguage": "sql",
                "version": "SQL",
                "httpMode": "GET",
                "tlsSkipVerify": True,
                "insecureConnection": True,
                "insecureGrpc": True
            },
            "secureJsonData": {}
        }

        # Check if exists
        try:
            resp = self.session.get(f"{self.grafana_url}/api/datasources/uid/{ds_uid}")
            exists = resp.status_code == 200
        except:
            exists = False

        try:
            if exists:
                resp = self.session.put(f"{self.grafana_url}/api/datasources/uid/{ds_uid}", json=payload)
                if resp.status_code in [200, 204]:
                    self.logger.info(f"✅ Updated datasource {ds_name}")
                    return True
                else:
                    self.logger.error(f"❌ Failed to update datasource: {resp.text}")
                    return False
            else:
                resp = self.session.post(f"{self.grafana_url}/api/datasources", json=payload)
                if resp.status_code in [200, 201]:
                    self.logger.info(f"✅ Created datasource {ds_name}")
                    return True
                else:
                    self.logger.error(f"❌ Failed to create datasource: {resp.text}")
                    return False
        except Exception as e:
            self.logger.error(f"❌ Error ensuring datasource: {e}")
            return False

    def load_dashboard_json(self, file_path: Path) -> Optional[Dict]:
        """Load dashboard JSON from file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON in {file_path}: {e}")
            return None
        except FileNotFoundError:
            self.logger.error(f"File not found: {file_path}")
            return None
        except Exception as e:
            self.logger.error(f"Error reading {file_path}: {e}")
            return None

    def deploy_dashboard(self, dashboard_json: Dict, overwrite: bool = True) -> bool:
        """Deploy a single dashboard to Grafana"""
        try:
            # Prepare the dashboard payload
            payload = {
                "dashboard": dashboard_json,
                "overwrite": overwrite,
                "message": "Deployed via deploy_dashboard.py"
            }

            # Remove id if it exists to avoid conflicts
            if "id" in payload["dashboard"]:
                del payload["dashboard"]["id"]

            # Post to Grafana API
            response = self.session.post(
                f"{self.grafana_url}/api/dashboards/db",
                json=payload,
                headers={"Content-Type": "application/json"}
            )

            if response.status_code in [200, 201]:
                dashboard_title = dashboard_json.get('title', 'Unknown')
                self.logger.info(
                    f"Successfully deployed dashboard: {dashboard_title}"
                )
                return True
            else:
                self.logger.error(
                    f"Failed to deploy dashboard. "
                    f"Status: {response.status_code}, "
                    f"Response: {response.text}"
                )
                return False

        except Exception as e:
            self.logger.error(f"Error deploying dashboard: {e}")
            return False

    def deploy_file(self, file_path: Path, overwrite: bool = True) -> bool:
        """Deploy dashboard from file"""
        self.logger.info(f"Loading dashboard from: {file_path}")

        dashboard_json = self.load_dashboard_json(file_path)
        if dashboard_json is None:
            return False

        return self.deploy_dashboard(dashboard_json, overwrite)

    def deploy_all_dashboards(self, dashboard_dir: Path,
                              pattern: str = "*.json",
                              overwrite: bool = False,
                              influx_port: int = 8181,
                              db: str = "metrics") -> int:
        """Deploy all dashboards in a directory"""
        # Ensure datasource before deploying dashboards
        if not self.ensure_datasource(influx_url=f"http://localhost:{influx_port}", db=db):
            self.logger.error("Failed to ensure datasource, aborting dashboard deployment")
            return 0

        if not dashboard_dir.is_dir():
            self.logger.error(f"Directory not found: {dashboard_dir}")
            return 0

        dashboard_files = list(dashboard_dir.glob(pattern))
        if not dashboard_files:
            self.logger.warning(
                f"No dashboard files found in {dashboard_dir} "
                f"matching pattern: {pattern}"
            )
            return 0

        successful_deployments = 0
        total_files = len(dashboard_files)

        self.logger.info(
            f"Found {total_files} dashboard files to deploy"
        )

        for file_path in dashboard_files:
            if self.deploy_file(file_path, overwrite):
                successful_deployments += 1

        self.logger.info(
            f"Deployment complete: {successful_deployments}/{total_files} "
            f"dashboards deployed successfully"
        )
        return successful_deployments

    def delete_dashboard_by_uid(self, uid: str) -> bool:
        """Delete dashboard by UID"""
        try:
            response = self.session.delete(
                f"{self.grafana_url}/api/dashboards/uid/{uid}"
            )
            if response.status_code == 200:
                self.logger.info(f"Successfully deleted dashboard UID: {uid}")
                return True
            else:
                self.logger.error(
                    f"Failed to delete dashboard UID: {uid}. "
                    f"Status: {response.status_code}, Response: {response.text}"
                )
                return False
        except Exception as e:
            self.logger.error(f"Error deleting dashboard UID {uid}: {e}")
            return False

    def delete_dashboard_by_title(self, title: str) -> bool:
        """Delete dashboard by title"""
        # First, search for the dashboard
        try:
            response = self.session.get(
                f"{self.grafana_url}/api/search",
                params={"query": title, "type": "dash-db"}
            )
            if response.status_code != 200:
                self.logger.error(
                    f"Failed to search for dashboard: {title}"
                )
                return False

            dashboards = response.json()
            matching_dashboards = [
                d for d in dashboards
                if d.get('title') == title
            ]

            if not matching_dashboards:
                self.logger.warning(
                    f"No dashboard found with title: {title}"
                )
                return False

            if len(matching_dashboards) > 1:
                self.logger.warning(
                    f"Multiple dashboards found with title: {title}. "
                    f"Deleting the first one."
                )

            dashboard = matching_dashboards[0]
            uid = dashboard.get('uid')
            if uid:
                return self.delete_dashboard_by_uid(uid)
            else:
                self.logger.error(
                    f"Dashboard {title} has no UID"
                )
                return False

        except Exception as e:
            self.logger.error(
                f"Error searching for dashboard {title}: {e}"
            )
            return False

    def delete_dashboards_by_pattern(self, pattern: str) -> int:
        """Delete dashboards matching a pattern"""
        try:
            response = self.session.get(f"{self.grafana_url}/api/search")
            if response.status_code != 200:
                self.logger.error("Failed to list dashboards")
                return 0

            dashboards = response.json()
            matching_dashboards = [
                d for d in dashboards
                if 'title' in d and pattern.lower() in d['title'].lower()
            ]

            if not matching_dashboards:
                self.logger.warning(
                    f"No dashboards found matching pattern: {pattern}"
                )
                return 0

            deleted_count = 0
            for dashboard in matching_dashboards:
                uid = dashboard.get('uid')
                title = dashboard.get('title')
                if uid and self.delete_dashboard_by_uid(uid):
                    deleted_count += 1
                else:
                    self.logger.error(
                        f"Failed to delete dashboard: {title}"
                    )

            self.logger.info(
                f"Deleted {deleted_count}/{len(matching_dashboards)} "
                f"dashboards matching pattern: {pattern}"
            )
            return deleted_count

        except Exception as e:
            self.logger.error(
                f"Error deleting dashboards by pattern {pattern}: {e}"
            )
            return 0

    def delete_all_dashboards(self, confirm: bool = False) -> int:
        """Delete all dashboards"""
        if not confirm:
            self.logger.error(
                "delete_all_dashboards requires explicit confirmation"
            )
            return 0

        try:
            response = self.session.get(f"{self.grafana_url}/api/search")
            if response.status_code != 200:
                self.logger.error("Failed to list dashboards")
                return 0

            dashboards = response.json()
            if not dashboards:
                self.logger.info("No dashboards found to delete")
                return 0

            deleted_count = 0
            for dashboard in dashboards:
                uid = dashboard.get('uid')
                title = dashboard.get('title')
                if uid and self.delete_dashboard_by_uid(uid):
                    deleted_count += 1
                else:
                    self.logger.error(
                        f"Failed to delete dashboard: {title}"
                    )

            self.logger.info(
                f"🗑️ Deleted {deleted_count}/{len(dashboards)} dashboards"
            )
            return deleted_count

        except Exception as e:
            self.logger.error(f"Error deleting all dashboards: {e}")
            return 0

    def remove_provisioned_dashboard_file(self, title: str,
                                          dashboard_dir: Path) -> bool:
        """Remove provisioned dashboard file by title"""
        try:
            dashboard_files = list(dashboard_dir.glob("*.json"))
            for file_path in dashboard_files:
                dashboard_json = self.load_dashboard_json(file_path)
                if (dashboard_json
                        and dashboard_json.get('title') == title):
                    file_path.unlink()
                    self.logger.info(
                        f"Removed dashboard file: {file_path}"
                    )
                    return True

            self.logger.warning(
                f"No dashboard file found with title: {title}"
            )
            return False

        except Exception as e:
            self.logger.error(
                f"Error removing dashboard file for {title}: {e}"
            )
            return False

    def restart_grafana_container(self,
                                  compose_file: str = "docker-compose.influxdb.yml") -> bool:
        """Restart Grafana container using docker-compose"""
        try:
            # Use the compose file in the same directory as this script
            compose_path = Path(__file__).parent / compose_file
            if not compose_path.exists():
                self.logger.error(
                    f"Docker compose file not found: {compose_path}"
                )
                return False

            # Restart Grafana service
            result = subprocess.run(
                ["docker", "compose", "-f", str(compose_path),
                 "restart", "grafana"],
                capture_output=True,
                text=True,
                check=True
            )

            if result.returncode == 0:
                self.logger.info("Grafana container restarted successfully")
                time.sleep(5)  # Wait for Grafana to start
                return True
            else:
                self.logger.error(
                    f"Failed to restart Grafana: {result.stderr}"
                )
                return False

        except subprocess.CalledProcessError as e:
            self.logger.error(f"Docker compose command failed: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Error restarting Grafana: {e}")
            return False

    def list_dashboards(self) -> List[Dict]:
        """List all dashboards"""
        try:
            response = self.session.get(f"{self.grafana_url}/api/search")
            if response.status_code == 200:
                dashboards = response.json()
                self.logger.info(f"📋 Found {len(dashboards)} dashboards:")
                for dashboard in dashboards:
                    title = dashboard.get('title', 'Unknown')
                    uid = dashboard.get('uid', 'No UID')
                    self.logger.info(f"  - {title} (UID: {uid})")
                return dashboards
            else:
                self.logger.error(
                    f"Failed to list dashboards. "
                    f"Status: {response.status_code}"
                )
                return []
        except Exception as e:
            self.logger.error(f"Error listing dashboards: {e}")
            return []

    def wait_for_grafana(self, timeout: int = 60) -> bool:
        """Wait for Grafana to be ready"""
        self.logger.info("⏳ Waiting for Grafana to be ready...")
        start_time = time.time()

        while time.time() - start_time < timeout:
            if self.test_connection():
                return True
            time.sleep(2)

        self.logger.error(f"Grafana not ready after {timeout} seconds")
        return False


def main():
    """Main function to handle command line arguments"""
    parser = argparse.ArgumentParser(
        description="Deploy Grafana dashboards",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Deploy a single dashboard
  python deploy_dashboard.py --deploy dashboard.json --overwrite

  # Deploy all dashboards in a directory
  python deploy_dashboard.py --deploy-all --dashboard-dir ./dashboards

  # Delete a dashboard by title
  python deploy_dashboard.py --delete "My Dashboard"

  # Delete a dashboard by UID
  python deploy_dashboard.py --delete-uid "abc123"

  # List all dashboards
  python deploy_dashboard.py --list

  # Remove provisioned dashboard file and restart Grafana
  python deploy_dashboard.py --remove-file "Dashboard Title" --restart-grafana

  # Deploy all dashboards with datasource
  python deploy_dashboard.py --deploy-all --influx-port 8181 --db metrics
        """
    )

    # Connection settings
    parser.add_argument("--grafana-url", default="http://localhost:3000",
                        help="Grafana server URL")
    parser.add_argument("--username", default="admin",
                        help="Grafana username")
    parser.add_argument("--password", default="admin123",
                        help="Grafana password")

    # Deployment options
    parser.add_argument("--deploy", metavar="FILE",
                        help="Deploy a single dashboard file")
    parser.add_argument("--deploy-all", action="store_true",
                        help="Deploy all dashboards in directory")

    # Deletion options
    parser.add_argument("--delete", metavar="TITLE",
                        help="Delete dashboard by title")
    parser.add_argument("--delete-uid", metavar="UID",
                        help="Delete dashboard by UID")
    parser.add_argument("--delete-pattern", metavar="PATTERN",
                        help="Delete dashboards matching pattern")
    parser.add_argument("--delete-all", action="store_true",
                        help="Delete all dashboards (requires --confirm)")

    # File management
    parser.add_argument("--remove-file", metavar="TITLE",
                        help="Remove provisioned dashboard file by title")
    parser.add_argument("--restart-grafana", action="store_true",
                        help="Restart Grafana container")
    parser.add_argument("--compose-file",
                        default="docker-compose.influxdb.yml",
                        help="Docker compose file name")

    # Directory and pattern settings
    parser.add_argument("--dashboard-dir", type=Path, default="dashboards",
                        help="Directory containing dashboard files")
    parser.add_argument("--pattern", default="*.json",
                        help="File pattern for dashboard files")

    # Other options
    parser.add_argument("--list", action="store_true",
                        help="List all existing dashboards")
    parser.add_argument("--wait", action="store_true",
                        help="Wait for Grafana to be ready before proceeding")
    parser.add_argument("--overwrite", action="store_true",
                        help="Overwrite existing dashboards")
    parser.add_argument("--confirm", action="store_true",
                        help="Confirm destructive operations")
    parser.add_argument("--verbose", action="store_true",
                        help="Enable verbose logging")

    # Add influx port
    parser.add_argument("--influx-port", type=int, default=8181,
                        help="InfluxDB port for datasource")

    # Add db
    parser.add_argument("--db", default="metrics",
                        help="InfluxDB database name")

    args = parser.parse_args()

    # Configure logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Create deployer instance
    deployer = GrafanaDashboardManager(
        grafana_url=args.grafana_url,
        username=args.username,
        password=args.password
    )

    success = True

    # Wait for Grafana if requested
    if args.wait:
        if not deployer.wait_for_grafana():
            sys.exit(1)

    # Test connection
    if not deployer.test_connection():
        sys.exit(1)

    # Execute requested operations
    if args.deploy:
        success = deployer.deploy_file(Path(args.deploy), args.overwrite)

    elif args.deploy_all:
        deployed = deployer.deploy_all_dashboards(
            args.dashboard_dir, args.pattern, args.overwrite, args.influx_port, args.db
        )
        success = deployed > 0

    elif args.delete:
        success = deployer.delete_dashboard_by_title(args.delete)

    elif args.delete_uid:
        success = deployer.delete_dashboard_by_uid(args.delete_uid)

    elif args.delete_pattern:
        deleted = deployer.delete_dashboards_by_pattern(args.delete_pattern)
        success = deleted > 0

    elif args.delete_all:
        if not args.confirm:
            deployer.logger.error(
                " --delete-all requires --confirm flag for safety"
            )
            success = False
        else:
            deleted = deployer.delete_all_dashboards(confirm=True)
            success = deleted > 0

    elif args.remove_file:
        success = deployer.remove_provisioned_dashboard_file(
            args.remove_file, args.dashboard_dir
        )

    elif args.list:
        dashboards = deployer.list_dashboards()
        success = len(dashboards) >= 0  # Always successful

    else:
        parser.print_help()
        sys.exit(1)

    # Restart Grafana if requested
    if args.restart_grafana:
        if not deployer.restart_grafana_container(args.compose_file):
            success = False

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
