import threading
from pymongo import MongoClient
import json
from dataset_parsers.db.ParallelDBParser import ParallelDBParser
from dataset_parsers.Graph import create_graph
import torch as th
from dgl import DGLGraph

class DatasetDBParser:

    def __init__(self,no_lone_nd: bool, client: str, port: int, db: str, collection: str, pwd: str = None, user: str = None):

        if pwd is not None and user is not None:
            self.client = MongoClient(f"mongodb://{user}:{pwd}@{client}:{port}/{db}")
        else:
            self.client = MongoClient(client, port)
        self.db = self.client[db]
        self.collection = self.db[collection]

        self._chunk_size = 50000
        self.worker_limit = 10
        self.num_of_w = 0
        self.no_lone_nd = no_lone_nd

        self._u: list[int] = []
        self._v: list[int] = []
        self._jacc: list[float] = []
        self._labels: list[int] = []

        self.workers = []

        self._result_lock = threading.Lock()

    @classmethod
    def from_config(cls, config: str):

        with open(config) as f:
            conf = json.load(f)

            if conf["pwd"] is not None:
                return cls(conf["client"], conf["port"], conf["db"], conf["collection"], conf["pwd"], conf["user"])
            else:
                return cls(conf["client"], conf["port"], conf["db"], conf["collection"])


    def store_results(self, u: list[int], v: list[int], jacc: list[float], labels: list[int]) -> None:
        self._result_lock.acquire()
        self._u.extend(u)
        self._v.extend(v)
        self._jacc.extend(jacc)
        self._labels.extend(labels)
        self._result_lock.release()

    def _send_worker(self, start_id: int, size: int) -> None:
        worker = ParallelDBParser(self, start_id, size, self.collection)
        self.workers.append(worker)
        worker.start()

    def _wait_on_workers(self) -> None:
        for worker in self.workers:
            worker.join()

    def _create_edges(self) -> int:

        count_all_nodes = self.collection.count_documents({})
        for start_node_id in range(0, count_all_nodes, self._chunk_size):
           self._send_worker(start_node_id, self._chunk_size if start_node_id + self._chunk_size <= count_all_nodes else count_all_nodes - start_node_id)

        self._wait_on_workers()

        return count_all_nodes

    def _create_edges_from_ranges(self, ranges: list[tuple[int,int]]) -> int:

        count_all_nodes = 0

        for start, end in ranges:
            size = end - start
            count_all_nodes += size
            self._send_worker(start, size)

        self._wait_on_workers()

        return count_all_nodes

    def parse(self) -> DGLGraph:

        count_of_all_nodes = self._create_edges()
        return create_graph(th.Tensor(self._u), th.Tensor(self._v), th.Tensor(self._jacc), th.Tensor(self._labels),count_of_all_nodes)


    def _check_ranges(self, ranges: list[tuple[int,int]]) -> None:

        max_id = self.collection.find().sort({"node_id":-1}).limit(1)[0]["node_id"]

        uniq: list[tuple[int,int]] = []

        for start, end in ranges:
            if end < start:
                raise IndexError(f"End index is smaller then the start index (start: {start}, end: {end})")
            elif end > max_id:
                raise IndexError(f"End index is greater then the max id (max_id: {max_id}, end: {end})")
            elif start > max_id:
                raise IndexError(f"Start index is greater then the max id (max_id: {max_id}, start: {start})")
            elif start < 0 or end < 0:
                raise IndexError("One of the indexes is smaller then zero")

            for us, ue in uniq:
                if us <= start <= ue or us <= end <= ue:
                    raise IndexError("Duplicate or overlapping ranges detected")

            uniq.append((start, end))



    def parse_from_ranges(self, ranges: list[tuple[int, int]]) -> DGLGraph | None:

        # note that even though ranges will implicitly specify number of nodes, in reality this number might be much much larger
        # because if node is neighbor with node that is not specified in ranges will still be created
        try:
            if ranges is None:
                return None
            self._check_ranges(ranges)
        except IndexError as e:
            print(e)
            return None

        count_of_all_nodes = self._create_edges_from_ranges(ranges)
        return create_graph(th.Tensor(self._u), th.Tensor(self._v), th.Tensor(self._jacc), th.Tensor(self._labels),count_of_all_nodes)




