import copy

from graph_repository.Neo4jDBDriver import Neo4jDBDriver, get_version_query
from graph_repository.graph_repo_misc import get_domains_parent_domains
from graph_repository.workers.common.GraphTypes import NodeTypes, EdgeTypes
from graph_repository.workers.common.TmpFunctions import register
from typing import Any

def tmp_add_subdomain_edge(domain: dict, version: int, tmp_node_id: int, driver: Neo4jDBDriver) -> list[tuple[list[dict], dict[str,Any]]] | None:
    """
    Function for creating subdomain edges between `domain` and its parent domains in graph
    :param domain: `dict` that contains domain data
    :param version: `int` graph version that is used to find parent domains
    :param tmp_node_id: `int` node_id of tmp_edge_workers domain
    :param driver: `Neo4jDBClient` open driver for interacting with Neo4j
    :return: `list[(` edges `,` edge_creation_options `)]` if there is at least one parent node in graph, otherwise `None`
    """

    domain_name = domain['domain_name']
    parent_domains = get_domains_parent_domains(domain_name)
    edges = []

    query = f"""
    UNWIND $parent_domains AS parent_domain
    
    OPTIONAL MATCH (n: {NodeTypes.DOMAIN.neo4j} {{ domain_name: parent_domain {get_version_query(version, False)}}})
    WITH n, parent_domain
    OPTIONAL MATCH (m: {NodeTypes.DUMMY_DOMAIN.neo4j} {{ domain_name: parent_domain {get_version_query(version, False)} }})
    WHERE n IS NULL
    
    WITH coalesce(n, m) AS parent_node, parent_domain
    WITH 
        parent_domain, 
        CASE
            WHEN parent_node IS NULL THEN NULL
            ELSE labels(parent_node)[0]
        END AS n_t
    
    RETURN parent_domain AS d, n_t
    """

    parent_domains_in_graph = driver.execute_read(query, parent_domains=parent_domains)

    d_edges = []
    dum_edges = []

    for row in parent_domains_in_graph:
        parent_domain = row['d']
        label = row['n_t']
        if label is not None:
            if label == NodeTypes.DOMAIN.neo4j:
                d_edges.append({'u': tmp_node_id, 'v': parent_domain})
            elif label == NodeTypes.DUMMY_DOMAIN.neo4j:
                dum_edges.append({'u': tmp_node_id, 'v': parent_domain})


    if len(d_edges) == len(dum_edges) == 0:
        return None

    query_option_d = {
        Neo4jDBDriver.E_NODE_T1: NodeTypes.TMP_DOMAIN,
        Neo4jDBDriver.E_NODE_T2: NodeTypes.DOMAIN,
        Neo4jDBDriver.E_OPTION: Neo4jDBDriver.EdgeCreationQueryOptions.NO_WEIGHT_REVERSE,
        Neo4jDBDriver.E_EDGE_T: EdgeTypes.SUBDOMAIN,
        Neo4jDBDriver.E_MATCH1: "node_id",
        Neo4jDBDriver.E_MATCH2: "domain_name"
    }

    query_option_dum = copy.deepcopy(query_option_d)
    query_option_dum[Neo4jDBDriver.E_NODE_T2] = NodeTypes.DUMMY_DOMAIN

    edges.append((d_edges, query_option_d))
    edges.append((dum_edges, query_option_dum))

    return edges

register("subdomain", tmp_add_subdomain_edge)