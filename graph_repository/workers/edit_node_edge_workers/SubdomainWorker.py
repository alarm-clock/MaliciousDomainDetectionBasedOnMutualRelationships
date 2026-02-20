from graph_repository.workers.common.EditWorker import EditWorker
from graph_repository.workers.common.GraphTypes import NodeTypes
from graph_repository.Neo4jDBClient import Neo4jDBClient
from graph_repository.graph_main.GraphRepository import GraphRepository
from graph_repository.graph_repo_misc import get_domains_parent_domains

class SubdomainWorker(EditWorker):

    worker_name = 'subdomain'
    _limit = 5000

    _index_query = f"""
        CREATE INDEX parentDomainsIndex 
        IF NOT EXISTS
        FOR (d: {NodeTypes.DOMAIN.value})
        ON EACH [d.parent_domains];
        """

    def __init__(self, domains: list[dict]):
        super().__init__(domains, SubdomainWorker._limit)


    # 1. prejst vsetky domeny a naskenovat graf na ich rodicovske domeny/ domeny zo stejnymi rodicmi
    #    ideal vyhladavanie podla podretazca + musim mysliet na to co ak domena je rodicovska domena inej domeny v grafe
    # 2. vytvorit prislusne hrany
    # 3. algoritmus ktory pre vsetky dane domeny prerata vahu (zrejme to uz budem musiet robit popri vyhladavani domen, z grafu moc velka extra narocnost)


    def _find_domains_with_same_parent_domain(self):

        driver = GraphRepository.get_instance().get_neo4j_driver()

        #argument is domains name parent domain/s
        find_sub_of_query = f"""
        UNWIND $parent_domains AS parent_domain
        MATCH (d: {NodeTypes.DOMAIN.value})
        WHERE parent_domain IN d.parent_domains
        RETURN d.domain_name
        """

        #argument is parent domain
        find_parent_d_query = f"""
        MATCH (d: {NodeTypes.DOMAIN.value} {{domain_name: $domain_name}})
        RETURN d.domain_name
        """

        #argument is domain name
        find_sub_query = f"""
        MATCH (d: {NodeTypes.DOMAIN.value})
        WHERE $domain_name IN d.parent_domains
        RETURN d.domain_name
        """

        for domain_dict in self._domains:

            domain_name = str(domain_dict['domain_name'])
            parent_domains = get_domains_parent_domains(domain_name)

            result = driver.execute_read(find_sub_query, parent_domains=parent_domains)

            result = driver.execute_read(find_parent_d_query, domain_name=parent_domains[0])

            result = driver.execute_read(find_sub_query, domain_name=domain_name)

        driver.close()


    #TODO ADD SOMEWHERE
    def _create_index(self, driver: Neo4jDBClient):
        driver.execute_write(self._index_query)

    def _compute(self):
        pass

