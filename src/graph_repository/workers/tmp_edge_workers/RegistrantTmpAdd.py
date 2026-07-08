from typing import Any
from graph_repository.workers.common.GraphTypes import NodeTypes, EdgeTypes
from graph_repository.Neo4jDBDriver import Neo4jDBDriver, get_version_query
from graph_repository.workers.common.TmpFunctions import register
from graph_repository.graph_repo_misc import get_registrant_from_record

def tmp_add_registrant_edge(domain: dict[str, Any], version: int, tmp_node_id: int, driver: Neo4jDBDriver) -> tuple[list[dict], dict[str, Any]] | None:

    registrant = get_registrant_from_record(domain)

    query = f"""
    OPTIONAL MATCH (r: {NodeTypes.REGISTRANT.neo4j} {{ name: $registrant {get_version_query(version, False)} }})
    RETURN r IS NOT NULL AS in_g
    """
    registrant_in_graph = driver.execute_read(query,registrant=registrant)['in_g']

    if not registrant_in_graph:
        return None

    query_params = {
        Neo4jDBDriver.E_EDGE_T: EdgeTypes.REGISTERED,
        Neo4jDBDriver.E_NODE_T1: NodeTypes.TMP_DOMAIN,
        Neo4jDBDriver.E_NODE_T2: NodeTypes.REGISTRANT,
        Neo4jDBDriver.E_OPTION: Neo4jDBDriver.EdgeCreationQueryOptions.NO_WEIGHT_REVERSE,
        Neo4jDBDriver.E_MATCH1: "node_id",
        Neo4jDBDriver.E_MATCH2: "name"
    }
    return [{'node_id': tmp_node_id, 'name': registrant}], query_params



register("registrant", tmp_add_registrant_edge)