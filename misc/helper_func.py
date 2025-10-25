import sys

def get_ips_from_record(doc) -> list[str]:
    ips = doc['dns']['A']
    ip_data_ip = doc['ip_data']
    if ip_data_ip is not None:
        ip_data_ip = ip_data_ip[0]['ip']

    if ips is None and ip_data_ip is not None:
        ips = [ip_data_ip]
    elif ip_data_ip is not None and ip_data_ip not in ips:
        ips.append(ip_data_ip)

    return ips

def parse_ranges(ranges: str) -> list[tuple[int, int]] | None:

    split_ranges = ranges.split(',')

    if len(split_ranges) % 2 != 0:
        print("The ranges provided are not even", file=sys.stderr)
        return None

    ranges: list[tuple[int, int]] = []
    for cnt in range(0, len(split_ranges), 2):
        start, end = split_ranges[cnt], split_ranges[cnt + 1]
        ranges.append((int(start), int(end)))

    return ranges