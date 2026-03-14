from graph_repository.graph_main.graph_editing.AddRequest import AddRequest
from graph_repository.graph_main.graph_editing.DeleteRequest import DeleteRequest
from graph_repository.graph_main.graph_editing.common.GraphRequest import GraphRequest
from graph_repository.graph_main.graph_editing.common.RequestPriority import RequestPriority

class EditRequest(GraphRequest):

    def __init__(self, domains: list[dict], priority: RequestPriority, timeout: float = 600.0):
        super().__init__(priority, timeout)
        self._domains = domains
        self._delete_req = DeleteRequest(domains, priority)
        self._add_req = AddRequest(domains, priority)

    #this is just basically delete and then add again, nothing more, nothing less

    def edit(self, version: int) -> None:
        self._delete_req.edit(version)
        self._add_req.edit(version)
        return