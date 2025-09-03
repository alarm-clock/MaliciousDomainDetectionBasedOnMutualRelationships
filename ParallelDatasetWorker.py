import threading
from Node import Node
from IPEdge import IPEdge
import ipaddress

class ParallelDatasetWorker(threading.Thread):

    def __init__(self, dispatcher, w_id, json_data, cnt, b):
        super().__init__()
        self._dispatcher = dispatcher
        self._w_id = w_id
        fcd = json_data[(w_id * cnt):]
        self.dataset = fcd[:(((w_id + 1) * cnt) - 1)]
        self.max = cnt
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


    def run(self):

        for cnt in range(len(self.dataset)):

            item = self.dataset[cnt]
            domain_id = (self._w_id * self.max) + cnt

            ips: list[int] = []
            ip_strs: list[str] = item['dns']['A']

            if ip_strs is not None:
                for ip_str in ip_strs:
                    ip_int = int(ipaddress.ip_address(ip_str))
                    self._add_ip_to_htable(ip_int, domain_id)
                    ips.append(ip_int)

            domain = item['domain_name']
            nd = Node(domain_id , domain, ips, self.b, [])
            self.nodes_result.append(nd)