from benchmon.common.utils import execute_cmd


class PciReader:
    def read(self):
        pci = execute_cmd('lspci -vvv')
        if pci.startswith("Absolute path to") and "so running it may require superuser privileges" in pci:
            pci = execute_cmd('/sbin/lspci -vvv')
        return pci
