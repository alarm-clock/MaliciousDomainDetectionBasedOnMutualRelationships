from typing import Any
import dgl
from graph_repository.Neo4jDBDriver import Neo4jDBDriver
from graph_repository.graph_main.GraphRepository import GraphRepository
from graph_repository.graph_main.graph_editing.EditConsumer import FinishType
from graph_repository.graph_main.graph_editing.common.RequestStates import RequestStates


class GraphRepositoryAPI(GraphRepository):

    def __init__(self, graph_repo_conf: str):
        pass

    def stop(self, finish_all_submitted_edits: FinishType = FinishType.FINISH_NONE) -> None:
        pass

    def get_neo4j_driver(self) -> Neo4jDBDriver | None:
        pass

    def add_request_to_queue(self, request):
        pass

    def get_request_state(self, job_id: str) -> RequestStates | None:
        pass

    def delete_finished_request(self) -> None:
        pass

    def temporary_add_domain(self, domain: dict[str, Any], job_id: str | None) -> int | None:
        pass

    def delete_temporary_domain(self, tmp_nd_id: int) -> None:
        pass

    def get_k_hop_neighborhood_dgl(self, tmp_node_id: int, for_ml: bool = False) -> dgl.DGLHeteroGraph:
        pass

