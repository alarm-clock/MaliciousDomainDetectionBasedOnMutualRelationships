import threading
import copy

import DGLTest
import torch as th
from dataset_parsers.raw.Node import Node
from  concurrent.futures import ThreadPoolExecutor


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


def calc_jaccard(nd1: Node, nd2: Node) -> float:

    return len(list_intersection(nd1.ip, nd2.ip)) / len(list_union(nd1.ip, nd2.ip))

def calc_jaccard_f_l(list1: list, list2: list) -> float:
    return len(list_intersection(list1, list2)) / len(list_union(list1, list2))

class ParallelEdgeConnectorWorker(threading.Thread):

    def __init__(self, dispatcher, batch: list[Node], display_progress: bool, do_parrallel_version: bool) -> None:
        super().__init__()
        self._dispatcher = dispatcher
        self._batch = batch
        self._display_progress = display_progress
        self._do_parrallel_version = do_parrallel_version

    def _parallel_edge(self, nd: Node):

        #label.append(int(nd.b))
        jacc = []

        new_neighbors = []
        for ip in nd.ip:
            # node with lower id will always create edge, this halfs the number of edges, dgl graph can create the second edge on its own
            new_neighbors.extend(
                [n for n in self._dispatcher.list_of_ips[ip].get_domains() if n > nd.id and n not in new_neighbors])

        #v.extend(new_neighbors)
        #u.extend([nd.id] * len(new_neighbors))

        for neighbor in new_neighbors:
            jacc.append(calc_jaccard(nd, self._dispatcher.list_of_nodes[neighbor]))

        return [nd.id] * len(new_neighbors), new_neighbors, jacc

    def parallel(self):

        u, v, jacc = [], [], []

        with ThreadPoolExecutor(max_workers=40) as executor:
            futures = [executor.submit(self._parallel_edge, nd) for nd in self._batch]

            for future in futures:
                result = future.result()

                if result:
                    u_r, v_r, jacc_r = result
                    u.extend(u_r)
                    v.extend(v_r)
                    jacc.extend(jacc_r)

                    u_r.clear()
                    v_r.clear()
                    jacc_r.clear()

        self._batch.clear()
        self._dispatcher.add_tensor_conc(u, v, jacc, [])

        u.clear()
        v.clear()
        jacc.clear()

    def normal(self):
        u, v, jacc, label = [], [], [], []

        for nd in self._batch:

            label.append(int(nd.b))

            new_neighbors = []
            for ip in nd.ip:
                # node with lower id will always create edge, this halfs the number of edges, dgl graph can create the second edge on its own
                new_neighbors.extend(
                    [n for n in self._dispatcher.list_of_ips[ip].get_domains() if n > nd.id and n not in new_neighbors])

            v.extend(new_neighbors)
            u.extend([nd.id] * len(new_neighbors))

            for neighbor in new_neighbors:
                jacc.append(calc_jaccard(nd, self._dispatcher.list_of_nodes[neighbor]))

        self._batch.clear()
        self._dispatcher.add_tensor_conc(th.tensor(u), th.tensor(v), th.tensor(jacc), th.tensor(label))

        u.clear()
        v.clear()
        jacc.clear()
        label.clear()

    def run(self) -> None:

        if self._do_parrallel_version:
            self.parallel()
        else:
            self.normal()