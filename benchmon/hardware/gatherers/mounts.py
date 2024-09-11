import logging

from benchmon.common.utils import execute_cmd

logger = logging.getLogger(__name__)

class MountpointsReader:
    def __init__(self):
        pass

    def read(self):
        disk_info = {}

        # Command to get all mounted file systems and disks, including network file systems
        cmd = "df --output=source,fstype,size,used,avail,pcent,target -x tmpfs -x devtmpfs -x squashfs -x efivarfs"
        result = execute_cmd(cmd).splitlines()[1:]

        for line in result:
            vals = line.split()
            disk_info[vals[0]] = {
                'fstype': vals[1],
                'size': vals[2],
                'used': vals[3],
                'avail': vals[4],
                'pcent': vals[5][:-1], # remove the percent sign
                'mountpoint': vals[6]
            }

        return disk_info