from benchmon.common.utils import execute_cmd


class PciReader:
    def read(self):
        return execute_cmd('lspci -vvv')
