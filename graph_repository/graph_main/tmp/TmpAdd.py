from misc.Logger import MyLogger
from misc.PackageImporter import get_options_from_registry
from graph_repository.workers.common.EditWorker import EDIT_WORKER_REGISTRY
from graph_repository.Neo4jDBClient import Neo4jDBClient
from typing import Callable, Any

#TODO unused tmp domains will be removed in bulks, maintained by graph repo

def _get_edges(available_options: list[
    Callable[[dict, int, Neo4jDBClient], tuple[list[dict], dict[str, Any]] | list[tuple[list[dict], dict[str,Any]]] | None]
], domain: dict[str, Any], driver: Neo4jDBClient) -> list[tuple[list[dict], dict[str,Any]]] | None:
    """
    Function that calls edge creation function for all registered edge relationship functions
    :param available_options: `list[function]` that contains all available edge relationship functions
    :param domain: `dict[str|Any] that holds temporary domain data
    :param driver: `Neo4jDBClient` db driver
    :return: list[tuple[ List of edges, edge creation options]] if there are any relationships otherwise None
    """

    version = driver.get_current_active_graph_version()

    edges = []
    for tmp_func in available_options:
        tmp_edges = tmp_func(domain, version, driver)

        if tmp_edges is not None:
            if type(tmp_edges) is list:
                edges.extend(tmp_edges)
            else:
                edges.append(tmp_edges)

    return edges if len(edges) > 0 else None


def _create_edges(domain: dict[str, Any], edges: list[tuple[list[dict], dict[str,Any]]], driver: Neo4jDBClient) -> int:
    """
    Function that creates temporary edges
    :param domain: `dict[str|Any] that holds temporary domain data
    :param edges: list of tuples [ List of edges, edge creation options]
    :param driver: `Neo4jDBClient` db driver
    :return: Allocated temporary edge id
    """

    tmp_node_id = driver.create_tmp_node(domain)

    for edges, edge_options_dict in edges:
        driver.create_edges(edge_options_dict, edges)

    return tmp_node_id


def add_temporary_domain(domain: dict[str, Any],  driver: Neo4jDBClient) -> int | None:
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
    get_options_from_registry(EDIT_WORKER_REGISTRY, available_options)
    edges = _get_edges(available_options, domain, driver)
    if edges is None:
        MyLogger.get_instance().log(f"Temporary domain {domain['domain_name']} has no neighbors in graph!")
        return None
    tmp_node_id = _create_edges(domain, edges, driver)

    MyLogger.get_instance().log(f"Temporary domain {domain['domain_name']} has been added to graph with node_id {tmp_node_id}")
    return tmp_node_id