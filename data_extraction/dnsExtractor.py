from typing import Any
import asyncio
import dns.resolver as rslv
from enum import Enum
from misc.Logger import MyLogger
import pandas as pd

_USED_REC_TYPES = ['A','AAAA','CNAME']
_CONC_LIMIT = 16

__rate_lim_semaphore__ = asyncio.Semaphore(_CONC_LIMIT)
__resolver__ = rslv.Resolver()
__resolver__.lifetime = 2.0
__resolver__.nameservers = ["8.8.8.8","1.1.1.1"]

class DnsErr(Enum):
    TIMEOUT = 0
    NO_ANSWER = 1
    NXDOMAIN = 2
    OTHER = 3

    def __str__(self):
        if self == DnsErr.TIMEOUT:
            return "Dns timeout"
        elif self == DnsErr.NO_ANSWER:
            return "There no dns entries that can be used"
        elif self == DnsErr.NXDOMAIN:
            return "Domain does not exists"
        elif self == DnsErr.OTHER:
            return "Dns error"
        else:
            return "Unknown error"

async def _get_domain_records(domain: str, record: str, n_retries: int = 4) -> list[str] | DnsErr:

    for resolve_try in range(n_retries):

        try:
            async with __rate_lim_semaphore__:
                answer = __resolver__.resolve(domain, record)

            return [str(rdata) for rdata in answer if rdata]
        except rslv.NoAnswer as e:
            MyLogger.get_instance().log_warning(f"Resolution - {domain} {record} returned no answer with msg: {e.msg}")
            return DnsErr.NO_ANSWER
        except rslv.NXDOMAIN as e:
            MyLogger.get_instance().log_warning(f"Resolution - {domain} {record} there is no such domain with msg: {e.msg}")
            return DnsErr.NXDOMAIN

        except Exception as e:

            if resolve_try == n_retries - 1:
                if isinstance(e, rslv.LifetimeTimeout):
                    MyLogger.get_instance().log_warning(f"Resolution - {domain} {record} timed out with msg: {e.msg}")
                    return DnsErr.TIMEOUT

                MyLogger.get_instance().log_warning(f"Resolution - {domain} {record} failed with msg: {e.msg}")
                return DnsErr.OTHER

            await asyncio.sleep(0.4 * (2**resolve_try))

    return DnsErr.OTHER

async def _get_records_for_domain(domain: str, records: list[str]) -> dict[str, Any] | DnsErr:
    extraction_tasks = [_get_domain_records(domain, rtype) for rtype in records]

    res = await asyncio.gather(*extraction_tasks)
    data = {}

    for rtype, rdata in zip(records,res):
        if isinstance(rdata, DnsErr):
            if rdata == DnsErr.NO_ANSWER:
                continue
            return rdata

        if rtype == 'CNAME':
            rdata = rdata[0][:-1]
        data[rtype] = rdata

    return data


async def _get_ip_data(domain_dict: dict[str, list]) -> list[Any] | DnsErr:

    cname_domain = domain_dict.get('CNAME',None)

    ip_data = []
    if cname_domain is not None:
        cname_ips = await _get_records_for_domain(cname_domain, ['A', 'AAAA'])
        if isinstance(cname_ips, DnsErr):
            return cname_ips

        cname_ipv4 = cname_ips.get('A', [])
        for ipv4 in cname_ipv4:
            #if ipv4 not in domain_dict['A']:
            #    domain_dict['A'].append(ipv4)
            if ipv4 in  domain_dict['A']: continue
            ip_data.append({"from_record": "CNAME", "ip": ipv4 })

        cname_ipv6 = cname_ips.get('AAAA', [])
        for ipv6 in cname_ipv6:
            #if ipv6 not in domain_dict['AAAA']:
            #    domain_dict['AAAA'].append(ipv6)
            if ipv6 in domain_dict['AAAA']: continue
            ip_data.append({"from_record": "CNAME", "ip": ipv6 })

    #TODO IF I EVER USE OTHER DATA ABOUT IP, HERE IT WILL BE COLLECTED

    return ip_data


async def extract_dns(domain: str) -> dict[str, Any] | DnsErr:

    dns_data = await _get_records_for_domain(domain, _USED_REC_TYPES)
    if isinstance(dns_data, DnsErr):
        return dns_data

    ip_data = await _get_ip_data(dns_data)
    if isinstance(ip_data, DnsErr):
        return ip_data

    return {'domain_name': domain,'dns': dns_data, 'ip_data': ip_data}

def extract_dns_sync(domain: str) -> dict[str, Any] | DnsErr:
    return asyncio.run(extract_dns(domain))

if __name__ == "__main__":
    df = pd.read_parquet("data-2026-04-08.parquet")

    for domain_name in df["domain_name"]:
        domain_data = extract_dns_sync(domain_name)
        print(domain_data)