
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