"""
File: graph_repository/dataset_creator/common/Worker.py
System module: graph_repository
Author: Jozef Michal Bukas
Email: xbukas00@stud.fit.vutbr.cz
Date: 10.2.2026
Description: Worker class used for parallel creation of edges from dataset
"""

import copy
import threading
from abc import ABC, abstractmethod
from graph_repository.graph_repo_misc import add_project_into_pipeline
import pymongo

"""
Dictionary storing worker classes identified by worker_name
"""
WORKER_REGISTRY = {}

class Worker(threading.Thread, ABC):
    """
        Base class for all other worker classes used for parallel creation of edges which are identified by worker_name.

        Static attributes:
            `worker_name (str)`: name identifying given worker class

            `available_options (list[tuple[str, str, dict | None]])`: list of available options for given worker class in
            format (name, option name, kwargs for that option or none)
    """

    worker_name: str
    available_options: list[tuple[str, str, dict | None]]  #list of option and kwargs for that option

    #(name, option name, kwargs for that option or none)

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if hasattr(cls, 'name'):
            WORKER_REGISTRY[cls.worker_name] = cls

    def __init__(self, submit_callback_method, collection: pymongo.collection.Collection, ranges: list, project: dict):
        """
        Initializes worker class shared attributes.
        :param submit_callback_method: Method for submitting results to dispatcher
        :param collection: Mongo collection with dataset
        :param ranges: Dictionary with `or` conditions used to filter collection entries by `node_id`
        :param project: Dictionary for filtering document
        """
        super().__init__()
        self._submit_callback_method = submit_callback_method
        self._collection = collection
        self._match = copy.deepcopy(ranges)
        add_project_into_pipeline(project, ranges)
        self._pipeline = ranges
        self._u: list[int] = []
        self._v: list[int] = []

    @abstractmethod
    def _compute(self):
        """
        Method for computing edges. Implemented by worker class.
        :return: None
        """
        pass

    def run(self):
        """
        Starts a worker thread.

        This method is automatically invoked when `threading.Thread.start()` is called.
        It only calls `_compute()` which is implemented in worker class.
        :return: None
        """
        self._compute()
