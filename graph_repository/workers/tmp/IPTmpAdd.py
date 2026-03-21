from typing import Any
from graph_repository.workers.common.Misc import IPModes, get_ips_from_record
from graph_repository.workers.common.GraphTypes import NodeTypes, EdgeTypes
from graph_repository.Neo4jDBClient import Neo4jDBClient, get_version_query
from graph_repository.workers.common.TmpFunctions import register

def tmp_add_ip_edge(domain: dict, version: int, driver: Neo4jDBClient) -> tuple[list[dict], dict[str, Any]] | None:
    """
    Function for creating edges between `domain` and it's IP addresses that are in the graph
    :param domain: `dict` with domain information
    :param version: `int` graph version in which to look for IP nodes
    :param driver: `Neo4jDBClient` open driver for graph querying
    :return: `tuple[` edges`,` edge_creation_options`]` when there is at least one domain's IP address in graph otherwise None
    """

    domain_name = domain['domain_name']
    ips = get_ips_from_record(domain, IPModes.BOTH)

    query = f"""
    UNWIND $ip_addrs AS ip_addr
    OPTIONAL MATCH (n:{NodeTypes.IP.neo4j} {{ip_str: ip_addr {get_version_query(version, False)}}}
    WITH ip_addr, n
    WHERE n IS NOT NULL
    RETURN ip_addr AS in_graph
    """

    res = driver.execute_read(query, **{'ip_addrs': [str(ip) for ip in ips]})
    ips_in_graph = [r['in_graph'] for r in res]

    if len(ips_in_graph) == 0:
        return None #no ip connection in graph

    edges = []
    for ip in ips_in_graph:
        edges.append({'u': domain_name, 'v': ip})

    query_params = {
        Neo4jDBClient.E_EDGE_T: EdgeTypes.TRANSLATES,
        Neo4jDBClient.E_NODE_T1: NodeTypes.TMP_DOMAIN,
        Neo4jDBClient.E_NODE_T2: NodeTypes.IP,
        Neo4jDBClient.E_OPTION: Neo4jDBClient.EdgeCreationQueryOptions.NO_WEIGHT_REVERSE,
        Neo4jDBClient.E_MATCH1: "domain_name",
        Neo4jDBClient.E_MATCH2: "ip_str"
    }

    return edges, query_params


register("ip", tmp_add_ip_edge)