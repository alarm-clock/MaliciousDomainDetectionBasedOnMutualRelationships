"""
File: GraphRepository.py
Author: Jozef Michal Bukas <xbukas00@stud.fit.vutbr.cz>
Date: 15.01.2026
Brief: File that contains abstract base class for graph repository implementations
    and singleton-style initialization of selected implementation
"""

from typing import Any
from graph_repository.Neo4jDBDriver import Neo4jDBDriver
from graph_repository.graph_main.graph_editing.EditConsumer import FinishType
from graph_repository.graph_main.graph_editing.common.RequestStates import RequestStates
from abc import ABC, abstractmethod


class GraphRepository(ABC):
    """
    Class that represents abstract base class for graph repository implementations
    """

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
        """
        Method that initializes singleton graph repository implementation
        :param implementation: `str` selected implementation key
        :param config: `str` path to configuration file
        :return: `GraphRepository` initialized repository instance
        """
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
        """
        Method that returns initialized singleton repository instance
        :return: repository instance or None
        """
        return cls._repository_instance_

    @abstractmethod
    def stop(self, finish_all_submitted_edits: FinishType = FinishType.FINISH_NONE) -> None:
        """
        Method that stops graph repository functionality
        :param finish_all_submitted_edits: `FinishType` strategy for finishing pending edits
        :return: None
        """
        pass

    @abstractmethod
    def get_neo4j_driver(self) -> Neo4jDBDriver | None:
        """
        Method that returns Neo4j driver instance
        :return: `Neo4jDBDriver | None` database driver or None
        """
        pass

    @abstractmethod
    def add_request_to_queue(self, request):
        """
        Method that adds request to processing queue
        :param request: graph-editing request instance
        :return: None
        """
        pass

    @abstractmethod
    def get_request_state(self, job_id: str) -> RequestStates | None:
        """
        Method that returns state of request with given id
        :param job_id: `str` request identifier
        :return: `RequestStates | None` request state or None
        """
        pass

    @abstractmethod
    def delete_finished_request(self) -> None:
        """
        Method that deletes finished requests from repository state
        :return: None
        """
        pass

    @abstractmethod
    def temporary_add_domain(self, domain: dict[str, Any], job_id: str | None) -> int | None:
        """
        Method that adds temporary domain into graph
        :param domain: `dict[str, Any]` temporary domain data
        :param job_id: `str | None` transaction or job identifier
        :return: `int | None` temporary node id or error indicator
        """
        pass

    @abstractmethod
    def delete_temporary_domain(self, tmp_nd_id: int, job_id: str) -> None:
        """
        Method that deletes temporary domain from graph
        :param tmp_nd_id: `int` temporary node id
        :param job_id: `str` associated job identifier
        :return: None
        """
        pass

    @abstractmethod
    def get_k_hop_neighborhood_dgl(self, tmp_node_id: int, for_ml: bool = False) -> Any:
        """
        Method that returns k-hop neighborhood as DGL graph
        :param tmp_node_id: `int` temporary node id
        :param for_ml: `bool` flag indicating whether graph should be prepared for machine learning
        :return: `dgl.DGLHeteroGraph` neighborhood graph
        """
        pass

    @abstractmethod
    def get_domain(self, domain_name: str) -> dict[str, Any] | None:
        """
        Method that returns domain data from graph
        :param domain_name: `str` searched domain name
        :return: `dict[str, Any] | None` domain data or None
        """
        pass

    @abstractmethod
    def get_neighbors_maliciousness(self, tmp_nd_id: int) -> tuple[float, float] | None:
        """
        Method that returns maliciousness metrics of temporary node neighbors
        :param tmp_nd_id: `int` temporary node id
        :return: `tuple[float, float] | None` maliciousness values or None
        """
        pass
