from typing import Any
from graph_repository.workers.common.GraphTypes import NodeTypes, EdgeTypes, NODE_ID, CERT_HASH, D_NAME
from graph_repository.Neo4jDBDriver import Neo4jDBDriver, get_version_query
from graph_repository.workers.common.TmpFunctions import register
from graph_repository.graph_repo_misc import parse_cert


def tmp_add_certificate_edge(domain: dict[str, Any], version: int, tmp_node_id: int, driver: Neo4jDBDriver) -> tuple[list[dict], dict[str, Any]] | None:

    cert_hash, _, _ = parse_cert(domain['tls'])

    query = f"""
    OPTIONAL MATCH (c: {NodeTypes.CERTIFICATE.neo4j} {{ {CERT_HASH}: $cert_hash {get_version_query(version, False)}  }})
    RETURN c IS NOT NULL AS in_g
    """

    in_g = driver.execute_read(query, cert_hash=cert_hash)

    if not in_g:
        return None

    query_params = {
        Neo4jDBDriver.E_EDGE_T: EdgeTypes.HAS_CERTIFICATE,
        Neo4jDBDriver.E_NODE_T1: NodeTypes.TMP_DOMAIN,
        Neo4jDBDriver.E_NODE_T2: NodeTypes.CERTIFICATE,
        Neo4jDBDriver.E_OPTION: Neo4jDBDriver.EdgeCreationQueryOptions.NO_WEIGHT_REVERSE,
        Neo4jDBDriver.E_MATCH1: NODE_ID,
        Neo4jDBDriver.E_MATCH2: CERT_HASH
    }

    return [{D_NAME: domain['domain_name'], CERT_HASH: cert_hash}], query_params

register('certificate', tmp_add_certificate_edge)