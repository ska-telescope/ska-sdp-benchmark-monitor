import shutil

from benchmon.common.utils import execute_cmd


class ModuleReader:
    def read(self):
        has_module_cmd = shutil.which('module') is not None
        if has_module_cmd:
            return execute_cmd('module list -t').splitlines()[1:]
        return None
