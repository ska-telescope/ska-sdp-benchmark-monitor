import shutil
import logging
from benchmon.common.utils import execute_cmd

log = logging.getLogger(__name__)

class AcceleratorReader:
    def __init__(self):
        pass

    def read(self):
        accelerators = {}

        if self.has_nvidia():
            try:
                accelerators['nvidia'] = self.get_nvidia_data()
            except Exception as e:
                log.error(f"Failed to get nvidia data: {e}")

        if self.has_amd():
            # todo: Write parser, need AMD system for that
            pass

        return accelerators

    def has_nvidia(self):
        # Expect nvidia-smi to be available
        return shutil.which('nvidia-smi') is not None

    def has_amd(self):
        # Expect rocm-smi to be available
        return shutil.which('rocm-smi') is not None

    def get_nvidia_data(self) -> list:
        nvidia_data = execute_cmd(
            "nvidia-smi --query-gpu=driver_version,count,name,pci.bus_id,pci.domain,pci.bus,pci.device,pci.device_id,pci.sub_device_id,pcie.link.gen.max,pcie.link.width.max,vbios_version,inforom.img,inforom.oem,pstate,memory.total,ecc.errors.corrected.aggregate.total,clocks.max.sm,clocks.max.memory --format=csv,nounits").splitlines()
        nvidia_data = [n.split(',') for n in nvidia_data]
        nvidia_data = [[k.strip() for k in n] for n in nvidia_data]
        headers = nvidia_data[0]
        data = nvidia_data[1:]

        nv_elems = []
        for row in data:
            device = {}
            for idx, elem in enumerate(headers):
                device[elem] = row[idx]
            nv_elems.append(device)
        return nv_elems