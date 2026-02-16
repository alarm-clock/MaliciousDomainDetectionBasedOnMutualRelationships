from enum import Enum
from graph_repository.dataset_creator.common.Worker import Worker
from graph_repository.dataset_creator.common.GraphTypes import NodeTypes, EdgeTypes
from graph_repository.graph_repo_misc import calc_jaccard
import pymongo
from concurrent.futures import ThreadPoolExecutor
import pygtrie
from misc.Logger import MyLogger

#TODO add list of well known hosting and cloud domains that will be used to filter out those parent domains, otherwise
# it has no informational value and causes creation of large clusters of domains that have no real connection

# noinspection DuplicatedCode
class SubdomainWorker(Worker):

    class Modes(Enum):
        BOTH = 0
        SUBDOMAIN = 1
        SUBDOMAIN_OF = 2

    worker_name = "subdomain"
    _e_type1 = EdgeTypes.SUBDOMAIN
    _e_type2 = EdgeTypes.SUBDOMAIN_OF
    available_options = [
        (worker_name, _e_type1.value, {'mode': Modes.SUBDOMAIN}),
        (worker_name, _e_type2.value, {'mode': Modes.SUBDOMAIN_OF}),
        (worker_name,f"{worker_name}_all",{'mode': Modes.BOTH})
    ]
    _project = {"_id": 0, "domain_name": 1, "node_id": 1}
    _nd_type = NodeTypes.DOMAIN

    def __init__(self, submit_callback_method, collection: pymongo.collection.Collection, ranges: list, mode: Modes = Modes.BOTH):
        super().__init__(submit_callback_method, collection, ranges, self._project)

        self._mode: SubdomainWorker.Modes = mode
        self._of_u: list[int] = []
        self._of_v: list[int] = []
        self._of_jacc: list[float] = []
        self._subs: dict = {}
        self._classes: dict = {}
        #self._subs_of: dict = {}


    def _remove_duplicities_in_sub_of(self):
        seen = set()
        of_v = []
        of_u = []
        of_jacc = []

        for cnt in range(len(self._of_u)):

            edge = (self._of_u[cnt], self._of_v[cnt])
            if edge not in seen:
                of_u.append(self._of_u[cnt])
                of_v.append(self._of_v[cnt])
                of_jacc.append(self._of_jacc[cnt])
                seen.add(edge)

        self._of_u = of_u
        self._of_v = of_v
        self._of_jacc = of_jacc

    def _submit_edges(self):

        if self._mode == self.Modes.SUBDOMAIN or self._mode == self.Modes.BOTH:
            self._submit_callback_method(self._u, self._v, self._nd_type, self._e_type1, self._nd_type)
            MyLogger.get_instance().log("Submitted all subdomain edges")
        if self._mode == self.Modes.SUBDOMAIN_OF or self._mode == self.Modes.BOTH:

            self._remove_duplicities_in_sub_of()

            e_data = ('sub_of_weight', self._of_jacc)

            self._submit_callback_method(self._of_u, self._of_v, self._nd_type, self._e_type2, self._nd_type, e_data=e_data)
            MyLogger.get_instance().log("Submitted all subdomain_of edges")

        del self._u, self._v, self._of_u, self._of_v, self._of_jacc, self._subs, self._classes

    def _reverse(self,d) -> tuple[int, str]:
        parts = d['domain_name'].strip().rstrip('.').split('.')
        return int(d['node_id']), '.'.join(reversed(parts))


    def _create_subdomain_edges(self) -> None:

        #print(self._subs)
        for key, vals in self._subs.items():
            if key < 0:
                continue
            u = [key] * len(vals)
            v = vals
            self._u.extend(u) #edges from superdomain to subdomains
            self._v.extend(v)
            self._u.extend(v) #edges from subdomains to superdomain
            self._v.extend(u)

    def _create_edges_between_subdomains(self, values: list[int]) -> tuple[list[int],list[int],list[float]]:
        u = []
        v = []
        jacc = []

        for id_u in range(len(values)):
            u.extend([values[id_u]] * (len(values) - 1))
            for id_v in range(len(values)):
                if id_u != id_v:
                    v.append(values[id_v])
                    jacc.append(calc_jaccard(self._classes[values[id_v]],self._classes[values[id_u]]))

        return u, v, jacc

    def _create_subdomain_of_edges(self) -> None:

        with ThreadPoolExecutor(max_workers=16) as executor:
            futures = [ executor.submit(self._create_edges_between_subdomains, values) for values in self._subs.values() ]

            for future in futures:
                result = future.result()
                if result:
                    u, v, jacc = result
                    self._of_v.extend(v)
                    self._of_u.extend(u)
                    self._of_jacc.extend(jacc)

                    del u, v, jacc

    def _create_edges(self) -> None:

        if self._mode == self.Modes.SUBDOMAIN or self._mode == self.Modes.BOTH:
            MyLogger.get_instance().log("Creating subdomain edges...")
            self._create_subdomain_edges()
            MyLogger.get_instance().log("Created subdomain edges")
        if self._mode == self.Modes.SUBDOMAIN_OF or self._mode == self.Modes.BOTH:
            MyLogger.get_instance().log("Creating subdomain_of edges...")
            self._create_subdomain_of_edges()
            MyLogger.get_instance().log("Created subdomain_of edges")

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

            for child in children_ids:
                if self._classes.get(child) is not None and domain[0] not in self._classes[child]:
                    self._classes[child].append(domain[0])
                else:
                    self._classes[child] = [domain[0]]


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

                if domain[0] not in self._classes:
                    self._classes[domain[0]] = [parent_id]
                else:
                    self._classes[domain[0]].append(parent_id)

    def _create_domain_tree(self, domains: list[tuple[int,str]], domain_id_dict: dict[str, int]) -> None:
        trie = pygtrie.StringTrie(separator='.')

        non_dset_id = -1
        for domain in domains:

            self._check_domain_and_put_it_in_trie(trie, domain, domain_id_dict)

            trie[domain[1]] = True

            domain_parts = domain[1].split('.')
            for cnt in range(2, len(domain_parts)):  # add every parent domain except the whole domain (-1)
                domain = '.'.join(domain_parts[:cnt])

                if domain_id_dict.get(domain):  # unique id for non dataset domains
                    domain_id = domain_id_dict[domain]
                else:
                    domain_id = non_dset_id
                    domain_id_dict[domain] = domain_id
                    non_dset_id -= 1            # "nedavaju sa ziadne zaporne body, oni si ich len zarobili zaporne" cca Hlineny

                self._check_domain_and_put_it_in_trie(trie, (domain_id, domain),
                                                      domain_id_dict)  # even if it isn't in dataset I still need it for subdomain_of
                trie[domain] = True

        del trie

    def _get_domains(self) -> list[tuple[int, str]]:

        cursor = self._collection.aggregate(self._pipeline, batchSize=10000)
        domains = []

        with ThreadPoolExecutor(max_workers=16) as executor:
            futures = [executor.submit(self._reverse, d) for d in cursor]
            # reverse domains so tree can be built from top level domain

            for future in futures:
                result = future.result()
                if result:
                    domains.append(result)

        cursor.close()
        return domains

    def _compute(self):

        MyLogger.get_instance().log("Getting domains for domain tree...")
        domains = self._get_domains()
       # print(domains)

        domain_id_dict = {}
        for domain in domains:
            domain_id_dict[domain[1]] = domain[0]  # store node ids in the hash table for fast retrieval

        #print(domain_id_dict)
        MyLogger.get_instance().log("Got all domains. Creating subdomain tree...")
        self._create_domain_tree(domains, domain_id_dict)
        del domains, domain_id_dict

        self._create_edges()
        self._submit_edges()