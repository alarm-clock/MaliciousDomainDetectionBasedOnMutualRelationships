import threading
from concurrent.futures import ThreadPoolExecutor
import pymongo

class CNAMEEdge(threading.Thread):

    def __init__(self, dispatcher, collection:  pymongo.collection.Collection):
        super().__init__()
        self._dispatcher = dispatcher
        self._collection = collection
        self._domains: dict[str, list] = {}
        self._u: list[int] = []
        self._v: list[int] = []

    def _submit_result(self):
        self._dispatcher.submit_edges(self._u, self._v, 'cname')
        self._u.clear()
        self._v.clear()
        self._domains.clear()

    def _find_in_db(self, domain: str) -> tuple[int, str] | None:

        doc = self._collection.find_one({"domain_name": domain})
        if doc is None:
            return None
        else:
            return doc["node_id"], domain

    def _connect_nodes_w_same_cname(self, node_ids: list[int]) -> tuple[list[int], list[int]]:
        u, v = [], []

        for u_id in node_ids:
            u.extend([u_id] * (len(node_ids) - 1))
            for v_id in node_ids:
                if u_id != v_id:
                    v.append(v_id)

        return u, v

    def _create_edges(self):

        with ThreadPoolExecutor(max_workers=16) as executor:
            futures = [executor.submit(self._connect_nodes_w_same_cname, cname_clust) for cname_clust in self._domains.values() if len(cname_clust) > 1] #no connection can be made with one domain

            for future in futures:
                result = future.result()
                if result is not None:
                    self._u.extend(result[0])
                    self._v.extend(result[1])

    def _find_cnames_in_db(self):
        with ThreadPoolExecutor(max_workers=32) as executor:
            futures = [executor.submit(self._find_in_db, d) for d in self._domains.keys()]

            for future in futures:
                result = future.result()
                if result is not None:
                    node_id, dom_name = result
                    if self._domains.get(dom_name) is not None:
                        self._domains[dom_name].append(node_id)
                    else:
                        self._domains[dom_name] = [node_id]


    def _match_entries_with_same_cname(self):
        cursor = self._collection.find({}, {'_id': 0, "dns.CNAME.value": 1, "node_id": 1}, batch_size=10000)

        for doc in cursor:
            if doc.get('dns'):
                if doc['dns']['CNAME']['value'] not in self._domains:
                    self._domains[doc['dns']['CNAME']['value']] = [int(doc['node_id'])]
                else:
                    self._domains[doc['dns']['CNAME']['value']].append(int(doc['node_id']))

        self._find_cnames_in_db()

    def run(self):
        self._match_entries_with_same_cname()
        self._create_edges()
        self._submit_result()
