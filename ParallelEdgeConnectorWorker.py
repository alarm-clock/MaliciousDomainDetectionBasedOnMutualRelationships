import threading
import copy
from Node import Node


def list_intersection(l_ip1: list, l_ip2: list) -> list:

    result = []

    for ip in l_ip1:
        if ip in l_ip2:
            result.append(ip)

    return result

def list_union(l_ip1: list, l_ip2: list) -> list:

    result = copy.deepcopy(l_ip1)

    for ip in l_ip2:
        if ip not in result:
            result.append(ip)

    return result

class ParallelEdgeConnectorWorker(threading.Thread):

    def __init__(self, dispatcher, batch: list[Node]) -> None:
        super().__init__()
        self._dispatcher = dispatcher
        self._batch = batch

    def _calc_jaccard(self, nd1: Node, nd2: Node) -> float:

        return len(list_intersection(nd1.ip, nd2.ip)) / len(list_union(nd1.ip, nd2.ip))

    def run(self) -> None:

        for node in self._batch:

            new_neighbors: list[int] = []
            for ip in node.ip:
                new_neighbors.extend(self._dispatcher.list_of_ips[ip].get_domains())

            new_neighbors_jaccard: list[float] = []
            for neighbor in new_neighbors:
                neighbor_node = self._dispatcher.list_of_nodes[neighbor]
                new_neighbors_jaccard.append(self._calc_jaccard(node, neighbor_node))

            neighbor_jacc_tup = list(zip(new_neighbors, new_neighbors_jaccard))

            node.add_neighbours(neighbor_jacc_tup)
