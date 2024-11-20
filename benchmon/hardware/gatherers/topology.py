import shutil

from benchmon.common.utils import execute_cmd


class TopologyReader:
    def read(self):
        if shutil.which('lstopo') is not None:
            return execute_cmd('lstopo -vvv')
        return None