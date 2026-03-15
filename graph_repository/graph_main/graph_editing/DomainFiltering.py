from misc.Logger import MyLogger
import graph_repository.graph_main.graph_editing.DomainFiltersOnGraphData as filters
from graph_repository.workers.common.GraphTypes import NodeTypes
from graph_repository.graph_main.GraphRepository import GraphRepository
from graph_repository.Neo4jDBClient import Neo4jDBClient
import inspect


def _rm_duplicates_and_no_basic_info(domains: list[dict]) -> list[dict]:
    parsed_domains = set()
    filtered_domains = []

    for domain in domains:
        if domain.get('domain_name') is None:
            MyLogger.get_instance().log_warning(
                "filter_domains - Omitted domain from adding because \'domain_name\' field is missing"
            )
            continue

        domain_name = str(domain["domain_name"])
        if domain_name in parsed_domains:
            continue

        if domain.get('label') is None:
            MyLogger.get_instance().log_warning(
                f"filter_domains - Omitted domain {domain_name} from adding because \'label\' field is missing"
            )
            continue

        parsed_domains.add(domain_name)
        filtered_domains.append(domain)

    return filtered_domains


def _rm_domains_that_are_in_graph(domains: list[dict], driver: Neo4jDBClient) -> list[dict]:

    filtered_domains = []
    current_version = driver.get_current_active_graph_version()

    filter_outputs: list[set[str]] = []
    for name, func in inspect.getmembers(filters, inspect.isfunction):
        if func.__module__ == filters.__name__:
            if name[:3] == 'rm_':
                filter_outputs.append(func(domains, current_version, driver))

    for domain in domains:
        domain_name = str(domain["domain_name"])
        stays = False
        for filter_output in filter_outputs:
            if domain_name in filter_output:
                stays = True
                break
        if stays:
            filtered_domains.append(domain)

    del domains
    return filtered_domains


def _get_add_update_sets(domains: list[dict], driver: Neo4jDBClient, get_just_add: bool) -> tuple[list[dict], list[dict]] | list[dict]:
    domains_dict = {}
    for domain in domains:
        domains_dict[domain['domain_name']] = domain

    del domains
    query = f"""
    UNWIND $domains AS domain
    OPTIONAL MATCH (n:{NodeTypes.DOMAIN.value} {{domain_name: domain}})
    RETURN collect({{
        d_n: domain,
        is_in: n IS NOT NULL 
    }}) AS doms 
    """
    res = driver.execute_read(query, domains=list(domains_dict.keys()))[0]['doms']

    add = []
    update = []

    for domain_dict in res:
        domain_name = str(domain_dict["d_n"])
        if domain_dict['is_in'] and not get_just_add:
            update.append(domains_dict[domain_name])  #these are domains that are in graph and must be deleted

        if not domain_dict['is_in'] or not get_just_add:
            add.append(domains_dict[domain_name])  #these are all domains

    del domains_dict
    return (add, update) if not get_just_add else add


def update_filter_domains(domains: list[dict]) -> tuple[list[dict], list[dict]]:
    filtered_domains = _rm_duplicates_and_no_basic_info(domains)
    driver: Neo4jDBClient = GraphRepository.get_instance().get_neo4j_driver()
    add_domains, update_domains = _get_add_update_sets(filtered_domains, driver, False)
    update_domains = _rm_domains_that_are_in_graph(update_domains, driver)

    driver.close()
    return add_domains, update_domains


def basic_filter_domains(domains: list[dict]) -> list[dict]:
    MyLogger.get_instance().log_debug(f" basic_filter_domains - Starting to filter domains")
    filtered_domains = _rm_duplicates_and_no_basic_info(domains)

    MyLogger.get_instance().log_debug(
        f" basic_filter_domains - Removed duplicate domains or domains without basic data")

    driver: Neo4jDBClient = GraphRepository.get_instance().get_neo4j_driver()
    filtered_domains = _get_add_update_sets(filtered_domains, driver, True)
    MyLogger.get_instance().log_debug(f" basic_filter_domains - removed domains that are already in graph")
    driver.close()
    return filtered_domains
