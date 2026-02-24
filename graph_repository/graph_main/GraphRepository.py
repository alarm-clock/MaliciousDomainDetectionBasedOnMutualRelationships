from queue import PriorityQueue

from graph_repository.Neo4jDBClient import Neo4jDBClient
#from graph_repository.graph_main.graph_editing.common.GraphRequest import GraphRequest
from graph_repository.graph_main.graph_editing.common.RequestPriority import RequestPriority

class GraphRepository:

    _repository_instance_ = None

    def __new__(cls, *args, **kwargs):
        if GraphRepository._repository_instance_ is None:
            cls._repository_instance_ = super().__new__(cls)
            cls._repository_instance_._initialized = False

        return cls._repository_instance_

    def __init__(self, neo4j_conf: str):
        if not self._initialized:
            self._initialized = True
            self._request_q = PriorityQueue()
            self._neo4j_conf = neo4j_conf

    @staticmethod
    def get_instance(neo4j_conf: str| None = None):
        if GraphRepository._repository_instance_ is None:
            if neo4j_conf is not None:
                GraphRepository(neo4j_conf)
            else:
                return None
        return GraphRepository._repository_instance_

    def get_neo4j_driver(self) -> Neo4jDBClient:
        return Neo4jDBClient.from_config(self._neo4j_conf)

    def add_request_to_queue(self, request):
        self._request_q.put(request)