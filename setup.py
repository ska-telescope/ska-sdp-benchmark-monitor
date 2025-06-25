import glob
import os
import subprocess
from setuptools import setup
from setuptools.command.build_py import build_py as _build_py

import sys


class build_rtmonitor(_build_py):
    def run(self):
        try:
            subprocess.check_call(["cmake", "--version"])
        except subprocess.CalledProcessError:
            print("CMake is required to build the CMake project.")
            sys.exit(1)

        # Run cmake and build
        build_dir = os.path.join(os.path.abspath(os.path.dirname(__file__)), "build/rt-monitor")
        if not os.path.exists(build_dir):
            os.makedirs(build_dir)

        subprocess.check_call(["cmake", "-DCMAKE_INSTALL_PREFIX=../../exec", "../../benchmon/rt-monitor"],
                              cwd=build_dir)
        subprocess.check_call(["cmake", "--build", "."], cwd=build_dir)
        subprocess.check_call(["cmake", "--install", "."], cwd=build_dir)

        super().run()


setup(
    name="ska-sdp-benchmark-monitor",
    version="0.0.0",
    description="SDP Benchmark Monitor for resource monitoring and performance analysis.",
    cmdclass={"build_py": build_rtmonitor},
    data_files=[("bin", glob.glob("exec/*"))],
    package_data={'rt-monitor': ['benchmon/rt-monitor']},
    include_package_data=True,
)
