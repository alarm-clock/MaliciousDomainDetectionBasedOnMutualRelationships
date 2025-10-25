import threading
from concurrent.futures import ThreadPoolExecutor
import pygtrie
import pymongo


class SubdomainEdge(threading.Thread):

    def __init__(self, dispatcher, collection: pymongo.collection.Collection, subdomains: bool, subdomain_of: bool):
        super().__init__()
        self._collection = collection
        self._dispatcher = dispatcher

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
            self._u.extend([key] * vals.__len__())
            self._v.extend(vals)

    def _create_edges_between_subdomains(self, values: list[int]) -> tuple[list[int],list[int]]:
        u = []
        v = []

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

    def _create_edges(self) -> None:

        if self._subdomains:
            self._create_subdomain_edges()
        if self._subdomain_of:
            self._create_subdomain_of_edges()

    def _submit_edges(self):

        if self._subdomains:
            self._dispatcher.submit_edges(self._u,self._v,'subdomain')
        if self._subdomain_of:
            self._dispatcher.submit_edges(self._of_u,self._of_v,'subdomain_of')

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


    def run(self):

        cursor = self._collection.find({}, {'_id': 0, 'domain_name': 1, 'node_id': 1}, batch_size=10000)
        domains = []

        with ThreadPoolExecutor(max_workers=16) as executor:
            futures = [executor.submit(self._reverse, d) for d in cursor] #reverse domains so tree can be built from top level domain

            for future in futures:
                result = future.result()
                if result:
                    domains.append(result)

        domain_id_dict = {}
        for domain in domains:
            domain_id_dict[domain[1]] = domain[0]  #store node ids in the hash table for fast retrieval

        trie = pygtrie.StringTrie(separator='.')

        non_dset_id = -1
        for domain in domains:

            self._check_domain_and_put_it_in_trie(trie, domain, domain_id_dict)

            trie[domain[1]] = True

            domain_parts = domain[1].split('.')
            for cnt in range(2, len(domain_parts)): #add every superdomain except the whole domain (-1)
                domain = '.'.join(domain_parts[:cnt])

                if domain_id_dict.get(domain):  #unique id for non dataset domains
                    domain_id = domain_id_dict[domain]
                else:
                    domain_id = non_dset_id
                    domain_id_dict[domain] = domain_id
                    non_dset_id -= 1

                self._check_domain_and_put_it_in_trie(trie, (domain_id,domain), domain_id_dict) #even if it isn't in dataset I still need it for subdomain_of
                trie[domain] = True

        self._create_edges()
        self._submit_edges()