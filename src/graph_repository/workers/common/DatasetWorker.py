"""
File: graph_repository/workers/common/Dataset/Worker.py
System module: graph_repository
Author: Jozef Michal Bukas
Email: xbukas00@stud.fit.vutbr.cz
Date: 10.2.2026
Description: Worker class used for parallel creation of edges from dataset
"""

import copy
from graph_repository.graph_repo_misc import add_project_into_pipeline
from graph_repository.workers.common.Worker import Worker
from graph_repository.workers.common.GraphTypes import NodeTypes, NODE_ATTRIBUTES
import pymongo

"""
Dictionary storing worker classes identified by worker_name
"""
DATASET_WORKER_REGISTRY = {}

class DatasetWorker(Worker):
    """
        Base class for all other worker classes used for parallel creation of edges which are identified by worker_name.

        Static attributes:
            `worker_name (str)`: name identifying given worker class

            `available_options (list[tuple[str, str, dict | None]])`: list of available options for given worker class in
            format (name, option name, kwargs for that option or none)
    """
    worker_name: str
    available_options: list[tuple[str, str, dict | None]]  # list of option and kwargs for that option

    def __init__(self, submit_callback_method, collection: pymongo.collection.Collection, ranges: list, project: dict, n_ts: list[NodeTypes] | None = None) -> None:
        """
        Initializes worker class shared attributes.
        :param submit_callback_method: Method for submitting results to dispatcher
        :param collection: Mongo collection with dataset
        :param ranges: Dictionary with `or` conditions used to filter collection entries by `node_id`
        :param project: Dictionary for filtering document
        :param n_ts: List of node types that worker creates used to initialize data store, if none then empty store is initialized
        """
        super().__init__()
        self._submit_callback_method = submit_callback_method
        self._collection = collection
        self._match = copy.deepcopy(ranges)
        add_project_into_pipeline(project, ranges)
        self._pipeline = ranges
        self._u: list[int] = []
        self._v: list[int] = []
        self._n_data = NDataStore(n_ts)


    @classmethod
    def _register(cls):
        if cls.__name__ != "DatasetWorker":
            DATASET_WORKER_REGISTRY[cls.worker_name] = cls

    @classmethod
    def opts(cls):
        return cls.available_options

class NDataStore:
    """
    Class for storing node data when creating domain relationship graph from dataset
    """

    def __init__(self, n_ts: list[NodeTypes] | None = None) -> None:
        self._data: dict[NodeTypes, dict[str, list]] = {}

        if n_ts is not None:
            for n_t in n_ts:
                self.reg_n_type(n_t, NODE_ATTRIBUTES[n_t])

    def reg_n_type(self, n_t: NodeTypes, attributes: list[str]) -> None:
        """
        Method for registering attributes for given node type
        :param n_t: Node type
        :param attributes: List of attributes to register
        :return: Nothing
        """
        self._data[n_t] = {attr: [] for attr in attributes}

    def store_n_data(self, n_t: NodeTypes, **kwargs) -> None:
        """
        Method for storing node data
        :param n_t: Node type
        :param kwargs: key-value pairs of attributes to store
        :return: Nothing
        """
        n_t_storage = self._data[n_t]

        for attr, val in kwargs.items():
            n_t_storage[attr].append(val)

    def get_n_data(self, n_t: NodeTypes) -> dict[str, list]:
        """
        Method for getting node data
        :param n_t: Node type of data you want to get
        :return: Node data for given node type
        """
        return self._data[n_t]