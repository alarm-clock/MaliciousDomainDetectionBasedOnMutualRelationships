"""
File: DeleteRequest.py
Author: Jozef Michal Bukas <xbukas00@stud.fit.vutbr.cz>
Date: 08.04.2026
Brief: File that contains graph-editing request implementation for deleting
    domain nodes from graph repository versions
"""

from graph_repository.graph_main.graph_editing.common.GraphRequest import GraphRequest
from graph_repository.graph_main.graph_editing.common.RequestPriority import RequestPriority
from graph_repository.graph_main.graph_editing.common.RequestStates import RequestStates
from graph_repository.workers.common.GraphTypes import NodeTypes
from graph_repository.Neo4jDBDriver import Neo4jDBDriver
from graph_repository.graph_main.GraphRepository import GraphRepository
from misc.Logger import MyLogger


class DeleteRequest(GraphRequest):
    """
    Class that represents graph-editing request used for deleting domain nodes
    from graph repository
    """

    def __init__(self, domains: list[dict], priority: RequestPriority, timeout: float = 1200.0):
        """
        Method that initializes delete request instance and keeps only domains
        with defined domain name
        :param domains: `list[dict]` submitted domain data
        :param priority: `RequestPriority` request priority
        :param timeout: `float` maximal waiting time in seconds
        :return: None
        """
        domains = [{'domain_name': domain['domain_name']} for domain in domains if domain.get('domain_name') is not None]
        super().__init__(domains, priority, timeout)

    def edit(self, version: int) -> bool:
        """
        Method that executes delete-request workflow for selected graph version
        :param version: `int` target graph version
        :return: `bool` True on success, otherwise False
        """
        self._stop_wait()

        if self._canceled:
            MyLogger.get_instance().log_warning(f"Delete request with id {self.id} is canceled before it could edit but after graph copy was created")
            if self.state != RequestStates.TIMEOUT:
                self.state = RequestStates.CANCELED

            del self._domains
            return False

        driver: Neo4jDBDriver = GraphRepository.get_instance().get_neo4j_driver()
        driver.delete_nodes(self._domains, NodeTypes.DOMAIN, True)
        driver.close()
        self.state = RequestStates.DONE
        del self._domains
        return True