from typing import Any
import dgl
from graph_repository.Neo4jDBDriver import Neo4jDBDriver
from graph_repository.graph_main.graph_editing.EditConsumer import FinishType
from graph_repository.graph_main.graph_editing.common.RequestStates import RequestStates
from abc import ABC, abstractmethod

class GraphRepository(ABC):

    _repository_instance_: 'GraphRepository | None' = None
    API = "api"
    ABI = "abi"
    TMP_ADD_STOP = -1
    TMP_ADD_NO_DB_ERR = -2

    _implementations = {
        "abi": "graph_repository.graph_main.graph_repo.GraphRepositoryABI.GraphRepositoryABI",
        "api": "graph_repository.graph_main.graph_repo.GraphRepositoryAPI.GraphRepositoryAPI"
    }

    @classmethod
    def init(cls, implementation: str, config: str) -> 'GraphRepository':
        if cls._repository_instance_ is None:
            path_to_impl = cls._implementations.get(implementation)
            if path_to_impl is None:
                raise ValueError(f"Unknown implementation: {implementation}")

            mod_p, class_name = path_to_impl.rsplit(".", 1)
            module = __import__(mod_p, fromlist=[class_name])
            impl_class = getattr(module, class_name)
            cls._repository_instance_ = impl_class(config)

        return cls._repository_instance_

    @classmethod
    def get_instance(cls):
        return cls._repository_instance_

    @abstractmethod
    def stop(self, finish_all_submitted_edits: FinishType = FinishType.FINISH_NONE) -> None:
        pass


    @abstractmethod
    def get_neo4j_driver(self) -> Neo4jDBDriver | None:
        pass

    @abstractmethod
    def add_request_to_queue(self, request):
        pass

    @abstractmethod
    def get_request_state(self, job_id: str) -> RequestStates | None:
        pass

    @abstractmethod
    def delete_finished_request(self) -> None:
        pass

    @abstractmethod
    def temporary_add_domain(self, domain: dict[str, Any], job_id: str | None) -> int | None:
        pass

    @abstractmethod
    def delete_temporary_domain(self, tmp_nd_id: int, job_id: str) -> None:
        pass

    @abstractmethod
    def get_k_hop_neighborhood_dgl(self, tmp_node_id: int, for_ml: bool = False) -> dgl.DGLHeteroGraph:
        pass

    @abstractmethod
    def get_domain(self, domain_name: str) -> dict[str, Any] | None:
        pass

    @abstractmethod
    def get_neighbors_maliciousness(self, tmp_nd_id: int) -> tuple[float, float] | None:
        pass
