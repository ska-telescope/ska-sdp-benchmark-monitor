import os
import sys

from benchmon.common.utils import execute_cmd


class PythonEnv:
    def read(self):
        # get indication about whether we're inside a python env

        data = {}

        # venv
        if self.is_venv():
            data["env"] = "venv"
        # conda
        elif self.is_conda_env():
            data["env"] = "conda"

        pkg_list = []
        if self.is_python_gte_38():
            # we can use importlib.metadata
            import importlib.metadata
            installed_packages = importlib.metadata.distributions()
            for package in installed_packages:
                if package.name is not None:
                    pkg_list.append({"name": package.metadata['Name'], "version": package.version})
        else:
            # we can't use importlib - falling back to pip
            pip_data = execute_cmd("pip list").splitlines()
            i = 0
            while not pip_data[i].startswith('-----'):
                i += 1
            pip_data = pip_data[i+1:]
            for package in pip_data:
                if package == '':
                    break
                package = package.strip().split()
                pkg_list.append({"name": package[0], "version": package[1]})

        data['packages'] = pkg_list
        return data

    def is_venv(self):
        return os.environ.get("VIRTUAL_ENV") is not None

    def is_conda_env(self):
        return os.environ.get("CONDA_DEFAULT_ENV") is not None

    def is_python_gte_38(self):
        # check if python version is greater than or equals to 3.8
        return sys.version_info >= (3, 8)
