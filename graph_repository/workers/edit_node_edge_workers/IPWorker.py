from typing import Any
from graph_repository.workers.common.EditWorker import EditWorker
from graph_repository.graph_main.GraphRepository import GraphRepository
from graph_repository.Neo4jDBClient import Neo4jDBClient
from concurrent.futures import ThreadPoolExecutor
from graph_repository.workers.dataset_edge_workers.IPWorker import IPWorker as en
from graph_repository.workers.dataset_edge_workers.IPWorker import get_ips_from_record
from graph_repository.workers.common.Enums import EditTypes
from graph_repository.workers.common.GraphTypes import NodeTypes, EdgeTypes

#TODO add modes and run options
#TODO LONG TERM add dynamic node_id checking e.g. not just check max id but also check if there are free ids between

class IPWorker(EditWorker):

    worker_name = 'IPWorker'
    req_callbacks = (worker_name, [EditWorker.ReqCallbacks.NODE, EditWorker.ReqCallbacks.EDGE])
    _limit = 2000

    def __init__(self, domains: list[dict], version: int, nodes_submit_callback, edges_submit_callback):
        super().__init__(domains, version, IPWorker._limit)
        self._submit_nodes_callback = nodes_submit_callback
        self._submit_edges_callback = edges_submit_callback


        self._edges: list[dict] = []
        self._ips: list[dict] = []

        self._ip_dict: dict[str, Any] = {}


    def _submit_results(self):
        self._submit_nodes_callback(self._ips, NodeTypes.IP, self.worker_name, EditTypes.IGNORE_NEW)

        query_params = {
            Neo4jDBClient.E_EDGE_T: EdgeTypes.TRANSLATES,
            Neo4jDBClient.E_NODE_T1: NodeTypes.DOMAIN,
            Neo4jDBClient.E_NODE_T2: NodeTypes.IP,
            Neo4jDBClient.E_OPTION: Neo4jDBClient.EdgeCreationQueryOptions.NO_WEIGHT_REVERSE,
            Neo4jDBClient.E_MATCH1: "domain_name",
            Neo4jDBClient.E_MATCH2: "ip_str"
        }
        self._submit_edges_callback(self._edges, query_params, self.worker_name)

    def _create_pairs(self, domain_name: str, ips: list) -> None:
        for ip in ips:
            self._edges.append({'ip_str': str(ip), 'domain_name': domain_name})


    def _create_ip_nodes(self):
        driver: Neo4jDBClient = GraphRepository.get_instance().get_neo4j_driver()

        query=f"""
        UNWIND $rows AS value
        OPTIONAL MATCH (n:{NodeTypes.IP.value} {{ip_str: value {self._get_version_query(False)}}}
        WITH value, n
        WHERE n IS NULL
        RETURN value AS missing
        """

        result = driver.execute_read(query, rows=list(self._ip_dict.keys()))
        non_existent_ips = [r['missing'] for r in result]

        ip_max_id = driver.get_max_id_of_node_type(NodeTypes.IP)
        curr_ip_id = ip_max_id + 1


        for ip in non_existent_ips:
            ip_address = self._ip_dict[str(ip)]
            self._ips.append({'ip_str': str(ip), 'ip_version': ip_address.version, 'node_id': curr_ip_id})
            curr_ip_id += 1

        driver.close()

    def _compute(self):

        for domain in self._domains:
            domain_name = str(domain['domain_name'])
            ips = get_ips_from_record(domain, en.Modes.BOTH)

            for ip in ips:
                self._ip_dict[str(ip)] = ip
                self._create_pairs( domain_name, list(self._ip_dict.keys()))


        self._create_ip_nodes()
        self._submit_results()
