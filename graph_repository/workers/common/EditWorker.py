from graph_repository.workers.common.Worker import Worker
from graph_repository.workers.common.GraphTypes import NodeTypes
from enum import Enum

EDIT_WORKER_REGISTRY = {}

class EditWorker(Worker):

    class ReqCallbacks(Enum):
        NODE = "nodes_submit_callback"
        EDGE = "edges_submit_callback"
        CALLBACK = "callbacks_submit_callback"
        ALL = "all"
    ADD_DOMAINS = True
    ADD_TMP_DOMAIN = False

    worker_name: str
    req_callbacks: tuple[str, list[ReqCallbacks]]

    def __init__(self, domains: list[dict], version: int , edge_limit: int):
        super().__init__()
        self._domains = domains
        self._edge_limit = edge_limit
        self._nodes: list[dict] = []
        self._edges: list[dict] = []
        self._version: int = version

    @classmethod
    def _register(cls):
        if cls.__name__ != "EditWorker":
            EDIT_WORKER_REGISTRY[cls.worker_name] = cls

    @classmethod
    def opts(cls):
        return cls.req_callbacks

    def compute(self) -> bool:

        if len(self._domains) > self._edge_limit:
            self.start()
            return True
        else:
            self.run()
            return False
