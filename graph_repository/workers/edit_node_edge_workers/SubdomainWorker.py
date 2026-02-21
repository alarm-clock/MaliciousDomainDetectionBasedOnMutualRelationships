from typing import Any
import pygtrie
from graph_repository.workers.common.EditWorker import EditWorker
from graph_repository.workers.common.GraphTypes import NodeTypes
from graph_repository.Neo4jDBClient import Neo4jDBClient
from graph_repository.graph_main.GraphRepository import GraphRepository
from graph_repository.graph_repo_misc import get_domains_parent_domains, reverse_domain
from enum import Enum

class SubdomainWorker(EditWorker):

    worker_name = 'subdomain'
    _limit = 5000
    _PARENT_DOMAINS = 0
    _MATCHES = 1
    _PARENT_DOMAINS_IN_GRAPH = 2
    _SUBDOMAINS = 3

    _index_query = f"""
        CREATE INDEX parentDomainsIndex 
        IF NOT EXISTS
        FOR (d: {NodeTypes.DOMAIN.value})
        ON EACH [d.parent_domains];
        """

    def __init__(self, domains: list[dict]):
        super().__init__(domains, SubdomainWorker._limit)
        self._domain_data: dict[str, tuple[list[str], list[dict], list[str], list[str]]] = {}


    # 1. prejst vsetky domeny a naskenovat graf na ich rodicovske domeny/ domeny zo stejnymi rodicmi
    #    ideal vyhladavanie podla podretazca + musim mysliet na to co ak domena je rodicovska domena inej domeny v grafe
    # 2. skontrolovat nove hrany medzi sebou ci niesu jedna druhej rodicovske domeny
    # 2. vytvorit prislusne hrany
    # 3. algoritmus ktory pre vsetky dane domeny prerata vahu (zrejme to uz budem musiet robit popri vyhladavani domen, z grafu moc velka extra narocnost)


    def put_domain_in_trie(self, trie: pygtrie.StringTrie, domain: str) -> None:

        if trie.has_node(domain):

            children = list(trie.keys(prefix=domain))

            if domain in children:
                children.remove(domain)

            children = [child for child in children if child in self._domain_data]

            #can only be done for domains that are new
            if domain in self._domain_data:
                self._domain_data[domain][self._SUBDOMAINS].extend(children)

            for child in children:
                #add parent domain for each child as domain that is in the graph
                self._domain_data[child][self._PARENT_DOMAINS_IN_GRAPH].append(domain)


        parent, _ = trie.longest_prefix(domain)

        if parent is not None:
            if parent == domain or domain not in self._domain_data:
                return

            self._domain_data[domain][self._PARENT_DOMAINS_IN_GRAPH].append(parent)

        return


    def _parse_new_domains(self, domains_and_related_domains: list[dict[str, str | list[str]]]) -> None:

        trie = pygtrie.StringTrie(separator='.')

        for domain_dict in domains_and_related_domains:
            reverse_domain_name = reverse_domain(domain_dict['domain_name'])
            reversed_parent_domains = [reverse_domain(parent_domain) for parent_domain in domain_dict['parent_domains']]




        return


    def _find_related_domains_and_data(self) -> None:

        driver = GraphRepository.get_instance().get_neo4j_driver()
        self._create_index(driver)

        find_related_domains_query = f"""
        UNWIND $domain_tuples AS domain 
        
        CALL (domain){{
            UNWIND domain.parent_domains AS parent_domain
            MATCH (d: {NodeTypes.DOMAIN.value})
            WHERE parent_domain IN d.parent_domains AND d.domain_name <> domain.domain_name
            WITH DISTINCT d
            RETURN collect({{
                match_domain_name: d.domain_name,
                parent_domains: d.parent_domains
            }}) AS matches
        }}
        CALL (domain){{
            UNWIND domain.parent_domains AS parent_domain
            OPTIONAL MATCH (d: {NodeTypes.DOMAIN.value} {{domain_name: parent_domain}})
            RETURN collect(d.domain_name) AS parent_domains_in_graph
        }}
        CALL (domain){{ 
            MATCH (d: {NodeTypes.DOMAIN.value})
            WHERE domain.domain_name IN d.parent_domains
            RETURN collect(d.domain_name) AS subdomains
        }}
        
        RETURN domain.domain_name AS domain_name, domain.parent_domains AS parent_domains, matches, parent_domains_in_graph, subdomains
        """

        domains_and_parents: list[dict[str, str | list[str]]] = []

        for domain_dict in self._domains:

            domain_name = str(domain_dict['domain_name'])
            parent_domains = get_domains_parent_domains(domain_name)
            domains_and_parents.append({'domain_name': domain_name, 'parent_domains': parent_domains})

        domains_and_related_domains = driver.execute_read(find_related_domains_query, parent_tuples=domains_and_parents)

        for row in domains_and_related_domains:
            self.domain_data[row["domain_name"]] = (row["parent_domains"], row['matches'], row["parent_domains_in_graph"], row["subdomains"])

        driver.close()
        return

    def _create_index(self, driver: Neo4jDBClient):
        driver.execute_write(self._index_query)

    def _compute(self):
        pass

