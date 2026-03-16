import threading
import time
import uuid
from abc import ABC, abstractmethod
from functools import total_ordering
from threading import Thread, Event
from graph_repository.graph_main.graph_editing.common.RequestPriority import RequestPriority
from graph_repository.graph_main.graph_editing.common.RequestStates import RequestStates
from typing import Callable
import json


#todo proper init
#todo addition of two requests together (this may not work because each type does it's own thing, or at least it will be hard to implement)

@total_ordering
class GraphRequest(ABC):

    def __init__(self, domains: list[dict], priority: RequestPriority, timeout: float = 1200.0,
                 filter_func: Callable[[list[dict]], tuple[list[dict], list[dict]] | list[dict]] | None = None):
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
        return data if type(data) == list else [data]

    @classmethod
    def _check_class(cls):
        if isinstance(cls, GraphRequest):
            raise TypeError("GraphRequest cannot be instantiated, only subclasses of GraphRequest are allowed")

    @classmethod
    def from_json_file(cls, json_file: str, priority: RequestPriority, timeout: float = 600.0):
        cls._check_class()
        with open(json_file) as f:
            domains = GraphRequest._normalize_json_data(json.load(f))
        return cls(domains, priority, timeout)

    @classmethod
    def from_json_str(cls, json_str: str, priority: RequestPriority, timeout: float = 600.0):
        cls._check_class()
        domains = GraphRequest._normalize_json_data(json.loads(json_str))
        return cls(domains, priority, timeout)

    def __lt__(self, other):
        if not isinstance(other, GraphRequest):
            return NotImplemented

        return self._priority.value < other._priority.value

    def __eq__(self, other):
        if not isinstance(other, GraphRequest):
            return NotImplemented

        return self._priority.value == other._priority.value

    def get_n_domains(self) -> int:
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
        self._cancel_wait_event.set()

    def _wait(self):
        if not self._cancel_wait_event.wait(self._timeout):
            self.state = RequestStates.TIMEOUT
            self._canceled = True

    def cancel(self):
        self.state = RequestStates.CANCELED
        self._canceled = True

    def is_canceled(self) -> bool:
        return self._canceled

    def submit(self, repository):
        repository.add_request_to_queue(self)
        Thread(target=self._wait, daemon=True).start()

    @abstractmethod
    def edit(self, version: int):
        pass


class FinishRequest(GraphRequest):

    def __init__(self):
        super().__init__([{}],RequestPriority.LOW)

    def edit(self, version: int) -> None:
        return