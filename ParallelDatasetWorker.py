import threading
from Node import Node
from IPEdge import IPEdge
import ipaddress
import time

class ParallelDatasetWorker(threading.Thread):

    def __init__(self, dispatcher, start_id: int, json_data, c_size, b):
        super().__init__()
        self._dispatcher = dispatcher
        self.curr_id = start_id
        self.dataset = json_data
        self.chunk_size = c_size
        self.b = b

        self.nodes_result: list[Node] = []
        self.IPs_result: dict[int, IPEdge] = {}


    def _add_ip_to_htable(self, ip: int, domain: int) -> None:

        if ip in self.IPs_result:
            self.IPs_result[ip].add_domain(domain)
        else:
            edge = IPEdge(ip)
            edge.add_domain(domain)
            self.IPs_result[ip] = edge

    def _return_results(self):
        self._dispatcher.add_ips_conc(self.IPs_result)
        self._dispatcher.add_nodes_conc(self.nodes_result)

    def run(self):

        start_time = time.perf_counter()
        cnt = 0
        for item in self.dataset:
            cnt +=1

            ips: list[int] = []
            ip_strs: list[str] = item['dns']['A']

            if ip_strs is not None:
                for ip_str in ip_strs:
                    ip_int = int(ipaddress.ip_address(ip_str))
                    self._add_ip_to_htable(ip_int, self.curr_id)
                    ips.append(ip_int)

            domain = item['domain_name']
            nd = Node(self.curr_id , domain, ips, self.b, [])
            self.nodes_result.append(nd)

            self.curr_id += 1

        self.dataset.clear()
        self._return_results()

        #self._dispatcher.debug_fun____(start_time,self.curr_id - len(self.dataset))