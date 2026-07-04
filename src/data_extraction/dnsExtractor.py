"""
File: dns_extraction.py
Author: Jozef Michal Bukas <xbukas00@stud.fit.vutbr.cz>
Date: 15.01.2026
Brief: File that contains asynchronous DNS extraction logic for domains, including
    record resolution, DNS error classification, CNAME-based IP extraction,
    and synchronous wrapper for asynchronous DNS lookup
"""

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
    """
    Class that represents possible DNS resolution error states returned by DNS extraction methods.
    """

    TIMEOUT = 0
    NO_ANSWER = 1
    NXDOMAIN = 2
    OTHER = 3

    def __str__(self):
        """
        Method that converts `DnsErr` value into human-readable error description
        :return: `str` textual description of current DNS error value
        """
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
    """
    Method that resolves DNS records of given type for selected domain with retry logic
    :param domain: `str` domain name for which DNS records should be resolved
    :param record: `str` DNS record type to resolve
    :param n_retries: `int` number of resolution attempts before returning error
    :return: `list[str] | DnsErr` list of resolved record values on success or `DnsErr` on failure
    """

    # Retry DNS resolution multiple times in case of transient resolver failures.
    for resolve_try in range(n_retries):

        try:
            # Limit number of concurrently running DNS queries.
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

            # Return classified error only after final retry attempt fails.
            if resolve_try == n_retries - 1:
                if isinstance(e, rslv.LifetimeTimeout):
                    MyLogger.get_instance().log_warning(f"Resolution - {domain} {record} timed out with msg: {e.msg}")
                    return DnsErr.TIMEOUT

                MyLogger.get_instance().log_warning(f"Resolution - {domain} {record} failed with msg: {e.msg}")
                return DnsErr.OTHER

            # Use exponential backoff before next retry attempt.
            await asyncio.sleep(0.4 * (2**resolve_try))

    return DnsErr.OTHER


async def _get_records_for_domain(domain: str, records: list[str]) -> dict[str, Any] | DnsErr:
    """
    Method that resolves multiple DNS record types for given domain
    :param domain: `str` domain name for which DNS data should be extracted
    :param records: `list[str]` list of DNS record types that should be resolved
    :return: `dict[str, Any] | DnsErr` dictionary with resolved DNS data on success or `DnsErr` on failure
    """
    # Create asynchronous resolution tasks for all requested DNS record types.
    extraction_tasks = [_get_domain_records(domain, rtype) for rtype in records]

    res = await asyncio.gather(*extraction_tasks)
    data = {}

    # Merge results into output dictionary while handling special DNS error cases.
    for rtype, rdata in zip(records,res):
        if isinstance(rdata, DnsErr):
            if rdata == DnsErr.NO_ANSWER:
                continue
            return rdata

        # Normalize CNAME value by removing trailing dot returned by resolver.
        if rtype == 'CNAME':
            rdata = rdata[0][:-1]
        data[rtype] = rdata

    return data


async def _get_ip_data(domain_dict: dict[str, list]) -> list[Any] | DnsErr:
    """
    Method that extracts additional IP-related data from resolved domain DNS information
    :param domain_dict: `dict[str, list]` dictionary containing already resolved DNS records for domain
    :return: `list[Any] | DnsErr` list of extracted IP-related objects on success or `DnsErr` on failure
    """

    cname_domain = domain_dict.get('CNAME',None)

    ip_data = []
    if cname_domain is not None:
        # Resolve IP addresses of canonical name when CNAME record is present.
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
    """
    Method that extracts DNS and related IP data for given domain
    :param domain: `str` domain name for which DNS information should be extracted
    :return: `dict[str, Any] | DnsErr` dictionary with domain DNS data on success or `DnsErr` on failure
    """

    # Resolve primary DNS records used by the system.
    dns_data = await _get_records_for_domain(domain, _USED_REC_TYPES)
    if isinstance(dns_data, DnsErr):
        return dns_data

    # Extract additional IP data, for example IP addresses behind CNAME target.
    ip_data = await _get_ip_data(dns_data)
    if isinstance(ip_data, DnsErr):
        return ip_data

    return {'domain_name': domain,'dns': dns_data, 'ip_data': ip_data}


def extract_dns_sync(domain: str) -> dict[str, Any] | DnsErr:
    """
    Method that synchronously extracts DNS and related IP data for given domain
    :param domain: `str` domain name for which DNS information should be extracted
    :return: `dict[str, Any] | DnsErr` dictionary with domain DNS data on success or `DnsErr` on failure
    """
    return asyncio.run(extract_dns(domain))


if __name__ == "__main__":
    # Load parquet file containing domains and print extracted DNS data for each one.
    df = pd.read_parquet("data-2026-04-08.parquet")

    for domain_name in df["domain_name"]:
        domain_data = extract_dns_sync(domain_name)
        print(domain_data)