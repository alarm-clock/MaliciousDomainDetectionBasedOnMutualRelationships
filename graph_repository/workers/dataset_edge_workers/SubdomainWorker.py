from enum import Enum
from graph_repository.workers.common.DatasetWorker import DatasetWorker
from graph_repository.workers.common.GraphTypes import NodeTypes, EdgeTypes
from graph_repository.graph_repo_misc import domain_depth, reverse_domain, get_domains_parent_domains
import pymongo
from concurrent.futures import ThreadPoolExecutor
import pygtrie
from misc.Logger import MyLogger

#TODO add list of well known hosting and cloud domains that will be used to filter out those parent domains, otherwise
# it has no informational value and causes creation of large clusters of domains that have no real connection

# noinspection DuplicatedCode
class SubdomainWorker(DatasetWorker):

    #class Modes(Enum):
    #    BOTH = 0
     #   SUBDOMAIN = 1
        #SUBDOMAIN_OF = 2

    worker_name = "subdomain"
    _e_type = EdgeTypes.SUBDOMAIN
    #_e_type2 = EdgeTypes.SUBDOMAIN_OF
    available_options = [
        (worker_name, _e_type.value, None),
        (worker_name, f"{worker_name}_all", None)
        #(worker_name, _e_type1.value, {'mode': Modes.SUBDOMAIN}),
        #(worker_name, _e_type2.value, {'mode': Modes.SUBDOMAIN_OF}),
        #(worker_name,f"{worker_name}_all",{'mode': Modes.SUBDOMAIN})
    ]
    _project = {"_id": 0, "domain_name": 1, "node_id": 1}
    _nd_type1 = NodeTypes.DOMAIN
    _nd_type2 = NodeTypes.DUMMY_SUB_DOMAIN

    def __init__(self, submit_callback_method, collection: pymongo.collection.Collection, ranges: list):
        super().__init__(submit_callback_method, collection, ranges, self._project)

        #self._mode: SubdomainWorker.Modes = mode
        #self._of_u: list[int] = []
        #self._of_v: list[int] = []
        #self._of_jacc: list[float] = []
        self._subs: dict = {}
        self._du_d_u: list = []
        self._du_d_v: list = []
        self._du_du_u: list = []
        self._du_du_v: list = []
        self._dummy_name: list = []
        self._dummy_depth: list = []

        #self._classes: dict = {}
        #self._subs_of: dict = {}


    def _submit_edges(self):

        self._submit_callback_method(self._u, self._v, self._nd_type1, self._e_type, self._nd_type1)
        self._submit_callback_method(
            self._du_du_u,
            self._du_du_v,
            self._nd_type2,
            self._e_type,
            self._nd_type2,
            u_data={"domain_name": self._dummy_name, 'depth': self._dummy_depth, "parent_domains": [get_domains_parent_domains(domain_name) for domain_name in self._dummy_name] }
        )
        self._submit_callback_method(self._du_d_u,self._du_d_v,self._nd_type2,self._e_type, self._nd_type1)
        self._submit_callback_method(self._du_d_v,self._du_d_u,self._nd_type1, self._e_type, self._nd_type2)
        MyLogger.get_instance().log("Submitted all subdomain edges")

        del self._u, self._v, self._subs, self._du_d_u, self._du_d_v, self._du_du_u, self._du_du_v

    def _reverse(self,d) -> tuple[int, str]:
        return int(d['node_id']), reverse_domain(str(d['domain_name']))

    def _add_reverse_edges(self) -> None:
        self._u[:], self._v[:] = self._u + self._v, self._v + self._u
        self._du_du_u[:], self._du_du_v[:] = self._du_du_u + self._du_du_v, self._du_du_v + self._du_du_u

    def _create_subdomain_edges(self) -> None:

        #print(self._subs)
        for key, vals in self._subs.items():
            if key < 0:
                key = -(key + 1)   #correction because nodes are created from 0 but algorithm requires to
                                   #have ability to distinguish both node types and because domains are also labeled from
                                   #0 then dummies must be -1 and less so here I add  +1 to move them into right value
                                   #also -() because there can't be node_id with negative value
                for val in vals:
                    if val < 0:
                        self._du_du_u.append(key)
                        self._du_du_v.append(-(val + 1))
                    else:
                        self._du_d_u.append(key)
                        self._du_d_v.append(val)
            else:
                for val in vals:
                    if val < 0:
                        self._du_d_v.append(key)
                        self._du_d_u.append(-(val + 1))
                    else:
                        self._u.append(key)
                        self._v.append(val)

        self._add_reverse_edges()

    def _create_edges(self) -> None:
        MyLogger.get_instance().log("Creating subdomain edges...")
        self._create_subdomain_edges()
        MyLogger.get_instance().log("Created subdomain edges")

    def _check_domain_and_put_it_in_dict(self, trie: pygtrie.StringTrie, domain: tuple[int, str], domain_id_dict: dict):

        if trie.has_subtrie(domain[1]):
            #print(f"{domain[1]} is superdomain")
            children = list(trie.keys(prefix=domain[1]))

            if domain[1] in children:
                children.remove(domain[1])
            children_ids = [domain_id_dict[child] for child in children]
            children_ids = [ch_id for ch_id in children_ids] # if ch_id >= 0]

            self._subs[domain[0]] = children_ids

        parent = trie.longest_prefix(domain[1])

        if parent:
            if parent[0] == domain[1]: # or domain[0] < 0:
                return

            if domain_id_dict.get(parent[0]) is not None:
                parent_id = domain_id_dict[parent.key]
                if parent_id not in self._subs:
                    self._subs[parent_id] = [domain[0]]
                else:
                    self._subs[parent_id].append(domain[0])

    def _create_domain_tree(self, domains: list[tuple[int,str]], domain_id_dict: dict[str, int]) -> None:
        trie = pygtrie.StringTrie(separator='.')
        non_dset_id = -1
        for domain in domains:

            self._check_domain_and_put_it_in_dict(trie, domain, domain_id_dict)

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
                    reversed_domain = reverse_domain(domain)
                    self._dummy_name.append(reversed_domain)
                    self._dummy_depth.append(domain_depth(reversed_domain))

                self._check_domain_and_put_it_in_dict(trie,
                                                      (domain_id, domain),
                                                      domain_id_dict)  # even if it isn't in dataset I still need it for subdomain_of
                trie[domain] = True

        del trie

    def _get_domains(self) -> tuple[ list[tuple[int, str]], dict[str,int]]:

        cursor = self._collection.aggregate(self._pipeline, batchSize=10000)
        domains = []
        domain_id_dict = {}

        with ThreadPoolExecutor(max_workers=16) as executor:
            futures = [executor.submit(self._reverse, d) for d in cursor]
            # reverse domains so tree can be built from top level domain

            for future in futures:
                result = future.result()
                if result:
                    domains.append(result)
                    domain_id_dict[result[1]] = result[0]

        cursor.close()
        return domains, domain_id_dict

    def _compute(self):

        MyLogger.get_instance().log("Getting domains for domain tree...")
        domains, domain_id_dict = self._get_domains()
       # print(domains)

        #print(domain_id_dict)
        MyLogger.get_instance().log("Got all domains. Creating subdomain tree...")
        self._create_domain_tree(domains, domain_id_dict)
        del domains, domain_id_dict

        self._create_edges()
        self._submit_edges()