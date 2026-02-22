import copy

from graph_repository.workers.common.EditWorker import EditWorker
from graph_repository.workers.common.GraphTypes import NodeTypes, EdgeTypes
from graph_repository.graph_main.GraphRepository import GraphRepository
from graph_repository.Neo4jDBClient import Neo4jDBClient
from misc.Logger import MyLogger
from functools import partial
from graph_repository.workers.common.Enums import CallbackWhen, EditTypes
from enum import Enum

class CNAMEWorker(EditWorker):

    worker_name = 'CNAMEWorker'
    req_callbacks = (worker_name, EditWorker.ReqCallbacks.ALL)
    _limit = 5000

    class NdTypes(Enum):
        DOMAIN  = 0
        DUMMY = 1

    def __init__(self, domains: list[dict], version: int, nodes_submit_callback, edges_submit_callback, callbacks_submit_callback):
        super().__init__(domains, version, CNAMEWorker._limit)
        self._edges_submit_callback = edges_submit_callback
        self._nodes_submit_callback = nodes_submit_callback
        self._callbacks_submit_callback = callbacks_submit_callback

        self._domain_names: list[str] = []
        self._domains_for_replacing: list[str] = []
        self._parsed_domains: list[ tuple[str, CNAMEWorker.NdTypes, list[str]]] = []
        self._create_domains: list[str] = []
       # self._cname_normal_dict: dict[str, tuple[CNAMEWorker.NdTypes, list[str]]] = {}
        self._dummy_nodes: list[dict] = []
        self._d_d_edges: list[dict] = []
        self._du_d_edges: list[dict] = []

    #extract cnames, match them with domains that are in edit
    #find cnames between normal domains in graph
    #find cnames between dummy domains in graph
    #check if any domain is not dummy domain in the graph, if yes, replace
    #create new dummies

    @staticmethod
    def _replace_dummies(domains_for_replacing: list[str], version_query: str) -> None:
        #this will run after normal nodes equivalents of dummies exists
        #they will have same domain name but node_id in parameter is for the du_domains

        replace_query = f"""
        
        UNWIND $domains as d
        
        MATCH (old: {NodeTypes.DUMMY_DOMAIN.value} {{domain_name: d {version_query}}})
        MATCH (new: {NodeTypes.DOMAIN.value} {{domain_name: d {version_query}}})
        WITH old, new
        MATCH (old)-[r:{EdgeTypes.CNAME.value}->(other)
        WITH old, new, r, other
            CASE WHEN startNode(r) = old THEN new ELSE other END AS startNode
            CASE WHEN endNode(r) = old THEN new ELSE other END AS endNode
        
        CREATE (startNode)-[newR: TYPE(r)]->(endNode)
        SET newR = PROPERTIES(r)
        DELETE r
        
        WITH old
        DETACH DELETE old
        """

        driver = GraphRepository.get_instance().get_neo4j_driver()
        driver.execute_write(replace_query, rows=domains_for_replacing)
        driver.close()
        return

    def _submit(self):

        replace_dummies_callback = partial(self._replace_dummies, self._domains_for_replacing, self._get_version_query(False))
        self._callbacks_submit_callback(replace_dummies_callback, CallbackWhen.BETWEEN_NODES_EDGES, self.worker_name)
        self._nodes_submit_callback(self._dummy_nodes, NodeTypes.DUMMY_DOMAIN, self.worker_name, EditTypes.IGNORE_NEW)

        query_option = {
            Neo4jDBClient.E_NODE_T1: NodeTypes.DOMAIN,
            Neo4jDBClient.E_NODE_T2: NodeTypes.DOMAIN,
            Neo4jDBClient.E_OPTION: Neo4jDBClient.EdgeCreationQueryOptions.NO_WEIGHT_REVERSE,
            Neo4jDBClient.E_EDGE_T: EdgeTypes.CNAME,
            Neo4jDBClient.E_MATCH1: "domain_name",
            Neo4jDBClient.E_MATCH2: "domain_name"
        }

        self._edges_submit_callback(self._d_d_edges, query_option, self.worker_name)

        query_option2 = copy.deepcopy(query_option)
        query_option2[Neo4jDBClient.E_NODE_T1] = NodeTypes.DUMMY_DOMAIN

        self._edges_submit_callback(self._du_d_edges, query_option2, self.worker_name)

    def _create_dummy_domains(self) -> None:
        driver: Neo4jDBClient = GraphRepository.get_instance().get_neo4j_driver()
        max_id = driver.get_max_id_of_node_type(NodeTypes.DUMMY_DOMAIN)
        driver.close()

        curr_id = max_id + 1
        for domain_name in self._create_domains:
            self._dummy_nodes.append({'node_id':curr_id, 'domain_name':domain_name})
            curr_id += 1

    def _create_edges(self):

        self._create_dummy_domains()

        for cname_domain, n_t, domains in self._parsed_domains:
            for domain_name in domains:
                if n_t == CNAMEWorker.NdTypes.DOMAIN:
                    self._d_d_edges.append({'u':cname_domain, 'v':domain_name})
                else:
                    self._du_d_edges.append({'u':cname_domain, 'v':domain_name})


    def _find_cnames_in_graph(self, cname_normal_dict: dict[str, list[str]]) -> None:

        driver: Neo4jDBClient = GraphRepository.get_instance().get_neo4j_driver()

        find_cnames_in_domains = f"""
        UNWIND $rows AS cname
        OPTIONAL MATCH (n: {NodeTypes.DOMAIN.value} {{domain_name: cname {self._get_version_query(False)}}})
        OPTIONAL MATCH (m: {NodeTypes.DUMMY_DOMAIN.value} {{domain_name: cname {self._get_version_query(False)}}})  
        RETURN cname, n AS domain, m AS dummy      
        """

        result = driver.execute_read(find_cnames_in_domains, rows=list(cname_normal_dict.keys()))

        for cname_domain in result:
            cname_name = cname_domain['cname']
            if cname_domain['domain'] is None and cname_domain['dummy'] is None:
                self._create_domains.append(cname_name)
                self._parsed_domains.append((cname_name, CNAMEWorker.NdTypes.DUMMY, cname_normal_dict[cname_name]))
                #replace(cname_normal_dict[cname_name],0,self.NdTypes.CREATE)
            elif cname_domain['domain'] is None:
                self._parsed_domains.append((cname_name, CNAMEWorker.NdTypes.DUMMY, cname_normal_dict[cname_name]))
                #replace(cname_normal_dict[cname_name],0,self.NdTypes.DOMAIN)
            elif cname_domain['dummy'] is None:
                self._parsed_domains.append((cname_name, CNAMEWorker.NdTypes.DOMAIN, cname_normal_dict[cname_name]))
                #replace(self._cname_normal_dict[cname_name],0,self.NdTypes.DUMMY)


        find_if_domain_is_dummy_in_graph = f"""
        UNWIND $rows AS domain
        OPTIONAL MATCH(n: {NodeTypes.DUMMY_DOMAIN.value} {{domain_name: domain {self._get_version_query(False)}}})
        WITH n, domain
        WHERE n IS NOT NULL
        RETURN domain AS domain_name
        """

        result = driver.execute_read(find_if_domain_is_dummy_in_graph, rows=self._domain_names)

        for regular_domain in result:
            domain_name = regular_domain['domain_name']
            self._domains_for_replacing.append(domain_name)

        driver.close()
        del cname_normal_dict


    def _extract_cnames(self) -> dict[str, list[str]]:

        cname_normal_dict: dict[str, list[str]] = {}

        for domain in self._domains:

            try:
                cname_domain = domain['dns']['CNAME']['value']
            except KeyError:
                try:
                    cname_domain = domain['dns']['CNAME']
                except KeyError:
                    continue

            domain_name = str(domain['domain_name'])
            self._domain_names.append(domain_name)

            if cname_normal_dict.get(cname_domain) is None:
                cname_normal_dict[cname_domain] = [domain_name]
            else:
                cname_normal_dict[cname_domain].append(domain_name)

        return cname_normal_dict

    def _compute(self) -> None:

        cname_normal_dict = self._extract_cnames()
        self._find_cnames_in_graph(cname_normal_dict)
        self._create_edges()
        self._submit()
