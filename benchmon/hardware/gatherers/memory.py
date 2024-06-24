import logging
from benchmon.common.utils import execute_cmd

log = logging.getLogger(__name__)


class MemoryReader:

    def read(self):
        return self.get_memory_info()

    def get_memory_info(self):
        """
        Get output from free command
        Example free output:

        <code>
        $ free -b -t -w
                       total        used        free      shared     buffers       cache   available
        Mem:     33321914368  7101882368 21159034880    90648576   196591616  4864405504 25648345088
        Swap:     2147479552           0  2147479552
        Total:   35469393920  7101882368 23306514432
        </code>

        We are interested in the "total" column
        """

        lines = execute_cmd('free -b -t -w').split('\n')

        # Prepare a dictionary to store the parsed values
        parsed_data = {}

        # Extract the column names from the first line
        columns = lines[0].split()

        # Process each line except the first one
        for line in lines[1:]:
            # Split the line into parts
            parts = line.split()

            # The first part is the key, the rest are values
            key, values = parts[0].lower(), parts[1:]

            # Convert string values to integers
            int_values = list(map(int, values))

            # Store the values in the dictionary
            parsed_data[key[:-1]] = dict(zip(columns, int_values))  # key[:-1] removes trailing ':' character

        return parsed_data
