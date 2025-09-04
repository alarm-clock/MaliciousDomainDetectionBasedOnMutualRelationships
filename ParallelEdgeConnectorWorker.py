import threading
from Node import Node

class ParallelEdgeConnectorWorker(threading.Thread):

    def __init__(self, dispatcher, batch: list[Node]) -> None:
        super().__init__()
        self._dispatcher = dispatcher
        self._batch = batch

    def run(self) -> None:

        for node in self._batch:

            for ip in node.ip:
                new_neighbors = self._dispatcher.list_of_ips[ip].get_domains()
                node.add_neighbours(new_neighbors)
