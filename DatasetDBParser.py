import threading
from pymongo import MongoClient
import json
from ParallelDBParser import ParallelDBParser
from Graph import create_graph
import torch as th

class DatasetDBParser:

    def __init__(self, client: str, port: int, db: str, collection: str, pwd: str = None, user: str = None):

        if pwd is not None and user is not None:
            self.client = MongoClient(f"mongodb://{user}:{pwd}@{client}:{port}/{db}")
        else:
            self.client = MongoClient(client, port)
        self.db = self.client[db]
        self.collection = self.db[collection]

        self._chunk_size = 50000
        self.worker_limit = 10
        self.num_of_w = 0

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


    def _create_edges(self) -> int:

        count_all_nodes = self.collection.count_documents({})
        for start_node_id in range(0, count_all_nodes, self._chunk_size):
            worker = ParallelDBParser(self,start_node_id, self._chunk_size if start_node_id + self._chunk_size <= count_all_nodes else count_all_nodes - start_node_id ,self.collection)
            self.workers.append(worker)
            worker.start()

        for worker in self.workers:
            worker.join()

        return count_all_nodes

    def parse(self):

        count_of_all_nodes = self._create_edges()
        return create_graph(th.Tensor(self._u), th.Tensor(self._v), th.Tensor(self._jacc), th.Tensor(self._labels),count_of_all_nodes)



