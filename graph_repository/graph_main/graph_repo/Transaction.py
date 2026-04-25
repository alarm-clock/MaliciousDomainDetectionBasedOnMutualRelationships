import threading
import time
from graph_repository.Neo4jDBDriver import Neo4jDBDriver
from graph_repository.workers.common.GraphTypes import NodeTypes


class Transaction:

    TIME_LIMIT = 1200#s

    def __init__(self, job_id: str, version: int):
        self._job_id = job_id
        self._version = version
        self._tmp_nodes: set[int] = set()
        self._lock = threading.Lock()
        self._start_time: float = time.time()

    @property
    def job_id(self) -> str: return self._job_id

    @property
    def version(self) -> int: return self._version

    @property
    def n_nodes(self): return len(self._tmp_nodes)

    @property
    def empty(self): return self.n_nodes == 0

    def is_over_time(self) -> bool:
        return time.time() - self._start_time > self.TIME_LIMIT

    def remove_tmp_node_from_transaction(self, node_id: int | None) -> bool:

        with self._lock:
            if node_id is not None:
                try:
                    self._tmp_nodes.remove(node_id)
                except KeyError:
                    pass

            return len(self._tmp_nodes) == 0

    def add_tmp_node_to_transaction(self, node_id: int) -> bool:
        if self.is_over_time():
            return False

        with self._lock:
            self._tmp_nodes.add(node_id)

        return True

    def delete_all_tmp_nodes(self, driver: Neo4jDBDriver) -> None:
        with self._lock:
            for node_id in self._tmp_nodes:
                driver.delete_node({'node_id': node_id}, NodeTypes.TMP_DOMAIN.neo4j)