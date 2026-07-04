"""
File: GraphRequest.py
Author: Jozef Michal Bukas <xbukas00@stud.fit.vutbr.cz>
Date: 27.03.2026
Brief: File that contains abstract graph request class and finish request implementation
    used for queueing, prioritizing, filtering, and executing graph-editing requests
"""

import uuid
from abc import ABC, abstractmethod
from functools import total_ordering
from threading import Thread, Event
from graph_repository.graph_main.graph_editing.common.RequestPriority import RequestPriority
from graph_repository.graph_main.graph_editing.common.RequestStates import RequestStates
from typing import Callable
import json


#todo addition of two requests together (this may not work because each type does it's own thing, or at least it will be hard to implement)

@total_ordering
class GraphRequest(ABC):
    """
    Class that represents abstract graph-editing request with priority, timeout,
    filtering support, and cancellation handling
    """

    def __init__(self, domains: list[dict], priority: RequestPriority, timeout: float = 1200.0,
                 filter_func: Callable[[list[dict]], tuple[list[dict], list[dict]] | list[dict]] | None = None):
        """
        Method that initializes graph request instance
        :param domains: `list[dict]` domains associated with request
        :param priority: `RequestPriority` request priority in processing queue
        :param timeout: `float` maximal waiting time in seconds before request is canceled
        :param filter_func: `Callable[[list[dict]], tuple[list[dict], list[dict]] | list[dict]] | None`
            optional domain filtering function
        :return: None
        """
        self._domains = domains
        self._priority = priority
        self._canceled = False
        self._cancel_wait_event = Event()
        self._timeout = timeout
        self._filter_func = filter_func
        self.id = str(uuid.uuid4())
        self.state = RequestStates.SUBMITTED

    @staticmethod
    def _normalize_json_data(data) -> list:
        """
        Method that normalizes JSON input into list representation
        :param data: input JSON-decoded object
        :return: `list` original list or list containing single object
        """
        return data if type(data) == list else [data]

    @classmethod
    def _check_class(cls):
        """
        Method that checks whether base abstract class itself is being instantiated
        :return: None
        :raises TypeError: if `GraphRequest` base class is used directly
        """
        if isinstance(cls, GraphRequest):
            raise TypeError("GraphRequest cannot be instantiated, only subclasses of GraphRequest are allowed")

    @classmethod
    def from_json_file(cls, json_file: str, priority: RequestPriority, timeout: float = 600.0):
        """
        Method that creates request instance from JSON file
        :param json_file: `str` path to JSON file with domain data
        :param priority: `RequestPriority` request priority
        :param timeout: `float` maximal waiting time in seconds
        :return: Initialized subclass instance of `GraphRequest`
        """
        cls._check_class()
        with open(json_file) as f:
            domains = GraphRequest._normalize_json_data(json.load(f))
        return cls(domains, priority, timeout)

    @classmethod
    def from_json_str(cls, json_str: str, priority: RequestPriority, timeout: float = 600.0):
        """
        Method that creates request instance from JSON string
        :param json_str: `str` JSON string with domain data
        :param priority: `RequestPriority` request priority
        :param timeout: `float` maximal waiting time in seconds
        :return: Initialized subclass instance of `GraphRequest`
        """
        cls._check_class()
        domains = GraphRequest._normalize_json_data(json.loads(json_str))
        return cls(domains, priority, timeout)

    def __lt__(self, other):
        """
        Method that compares request priority for ordering
        :param other: other compared object
        :return: comparison result or `NotImplemented`
        """
        if not isinstance(other, GraphRequest):
            return NotImplemented

        return self._priority.value < other._priority.value

    def __eq__(self, other):
        """
        Method that checks equality of request priorities
        :param other: other compared object
        :return: comparison result or `NotImplemented`
        """
        if not isinstance(other, GraphRequest):
            return NotImplemented

        return self._priority.value == other._priority.value

    def get_n_domains(self) -> int:
        """
        Method that returns number of stored domains
        :return: `int` number of domains
        """
        return len(self._domains)

    def filter(self, filter_func: Callable[[list[dict]], tuple[list[dict], list[dict]] | list[dict]] | None = None) -> None:
        """
        Method that filters domains using ``filter_func``. Note that filter should del old domains object
        :param filter_func: Function that takes domains (`list[dict]`) as parameter and returns new domains
        :return: None
        """

        if filter_func is None:
            if self._filter_func is None:
                return
            filter_func = self._filter_func

        self._domains = filter_func(self._domains)
        return

    def _stop_wait(self):
        """
        Method that stops timeout waiting by setting internal event
        :return: None
        """
        self._cancel_wait_event.set()

    def _wait(self):
        """
        Method that waits for request completion or timeout expiration
        :return: None
        """
        if not self._cancel_wait_event.wait(self._timeout):
            self.state = RequestStates.TIMEOUT
            self._canceled = True

    def cancel(self):
        """
        Method that cancels request
        :return: None
        """
        self.state = RequestStates.CANCELED
        self._canceled = True

    def is_canceled(self) -> bool:
        """
        Method that checks whether request is canceled
        :return: `bool` True if request is canceled, otherwise False
        """
        return self._canceled

    def submit(self, repository):
        """
        Method that submits request into repository queue and starts timeout watcher thread
        :param repository: repository object that accepts queued requests
        :return: None
        """
        repository.add_request_to_queue(self)
        Thread(target=self._wait, daemon=True).start()

    @abstractmethod
    def edit(self, version: int):
        """
        Abstract method that performs graph edit for selected graph version
        :param version: `int` graph version that should be edited
        :return: None
        """
        pass


class FinishRequest(GraphRequest):
    """
    Class that represents terminating request used for finishing request-processing workflow
    """

    def __init__(self):
        """
        Method that initializes finish request with low priority
        :return: None
        """
        super().__init__([{}],RequestPriority.LOW)

    def edit(self, version: int) -> None:
        """
        Method that performs no action because finish request only signals termination
        :param version: `int` graph version
        :return: None
        """
        return