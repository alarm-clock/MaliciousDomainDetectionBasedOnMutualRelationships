from typing import Any
from graph_repository.workers.common.EditWorker import EditWorker
from graph_repository.graph_main.GraphRepository import GraphRepository
from graph_repository.Neo4jDBClient import Neo4jDBClient, get_version_query
from graph_repository.workers.common.Misc import IPModes, get_ips_from_record
from graph_repository.workers.common.Enums import EditTypes
from graph_repository.workers.common.GraphTypes import NodeTypes, EdgeTypes


#TODO add modes and run options

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

    def _submit_results(self) -> None:
        self._submit_nodes_callback(self._ips, NodeTypes.IP, self.worker_name, EditTypes.IGNORE_NEW)

        query_params = {
            Neo4jDBClient.E_EDGE_T: EdgeTypes.TRANSLATES,
            Neo4jDBClient.E_NODE_T1: NodeTypes.IP,
            Neo4jDBClient.E_NODE_T2: NodeTypes.DOMAIN,
            Neo4jDBClient.E_OPTION: Neo4jDBClient.EdgeCreationQueryOptions.NO_WEIGHT_REVERSE,
            Neo4jDBClient.E_MATCH1: "ip_str",
            Neo4jDBClient.E_MATCH2: "domain_name"
        }
        self._submit_edges_callback(self._edges, query_params, self.worker_name)

    def _create_pairs(self, domain_name: str, ips: list) -> None:
        for ip in ips:
            self._edges.append({'u': str(ip), 'v': domain_name})

    def _create_index_on_ip_str(self, driver: Neo4jDBClient) -> None:

        driver.execute_write(f"""
        CREATE INDEX {NodeTypes.IP.value}_ip_str_idx
        IF NOT EXISTS
        FOR (n: {NodeTypes.IP.value})
        ON (n.ip_str);
        """)

        driver.wait_for_index_creation([f'{NodeTypes.IP.value}_ip_str_idx'])

    def _create_ip_nodes(self) -> None:
        driver: Neo4jDBClient = GraphRepository.get_instance().get_neo4j_driver()

        self._create_index_on_ip_str(driver)

        query = f"""
        UNWIND $rows AS ip
        OPTIONAL MATCH (n:{NodeTypes.IP.value} {{ip_str: ip {get_version_query(self._version,False)}}})
        WITH ip, n
        WHERE n IS NULL
        RETURN collect(ip) AS missing
        """

        non_existent_ips = driver.execute_read(query, rows=list(self._ip_dict.keys()))[0]['missing']
        available_ids = driver.get_free_node_id(NodeTypes.IP, len(non_existent_ips))

        for cnt, ip in enumerate(non_existent_ips):
            ip_address = self._ip_dict[str(ip)]
            self._ips.append({'ip_str': str(ip), 'ip_version': ip_address.version, 'node_id': available_ids[cnt]})

        driver.close()

    def _compute(self):

        for domain in self._domains:
            domain_name = str(domain['domain_name'])
            ips = get_ips_from_record(domain, IPModes.BOTH)

            ip_strs = []
            for ip in ips:
                ip_str = str(ip)
                self._ip_dict[ip_str] = ip
                ip_strs.append(ip_str)

            self._create_pairs(domain_name, ip_strs)

        self._create_ip_nodes()
        self._submit_results()
