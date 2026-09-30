import os
import sys
import glob
import subprocess
from setuptools import setup, find_packages
from setuptools.command.build_py import build_py as _build_py


class build_rtmonitor(_build_py):
    def run(self):
        try:
            subprocess.check_call(["cmake", "--version"])
        except (OSError, subprocess.CalledProcessError):
            print("CMake is required to build the CMake project.")
            sys.exit(1)

        # Build directory
        build_dir = os.path.join(os.path.abspath(os.path.dirname(__file__)), "build", "rt-monitor")
        os.makedirs(build_dir, exist_ok=True)

        # Run cmake and build/install
        subprocess.check_call([
            "cmake",
            "-DCMAKE_INSTALL_PREFIX=../../exec",
            "../../benchmon/rt-monitor"
        ], cwd=build_dir)
        subprocess.check_call(["cmake", "--build", "."], cwd=build_dir)
        subprocess.check_call(["cmake", "--install", "."], cwd=build_dir)

        super().run()


if not os.path.exists("pytest.ini"):
    with open("pytest.ini", "w") as f:
        f.write("""\
[pytest]
addopts = -vsra --cov=benchmon/run --cov=benchmon/visualization --cov-report=term-missing
testpaths = tests
python_files = test_*.py
""")

setup(
    name="ska-sdp-benchmark-monitor",
    version="0.0.0",
    description="SDP Benchmark Monitor for resource monitoring and performance analysis.",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    author="Anass Serhani, Manuel Stutz, Shan Mignot, Hamza Chouh",
    author_email="anass.serhani@inria.fr, manuel.stutz@fhnw.ch, shan.mignot@oca.eu, hamza.chouh@epfl.ch",
    python_requires=">=3.8",
    packages=find_packages(where=".", include=["benchmon*"]),
    install_requires=[
        "numpy",
        "matplotlib",
        "ping3",
        "psutil",
        "requests",
        "scipy"
    ],
    extras_require={
        "test": [
            "pytest",
            "pytest-cov",
            "flake8"
        ]
    },
    project_urls={
        "Repository": "https://gitlab.com/ska-telescope/sdp/ska-sdp-benchmark-monitor",
        "Documentation": "https://ska-telescope-ska-sdp-benchmark-monitor.readthedocs.io",
    },
    data_files=[
        ("bin", glob.glob("exec/*"))
    ],
    package_data={
        "benchmon.run": ["*.sh"],
    },
    include_package_data=True,
    cmdclass={
        "build_py": build_rtmonitor
    },
    setup_requires=[
        "cmake>=3.18",
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent"
    ],
)
