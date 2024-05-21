#!/usr/bin/env python3
""" Main script to monitor benchmark metrics from SDP benchmark runs. """

import sys
import os
import argparse


# Add parent directory to PYTHONPATH
parent_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
print("Add parent directory to sys.path.")
sys.path.insert(0, parent_dir)

try:
    import benchmon
    import benchmon.hardware as hardware_context
except ImportError as e:
    print("Could not import benchmon!")
    print(sys.executable, sys.version)
    print('sys.path:')
    for i in range(len(sys.path)):
        print('%2d) %s' % (i + 1, sys.path[i]))
    raise


def parse_args():
    parser = argparse.ArgumentParser()

    # add arguments
    parser.add_argument(
        '-d',
        '--save-dir',
        default=os.getcwd(),
        nargs='?',
        help='''
            Base directory where hardware context will be saved. This directory should 
            be available from all compute nodes. Default is $PWD
        ''',
    )

    parser.add_argument(
        '-p',
        '--prefix',
        default=None,
        nargs='?',
        help='''
                Name of the directory to be created to save hardware context data. If provided, 
                hardware information will be located at $SAVE_DIR/$PREFIX.
            ''',
    )

    parser.add_argument(
        '-v',
        '--verbose',
        action='store_true',
        default=False,
        help="Enable verbose mode. Display debug messages",
    )

    return parser.parse_args()


if __name__ == '__main__':
    print(f'benchmon-hardware version {benchmon.__version__}', sys.executable, str(sys.version).replace('\n', ' '))
    print("Beginning gathering of hardware context.")
    args = parse_args()
    hardware_context.gather_hardware_context(args)
