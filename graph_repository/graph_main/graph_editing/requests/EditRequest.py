from graph_repository.graph_main.graph_editing.common.RequestStates import RequestStates
from graph_repository.graph_main.graph_editing.requests.AddRequest import AddRequest
from graph_repository.graph_main.graph_editing.requests.DeleteRequest import DeleteRequest
from graph_repository.graph_main.graph_editing.common.GraphRequest import GraphRequest
from graph_repository.graph_main.graph_editing.DomainFiltering import update_filter_domains, basic_filter_domains
from graph_repository.graph_main.graph_editing.common.RequestPriority import RequestPriority
from graph_repository.graph_main.GraphRepository import GraphRepository
from graph_repository.Neo4jDBClient import Neo4jDBClient
from graph_repository.workers.common.GraphTypes import NodeTypes
from typing import Callable

from misc.Logger import MyLogger


class EditRequest(GraphRequest):

    def __init__(self, domains: list[dict], priority: RequestPriority, timeout: float = 600.0):
        super().__init__(domains,priority, timeout, update_filter_domains)
        #self._delete_req = DeleteRequest(domains, priority)
        self._first_filter = True
        self._update = []
        self._add = []

    #this is just basically delete and then add again, nothing more, nothing less

    def filter(self, filter_func: Callable[[list[dict]], tuple[list[dict], list[dict]] | list[dict]] | None = None) -> None:
        """
        Method that filters domains using ``filter_func``. Note that filter should del old domains object
        :param filter_func: Function that takes domains (`list[dict]`) as parameter and returns new domains
        :return: None
        """

        if filter_func is None:
            if self._filter_func is None:
                return
            filter_func = self._filter_func

        if self._first_filter:
            self._first_filter = False
            self._domains = basic_filter_domains(self._domains)
        else:
            add, update = filter_func(self._domains)
            #print(add, update)
            self._add = add
            self._update = [{"domain_name":domain['domain_name']} for domain in update]

        return

    def edit(self, version: int) -> bool:
        self._stop_wait()

        if self._canceled:
            MyLogger.get_instance().log_warning(f"Delete request with id {self.id} is canceled before it could edit but after graph copy was created")
            if self.state != RequestStates.TIMEOUT:
                self.state = RequestStates.CANCELED
            return False

        #self._delete_req.edit(version)
        driver: Neo4jDBClient = GraphRepository.get_instance().get_neo4j_driver()

        driver.delete_nodes(self._update, NodeTypes.DOMAIN, True, True)
        #TODO find a way how to not delete subdodomains
        driver.close()

        add = AddRequest(self._add,self._priority)
        res = add.edit(version)
        self.state = RequestStates.DONE
        del self._add, self._update
        return res