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

        if not getattr(cls,"__abstractmethods__", None):
            cls._register()

    def __init__(self):
        """
        Initializes worker class shared attributes.
        """
        super().__init__()


    @classmethod
    @abstractmethod
    def _register(cls):
        pass

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
