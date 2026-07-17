"""
File: DomainFiltersOnGraphData.py
Author: Jozef Michal Bukas <xbukas00@stud.fit.vutbr.cz>
Date: 14.3.2026
Brief: File that holds functions for filtering out domains that already have same data in graph.
    Note that you can create supporting function but main filter function must start with prefix
    "rm_" so that they can be differentiated from the other functions. Also, all main functions
    must have same parameters and all main function must return set with domains that should stay.
"""

from graph_repository.Neo4jDBDriver import Neo4jDBDriver, get_version_query
from graph_repository.graph_repo_misc import get_registrant_from_record, parse_cert, tls_data_present, \
    tls_data_present
from graph_repository.workers.common.GraphTypes import NodeTypes, EdgeTypes, D_NAME, CERT_HASH
from typing import Callable, Any


def rm_domains_with_same_ip(domains: list[dict], version: int, driver: Neo4jDBDriver) -> set[str]:
    """
    Function that filters out domains that have the same IP addresses as their graph counterparts
    :param domains: `list[dict]` with domain data which may or may not hold A and AAAA records
    :param version: `int` graph version
    :param driver: `Neo4jDBClient` driver used to query db
    :return: `set[str]` with domains (their_domain_names) that have different IPS in graph
    """
    rows = []
    for domain in domains:
        row = {'domain_name': domain['domain_name']}
        ips = []
        if domain['dns'].get('A') is not None:
            ips.extend(domain['dns']['A'])
        if domain['dns'].get('AAAA') is not None:
            ips.extend(domain['dns']['AAAA'])

        if len(ips) > 0:
            row['IPS'] = ips
        rows.append(row)

    query = f"""
    UNWIND $domains AS domain
    OPTIONAL MATCH (:{NodeTypes.DOMAIN.neo4j} {{domain_name: domain.domain_name {get_version_query(version, False)}}})
                  -[:{EdgeTypes.TRANSLATES.value}]->(m:{NodeTypes.IP.neo4j})
    WITH domain, m
    WHERE (domain.IPS IS NOT NULL AND m IS NULL) OR 
          (domain.IPS IS NULL AND m IS NOT NULL) OR
          NOT (m.ip_str IN domain.IPS)
    RETURN collect(DISTINCT domain.domain_name) AS diff_domains
    """

    diff_domain_names = driver.execute_read(query, domains=rows)[0]['diff_domains']
    diff_domains = set(diff_domain_names)

    del diff_domain_names, rows
    return diff_domains

# TODO TEST METHODS FOR PARAMETRIZED UNIVERSAL FILTER

def _retrieve_cname(domain: dict[str, Any]) -> str | None:
    if domain['dns'].get('CNAME') is not None:
        if type(domain['dns']['CNAME']) == str:
            return domain['dns']['CNAME']
        elif domain['dns']['CNAME'].get('value') is not None:
            return domain['dns']['CNAME']['value']

    return None

def _retrieve_certificate(domain: dict[str, Any]) -> str | None:

    if tls_data_present(domain):
        cert_hash, _, _ = parse_cert(domain['tls'])
        return cert_hash

    return None

def _rm_domains_exact_match_universal(
        domains: list[dict],
        version: int,
        driver: Neo4jDBDriver,
        v_attr_name: str,
        e_t: EdgeTypes,
        n_data_retrieval_func: Callable[[dict[str, Any]],str | None],
        v_t: NodeTypes | None = None,
        e_attr_name: str | None = None,
        e_data_retrieval_func: Callable[[dict[str, Any]],str | None] | None = None
) -> set[str]:

    rows = []
    for domain in domains:
        row = { D_NAME: domain[D_NAME] }
        v_val = n_data_retrieval_func(domain)
        if v_val is not None:
            row['v_val'] = v_val

        if e_attr_name is not None and e_data_retrieval_func is not None:
            e_val = e_data_retrieval_func(domain)
            if e_val is not None:
                row['e_val'] = e_val

        rows.append(row)

    edge_attr_query = "" if e_data_retrieval_func is None or e_attr_name is None else f"{{{e_attr_name}: domain.e_val}}"
    v_t_query = '' if v_t is None else f":{v_t.neo4j}"

    query = f"""
    UNWIND $domains AS domain
    OPTIONAL MATCH (:{NodeTypes.DOMAIN.neo4j} {{{D_NAME}: domain.{D_NAME} {get_version_query(version, False)} }})
                  -[:{e_t.value} {edge_attr_query}]->(m {v_t_query})
    WITH domain, m
    WHERE (domain.v_val IS NOT NULL AND m IS NULL) OR (domain.v_val IS NULL AND m IS NOT NULL) OR domain.v_val <> m.{v_attr_name}
    RETURN collect(domain.domain_name) AS diff_domains
    """

    diff_domain_names = driver.execute_read(query, domains=rows)[0]['diff_domains']
    diff_domains = set(diff_domain_names)
    del diff_domain_names, rows

    return diff_domains

#TODO FINISH THIS

#OLD WORKING CODE IN USE FROM HERE


def rm_domains_with_same_cname(domains: list[dict], version: int, driver: Neo4jDBDriver) -> set[str]:
    """
    Function that filters out domains that have the same CNAME as their graph counterparts
    :param domains: `list[dict]` with domain data which may or may not hold A and AAAA records
    :param version: `int` graph version
    :param driver: `Neo4jDBClient` driver used to query db
    :return: `set[str]` with domains (their domain names) that have different CNAME in graph
    """

    rows = []
    for domain in domains:
        row = {"domain_name": domain['domain_name']}
        if domain['dns'].get('CNAME') is not None:
            if type(domain['dns']['CNAME']) == str:
                row['CNAME'] = domain['dns']['CNAME']
            elif domain['dns']['CNAME'].get('value') is not None:
                row['CNAME'] = domain['dns']['CNAME']['value']

        rows.append(row)

    query = f"""
    UNWIND $domains AS domain
    OPTIONAL MATCH (:{NodeTypes.DOMAIN.neo4j} {{domain_name: domain.domain_name {get_version_query(version, False)} }})
                  -[:{EdgeTypes.CNAME.value} {{owner: domain.domain_name}}]->(m)
    WITH domain, m
    WHERE (domain.CNAME IS NOT NULL AND m IS NULL) OR (domain.CNAME IS NULL AND m IS NOT NULL) OR domain.CNAME <> m.domain_name
    RETURN collect(domain.domain_name) AS diff_domains
    """

    diff_domain_names = driver.execute_read(query, domains=rows)[0]['diff_domains']
    diff_domains = set(diff_domain_names)
    del diff_domain_names, rows

    return diff_domains

def rm_domains_with_same_registrant(domains: list[dict], version: int, driver: Neo4jDBDriver) -> set[str]:
    """
    Method that filters out domains that have the same registrant as their graph counterparts
    :param domains: `list[dict]` with domain data which may or may not hold A and AAAA records
    :param version: `int` graph version
    :param driver: `Neo4jDBClient` driver used to query db
    :return: `set[str]` with domains (their domain names) that have different registrant in graph
    """

    rows = []
    for domain in domains:
        row = {"domain_name": domain['domain_name']}
        registrant = get_registrant_from_record(domain)
        if registrant is not None:
            row['registrant'] = registrant

        rows.append(row)

    query = f"""
    UNWIND $domains AS domain
    OPTIONAL MATCH (:{NodeTypes.DOMAIN.neo4j} {{domain_name: domain.domain_name {get_version_query(version, False)} }})
                  -[:{EdgeTypes.REGISTERED.value}]->(m:{NodeTypes.REGISTRANT.neo4j})
    WITH domain, m
    WHERE (domain.registrant IS NOT NULL AND m IS NULL) OR (domain.registrant IS NULL AND m IS NOT NULL) OR domain.registrant <> m.name
    RETURN collect(domain.domain_name) AS diff_domains
    """

    diff_domain_names = driver.execute_read(query, domains=rows)[0]['diff_domains']
    diff_domains = set(diff_domain_names)
    del diff_domain_names, rows
    return diff_domains

def rm_domains_with_same_certificate(domains: list[dict], version: int, driver: Neo4jDBDriver) -> set[str]:

    rows = []
    for domain in domains:
        row = {"domain_name": domain['domain_name']}

        if tls_data_present(domain):
            cert_hash, _, _ = parse_cert(domain['tls'])
            row['cert_hash'] = cert_hash

        rows.append(row)

    query= f"""
    UNWIND $domains AS domain
    OPTIONAL MATCH (:{NodeTypes.DOMAIN.neo4j} {{domain_name: domain.domain_name {get_version_query(version, False)} }})
                  -[:{EdgeTypes.HAS_CERTIFICATE.value}]->(m:{NodeTypes.CERTIFICATE.neo4j})
    WITH domain, m
    WHERE (domain.cert_hash IS NOT NULL AND m IS NULL) OR (domain.cert_hash IS NULL AND m IS NOT NULL) OR domain.cert_hash <> m.{CERT_HASH}
    RETURN collect(domain.domain_name) AS diff_domains
    """

    diff_domain_names = driver.execute_read(query, domains=rows)[0]['diff_domains']
    diff_domains = set(diff_domain_names)
    del diff_domain_names, rows
    return diff_domains