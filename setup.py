import os
import subprocess
from setuptools import setup
from setuptools.command.build_ext import build_ext
import sys


class CMakeBuild(build_ext):
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

        subprocess.check_call(["cmake", "-G", "Ninja", "-DCMAKE_INSTALL_PREFIX=../../exec",
                               "../../benchmon/rt-monitor"], cwd=build_dir)
        subprocess.check_call(["cmake", "--build", "."], cwd=build_dir)
        subprocess.check_call(["cmake", "--install", "."], cwd=build_dir)

        super().run()


setup(
    name="ska-sdp-benchmark-monitor",
    version="0.0.0",
    description="SDP Benchmark Monitor for resource monitoring and performance analysis.",
    cmdclass={"build_ext": CMakeBuild},
    packages=["benchmon"],
    data_files=[("bin", ["exec/*"])],
)
