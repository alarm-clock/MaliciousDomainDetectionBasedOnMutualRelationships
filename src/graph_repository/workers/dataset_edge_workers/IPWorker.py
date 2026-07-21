from graph_repository.workers.common.Misc import IPModes, get_ips_from_record
from graph_repository.workers.common.DatasetWorker import DatasetWorker
from misc.Logger import MyLogger
from graph_repository.workers.common.GraphTypes import NodeTypes, EdgeTypes, IP_STR, IP_VERSION
from pymongo.collection import Collection
from pymongo import ASCENDING


class IPWorker(DatasetWorker):

    worker_name = 'ip'
    available_options = [
        (worker_name, 'ipv4', {'mode': IPModes.V4}),
        (worker_name, 'ipv6', {'mode': IPModes.V6}),
        (worker_name, f'{worker_name}_all', {'mode': IPModes.BOTH})
    ]

    _project = {'_id': 0, 'domain_name': 1, 'dns.A': 1, 'dns.AAAA': 1, 'ip_data': 1, 'node_id': 1 }
    _sort = {'node_id': ASCENDING}

    _node_type1 = NodeTypes.DOMAIN
    _node_type2 = NodeTypes.IP
    _edge_type = EdgeTypes.TRANSLATES

    def __init__(self, submit_callback_method, collection: Collection, ranges: list, mode: IPModes = IPModes.BOTH):
        super().__init__(submit_callback_method, collection, ranges, self._project, [NodeTypes.IP])
        #add_sort_into_pipeline(self._sort, self._pipeline)
        self._mode = mode
        self._curr_ip_id = 0
        self._ip_htab: dict[int,tuple[int,list[int]]] = {}

    def _submit_results(self) -> None:

        self._submit_callback_method(self._u,self._v,self._node_type1,self._edge_type,self._node_type2,v_data=self._n_data.get_n_data(NodeTypes.IP))
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
                self._n_data.store_n_data(NodeTypes.IP, **{IP_STR: str(ip), IP_VERSION: ip.version})
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
        MyLogger.get_instance().log("Submitted all IP edges and nodes")

        del self._ip_htab, self._u, self._v