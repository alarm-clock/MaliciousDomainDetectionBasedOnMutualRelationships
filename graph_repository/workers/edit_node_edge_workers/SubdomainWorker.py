import pygtrie
from graph_repository.workers.common.EditWorker import EditWorker
from graph_repository.workers.common.GraphTypes import NodeTypes, EdgeTypes
from graph_repository.Neo4jDBClient import Neo4jDBClient, get_version_query
from graph_repository.graph_main.GraphRepository import GraphRepository
from graph_repository.graph_repo_misc import get_domains_parent_domains, reverse_domain, calc_jaccard, domain_depth
from graph_repository.workers.common.Enums import EditTypes
from misc.Pair import replace
from typing import Any, Iterable

class SubdomainWorker(EditWorker):

    worker_name = 'subdomain'
    req_callbacks = (worker_name, [EditWorker.ReqCallbacks.EDGE])
    _limit = 5000

    _index_query = f"""
        CREATE INDEX parentDomainsIndex 
        IF NOT EXISTS
        FOR (d: {NodeTypes.DOMAIN.value})
        ON EACH [d.parent_domains];
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
                sub_n_t = NodeTypes.DOMAIN.value
            else:
                sub_n_t = self._subs[subdomain][self._NODE_TYPE_POS]

            if parent_domain_n_t == NodeTypes.DOMAIN.value and sub_n_t == NodeTypes.DOMAIN.value:
                self._d_d_sub_edges.append({"u": parent_domain, "v": subdomain})
            elif parent_domain_n_t == NodeTypes.DOMAIN.value and sub_n_t == NodeTypes.DUMMY_DOMAIN.value:
                self._d_dum_sub_edges.append({"u": parent_domain, "v": subdomain})
            elif parent_domain_n_t == NodeTypes.DUMMY_DOMAIN and sub_n_t == NodeTypes.DOMAIN.value:
                self._d_dum_sub_edges.append({"u": subdomain, "v": parent_domain})
            else:
                self._dum_dum_sub_edges.append({'u': parent_domain, 'v': subdomain})


    def _create_sub_edges(self) -> None:

        self._nodes_submit_callback(self._dummies_for_creation, NodeTypes.DUMMY_DOMAIN, self.worker_name, EditTypes.IGNORE_EXISTING)

        for parent_domain, data_tuple in self._subs.items():
            parent_n_t, sub_ds, sub_ds_from_dset = data_tuple
            self._create_edges_between_d_and_sub_ds(parent_domain, parent_n_t, sub_ds, False)
            self._create_edges_between_d_and_sub_ds(parent_domain, parent_n_t, sub_ds_from_dset, True)


        query_option = {
            Neo4jDBClient.E_NODE_T1: NodeTypes.DOMAIN,
            Neo4jDBClient.E_NODE_T2: NodeTypes.DOMAIN,
            Neo4jDBClient.E_OPTION: Neo4jDBClient.EdgeCreationQueryOptions.NO_WEIGHT_REVERSE,
            Neo4jDBClient.E_EDGE_T: EdgeTypes.SUBDOMAIN,
            Neo4jDBClient.E_MATCH1: "domain_name",
            Neo4jDBClient.E_MATCH2: "domain_name",
        }
        self._edge_submit_callback(self._d_d_sub_edges, query_option, self.worker_name + "_d_d")

        query_option[Neo4jDBClient.E_NODE_T2] = NodeTypes.DUMMY_DOMAIN
        self._edge_submit_callback(self._d_dum_sub_edges, query_option, self.worker_name + "_d_dum")

        query_option[Neo4jDBClient.E_NODE_T1] = NodeTypes.DUMMY_DOMAIN
        self._edge_submit_callback(self._dum_dum_sub_edges, query_option, self.worker_name + "_dum_dum")
        return

    def _find_related_domains_and_data(self) -> None:

        driver = GraphRepository.get_instance().get_neo4j_driver()
        #TODO CHECK IF I NEED TO CREATE INDEX FOR THIS OR IF IT IS ALREADY CREATED ELSEWHERE
        #self._create_index(driver)

        find_related_domains_query = f"""
        UNWIND $parent_domains AS parent_domain    
        
        OPTIONAL MATCH (n: {NodeTypes.DUMMY_DOMAIN.value} {{ domain_name: parent_domain {get_version_query(self._version, False)} }}) 
        WITH n, parent_domain
        OPTIONAL MATCH (m: {NodeTypes.DOMAIN.value} {{ domain_name: parent_domain {get_version_query(self._version, False)} }})
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
                        None if parent_domain not in self._domains_in_dset else NodeTypes.DOMAIN.value,
                        set(parent_domains[:cnt]),
                        []
                    )
                else:
                    self._subs[parent_domain][self._SUBDOMAINS_POS] |= parent_domains[:cnt]
                    self._subs[parent_domain][self._SUBDOMAINS_FROM_DSET].append(domain_name)

        domains_and_related_domains = driver.execute_read(find_related_domains_query, parent_tuples=list(self._subs.keys()))

        for row in domains_and_related_domains:
            #self._domain_data[row["domain_name"]] = row['parents_in_graph']
            if row['d'] not in self._domains_in_dset:
                n_t = row['n_t']

                if n_t is None:
                    n_t = NodeTypes.DUMMY_DOMAIN.value
                    self._dummies_for_creation.append({
                        "domain_name": row['d'],
                        "depth": domain_depth(row['d']),
                        "parent_domains": get_domains_parent_domains(row['d'])
                    })

                replace(self._subs[row['d']],self._NODE_TYPE_POS,n_t)


        del domains_and_related_domains
        driver.close()
        return

    def _create_index(self, driver: Neo4jDBClient):
        driver.execute_write(self._index_query)

    def _compute(self):
        self._find_related_domains_and_data()
        #self._parse_new_domains()
        self._create_sub_edges()
        #self._create_sub_of_edges()


#could still be useful for subdomain_of edges creation If I decide to implement it outside of graph
f"""
        UNWIND $domain_tuples AS domain 

        CALL (domain){{
            UNWIND domain.parent_domains AS parent_domain
            MATCH (d: {NodeTypes.DOMAIN.value})
            WHERE parent_domain IN d.parent_domains AND d.domain_name <> domain.domain_name AND d.graph_version = {9}
            WITH DISTINCT d
            RETURN collect({{
                match_domain_name: d.domain_name,
                parent_domains: d.parent_domains
            }}) AS matches
        }}
        CALL (domain){{
            UNWIND domain.parent_domains AS parent_domain
            OPTIONAL MATCH (d: {NodeTypes.DOMAIN.value} {{domain_name: parent_domain {get_version_query(9, False)}}})
            RETURN collect(d.domain_name) AS parent_domains_in_graph
        }}
        CALL (domain){{ 
            MATCH (d: {NodeTypes.DOMAIN.value})
            WHERE domain.domain_name IN d.parent_domains AND d.graph_version = {9}
            RETURN collect(d.domain_name) AS subdomains
        }}

        RETURN domain.domain_name AS domain_name, 
               domain.parent_domains AS parent_domains, 
               matches, 
               parent_domains_in_graph, 
               subdomains
        """



"""
    def _put_domain_in_trie(self, trie: pygtrie.StringTrie, domain: str) -> None:

        reversed_domain = reverse_domain(domain)

        if trie.has_node(reversed_domain):

            children = list(trie.keys(prefix=reversed_domain))

            if reversed_domain in children:
                children.remove(reversed_domain)

            children = [reverse_domain(child) for child in children if reverse_domain(child) in self._domain_data]

            for child in children:
                #add parent domain for each child as domain that is in the graph
                self._domain_data[child][domain] = NodeTypes.DOMAIN.value

        parent, _ = trie.longest_prefix(reverse_domain)

        if parent is not None:
            if parent == reversed_domain:
                return

            self._domain_data[domain][parent] = NodeTypes.DOMAIN.value

        trie[reversed_domain] = True
        return


    def _parse_new_domains(self) -> None:

        trie = pygtrie.StringTrie(separator='.')

        for domain_name in self._domain_data.keys():
            self._put_domain_in_trie(trie, domain_name)

            #for parent_domain in data.keys():
            #    self._put_domain_in_trie(trie, parent_domain)

        del trie
        return

    def _create_edges_between_domains(self, domains: list[str], seen: set[tuple[str, str]], sub_of_edges: list[dict[str, str]]) -> None:

        for cnt1 in range(len(domains)):
            for cnt2 in range(len(domains)):
                if cnt1 != cnt2 and (domains[cnt1],domains[cnt2]) not in seen:
                    jacc = calc_jaccard(self._domain_data[domains[cnt1]][self._PARENT_DOMAINS], self._domain_data[domains[cnt2]][self._PARENT_DOMAINS])
                    sub_of_edges.append({'u': domains[cnt1], 'v': domains[cnt2], 'weight': jacc})
                    seen.add((domains[cnt1],domains[cnt2]))

        return

    def _create_sub_of_edges_dataset(self, sub_of_edges: list[dict[str, str]]) -> None:

        seen = set()

        for domains in self._subs.values():
            self._create_edges_between_domains(domains, seen, sub_of_edges)

        del seen
        return

    def _create_sub_of_edges_graph(self, sub_of_edges: list[dict[str, str]]) -> None:

        u, v, jacc = [], [], []

        for domain_name, data in self._domain_data.items():
            if len(data[self._MATCHES]) < 1:
                continue

            match_domains = [match['domain_name'] for match in data[self._MATCHES]]
            domain_name_list = [domain_name] * len(match_domains)
            u_tmp, v_tmp = domain_name_list + match_domains, match_domains + domain_name_list

            jacc_tmp = []
            for match_domain in data[self._MATCHES]:
                jacc_tmp.append(calc_jaccard(data[self._PARENT_DOMAINS], match_domain['parent_domains']))

            u.extend(u_tmp)
            v.extend(v_tmp)
            jacc.extend(jacc_tmp)
            jacc.extend(jacc_tmp) #this is done for reverse edges


        for cnt in range(len(u)):
            sub_of_edges.append({'u': u[cnt], 'v': v[cnt], 'weight': jacc[cnt]})

        del u, v, jacc
        return


    def _create_sub_of_edges(self) -> None:

        sub_of_edges: list[dict[str, str]] = []

        self._create_sub_of_edges_graph(sub_of_edges)
        self._create_sub_of_edges_dataset(sub_of_edges)

        query_option = {
            Neo4jDBClient.E_NODE_T1: NodeTypes.DOMAIN,
            Neo4jDBClient.E_NODE_T2: NodeTypes.DOMAIN,
            Neo4jDBClient.E_OPTION: Neo4jDBClient.EdgeCreationQueryOptions.WEIGHT_NO_REVERSE,
            Neo4jDBClient.E_EDGE_T: EdgeTypes.SUBDOMAIN_OF,
            Neo4jDBClient.E_MATCH1: "domain_name",
            Neo4jDBClient.E_MATCH2: "domain_name",
            Neo4jDBClient.E_EDGE_VALUE_NAME: "weight"
        }

        self._edge_submit_callback(sub_of_edges,query_option,self.worker_name + "sub_of")
        return
"""