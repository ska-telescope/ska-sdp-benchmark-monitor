import datetime

from benchmon.common.utils import execute_cmd


class SystemReader:
    def read(self):
        return {
            'kernel_name': execute_cmd('uname -s'),
            'hostname': execute_cmd('uname -n'),
            'kernel_release': execute_cmd('uname -r'),
            'kernel_version': execute_cmd('uname -v'),
            'hardware_machine': execute_cmd('uname -m'),
            'processor_type': execute_cmd('uname -p'),
            'hardware_platform': execute_cmd('uname -i'),
            'ostype': execute_cmd('uname -o'),
            'time': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }
