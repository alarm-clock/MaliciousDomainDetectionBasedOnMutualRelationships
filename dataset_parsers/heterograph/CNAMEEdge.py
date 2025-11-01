import copy
import threading
from concurrent.futures import ThreadPoolExecutor
from misc.Logger import MyLogger
from misc.helper_func import add_project_into_pipeline
import pymongo

class CNAMEEdge(threading.Thread):

    def __init__(self, dispatcher, collection:  pymongo.collection.Collection, ranges: list):
        super().__init__()
        self._dispatcher = dispatcher
        self._collection = collection
        self._domains: dict[str, list] = {}
        self._u: list[int] = []
        self._v: list[int] = []

        self._match = copy.deepcopy(ranges)
        add_project_into_pipeline({'_id': 0, "dns.CNAME.value": 1, "node_id": 1}, ranges)
        self._pipeline = ranges

    def _submit_result(self):
        self._dispatcher.submit_edges(self._u, self._v, 'cname')

        del self._u, self._v, self._domains

#    def _find_in_db(self, domain: str) -> tuple[int, str] | None:

#        match = {"$and": [{"domain_name": domain}, self._match[0]["$match"]]} if len(self._match) != 0 else {"domain_name": domain}
#        doc = self._collection.find_one(match)
#        if doc is None:
#            return None
#        else:
#            return doc["node_id"], domain

    def _connect_nodes_w_same_cname(self, node_ids: list[int]) -> tuple[list[int], list[int]]:
        u, v = [], []

        for u_id in node_ids:
            #u.extend([u_id] * (len(node_ids) - 1)) #can't do this like this because there might be domains that with
            #cname point to themselves, and using cnt should use less computing power then looping through every list when
            #adding domain to the list
            num_of_diff_domains = 0
            for v_id in node_ids:
                if u_id != v_id:
                    v.append(v_id)
                    num_of_diff_domains += 1

            u.append([u_id] * num_of_diff_domains)

        return u, v

    def _create_edges(self):

        with ThreadPoolExecutor(max_workers=16) as executor:
            futures = [executor.submit(self._connect_nodes_w_same_cname, cname_clust) for cname_clust in self._domains.values() if len(cname_clust) > 1] #no connection can be made with one domain

            for future in futures:
                result = future.result()
                if result is not None:
                    self._u.extend(result[0])
                    self._v.extend(result[1])

#    def _find_cnames_in_db(self):
#        with ThreadPoolExecutor(max_workers=32) as executor:
#            futures = [executor.submit(self._find_in_db, d) for d in self._domains.keys()]

#            for future in futures:
#                result = future.result()
#                if result is not None:
#                    node_id, dom_name = result
#                    if self._domains.get(dom_name) is not None:
#                        self._domains[dom_name].append(node_id)
#                    else:
#                        self._domains[dom_name] = [node_id]

    def _create_domain_batches(self) -> list[list[str]]:

        batch_size = 5000
        domain_names = list(self._domains.keys())
        batches = []

        for start in range(0, len(domain_names), batch_size):
            batches.append(domain_names[start:start+batch_size])

        return batches

    def _find_domains_in_db(self, domains: list[str]) -> None:

        match = {"$and": [{"domain_name": {"$in" : domains}}, self._match[0]["$match"]]} if len(self._match) != 0 else {"domain_name": {"$in": domains}}
        found = self._collection.find(match, {"domain_name": 1, "_id": 0, "node_id": 1})

        for doc in found:
            self._domains[doc["domain_name"]].append(doc["node_id"])
            # I don't need to check if domain is in the domains dictionary because I got it from it
            # also I don't need to check if there is a list because there already must be one
            # there also isn't need for the lock because in dictionary this domain is a key

        found.close()

    def _find_cnames_in_db(self):

        self._collection.create_index({"domain_name": 1})
        domain_name_batches = self._create_domain_batches()

        with ThreadPoolExecutor(max_workers=16) as executor:
            futures = [executor.submit(self._find_domains_in_db, batch) for batch in domain_name_batches]

            for future in futures:
                future.result()

    def _match_entries_with_same_cname(self):
        #cursor = self._collection.find({}, {'_id': 0, "dns.CNAME.value": 1, "node_id": 1}, batch_size=10000)
        cursor = self._collection.aggregate(self._pipeline, batchSize=10000)

        for doc in cursor:
            if doc.get('dns'):
                if doc['dns']['CNAME']['value'] not in self._domains:
                    self._domains[doc['dns']['CNAME']['value']] = [int(doc['node_id'])]
                else:
                    self._domains[doc['dns']['CNAME']['value']].append(int(doc['node_id']))

        MyLogger.get_instance().log("Stored all CNAME domains in the internal structure")
        self._find_cnames_in_db()
        MyLogger.get_instance().log("Found all CNAME domains that are also in the database")
        cursor.close()

    def run(self):
        MyLogger.get_instance().log("Starting to match CNAME entries...")
        self._match_entries_with_same_cname()
        MyLogger.get_instance().log("Creating CNAME edges...")
        self._create_edges()
        MyLogger.get_instance().log("All CNAME edges created")
        self._submit_result()
