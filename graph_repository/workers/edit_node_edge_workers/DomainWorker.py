from graph_repository.workers.common.EditWorker import EditWorker
from graph_repository.graph_main.GraphRepository import GraphRepository
from graph_repository.Neo4jDBClient import Neo4jDBClient
from graph_repository.workers.common.GraphTypes import NodeTypes
from graph_repository.workers.common.Enums import EditTypes
from misc.Logger import MyLogger

class DomainWorker(EditWorker):

    worker_name = 'DomainWorker'
    _limit = 5000

    def __init__(self, domains: list[dict], node_submission_callback):
        super().__init__(domains,DomainWorker._limit)
        self._node_submission_callback = node_submission_callback
        self._domains_for_creation: list[dict] = []

    def _compute(self):

        driver: Neo4jDBClient = GraphRepository.get_instance().get_neo4j_driver()
        max_domain_id = driver.get_max_id_of_node_type(NodeTypes.DOMAIN)
        driver.close()

        curr_id = max_domain_id + 1

        for domain in self._domains:

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

            node_id = curr_id
            curr_id += 1

            try:
                other_data = str(domain["other_data"])
            except KeyError:
                other_data = None

            self._domains_for_creation.append({'domain_name': domain_name, 'label': label, 'node_id': node_id, 'other_data': other_data})

        self._node_submission_callback(self._domains_for_creation, NodeTypes.DOMAIN, self.worker_name , EditTypes.UPDATE)