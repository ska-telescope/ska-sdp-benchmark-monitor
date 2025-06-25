"""Utils module to run benchmon"""

import argparse
import logging
import os

HOSTNAME = os.uname()[1]
JOBID = os.getenv("SLURM_JOB_ID") or os.getenv("OAR_JOB_ID") or ""


class RunUtils:
    """
    RunUtils class to run benchmon
    """

    @staticmethod
    def parse_args() -> argparse.ArgumentParser:
        """
        Parse benchmon-run arguments

        Returns:
            argaprse.ArgumentParser Argument namespace
        """
        parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter)

        # add arguments
        parser.add_argument(
            "-d",
            "--save-dir",
            default=f"{os.getcwd()}/benchmon_traces_{JOBID}",
            help="Base directory where metrics will be saved"
        )

        parser.add_argument(
            "-v",
            "--verbose",
            action="store_true",
            default=False,
            help="Enable verbose mode. Display debug messages"
        )

        parser.add_argument(
            "--system",
            "--sys",
            action="store_true",
            help="Enable system monitoring"
        )

        parser.add_argument(
            "--sys-freq",
            type=int,
            default=10,
            help="System monitoring frequency. Default: 10 Hz"
        )

        parser.add_argument(
            "--power",
            "--pow",
            action="store_true",
            help="Enable power monitoring"
        )

        parser.add_argument(
            "--power-sampling-interval",
            "--pow-sampl-intv",
            type=int,
            default=250,
            help="Sampling interval to collect power metrics. Default value is 250 milliseconds"
        )

        parser.add_argument(
            "--power-g5k",
            "--pow-g5k",
            action="store_true",
            help="Download grid5000 power monitoring"
        )

        parser.add_argument(
            "--call",
            action="store_true",
            help="Enable callstack tracing"
        )

        parser.add_argument(
            "--call-mode",
            type=str,
            default="dwarf,32",
            help="Call graph collection mode (dwarf, lbr, fp). Default: dwarf"
        )

        parser.add_argument(
            "--call-profiling-frequency",
            "--call-prof-freq",
            type=int,
            default=10,
            help="Profiling frequency. Default: 10 Hz"
        )

        parser.add_argument(
            "--call-keep-datafile",
            action="store_true",
            help="Keep perf data file"
        )

        parser.add_argument(
            "--test-timeout",
            type=int,
            help="Timeout for testing"
        )

        parser.add_argument(
            "--start-after",
            type=int,
            default=0,
            help="Wait a certain time (in seconds) before starting monitoring. Default: 0"
        )

        return parser.parse_args()


    @staticmethod
    def create_logger(save_dir: str, verbose: bool) -> logging.Logger:
        """
        Create logging manager
        """
        logger = logging.getLogger("benchmon_logger")
        logger.setLevel(logging.DEBUG)

        fmt = f"<%(filename)s> [{HOSTNAME}] [%(asctime)s] [%(levelname)s] %(message)s"
        datefmt = "%Y-%m-%d %H:%M:%S"
        fmtter = logging.Formatter(fmt=fmt, datefmt=datefmt)

        file_handler = logging.FileHandler(f"{save_dir}/benchmon_{HOSTNAME}.log")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(fmtter)

        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(logging.DEBUG if verbose else logging.INFO)
        stream_handler.setFormatter(fmtter)

        logger.addHandler(file_handler)
        logger.addHandler(stream_handler)

        return logger


    @staticmethod
    def get_benchmon_pid(logger: logging.Logger) -> None:
        """
        Get benchmon-run pid
        """
        filename = f"./.benchmon-run_pid_{JOBID}_{HOSTNAME}"
        with open(filename, "w") as fn:
            fn.write(f"{os.getpid()}")

        logger.debug(f"PID file created: {filename}")
