from typing import Any
from graph_repository.workers.common.EditWorker import EditWorker
from graph_repository.graph_main.GraphRepository import GraphRepository
from graph_repository.Neo4jDBDriver import Neo4jDBDriver, get_version_query
from graph_repository.workers.common.Enums import EditTypes
from graph_repository.workers.common.GraphTypes import NodeTypes, EdgeTypes
from graph_repository.graph_repo_misc import get_registrant_from_record
from misc.Logger import MyLogger


class RegistrantWorker(EditWorker):

    worker_name = 'registrant'
    req_callbacks = (worker_name, [EditWorker.ReqCallbacks.EDGE, EditWorker.ReqCallbacks.NODE])
    _limit = 250

    def __init__(self, domains: list[dict], version: int, nodes_submit_callback, edges_submit_callback) -> None:
        super().__init__(domains,version,RegistrantWorker._limit)
        self._nodes_submit_callback = nodes_submit_callback
        self._edges_submit_callback = edges_submit_callback

        self._registrants_to_create: list[dict[str, Any]] = []
        self._edges: list[dict] = []

    def _submit_edges(self) -> None:

        self._nodes_submit_callback(self._registrants_to_create, NodeTypes.REGISTRANT, self.worker_name, EditTypes.IGNORE_NEW)

        query_params = {
            Neo4jDBDriver.E_NODE_T1: NodeTypes.REGISTRANT,
            Neo4jDBDriver.E_NODE_T2: NodeTypes.DOMAIN,
            Neo4jDBDriver.E_OPTION: Neo4jDBDriver.EdgeCreationQueryOptions.NO_WEIGHT_REVERSE,
            Neo4jDBDriver.E_EDGE_T: EdgeTypes.REGISTERED,
            Neo4jDBDriver.E_MATCH1: "name",
            Neo4jDBDriver.E_MATCH2: "domain_name"
        }
        self._edges_submit_callback(self._edges, query_params, self.worker_name)

    @staticmethod
    def _create_index_on_reg_name(driver: Neo4jDBDriver) -> None:

        index_name = f'{NodeTypes.REGISTRANT.neo4j}_name_idx'

        query = f"""
        CREATE INDEX {index_name} 
        IF NOT EXISTS
        FOR (n: {NodeTypes.REGISTRANT.neo4j})
        ON (n.name)
        """

        driver.execute_write(query)
        driver.wait_for_index_creation([index_name])
        return

    def _find_registrants_in_graph(self, registrants: set[str]) -> None:

        driver: Neo4jDBDriver = GraphRepository.get_instance().get_neo4j_driver()
        self._create_index_on_reg_name(driver)

        query = f"""
        UNWIND $registrants AS registrant
        OPTIONAL MATCH (r: {NodeTypes.REGISTRANT.neo4j} {{name: registrant {get_version_query(self._version, False)} }})
        WITH registrant, r
        WHERE r IS NULL
        RETURN collect(r) AS missing
        """

        missing_registrants = driver.execute_read(query,registrants=list(registrants))['missing']
        len_miss_reg = len(missing_registrants)
        ids = driver.get_free_node_id(NodeTypes.REGISTRANT, len_miss_reg)

        if ids == 1:
            self._registrants_to_create.append({'name': missing_registrants[0], 'node_id': ids})
        else:
            for cnt in range(len_miss_reg):
                self._registrants_to_create.append({'name': missing_registrants[cnt], "node_id": ids[cnt]})

        return None

    def _extract_registrants(self) -> set[str]:

        registrants: set[str] = set()

        for domain in self._domains:
            domain_name = domain['domain_name']
            registrant = get_registrant_from_record(domain)

            if registrant is None:
                MyLogger.get_instance().log_debug(f"Omitting domain {domain_name} because it does not have a registrant entry!")
                continue

            self._edges.append({"name": registrant, "domain_name": domain_name})
            registrants.add(registrant)

        return registrants


    def _compute(self) -> None:
        registrants: set[str] = self._extract_registrants()
        self._find_registrants_in_graph(registrants)
        del registrants
        self._submit_edges()
