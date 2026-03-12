from graph_repository.workers.common.EditWorker import EditWorker
from graph_repository.graph_main.GraphRepository import GraphRepository
from graph_repository.Neo4jDBClient import Neo4jDBClient, get_version_query
from graph_repository.workers.common.GraphTypes import NodeTypes
from graph_repository.workers.common.Enums import EditTypes, CallbackWhen
from graph_repository.graph_repo_misc import get_domains_parent_domains, domain_depth
from functools import partial
from misc.Logger import MyLogger

class DomainWorker(EditWorker):

    worker_name = 'DomainWorker'
    req_callbacks = (worker_name, [EditWorker.ReqCallbacks.NODE,EditWorker.ReqCallbacks.CALLBACK])
    _limit = 5000

    def __init__(self, domains: list[dict], version: int, nodes_submit_callback, callbacks_submit_callback):
        super().__init__(domains, version, DomainWorker._limit)
        self._node_submission_callback = nodes_submit_callback
        self._callbacks_submit_callback = callbacks_submit_callback
        self._domains_for_creation: list[dict] = []

    @staticmethod
    def _replace_dummies(domains_for_replacing: list[str], version_query: str) -> None:
        # this will run after normal nodes equivalents of dummies exists
        # they will have same domain name but node_id in parameter is for the du_domains

        driver: Neo4jDBClient = GraphRepository.get_instance().get_neo4j_driver()
        replace_query = f"""

        UNWIND $domains as d

        MATCH (old: {NodeTypes.DUMMY_DOMAIN.value} {{domain_name: d {version_query}}})
        MATCH (new: {NodeTypes.DOMAIN.value} {{domain_name: d {version_query}}})
        {driver.get_node_replace_query('old','new', NodeTypes.DUMMY_DOMAIN.value ,False)}
        """

        driver.execute_write(replace_query, domains=domains_for_replacing)
        driver.close()
        return

    def _find_du_domains(self, domain_names: list[str], driver: Neo4jDBClient) -> None:

        find_if_domain_is_dummy_in_graph = f"""
        UNWIND $domains AS domain
        OPTIONAL MATCH(n: {NodeTypes.DUMMY_DOMAIN.value} {{domain_name: domain {get_version_query(self._version,False)}}})
        WITH n, domain
        WHERE n IS NOT NULL
        RETURN domain AS domain_name
        """

        result = driver.execute_read(find_if_domain_is_dummy_in_graph, domains=domain_names)

        domains_for_replacing = []
        for regular_domain in result:
            domain_name = regular_domain['domain_name']
            domains_for_replacing.append(domain_name)

        pre_filled = partial(DomainWorker._replace_dummies, domains_for_replacing, get_version_query(self._version,False))

        self._callbacks_submit_callback(pre_filled, CallbackWhen.BETWEEN_NODES_EDGES, self.worker_name)

    def _compute(self):

        driver: Neo4jDBClient = GraphRepository.get_instance().get_neo4j_driver()
        available_ids = driver.get_free_node_id(NodeTypes.DOMAIN, len(self._domains))

        domain_names = []
        for cnt, domain in enumerate(self._domains):

            try:
                domain_name = str(domain["domain_name"])
            except KeyError:
                MyLogger.get_instance().log_warning("Omitted domain from adding because \'domain_name\' field is missing")
                continue

            try:
                label = int(str(domain["label"]).find('benign') != -1)
            except KeyError:
                MyLogger.get_instance().log_warning(f"Omitted domain {domain_name} from adding because \'label\' field is missing")
                continue

            node_id = available_ids[cnt]

            try:
                other_data = str(domain["other_data"])
            except KeyError:
                other_data = None

            parent_domains = get_domains_parent_domains(domain_name)
            depth = domain_depth(domain_name)
            self._domains_for_creation.append({
                'domain_name': domain_name,
                'label': label,
                'node_id': node_id,
                'other_data': other_data,
                'parent_domains': parent_domains,
                'depth': depth
            })
            domain_names.append(domain_name)

        self._find_du_domains(domain_names, driver)
        driver.close()
        self._node_submission_callback(self._domains_for_creation, NodeTypes.DOMAIN, self.worker_name , EditTypes.UPDATE)