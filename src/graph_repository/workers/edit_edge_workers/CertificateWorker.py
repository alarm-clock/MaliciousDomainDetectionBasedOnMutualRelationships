from graph_repository.Neo4jDBDriver import Neo4jDBDriver, get_version_query
from graph_repository.graph_main.GraphRepository import GraphRepository
from graph_repository.workers.common.EditWorker import EditWorker
from graph_repository.workers.common.Enums import EditTypes
from graph_repository.workers.common.GraphTypes import NodeTypes, EdgeTypes, D_NAME, CERT_HASH, CERT_CN, CERT_ORG, CERT_SUBJ_K_ID, \
    CERT_BEFORE, CERT_AFTER, NODE_ID
from graph_repository.graph_repo_misc import parse_cert
from misc.Logger import MyLogger


class CertificateWorker(EditWorker):

    worker_name = 'certificate'
    req_callbacks = (worker_name, [EditWorker.ReqCallbacks.EDGE, EditWorker.ReqCallbacks.NODE])
    _limit = 250

    def __init__(self, domains: list[dict], version: int, nodes_submit_callback, edges_submit_callback) -> None:
        super().__init__(domains,version,CertificateWorker._limit)
        self._nodes_submit_callback = nodes_submit_callback
        self._edges_submit_callback = edges_submit_callback

        self._certs_for_creation = []


    def _submit_edges(self) -> None:
        self._nodes_submit_callback(self._certs_for_creation, NodeTypes.CERTIFICATE, self.worker_name, EditTypes.IGNORE_NEW)

        query_params = {
            Neo4jDBDriver.E_NODE_T1: NodeTypes.DOMAIN,
            Neo4jDBDriver.E_NODE_T2: NodeTypes.CERTIFICATE,
            Neo4jDBDriver.E_OPTION: Neo4jDBDriver.EdgeCreationQueryOptions.NO_WEIGHT_REVERSE,
            Neo4jDBDriver.E_EDGE_T: EdgeTypes.HAS_CERTIFICATE,
            Neo4jDBDriver.E_MATCH1: D_NAME,
            Neo4jDBDriver.E_MATCH2: CERT_HASH
        }
        self._edges_submit_callback(self._edges, query_params, self.worker_name)

    @staticmethod
    def _create_index_on_cert_hash(driver: Neo4jDBDriver) -> None:

        index_name = f'{NodeTypes.CERTIFICATE.neo4j}_hash_idx'

        query = f"""
            CREATE INDEX {index_name}
            IF NOT EXISTS
            FOR (n: {NodeTypes.CERTIFICATE.neo4j})
            ON (n.{CERT_HASH})
        """
        driver.execute_write(query)
        driver.wait_for_index_creation([index_name])
        return

    def _find_certificates_in_graph(self, certificates: dict[str, tuple[str, str, str, float, float]]) -> None:

        driver: Neo4jDBDriver = GraphRepository.get_instance().get_neo4j_driver()
        self._create_index_on_cert_hash(driver)

        query = f"""
            UNWIND $certificates AS cert
            OPTIONAL MATCH (n: {NodeTypes.CERTIFICATE.neo4j}  {{ {CERT_HASH}: cert {get_version_query(self._version, False)} }} )
            WITH cert, n
            WHERE n IS NULL
            RETURN cert AS missing
        """
        missing = driver.execute_read(query, certificates=list(certificates))['missing']
        n_missing = len(missing)
        ids = driver.get_free_node_id(NodeTypes.CERTIFICATE, n_missing)

        if n_missing == 1:
            cn, org, subj_key_id, start, end = certificates[missing[0]]
            self._certs_for_creation.append({
                CERT_CN: cn,
                CERT_HASH: missing[0],
                CERT_ORG: org,
                CERT_SUBJ_K_ID: subj_key_id,
                CERT_BEFORE: start,
                CERT_AFTER: end,
                NODE_ID: ids
            })
        else:
            for cnt, missing_hash in enumerate(missing):
                cn, org, subj_key_id, start, end = certificates[missing_hash]
                self._certs_for_creation.append({
                    CERT_CN: cn,
                    CERT_HASH: missing_hash,
                    CERT_ORG: org,
                    CERT_SUBJ_K_ID: subj_key_id,
                    CERT_BEFORE: start,
                    CERT_AFTER: end,
                    NODE_ID: ids[cnt]
                })

        return

    def _extract_certificates(self) -> dict[str, tuple[str, str, str, float, float]]:

        certificates = {}

        for domain in self._domains:

            domain_name = domain['domain_name']
            if domain.get('tls') is None:
                MyLogger.get_instance().log_debug(
                    f'Omitting domain {domain_name} because it does not have a TLS entry'
                )
                continue

            hash, ca, data = parse_cert(domain['tls'])
            certificates[hash] = data
            self._edges.append({D_NAME: domain_name, CERT_HASH: hash})

        return certificates

    def _compute(self):
        certificates = self._extract_certificates()
        self._find_certificates_in_graph(certificates)
        del certificates