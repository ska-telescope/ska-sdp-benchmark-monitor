"""Docstring @todo."""

import json
import logging
import os
import time

from benchmon.common.utils import execute_cmd

log = logging.getLogger(__name__)


class SpackReader:
    """Docstring @todo."""

    DEFAULT_TIMEOUT = 10.0
    DISABLE_ENV = "BENCHMON_DISABLE_SPACK"
    TIMEOUT_ENV = "BENCHMON_SPACK_TIMEOUT"

    def __init__(self):
        """Docstring @todo."""

        self.timeout = self._get_timeout()
        self.deadline = None

    def _get_timeout(self):
        """Return the total time budget for spack probing."""

        raw_value = os.getenv(self.TIMEOUT_ENV, str(self.DEFAULT_TIMEOUT)).strip()
        if raw_value.lower() in {"0", "none", "off", "false"}:
            return None

        try:
            timeout = float(raw_value)
        except ValueError:
            log.warning(
                "Invalid %s=%r. Falling back to %.1f seconds.",
                self.TIMEOUT_ENV,
                raw_value,
                self.DEFAULT_TIMEOUT,
            )
            return self.DEFAULT_TIMEOUT

        if timeout <= 0:
            return None

        return timeout

    def _spack_disabled(self):
        """Return whether spack probing is explicitly disabled."""

        return os.getenv(self.DISABLE_ENV, "").strip().lower() in {"1", "true", "yes", "on"}

    def _start_deadline(self):
        """Initialize the timeout window for this probe run."""

        if self.timeout is None:
            self.deadline = None
        else:
            self.deadline = time.monotonic() + self.timeout

    def _remaining_timeout(self):
        """Return the remaining timeout budget in seconds."""

        if self.deadline is None:
            return None

        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            return 0
        return remaining

    def _run_spack_cmd(self, cmd):
        """Run a spack command within the configured timeout budget."""

        remaining = self._remaining_timeout()
        if remaining == 0:
            return "not_available"
        return execute_cmd(cmd, timeout=remaining)

    def read(self):
        """Docstring @todo."""

        if self._spack_disabled():
            log.info("Skipping gathering of spack dependency tree because %s is set", self.DISABLE_ENV)
            return None

        self._start_deadline()
        data = self.get_spack_dependency_tree()
        if data is None:
            log.warning("Spack is unavailable or did not respond in time. Skipping gathering of spack dependency tree")
        return data

    def get_spack_dependency_tree(self):
        """Get output from spack"""

        found = self._run_spack_cmd("which spack") != "not_available"
        if not found:
            return None

        # spack was found. See if we are in an environment:
        env = None
        env_data = self._run_spack_cmd("spack env status")
        if env_data == "not_available":
            log.warning("Unable to query 'spack env status' before the timeout budget expired")
            return None
        if env_data.startswith("==> In environment"):
            env = env_data.strip().split()[-1]
        elif env_data.startswith("==> No active environment"):
            env = None
        else:
            # something is wrong with the spack installation! Logging and aborting
            log.error("Could not determine spack env status! Is the spack installation corrupt?")
            return None

        if env is not None:
            # We are in an environment, use env specific commands
            val = self._run_spack_cmd("spack spec -c paths --json")
            if val == "not_available":
                log.warning("Unable to query 'spack spec -c paths --json' before the timeout budget expired")
                return None
            val = val.split("\n")
            deps_list = [json.loads(k)["spec"]["nodes"] for k in val]
            full_deps = {}
            for d in deps_list:
                full_deps[d[0]["name"]] = d

        else:
            # Not in an environment, use generic commands
            val = self._run_spack_cmd("spack find --explicit --json")
            if val == "not_available":
                log.warning(
                    "Unable to query 'spack find --explicit --json' before the timeout budget expired"
                )
                return None
            root_deps = json.loads(val)
            full_deps = {}
            for d in root_deps:
                val = self._run_spack_cmd(f"spack spec -c paths --json {d['name']}/{d['hash']}")
                if val == "not_available":
                    log.warning(
                        "Stopping spack dependency collection after %s/%s exceeded the timeout budget",
                        d["name"],
                        d["hash"],
                    )
                    return full_deps or None
                full_deps[d["name"]] = json.loads(val)["spec"]["nodes"]

        return full_deps
