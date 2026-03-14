import time
from abc import ABC, abstractmethod
from functools import total_ordering
from threading import Thread
from graph_repository.graph_main.graph_editing.common.RequestPriority import RequestPriority
import json

#TODO check and wait limited time in the main queue
#todo proper init
#todo addition of two requests together (this may not work because each type does it's own thing, or at least it will be hard to implement)

@total_ordering
class GraphRequest(ABC):

    def __init__(self, priority: RequestPriority, timeout: float = 1200.0):
        self._priority = priority
        self._canceled = False
        self._timeout = timeout
        self.id = None  #TODO


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
        if not isinstance(other, RequestPriority):
            return NotImplemented

        return self._priority.value < other._priority.value

    def __eq__(self, other):
        if not isinstance(other, RequestPriority):
            return NotImplemented

        return self._priority.value == other._priority.value

    def _wait(self):
        time.sleep(self._timeout)
        self._canceled = True

    def cancel(self):
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
        super().__init__(RequestPriority.LOW)


    def edit(self, version: int) -> None:
        return