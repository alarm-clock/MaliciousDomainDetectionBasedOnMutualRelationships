import threading
from concurrent.futures import ThreadPoolExecutor
import pygtrie
import pymongo
from misc.Logger import MyLogger
from misc.helper_func import add_project_into_pipeline


class SubdomainEdge(threading.Thread):

    def __init__(self, dispatcher, collection: pymongo.collection.Collection, ranges: list, subdomains: bool, subdomain_of: bool):
        super().__init__()
        self._collection = collection
        self._dispatcher = dispatcher

        add_project_into_pipeline({"_id": 0, "domain_name": 1, "node_id": 1}, ranges)
        self._pipeline = ranges

        self._u: list[int] = []
        self._v: list[int] = []
        self._of_u: list[int] = []
        self._of_v: list[int] = []
        self._subs: dict = {}
        self._subs_of: dict = {}
        self._subdomains = subdomains
        self._subdomain_of = subdomain_of

    def _reverse(self,d) -> tuple[int, str]:
        parts = d['domain_name'].strip().rstrip('.').split('.')
        return int(d['node_id']), '.'.join(reversed(parts))


    def _create_subdomain_edges(self) -> None:

        for key, vals in self._subs.items():
            if key < 0:
                continue
            u = [key] * len(vals)
            v = vals
            self._u.extend(u) #edges from superdomain to subdomains
            self._v.extend(v)
            self._u.extend(v) #edges from subdomains to superdomain
            self._v.extend(u)

    def _create_edges_between_subdomains(self, values: list[int]) -> tuple[list[int],list[int]]:
        u = []
        v = []

        #print(values)
        #todo I must rework this to calculate some probability value for every edge that will reflect that all
        #todo domains that share same top level domains like kokot.a.d.cz and pica.a.d.cz will have higher probability
        #todo of being chosen in walk from one to another then domain like jebaci.d.cz
        for cnt in range(len(values)):
            u.extend([values[cnt]] * (len(values) - 1))
            for cnt2 in range(len(values)):
                if cnt != cnt2:
                    v.append(values[cnt2])

        return u, v

    def _create_subdomain_of_edges(self) -> None:

        with ThreadPoolExecutor(max_workers=16) as executor:
            futures = [ executor.submit(self._create_edges_between_subdomains, values) for values in self._subs.values() ]

            for future in futures:
                result = future.result()
                if result:
                    u, v = result
                    self._of_v.extend(v)
                    self._of_u.extend(u)

                    del u, v

    def _create_edges(self) -> None:

        if self._subdomains:
            MyLogger.get_instance().log("Creating subdomain edges...")
            self._create_subdomain_edges()
            MyLogger.get_instance().log("Created subdomain edges")
        if self._subdomain_of:
            MyLogger.get_instance().log("Creating subdomain_of edges...")
            self._create_subdomain_of_edges()
            MyLogger.get_instance().log("Created subdomain_of edges")

    def _submit_edges(self):

        if self._subdomains:
            self._dispatcher.submit_edges(self._u,self._v,'subdomain')
            MyLogger.get_instance().log("Submitted all subdomain edges")
        if self._subdomain_of:
            self._dispatcher.submit_edges(self._of_u,self._of_v,'subdomain_of')
            MyLogger.get_instance().log("Submitted all subdomain_of edges")

        del self._u, self._v, self._of_u, self._of_v

    def _check_domain_and_put_it_in_trie(self, trie: pygtrie.StringTrie, domain: tuple[int, str], domain_id_dict: dict):

        if trie.has_subtrie(domain[1]):
            #print(f"{domain[1]} is superdomain")
            children = list(trie.keys(prefix=domain[1]))

            if domain[1] in children:
                children.remove(domain[1])
            children_ids = [domain_id_dict[child] for child in children]
            children_ids = [ch_id for ch_id in children_ids if ch_id >= 0]
            #print(children_ids)
            self._subs[domain[0]] = children_ids


        parent = trie.longest_prefix(domain[1])

        if parent:
            if parent[0] == domain[1] or domain[0] < 0:
                return

            if domain_id_dict.get(parent[0]) is not None:
                parent_id = domain_id_dict[parent.key]
                if parent_id not in self._subs:
                    self._subs[parent_id] = [domain[0]]
                else:
                    self._subs[parent_id].append(domain[0])

    def _get_domains(self) -> list[tuple[int, str]]:
        #cursor = self._collection.find({}, {'_id': 0, 'domain_name': 1, 'node_id': 1}, batch_size=10000)
        cursor = self._collection.aggregate(self._pipeline, batchSize=10000)
        domains = []

        with ThreadPoolExecutor(max_workers=16) as executor:
            futures = [executor.submit(self._reverse, d) for d in
                       cursor]  # reverse domains so tree can be built from top level domain

            for future in futures:
                result = future.result()
                if result:
                    domains.append(result)

        cursor.close()
        return domains

    def _create_domain_tree(self, domains: list[tuple[int,str]], domain_id_dict: dict[str, int]) -> None:
        trie = pygtrie.StringTrie(separator='.')

        non_dset_id = -1
        for domain in domains:

            self._check_domain_and_put_it_in_trie(trie, domain, domain_id_dict)

            trie[domain[1]] = True

            domain_parts = domain[1].split('.')
            for cnt in range(2, len(domain_parts)):  # add every superdomain except the whole domain (-1)
                domain = '.'.join(domain_parts[:cnt])

                if domain_id_dict.get(domain):  # unique id for non dataset domains
                    domain_id = domain_id_dict[domain]
                else:
                    domain_id = non_dset_id
                    domain_id_dict[domain] = domain_id
                    non_dset_id -= 1

                self._check_domain_and_put_it_in_trie(trie, (domain_id, domain),
                                                      domain_id_dict)  # even if it isn't in dataset I still need it for subdomain_of
                trie[domain] = True

        del trie

    def run(self):
        MyLogger.get_instance().log("Getting domains for domain tree...")
        domains = self._get_domains()

        domain_id_dict = {}
        for domain in domains:
            domain_id_dict[domain[1]] = domain[0]  #store node ids in the hash table for fast retrieval

        MyLogger.get_instance().log("Got all domains. Creating subdomain tree...")
        self._create_domain_tree(domains, domain_id_dict)
        self._create_edges()
        self._submit_edges()
