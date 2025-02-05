import os
import glob
from setuptools import setup, find_packages

# Get version information
version = {}
VERSION_PATH = os.path.join('benchmon', '_version.py')
with open(VERSION_PATH, 'r') as file:
    exec(file.read(), version)

# Load local readme file
with open("README.md") as readme_file:
    readme = readme_file.read()

# List of all packages
packages = [
    "benchmon",
]
packages += [
    i for p in packages for i in glob.glob(p + "/*/") +
                                 glob.glob(p + "/*/*/") +
                                 glob.glob(p + "/*/*/*/") +
                                 glob.glob(p + "/*/*/*/*/") +
                                 glob.glob(p + "/*/*/*/*/")
    if '__pycache__' not in i
]

# List of all required packages
reqs = [
    line.strip()
    for line in open("requirements.txt").readlines()
]

# setup config
setup(
    name="ska-sdp-perfmon",
    version=version['__version__'],
    python_requires=">=3.8",
    description="A toolkit to monitor performance metrics for the jobs submitted using workload manager",
    long_description=readme + "\n\n",
    maintainer="Manuel Stutz",
    maintainer_email="manuel.stutz@fhnw.ch",
    url="https://gitlab.com/ska-telescope/sdp/ska-sdp-benchmark-monitor",
    project_urls={
        "Documentation": "https://developer.skao.int/projects/ska-telescope-sdp-workflows-performance-monitoring/en/latest/",
        "Source": "https://gitlab.com/ska-telescope/sdp/ska-sdp-benchmark-monitor",
    },
    zip_safe=False,
    classifiers=[
        "Development Status :: Alpha",
        "Intended Audience :: Developers",
        "Natural Language :: English",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
    ],
    packages=packages,
    scripts=['bin/benchmon-hardware',
             'bin/benchmon-software', 
             'bin/benchmon-run',
             'bin/benchmon-slurm-start',
             'bin/benchmon-slurm-stop',
             'bin/benchmon-start',
             'bin/benchmon-stop',
             'bin/benchmon-visu'],
    install_requires=reqs,
    packages=find_packages(),
    package_data={
        "benchmon": ["run/*.sh"],
    },
    include_package_data=True, 
)