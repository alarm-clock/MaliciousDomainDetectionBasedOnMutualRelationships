from graph_repository.workers.common.GraphTypes import NodeTypes
from misc.Logger import MyLogger
from misc.PackageImporter import get_functions_from_registry
from graph_repository.workers.common.TmpFunctions import TMP_REGISTRY, TMP_FUNC_T, EDGES_T
from graph_repository.Neo4jDBDriver import Neo4jDBDriver
from typing import Any

def _get_edges(available_options: list[TMP_FUNC_T], domain: dict[str, Any], driver: Neo4jDBDriver, version: int, tmp_node_id) -> EDGES_T | None:
    """
    Function that calls edge creation function for all registered edge relationship functions
    :param available_options: `list[function]` that contains all available edge relationship functions
    :param domain: `dict[str|Any] that holds temporary domain data
    :param driver: `Neo4jDBClient` db driver
    :return: list[tuple[ List of edges, edge creation options]] if there are any relationships otherwise None
    """

    edges = []
    for tmp_func in available_options:
        tmp_edges = tmp_func(domain, version, tmp_node_id, driver)

        if tmp_edges is not None:
            if type(tmp_edges) is list:
                edges.extend(tmp_edges)
            else:
                edges.append(tmp_edges)

    return edges if len(edges) > 0 else None


def _prepare_domain_for_adding(domain: dict[str, Any], version: int, tmp_node_id: int) -> dict[str, Any]:

    keys_for_keeping: set[str] = {"domain_name"}
    domain_for_adding = {key: val for key, val in domain.items() if key in keys_for_keeping}
    domain_for_adding['graph_version'] = version
    domain_for_adding['node_id'] = tmp_node_id
    return domain_for_adding

def _create_edges(domain: dict[str, Any], edges: EDGES_T, driver: Neo4jDBDriver, version: int, tmp_node_id) -> None:
    """
    Function that creates temporary edges
    :param domain: `dict[str|Any] that holds temporary domain data
    :param edges: list of tuples [ List of edges, edge creation options]
    :param driver: `Neo4jDBClient` db driver
    :return: Allocated temporary edge id
    """
    domain_for_adding = _prepare_domain_for_adding(domain, version, tmp_node_id)
    driver.create_tmp_node(domain_for_adding)

    for edges_data, edge_options_dict in edges:
        driver.create_edges(edge_options_dict, edges_data)

    return


def add_temporary_domain(domain: dict[str, Any], driver: Neo4jDBDriver) -> int | None:
    """
    Function that creates a temporary domain and it's relationships with ground truth domains
    :param domain: `dict[str|Any` that holds temporary domain data, mut at least hold domain name otherwise function fails
    :param driver: `Neo4jDBClient` db driver
    :return: Allocated temporary domain id on success, None if domain has no domain name or domain has no relationships in graph
    """

    if domain.get("domain_name") is None:
        MyLogger.get_instance().log_warning('Can not add temporary domain without domain name!')
        return None

    available_options = []
    get_functions_from_registry(TMP_REGISTRY, available_options)

    version =  driver.get_current_active_graph_version()
    tmp_node_id = driver.get_free_node_id(NodeTypes.TMP_DOMAIN)
    edges = _get_edges(available_options, domain, driver, version, tmp_node_id)
    if edges is None:
        MyLogger.get_instance().log(f"Temporary domain {domain['domain_name']} has no neighbors in graph!")
        driver.return_unused_node_ids(NodeTypes.TMP_DOMAIN, tmp_node_id)
        return None

    _create_edges(domain, edges, driver, version, tmp_node_id)

    MyLogger.get_instance().log(f"Temporary domain {domain['domain_name']} has been added to graph with node_id {tmp_node_id}")
    return tmp_node_id