import threading
from dataset_parsers.raw.Node import Node
from dataset_parsers.raw.IPEdge import IPEdge
from misc.helper_func import get_ips_from_record
from misc.Logger import MyLogger
import ipaddress


class ParallelDatasetWorker(threading.Thread):

    def __init__(self, dispatcher, start_id: int, json_data: list, b: bool, has_node_id: bool = False):
        super().__init__()
        self._dispatcher = dispatcher
        self._s = start_id
        self.curr_id = start_id
        self.dataset = json_data
        self._has_node_id = has_node_id
        self.b = b

        self.nodes_result: list[Node] = []
        self.IPs_result: dict[int, IPEdge] = {}
        self.domains: list[tuple[int, str]] = []

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
        self._dispatcher.add_domains_conc(self.domains)

        MyLogger.get_instance().log(f"Dataset worker with start_id {self._s} has finished...")

        self.IPs_result.clear()
        self.nodes_result.clear()
        self.domains.clear()

    def run(self):
        MyLogger.get_instance().log(f"Dataset worker with start_id {self._s} has started...")

        for item in self.dataset:

            ips: list[int] = []
            ip_strs: list[str] = get_ips_from_record(item)

            if ip_strs is not None:
                for ip_str in ip_strs:
                    ip_int = int(ipaddress.ip_address(ip_str))
                    self._add_ip_to_htable(ip_int, self.curr_id)
                    ips.append(ip_int)

            domain = item['domain_name']
            node_id = item['node_id'] if self._has_node_id else self.curr_id
            self.domains.append((node_id, domain))
            nd = Node(node_id , domain, ips, self.b, [])
            self.nodes_result.append(nd)

            self.curr_id += 1

        self.dataset.clear()
        self._return_results()

