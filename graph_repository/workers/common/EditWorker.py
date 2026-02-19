from graph_repository.workers.common.Worker import Worker

EDIT_WORKER_REGISTRY = {}

class EditWorker(Worker):

    def __init__(self, domains: list[dict] , edge_limit: int):
        super().__init__()
        self._domains = domains
        self._edge_limit = edge_limit
        self._nodes: list[dict] = []
        self._edges: list[dict] = []

    @classmethod
    def _register(cls):
        if hasattr(cls, 'name'):
            EDIT_WORKER_REGISTRY[cls.worker_name] = cls


    def compute(self) -> bool:

        if len(self._domains) > self._edge_limit:
            self.start()
            return False
        else:
            self.run()
            return True
