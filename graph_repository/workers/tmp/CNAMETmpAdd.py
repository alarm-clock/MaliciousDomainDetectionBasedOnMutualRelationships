from typing import Any
from graph_repository.Neo4jDBClient import Neo4jDBClient, get_version_query
from graph_repository.workers.common.GraphTypes import NodeTypes, EdgeTypes
from graph_repository.workers.common.TmpFunctions import register


def _find_cname_in_graph(cname_domain: str, version: int, driver: Neo4jDBClient) -> dict[str, Any] | None:

    find_cnames_in_domains = f"""
    OPTIONAL MATCH (n: {NodeTypes.DOMAIN.value} {{domain_name: $cname {get_version_query(version, False)}}})
    OPTIONAL MATCH (m: {NodeTypes.DUMMY_DOMAIN.value} {{domain_name: $cname {get_version_query(version, False)}}})  
    RETURN n AS domain, m AS dummy      
    """
    result = driver.execute_read(find_cnames_in_domains, **{'cname': cname_domain})[0]

    if result['domain'] is not None:
        return {
            Neo4jDBClient.E_NODE_T1: NodeTypes.TMP_DOMAIN,
            Neo4jDBClient.E_NODE_T2: NodeTypes.DOMAIN,
            Neo4jDBClient.E_OPTION: Neo4jDBClient.EdgeCreationQueryOptions.NO_WEIGHT_REVERSE,
            Neo4jDBClient.E_EDGE_T: EdgeTypes.CNAME,
            Neo4jDBClient.E_MATCH1: "domain_name",
            Neo4jDBClient.E_MATCH2: "domain_name"
        }
    elif result['dummy'] is not None:
        return {
            Neo4jDBClient.E_NODE_T1: NodeTypes.TMP_DOMAIN,
            Neo4jDBClient.E_NODE_T2: NodeTypes.DUMMY_DOMAIN,
            Neo4jDBClient.E_OPTION: Neo4jDBClient.EdgeCreationQueryOptions.NO_WEIGHT_REVERSE,
            Neo4jDBClient.E_EDGE_T: EdgeTypes.CNAME,
            Neo4jDBClient.E_MATCH1: "domain_name",
            Neo4jDBClient.E_MATCH2: "domain_name"
        }
    return None

def _find_domains_that_have_domain_as_cname(domain_name: str, version: int, driver: Neo4jDBClient) -> list | None:

    query=f"""
    MATCH (du: {NodeTypes.DUMMY_DOMAIN.value} {{ domain_name: "{domain_name}" {get_version_query(version, False)} }})
    OPTIONAL MATCH (du)-[:{EdgeTypes.CNAME.value}]->(d:{NodeTypes.DOMAIN.value})
    RETURN collect(d.node_id) AS domains
    """
    domains = driver.execute_read(query)[0]['domains']
    #for now, I will ignore the fact that there is dummy domain and same tmp domain, system will work regardless
    return domains if len(domains) > 0 else None

def tmp_add_cname_edge(domain: dict, version: int, driver: Neo4jDBClient) -> list[tuple[list[dict],dict[str,Any]]]| None:

    try:
        cname_domain = domain['dns']['CNAME']['value']
    except KeyError:
        try:
            cname_domain = domain['dns']['CNAME']
        except KeyError:
            return None

    domain_name = str(domain['domain_name'])

    edges = []

    edge_creation_dict = _find_cname_in_graph(cname_domain, version, driver)
    if edge_creation_dict is not None:
        edges.append(([{'u': domain_name, "v": cname_domain}], edge_creation_dict))

    domains_with_tmp_as_cname = _find_domains_that_have_domain_as_cname(domain_name, version, driver)
    if domains_with_tmp_as_cname is not None:
        edge_creation_dict = {
            Neo4jDBClient.E_NODE_T1: NodeTypes.TMP_DOMAIN,
            Neo4jDBClient.E_NODE_T2: NodeTypes.DOMAIN,
            Neo4jDBClient.E_OPTION: Neo4jDBClient.EdgeCreationQueryOptions.NO_WEIGHT_REVERSE,
            Neo4jDBClient.E_EDGE_T: EdgeTypes.CNAME,
            Neo4jDBClient.E_MATCH1: "domain_name",
            Neo4jDBClient.E_MATCH2: "node_id"
        }
        d_tmp_edges = []
        for domain in domains_with_tmp_as_cname:
            d_tmp_edges.append({'u': domain_name,'v': domain})

        edges.append((d_tmp_edges, edge_creation_dict))

    return edges if len(edges) > 0 else None


register('cname', tmp_add_cname_edge)