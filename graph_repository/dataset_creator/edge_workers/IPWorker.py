from ipaddress import ip_address
from enum import Enum
from graph_repository.dataset_creator.common.Worker import Worker
from graph_repository.graph_repo_misc import add_sort_into_pipeline
from misc.Logger import MyLogger
from graph_repository.dataset_creator.common.GraphTypes import NodeTypes, EdgeTypes
from pymongo.collection import Collection
from pymongo import ASCENDING


class IPWorker(Worker):

    class Modes(Enum):
        BOTH = 0
        V4 = 1
        V6 = 2

    worker_name = 'ip'
    available_options = [
        (worker_name, 'ipv4', {'mode': Modes.V4}),
        (worker_name, 'ipv6', {'mode': Modes.V6}),
        (worker_name, f'{worker_name}_all', {'mode': Modes.BOTH})
    ]

    _project = {'_id': 0, 'domain_name': 1, 'dns.A': 1, 'dns.AAAA': 1, 'ip_data': 1, 'node_id': 1 }
    _sort = {'node_id': ASCENDING}

    _version_str = 'ip_version'
    _ip_str_str = 'ip_str'

    _node_type1 = NodeTypes.DOMAIN
    _node_type2 = NodeTypes.IP
    _edge_type = EdgeTypes.TRANSLATES

    def __init__(self, submit_callback_method, collection: Collection, ranges: list, mode: Modes = Modes.BOTH):
        super().__init__(submit_callback_method, collection, ranges, self._project)
        #add_sort_into_pipeline(self._sort, self._pipeline)
        self._mode = mode
        self._curr_ip_id = 0
        self._ip_data: dict[str, list] = {self._ip_str_str: [], self._version_str: []}
        self._ip_htab: dict[int,tuple[int,list[int]]] = {}

    def _submit_results(self) -> None:

        self._submit_callback_method(self._u,self._v,self._node_type1,self._edge_type,self._node_type2,v_data=self._ip_data)
        self._submit_callback_method(self._v,self._u,self._node_type2,self._edge_type,self._node_type1)

    def _create_edges(self) -> None:

        for ip_id, node_ids in self._ip_htab.values():
            self._u.extend(node_ids)
            self._v.extend([ip_id] * len(node_ids))

    def _parse_ips(self, ips: list, node_id: int) -> None:

        for ip in ips:
            ip_id = int(ip)

            if self._ip_htab.get(ip_id) is None:
                self._ip_htab[ip_id] = (self._curr_ip_id,[node_id])
                self._ip_data[self._ip_str_str].append(str(ip))
                self._ip_data[self._version_str].append(ip.version)
                self._curr_ip_id += 1
            else:
                self._ip_htab[ip_id][1].append(node_id)


    def _extract_domains_and_ips(self) -> None:
        cursor = self._collection.aggregate(self._pipeline, batchSize=25000)

        for doc in cursor:
            node_id = int(doc['node_id'])
            ips = get_ips_from_record(doc, self._mode)
            self._parse_ips(ips, node_id)

        cursor.close()

    def _compute(self):
        MyLogger.get_instance().log(f"IPWorker started in mode {self._mode}. Extracting domains and theirs IPs...")
        self._extract_domains_and_ips()
        MyLogger.get_instance().log("Extracted domains and theirs IPs")
        MyLogger.get_instance().log("Creating edges between Domains and IPs...")
        self._create_edges()
        MyLogger.get_instance().log("Created edges between Domains and IPs, submitting results...")
        self._submit_results()

        del self._ip_htab, self._ip_data, self._u, self._v


#========================End of class==============================================


def get_ips_from_record(doc: dict, mode: IPWorker.Modes) -> list:
    ips: list = []

    if mode == IPWorker.Modes.V4 or mode == IPWorker.Modes.BOTH:
        a_list = doc['dns'].get('A',[])
        if a_list is not None:
            ips.extend([ ip_address(ip_str) for ip_str in a_list  if ip_str != '' ])

    if mode == IPWorker.Modes.V6 or mode == IPWorker.Modes.BOTH:
        aaaa_list = doc['dns'].get('AAAA',[])
        if aaaa_list is not None:
            ips.extend([ ip_address(ip_str) for ip_str in aaaa_list if ip_str != ''])

    if doc.get('ip_data'):
        ip_data_ips = doc['ip_data']
        if ip_data_ips is not None:

            for ip_data_item in ip_data_ips:
                addr: str = ip_data_item['ip']

                if addr == '':
                    continue

                ip_addr = ip_address(addr)

                if ip_addr in ips:
                    continue

                if mode == IPWorker.Modes.BOTH:
                    ips.append(ip_address(addr))

                elif ip_addr.version == 4 and mode == IPWorker.Modes.V4:
                    ips.append(ip_address(addr))

                elif ip_addr.version == 6 and mode == IPWorker.Modes.V6:
                    ips.append(ip_address(addr))

    return ips