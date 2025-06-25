import numpy as np
import struct
from typing import List, Dict, Type


class generic_sample:
    """
    A generic class to represent structured data with dynamic fields.
    """

    def __init__(self, field_definitions: Dict[str, Type]):
        """
        Initialize the generic sample with field definitions. Field values of type str must not exceed 32 characters.

        Args:
            field_definitions (Dict[str, Type]): A dictionary where keys are field names and values are their types
                                                (e.g., int, float).
        """
        self.field_definitions = field_definitions

        # Type to format character dictionary for Python binary pack/unpack.
        type_map = {np.uint8: "B", np.uint16: "H", np.uint32: "I", np.uint64: "Q", np.float32: "f", np.float64: "d",
                    np.int8: "b", np.int16: "h", np.int32: "i", np.int64: "q", np.double: "d", np.longdouble: "d",
                    np.bool_: "?", str: "32s"}
        # Builds the format string for Python binary pack/unpack.
        self.format_string_static = "<" + " ".join(type_map[field_type] for _, field_type,
                                                   enabled in field_definitions if enabled)
        self.pack_size = struct.calcsize(self.format_string_static)
        self.enabled_fields = [field for field in self.field_definitions if field[2]]


    def get_pack_size(self) -> int:
        """
        Get the size of the packed data.

        Returns:
            int: The size of the packed data.
        """
        return self.pack_size


    def get_format_string(self) -> str:
        """
        Get the format string used for struct packing/unpacking.

        Returns:
            str: The format string.
        """
        return self.format_string_static


    def binary_to_dict(self, data: bytes):
        """
        Convert binary data to a dictionary.

        Args:
            data (bytes): The binary data to convert.

        Returns:
            Dict[str, Type]: The deserialized object as a dictionary.
        """
        if len(data) != self.pack_size:
            raise ValueError("Data length does not match field definitions.")
        unpacked = struct.unpack(self.format_string_static, data)
        return {
            field_name: value.decode('utf-8').replace('\x00', "") if field_type == str else value
            for (field_name, field_type, _), value in zip(self.enabled_fields, unpacked)
        }


    def bytes_to_str(self, data: bytes) -> List[str]:
        """
        Convert bytes to a list of strings.

        Args:
            data (bytes): The byte array to convert.

        Returns:
            List[str]: The deserialized object as a list of strings.
        """
        if len(data) != self.pack_size:
            raise ValueError("Data length does not match field definitions.")
        unpacked = struct.unpack(self.format_string_static, data)
        return [
            value.decode('utf-8').replace('\x00', "") if field_type == str else value
            for (_, field_type, _), value in zip(self.enabled_fields, unpacked)
        ]


    def validate_binary(self, data: bytes) -> bool:
        """
        Validate if a binary data matches the field definitions.

        Args:
            data (bytes): The binary data to validate.

        Returns:
            bool: True if the binary data matches the field definitions, False otherwise.
        """
        if len(data) != self.pack_size:
            return False

        try:
            struct.unpack(self.format_string_static, data)
        except struct.error:
            return False

        return True


class hf_cpu_sample(generic_sample):
    """
    A class representing a high-frequency CPU sample, inheriting from `generic_sample`.

    This class is used to define and initialize the structure of a CPU sample with various fields related to CPU usage
    statistics.

    Attributes:
        timestamp (np.float64:  The timestamp of the sample in seconds since the epoch.
        cpu_id (str):           The identifier of the CPU core.
        user (np.uint64):       Time spent in user mode.
        nice (np.uint64):       Time spent in user mode with low priority (nice).
        system (np.uint64):     Time spent in system mode.
        idle (np.uint64):       Time spent in the idle task.
        iowait (np.uint64):     Time spent waiting for I/O to complete.
        irq (np.uint64):        Time spent servicing hardware interrupts.
        softirq (np.uint64):    Time spent servicing software interrupts.
        steal (np.uint64):      Time spent in involuntary wait by virtual CPUs.
        guest (np.uint64):      Time spent running a virtual CPU in guest mode.
        guest_nice (np.uint64): Time spent running a low-priority virtual CPU in guest mode.

    Methods:
        __init__(): Initializes the `hf_cpu_sample` instance with predefined field definitions.
    """

    def __init__(self):
        """
        Initializes the class with field definitions for monitoring data.

        The field definitions specify the structure of the data to be monitored, including the field name, data type,
        and whether the field is enabled.
        """
        field_definitions = [
            ["timestamp", np.uint64, True],
            ["cpu", np.uint32, True],
            ["user", np.uint32, True],
            ["nice", np.uint32, True],
            ["system", np.uint32, True],
            ["idle", np.uint32, True],
            ["iowait", np.uint32, True],
            ["irq", np.uint32, True],
            ["softirq", np.uint32, True],
            ["steal", np.uint32, True],
            ["guest", np.uint32, True],
            ["guestnice", np.uint32, True],
        ]
        super().__init__(field_definitions)


class hf_cpufreq_sample(generic_sample):
    """
    A class representing a sample of CPU frequency data.

    This class inherits from `generic_sample` and is used to define the structure of a CPU frequency sample, including
    the timestamp, CPU ID, and CPU frequency.

    Attributes:
        timestamp (np.uint64): The timestamp of the sample in timestamp format.
        cpu (str):             The identifier of the CPU.
        cpu_freq (np.float32): The frequency of the CPU in Hz.
    """

    def __init__(self):
        """
        Initializes the class with field definitions for monitoring data.

        The field definitions specify the structure of the data to be monitored, including the field name, data type,
        and whether the field is enabled.
        """
        field_definitions = [
            ["timestamp", np.uint64, True],
            ["cpu", np.uint32, True],
            ["frequency", np.uint32, True],
        ]
        super().__init__(field_definitions)


class hf_disk_sample(generic_sample):
    """
    A class representing a sample of disk-related metrics.

    This class inherits from `generic_sample` and is used to define the structure of a disk monitoring sample.

    Attributes:
        timestamp (np.float64):                The timestamp timestamp of the sample.
        major (np.uint32):                     The major device number.
        minor (np.uint32):                     The minor device number.
        device_id (np.uint32):                 The index of the device.
        reads_completed (np.uint64):           The number of read operations completed.
        reads_merged (np.uint64):              The number of read operations merged.
        sectors_read (np.uint64):              The number of sectors read.
        time_spent_reading (np.uint64):        The time spent on reading operations (in milliseconds).
        writes_completed (np.uint64):          The number of write operations completed.
        writes_merged (np.uint64):             The number of write operations merged.
        sectors_written (np.uint64):           The number of sectors written.
        time_spent_writing (np.uint64):        The time spent on writing operations (in milliseconds).
        io_in_progress (np.uint64):            The number of I/O operations currently in progress.
        time_spent_on_io (np.uint64):          The time spent on I/O operations (in milliseconds).
        weighted_time_spent_on_io (np.uint64): The weighted time spent on I/O operations (in milliseconds).
        discard_completed (np.uint64):         The number of discard operations completed.
        discard_merged (np.uint64):            The number of discard operations merged.
        sectors_discarded (np.uint64):         The number of sectors discarded.
        time_spent_discarding (np.uint64):     The time spent on discard operations (in milliseconds).
        flush_completed (np.uint64):           The number of flush operations completed.
        time_spent_flushing (np.uint64):       The time spent on flush operations (in milliseconds).

    Methods:
        __init__: Initializes the hf_disk_sample instance with predefined field definitions.
    """

    def __init__(self):
        """
        Initializes the class with a predefined set of field definitions.

        The field definitions specify the structure of the data to be monitored, including the field name, data type,
        and whether the field is enabled.
        """
        field_definitions = [
            ["timestamp", np.uint64, True],
            ["major", np.uint32, True],
            ["minor", np.uint32, True],
            ["device_id", np.uint32, True],
            ["#rd-cd", np.uint64, True],
            ["#rd-md", np.uint64, True],
            ["sect-rd", np.uint64, True],
            ["time-rd", np.uint64, True],
            ["#wr-cd", np.uint64, True],
            ["#wr-md", np.uint64, True],
            ["sect-wr", np.uint64, True],
            ["time-wr", np.uint64, True],
            ["#io-ip", np.uint64, True],
            ["time-io", np.uint64, True],
            ["time-wei-io", np.uint64, True],
            ["#disc-cd", np.uint64, True],
            ["#disc-md", np.uint64, True],
            ["sect-disc", np.uint64, True],
            ["time-disc", np.uint64, True],
            ["#flush-req", np.uint64, True],
            ["time-flush", np.uint64, True],
        ]
        super().__init__(field_definitions)


class hf_mem_sample(generic_sample):
    """
    A class representing a sample of memory-related metrics.

    The field definitions specify the structure of the data to be monitored, including the field name, data type, and
    whether the field is enabled.

    Attributes:
        time (np.float64):              Timestamp of the sample.
        mem_total (np.uint64):          Total memory available.
        mem_free (np.uint64):           Free memory available.
        mem_available (np.uint64):      Memory available for allocation.
        buffers (np.uint64):            Memory used for buffers.
        cached (np.uint64):             Memory used for caching.
        swap_cached (np.uint64):        Swap memory used for caching.
        active (np.uint64):             Active memory.
        inactive (np.uint64):           Inactive memory.
        active_anon (np.uint64):        Active anonymous memory.
        inactive_anon (np.uint64):      Inactive anonymous memory.
        active_file (np.uint64):        Active file-backed memory.
        inactive_file (np.uint64):      Inactive file-backed memory.
        unevictable (np.uint64):        Unevictable memory.
        mlocked (np.uint64):            Memory locked in RAM.
        swap_total (np.uint64):         Total swap memory.
        swap_free (np.uint64):          Free swap memory.
        zswap (np.uint64):              Compressed swap memory in RAM.
        zswapped (np.uint64):           Compressed swap memory written to disk.
        dirty (np.uint64):              Memory waiting to be written to disk.
        writeback (np.uint64):          Memory actively being written to disk.
        anon_pages (np.uint64):         Anonymous memory pages.
        mapped (np.uint64):             Memory mapped to userspace.
        shmem (np.uint64):              Shared memory.
        kreclaimable (np.uint64):       Kernel reclaimable memory.
        slab (np.uint64):               Memory used by kernel slabs.
        sreclaimable (np.uint64):       Reclaimable slab memory.
        sunreclaim (np.uint64):         Unreclaimable slab memory.
        kernel_stack (np.uint64):       Memory used by kernel stacks.
        page_tables (np.uint64):        Memory used by page tables.
        sec_page_tables (np.uint64):    Memory used by secondary page tables.
        nfs_unstable (np.uint64):       Unstable NFS pages.
        bounce (np.uint64):             Memory used for bounce buffers.
        writeback_tmp (np.uint64):      Temporary writeback memory.
        commit_limit (np.uint64):       Commit limit for memory.
        committed_as (np.uint64):       Memory committed for allocation.
        vmalloc_total (np.uint64):      Total vmalloc memory.
        vmalloc_used (np.uint64):       Used vmalloc memory.
        vmalloc_chunk (np.uint64):      Largest contiguous vmalloc memory chunk.
        percpu (np.uint64):             Memory used for per-CPU allocations.
        hardware_corrupted (np.uint64): Memory marked as hardware corrupted.
        anon_huge_pages (np.uint64):    Anonymous huge pages.
        shmem_huge_pages (np.uint64):   Shared memory huge pages.
        shmem_pmd_mapped (np.uint64):   Shared memory PMD-mapped pages.
        file_huge_pages (np.uint64):    File-backed huge pages.
        file_pmd_mapped (np.uint64):    File-backed PMD-mapped pages.
        unaccepted (np.uint64):         Unaccepted memory.
        hugepages_total (np.uint64):    Total huge pages.
        hugepages_free (np.uint64):     Free huge pages.
        hugepages_rsvd (np.uint64):     Reserved huge pages.
        hugepages_surp (np.uint64):     Surplus huge pages.
        hugepagesize (np.uint64):       Size of a huge page.
        hugetlb (np.uint64):            Memory used by hugetlb.
        direct_map_4k (np.uint64):      Directly mapped 4K pages.
        direct_map_2m (np.uint64):      Directly mapped 2M pages.
        direct_map_1g (np.uint64):      Directly mapped 1G pages.
    """

    def __init__(self):
        """
        Initializes the class with a predefined set of field definitions.

        The field definitions represent various system memory metrics, each defined by a name, data type, and a boolean
        indicating whether the field is enabled.
        """
        field_definitions = [
            ["timestamp", np.uint64, True],
            ["MemTotal", np.uint64, True],
            ["MemFree", np.uint64, True],
            ["MemAvailable", np.uint64, False],
            ["Buffers", np.uint64, True],
            ["Cached", np.uint64, True],
            ["SwapCached", np.uint64, True],
            ["Active", np.uint64, False],
            ["Inactive", np.uint64, False],
            ["Active(anon)", np.uint64, False],
            ["Inactive(anon)", np.uint64, False],
            ["Active(file)", np.uint64, False],
            ["Inactive(file)", np.uint64, False],
            ["Unevictable", np.uint64, False],
            ["Mlocked", np.uint64, False],
            ["SwapTotal", np.uint64, True],
            ["SwapFree", np.uint64, True],
            ["Zswap", np.uint64, False],
            ["Zswapped", np.uint64, False],
            ["Dirty", np.uint64, False],
            ["Writeback", np.uint64, False],
            ["AnonPages", np.uint64, False],
            ["Mapped", np.uint64, False],
            ["Shmem", np.uint64, False],
            ["KReclaimable", np.uint64, False],
            ["Slab", np.uint64, True],
            ["SReclaimable", np.uint64, False],
            ["SUnreclaim", np.uint64, False],
            ["KernelStack", np.uint64, False],
            ["PageTables", np.uint64, False],
            ["SecPageTables", np.uint64, False],
            ["NFS_Unstable", np.uint64, False],
            ["Bounce", np.uint64, False],
            ["WritebackTmp", np.uint64, False],
            ["CommitLimit", np.uint64, False],
            ["Committed_AS", np.uint64, False],
            ["VmallocTotal", np.uint64, False],
            ["VmallocUsed", np.uint64, False],
            ["VmallocChunk", np.uint64, False],
            ["Percpu", np.uint64, False],
            ["HardwareCorrupted", np.uint64, False],
            ["AnonHugePages", np.uint64, False],
            ["ShmemHugePages", np.uint64, False],
            ["ShmemPmdMapped", np.uint64, False],
            ["FileHugePages", np.uint64, False],
            ["FilePmdMapped", np.uint64, False],
            ["Unaccepted", np.uint64, False],
            ["Hugepages_Total", np.uint64, False],
            ["Hugepages_Free", np.uint64, False],
            ["Hugepages_Rsvd", np.uint64, False],
            ["Hugepages_Surp", np.uint64, False],
            ["Hugepagesize", np.uint64, False],
            ["Hugetlb", np.uint64, False],
            ["DirectMap4k", np.uint64, False],
            ["DirectMap2M", np.uint64, False],
            ["DirectMap1G", np.uint64, False],
        ]
        super().__init__(field_definitions)


class hf_net_sample(generic_sample):
    """
    A class representing a sample of network traffic related metrics.

    This class extends `generic_sample` and defines a set of fields that capture network interface statistics,
    including metrics for bytes, packets, errors, and other transmission and reception details.

    Attributes:
        timestamp (np.float64):    The timestamp of the sample.
        interface (str): The       name of the network interface.
        rx-bytes (np.uint64):      The number of bytes received.
        rx-packets (np.uint64):    The number of packets received.
        rx-errs (np.uint64):       The number of errors encountered while receiving.
        rx-drop (np.uint64):       The number of dropped packets while receiving.
        rx-fifo (np.uint64):       The number of FIFO errors while receiving.
        rx-frame (np.uint64):      The number of frame errors while receiving.
        rx-compressed (np.uint64): The number of compressed packets received.
        rx-multicast (np.uint64):  The number of multicast packets received.
        tx-bytes (np.uint64):      The number of bytes transmitted.
        tx-packets (np.uint64):    The number of packets transmitted.
        tx-errs (np.uint64):       The number of errors encountered while transmitting.
        tx-drop (np.uint64):       The number of dropped packets while transmitting.
        tx-fifo (np.uint64):       The number of FIFO errors while transmitting.
        tx-colls (np.uint64):      The number of collisions encountered while transmitting.
        tx-carrier (np.uint64):    The number of carrier errors while transmitting.
        tx-compressed (np.uint64): The number of compressed packets transmitted.
    """

    def __init__(self):
        """
        Initializes the class with a predefined set of field definitions.

        The field definitions specify the structure of the data to be monitored, including the field name, data type,
        and whether the field is enabled.
        """
        field_definitions = [
            ["timestamp", np.uint64, True],
            ["interface", str, True],
            ["rx-bytes", np.uint64, True],
            ["rx-packets", np.uint64, True],
            ["rx-errs", np.uint64, True],
            ["rx-drop", np.uint64, True],
            ["rx-fifo", np.uint64, True],
            ["rx-frame", np.uint64, True],
            ["rx-compressed", np.uint64, True],
            ["rx-multicast", np.uint64, True],
            ["tx-bytes", np.uint64, True],
            ["tx-packets", np.uint64, True],
            ["tx-errs", np.uint64, True],
            ["tx-drop", np.uint64, True],
            ["tx-fifo", np.uint64, True],
            ["tx-colls", np.uint64, True],
            ["tx-carrier", np.uint64, True],
            ["tx-compressed", np.uint64, True],
        ]
        super().__init__(field_definitions)
