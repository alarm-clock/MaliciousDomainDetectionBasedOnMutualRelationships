from graph_repository.graph_main.graph_editing.common.GraphRequest import GraphRequest
from graph_repository.graph_main.graph_editing.common.RequestPriority import RequestPriority
from graph_repository.workers.common.GraphTypes import NodeTypes
from graph_repository.Neo4jDBClient import Neo4jDBClient
from graph_repository.graph_main.GraphRepository import GraphRepository


class DeleteRequest(GraphRequest):

    def __init__(self, domains: list[dict], priority: RequestPriority, timeout: float = 600.0):
        super().__init__(priority, timeout)
        self._domains = [{'domain_name': domain['domain_name']} for domain in domains if
                         domain.get('domain_name') is not None]

    def edit(self, version: int):
        driver: Neo4jDBClient = GraphRepository.get_instance().get_neo4j_driver()
        driver.delete_nodes(self._domains, NodeTypes.DOMAIN, True)
        driver.close()
        return
