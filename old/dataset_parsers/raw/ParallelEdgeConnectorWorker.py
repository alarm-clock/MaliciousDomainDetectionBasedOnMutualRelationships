import array
import threading
import copy
from misc.Logger import  MyLogger
import torch as th
from old.dataset_parsers.raw.Node import Node
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

    def _parse_neighbors(self, ips: list[int], node_id: int) -> array.array:

        new_neighbors = array.array('I')
        in_new_neighbors = set()
        for ip in ips:
            # node with lower id will always create edge, this halfs the number of edges, dgl graph can create the second edge on its own
            for neighbor_id in self._dispatcher.list_of_ips[ip].get_domains(): #to my future self, it isn't list of ips but dictionary of ips
                if neighbor_id > node_id and neighbor_id not in in_new_neighbors:
                    new_neighbors.append(neighbor_id)
                    in_new_neighbors.add(neighbor_id)

        return new_neighbors

    def _calc_jacc_for_node(self, nd: Node, neighbors: array.array, jacc: array.array) -> None:
        for neighbor in neighbors:
            jacc.append(calc_jaccard(nd, self._dispatcher.list_of_nodes[neighbor]))

    def _parallel_edge(self, nd: Node) -> tuple[ array.array, array.array, array.array]:

        jacc = array.array('d')
        new_neighbors = self._parse_neighbors(nd.ip,nd.id)
        self._calc_jacc_for_node(nd,new_neighbors,jacc)

        return array.array('I',[nd.id]) * len(new_neighbors), new_neighbors, jacc

    def parallel(self):


        #u, v, jacc = [], [], []
        u, v, jacc = array.array('I'), array.array('I'), array.array('d')

        with ThreadPoolExecutor(max_workers=40) as executor:
            futures = [executor.submit(self._parallel_edge, nd) for nd in self._batch]

            for future in futures:
                result = future.result()

                if result:
                    u_r, v_r, jacc_r = result
                    u.extend(u_r)
                    v.extend(v_r)
                    jacc.extend(jacc_r)
                    del u_r, v_r, jacc_r

        self._dispatcher.add_tensor_conc(u, v, jacc, [])
        MyLogger.get_instance().log(f"Edge connector whose first batch element is {self._batch[0].id} is finished...")
        del u, v, jacc, self._batch

    def normal(self):
        u, v, jacc, label = array.array('I'), array.array('I'), array.array('d'), array.array('I')

        for nd in self._batch:

            label.append(int(nd.b))

            new_neighbors = self._parse_neighbors(nd.ip,nd.id)

            v.extend(new_neighbors)
            u.extend([nd.id] * len(new_neighbors))

            self._calc_jacc_for_node(nd,new_neighbors,jacc)

        self._batch.clear()
        self._dispatcher.add_tensor_conc(th.tensor(u), th.tensor(v), th.tensor(jacc), th.tensor(label))

        u.clear()
        v.clear()
        jacc.clear()
        label.clear()

    def run(self) -> None:
        MyLogger.get_instance().log(f"Edge connector whose first batch element is {self._batch[0].id} is starting...")

        if self._do_parrallel_version:
            self.parallel()
        else:
            self.normal()