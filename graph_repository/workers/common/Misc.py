from enum import Enum
from ipaddress import ip_address

class IPModes(Enum):
    BOTH = 0
    V4 = 1
    V6 = 2

def get_ips_from_record(doc: dict, mode: IPModes) -> list:
    ips: list = []

    if doc.get('dns') is None:
        return ips

    if mode == IPModes.V4 or mode == IPModes.BOTH:
        a_list = doc['dns'].get('A',[])
        if a_list is not None:
            ips.extend([ ip_address(ip_str) for ip_str in a_list  if ip_str != '' ])

    if mode == IPModes.V6 or mode == IPModes.BOTH:
        aaaa_list = doc['dns'].get('AAAA',[])
        if aaaa_list is not None:
            ips.extend([ ip_address(ip_str) for ip_str in aaaa_list if ip_str != ''])

    if doc.get('ip_data'):
        ip_data_ips = doc['ip_data']
        if ip_data_ips is not None:

            for ip_data_item in ip_data_ips:
                addr: str = ip_data_item['ip']

                if addr == '':
                    continue

                ip_addr = ip_address(addr)

                if ip_addr in ips:
                    continue

                if mode == IPModes.BOTH:
                    ips.append(ip_address(addr))

                elif ip_addr.version == 4 and mode == IPModes.V4:
                    ips.append(ip_address(addr))

                elif ip_addr.version == 6 and mode == IPModes.V6:
                    ips.append(ip_address(addr))

    return ips