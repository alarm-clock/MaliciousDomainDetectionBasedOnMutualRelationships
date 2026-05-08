"""
:File: DomainFiltersOnGraphData.py
:Author: Jozef Michal Bukas <xbukas00@stud.fit.vutbr.cz>
:Date: 14.3.2026
:Brief: File that holds functions for filtering out domains that already have same data in graph.
    Note that you can create supporting function but main filter function must start with prefix
    "rm_" so that they can be differentiated from the other functions. Also, all main functions
    must have same parameters and all main function must return set with domains that should stay.
"""
from graph_repository.Neo4jDBDriver import Neo4jDBDriver, get_version_query
from graph_repository.workers.common.GraphTypes import NodeTypes, EdgeTypes

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
    RETURN collect( DISTINCT domain.domain_name) AS diff_domains
    """

    diff_domain_names = driver.execute_read(query,domains=rows)[0]['diff_domains']
    diff_domains = set(diff_domain_names)

    del diff_domain_names, rows
    return diff_domains


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
        row  = {"domain_name": domain['domain_name']}
        if domain['dns'].get('CNAME') is not None:
            if type(domain['dns']['CNAME']) == str:
                row['CNAME'] = domain['dns']['CNAME']
            elif domain['dns']['CNAME'].get('value') is not None:
                row['CNAME'] = domain['dns']['CNAME']['value']

        rows.append(row)

    query = f"""
    UNWIND $domains AS domain
    OPTIONAL MATCH (:{NodeTypes.DOMAIN.neo4j} {{domain_name: domain.domain_name {get_version_query(version,False)} }})
                  -[:{EdgeTypes.CNAME.value} {{owner: domain.domain_name}}]->(m)
    WITH domain, m
    WHERE (domain.CNAME IS NOT NULL AND m IS NULL) OR (domain.CNAME IS NULL AND m IS NOT NULL) OR domain.CNAME <> m.domain_name
    RETURN collect(domain.domain_name) AS diff_domains
    """

    diff_domain_names = driver.execute_read(query,domains=rows)[0]['diff_domains']
    diff_domains = set(diff_domain_names)
    del diff_domain_names, rows

    return diff_domains