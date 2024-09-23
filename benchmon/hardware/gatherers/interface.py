import psutil

import logging
log = logging.getLogger(__name__)

class InterfacesReader():
    def __init__(self):
        pass

    def read(self):
        net_interfaces = {}

        interfaces = psutil.net_if_addrs()

        for interface_name, interface_addresses in interfaces.items():
            if interface_name == 'lo':
                # skip the loopback interface
                continue

            if interface_name not in net_interfaces:
                addresses = []

                for address in interface_addresses:
                    addr = {
                        'address': address.address,
                        'netmask': address.netmask,
                        'broadcast': address.broadcast,
                        'family': address.family,
                        'ptp': address.ptp
                    }
                    addresses.append(addr)

                net_interfaces[interface_name] = addresses
        return net_interfaces
