import copy
from graph_repository.workers.common.EditWorker import EditWorker
from graph_repository.workers.common.GraphTypes import NodeTypes, EdgeTypes, D_PARENT_DOMAINS, D_NAME, D_DEPTH
from graph_repository.Neo4jDBDriver import Neo4jDBDriver, get_version_query
from graph_repository.graph_main.GraphRepository import GraphRepository
from graph_repository.graph_repo_misc import get_domains_parent_domains, domain_depth
from graph_repository.workers.common.Enums import EditTypes
from misc.Pair import replace
from typing import Any, Iterable

class SubdomainWorker(EditWorker):

    worker_name = 'subdomain'
    req_callbacks = (worker_name, [EditWorker.ReqCallbacks.EDGE, EditWorker.ReqCallbacks.NODE])
    _limit = 250

    _index_query = f"""
        CREATE INDEX parentDomainsIndex 
        IF NOT EXISTS
        FOR (d: {NodeTypes.DOMAIN.neo4j})
        ON EACH [d.{D_PARENT_DOMAINS}];
        """

    _NODE_TYPE_POS = 0
    _SUBDOMAINS_POS = 1
    _SUBDOMAINS_FROM_DSET = 2

    def __init__(self, domains: list[dict], version: int, edges_submit_callback, nodes_submit_callback):
        super().__init__(domains, version, SubdomainWorker._limit)
        self._edge_submit_callback = edges_submit_callback
        self._nodes_submit_callback = nodes_submit_callback

        #domain_name, dict[parent_domain_n, nt in graph]
        self._domain_data: dict[str, dict[str, str]] = {}

        self._domains_in_dset = set([domain_dict['domain_name'] for domain_dict in self._domains])
        #domain_name,  tuple[node type, subdomains, domains from dataset that are subdomains
        self._subs: dict[str, tuple[ str | None, set[str], list[str]]] = {}

        self._dummies_for_creation: list[dict[str, Any]] = []


        self._d_d_sub_edges: list[dict[str, str]] = []
        self._d_dum_sub_edges: list[dict[str, str]] = []
        self._dum_dum_sub_edges: list[dict[str, str]] = []


    def _create_edges_between_d_and_sub_ds(self, parent_domain: str, parent_domain_n_t: str | None, sub_ds: Iterable, ds_from_dset: bool) -> None:

        for subdomain in sub_ds:

            if ds_from_dset:
                sub_n_t = NodeTypes.DOMAIN.neo4j
            else:
                sub_n_t = self._subs[subdomain][self._NODE_TYPE_POS]

            if parent_domain_n_t == NodeTypes.DOMAIN.neo4j and sub_n_t == NodeTypes.DOMAIN.neo4j:
                self._d_d_sub_edges.append({"u": parent_domain, "v": subdomain})
            elif parent_domain_n_t == NodeTypes.DOMAIN.neo4j and sub_n_t == NodeTypes.DUMMY_DOMAIN.neo4j:
                self._d_dum_sub_edges.append({"u": parent_domain, "v": subdomain})
            elif parent_domain_n_t == NodeTypes.DUMMY_DOMAIN.neo4j and sub_n_t == NodeTypes.DOMAIN.neo4j:
                self._d_dum_sub_edges.append({"u": subdomain, "v": parent_domain})
            else:
                self._dum_dum_sub_edges.append({'u': parent_domain, 'v': subdomain})


    def _create_sub_edges(self) -> None:

        self._nodes_submit_callback(self._dummies_for_creation, NodeTypes.DUMMY_DOMAIN, self.worker_name, EditTypes.IGNORE_EXISTING)

        for parent_domain, data_tuple in self._subs.items():
            parent_n_t, sub_ds, sub_ds_from_dset = data_tuple
            #print(data_tuple)
            self._create_edges_between_d_and_sub_ds(parent_domain, parent_n_t, sub_ds, False)
            self._create_edges_between_d_and_sub_ds(parent_domain, parent_n_t, sub_ds_from_dset, True)


        query_option = {
            Neo4jDBDriver.E_NODE_T1: NodeTypes.DOMAIN,
            Neo4jDBDriver.E_NODE_T2: NodeTypes.DOMAIN,
            Neo4jDBDriver.E_OPTION: Neo4jDBDriver.EdgeCreationQueryOptions.NO_WEIGHT_REVERSE,
            Neo4jDBDriver.E_EDGE_T: EdgeTypes.SUBDOMAIN,
            Neo4jDBDriver.E_MATCH1: D_NAME,
            Neo4jDBDriver.E_MATCH2: D_NAME,
        }
        self._edge_submit_callback(self._d_d_sub_edges, query_option, self.worker_name + "_d_d")

        query_option_du_d = copy.deepcopy(query_option)
        query_option_du_d[Neo4jDBDriver.E_NODE_T2] = NodeTypes.DUMMY_DOMAIN
        self._edge_submit_callback(self._d_dum_sub_edges, query_option_du_d, self.worker_name + "_d_dum")

        query_option_du_du = copy.deepcopy(query_option_du_d)
        query_option_du_du[Neo4jDBDriver.E_NODE_T1] = NodeTypes.DUMMY_DOMAIN
        self._edge_submit_callback(self._dum_dum_sub_edges, query_option_du_du, self.worker_name + "_dum_dum")
        return

    def _find_related_domains_and_data(self) -> None:

        driver = GraphRepository.get_instance().get_neo4j_driver()
        #self._create_index(driver)

        find_related_domains_query = f"""
        UNWIND $parent_domains AS parent_domain    
        
        OPTIONAL MATCH (n: {NodeTypes.DUMMY_DOMAIN.neo4j} {{ {D_NAME}: parent_domain {get_version_query(self._version, False)} }}) 
        WITH n, parent_domain
        OPTIONAL MATCH (m: {NodeTypes.DOMAIN.neo4j} {{ {D_NAME}: parent_domain {get_version_query(self._version, False)} }})
        WHERE n IS NULL
        WITH coalesce(n, m) AS parent_in_graph, parent_domain
        WITH parent_domain, CASE 
                WHEN parent_in_graph IS NULL THEN NULL
                ELSE labels(parent_in_graph)[0]  
            END AS n_t
        
        RETURN parent_domain AS d, n_t
        """

        #domains_and_parents: list[dict[str, str | list[str]]] = []
        for domain_dict in self._domains:

            domain_name = str(domain_dict['domain_name'])
            parent_domains = get_domains_parent_domains(domain_name)
            #domains_and_parents.append({'domain_name': domain_name, 'parent_domains': parent_domains})

            for cnt, parent_domain in enumerate(parent_domains):

                if parent_domain not in self._subs:
                    self._subs[parent_domain] = (
                        None if parent_domain not in self._domains_in_dset else NodeTypes.DOMAIN.neo4j,
                        set(parent_domains[:cnt]),
                        [domain_name]
                    )
                else:
                    self._subs[parent_domain][self._SUBDOMAINS_POS].update(parent_domains[:cnt])
                    self._subs[parent_domain][self._SUBDOMAINS_FROM_DSET].append(domain_name)

        domains_and_related_domains = driver.execute_read(find_related_domains_query, parent_domains=list(self._subs.keys()))

        for row in domains_and_related_domains:

            if row['d'] not in self._domains_in_dset:
                n_t = row['n_t']

                if n_t is None:
                    n_t = NodeTypes.DUMMY_DOMAIN.neo4j
                    self._dummies_for_creation.append({
                        D_NAME: row['d'],
                        D_DEPTH: domain_depth(row['d']),
                        D_PARENT_DOMAINS: get_domains_parent_domains(row['d'])
                    })
                self._subs[row['d']] = replace(self._subs[row['d']],self._NODE_TYPE_POS,n_t)



        del domains_and_related_domains
        driver.close()
        return

    def _create_index(self, driver: Neo4jDBDriver):
        driver.execute_write(self._index_query)

    def _compute(self):
        self._find_related_domains_and_data()
        self._create_sub_edges()
