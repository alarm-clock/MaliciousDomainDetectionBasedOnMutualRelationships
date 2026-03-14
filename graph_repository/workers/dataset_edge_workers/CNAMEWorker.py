"""
File: graph_repository/dataset_creator/dataset_edge_workers/CNAMEWorker.py
System module: graph_repository
Author: Jozef Michal Bukas
Email: xbukas00@stud.fit.vutbr.cz
Date: 10.2.2026
Description: Class used for parallel creation of CNAME edges from dataset
"""
import copy

from graph_repository.workers.common.DatasetWorker import DatasetWorker
from graph_repository.workers.common.GraphTypes import NodeTypes, EdgeTypes
from graph_repository.graph_repo_misc import domain_depth
from graph_repository.graph_repo_misc import get_domains_parent_domains
from concurrent.futures import ThreadPoolExecutor
from misc.Logger import MyLogger
from misc.Pair import replace
import pymongo


class CNAMEWorker(DatasetWorker):
    """
    Worker class for creating CNAME edges on separate thread.

    Static attributes:
        `worker_name (str)`: name identifying this class

        `available_options (list[tuple[str, str, dict | None]])`: list of available options for this class in
        format (name, option name, kwargs for that option or none)
    """

    LONE_CNAMES = True
    NO_LONE_CNAMES = False

    worker_name = "cname"
    available_options = [
        (worker_name,worker_name,{"mode": True}),
        (worker_name,worker_name+"_no_lone", {"mode": False}),
        (worker_name,f'{worker_name}_all',{"mode": True})
    ]

    _project: dict = {'_id': 0, "dns.CNAME.value": 1, "node_id": 1, "domain_name": 1}
    _nd_type1 = NodeTypes.DOMAIN
    _nd_type2 = NodeTypes.DUMMY_DOMAIN
    _DUMMY = False
    _DOMAIN = True

    _DOMAINS_TYPE = 0
    _DOMAINS_ID = 1
    _DOMAINS_LIST = 2
    _DOMAIN_NAMES_LIST = 3
    _BATCH_SIZE = 5000

    def __init__(self, submit_callback_method, collection: pymongo.collection.Collection, ranges: list, mode: bool):
        """
        Initializes CNAMEWorker class attributes.
        :param submit_callback_method: Method for submitting results to dispatcher
        :param collection: Mongo collection with dataset
        :param ranges: Dictionary with `or` conditions used to filter collection entries by `node_id`
        """
        super().__init__(submit_callback_method, collection, ranges, self._project)
        self._domains: dict[str, tuple[bool, int, list[int], list[str]]] = {}

        self._owners = []
        self._d_du_owners = []
        self._du: list[int] = []
        self._dum_dv: list[int] = []
        self._dum_d_names: list[str] = []
        self._dum_d_depth: list[int] = []
        self._mode = mode

    def _submit_result(self) -> None:
        """
        Method for submitting results to dispatcher.
        :return: None
        """

        if len(self._u) > 0:
            MyLogger.get_instance().log("Submitting d -> cname -> d")
            self._submit_callback_method(
                self._u,
                self._v,
                self._nd_type1,
                EdgeTypes.CNAME,
                self._nd_type1,
                e_data=('owner',self._owners)
            )

        if len(self._du) > 0:
            #must submit reverse edge separately
            self._submit_callback_method(
                self._du,
                self._dum_dv,
                self._nd_type1,
                EdgeTypes.CNAME,
                self._nd_type2,
                v_data={
                    'domain_name': self._dum_d_names,
                    'depth': self._dum_d_depth,
                    'parent_domains': [get_domains_parent_domains(domain) for domain in self._dum_d_names]
                },
                e_data=("owner",self._d_du_owners)
            )
            self._submit_callback_method(
                self._dum_dv,
                self._du,
                self._nd_type2,
                EdgeTypes.CNAME,
                self._nd_type1 ,
                e_data=("owner",self._d_du_owners)
            )

    def _connect_nodes_w_cname(self, cname_tup: tuple[bool, int, list[int], list[str]]) -> tuple[bool, list[int], list[int], list[int]]:
        """
        Method for connecting domains with their CNAME domain which is either in datasets or dummy domain is created
        instead. For dummy domain option it only creates edges in one way, the other way is created by submitting in
        reversed relation.
        :param cname_tup: Tuple containing flag (`bool`) indicating if this tuple is dummy domain or not, id of domain
        or dummy domain (`int`), and list of node_ids (`list[int]`) that will be connected to their cname
        :return: Tuple with (flag indicating if these edges are for dummy or normal domain, u, v)
        """

        cname_id = cname_tup[self._DOMAINS_ID]
        u = []
        owner = []

        for cnt in range(len(cname_tup[self._DOMAINS_LIST])):
            u_id = cname_tup[self._DOMAINS_LIST][cnt]
            if u_id != cname_id:
                u.append(u_id)
                owner.append(cname_tup[self._DOMAIN_NAMES_LIST][cnt])

        #u = [u_id for u_id in cname_tup[self._DOMAINS_LIST] if u_id != cname_id]
        v = [cname_id] * len(u)
        #owner = copy.deepcopy(u) #owner is domain that has cname entry

        if cname_tup[self._DOMAINS_TYPE] == self._DOMAIN:
            u[:], v[:] = u + v, v + u
            owner[:] = owner + owner #reverse edges but both half's have same order

        return cname_tup[self._DOMAINS_TYPE], u, v, owner

    def _create_edges(self):

        with ThreadPoolExecutor(max_workers=16) as executor:
            futures = [
                executor.submit(self._connect_nodes_w_cname, cname_tup) for cname_tup in self._domains.values()
                if len(cname_tup[self._DOMAINS_LIST]) > 1 or self._mode == self.LONE_CNAMES
            ]

            #TODO mode to toggle this
            #if len(cname_tup[self._DOMAINS_LIST]) > 1
            # no connection can be made with one domain

            for future in futures:
                result = future.result()
                if result is not None:
                    edge_t, u, v, owners = result

                    if edge_t == self._DUMMY:
                        self._du.extend(u)
                        self._dum_dv.extend(v)
                        self._d_du_owners.extend(owners)
                    else:
                        self._u.extend(u)
                        self._v.extend(v)
                        self._owners.extend(owners)

    def _create_domain_batches(self) -> list[list[str]]:

        domain_names = list(self._domains.keys())
        batches = []

        for start in range(0, len(domain_names), self._BATCH_SIZE):
            batches.append(domain_names[start:start + self._BATCH_SIZE])

        return batches

    def _find_domains_in_db(self, domains: list[str]) -> None:

        match = {
            "$and": [{"domain_name": {"$in": domains}}, self._match[0]["$match"]]
        } if len(self._match) != 0 else {"domain_name": {"$in": domains}}

        found = self._collection.find(match, {"domain_name": 1, "_id": 0, "node_id": 1})

        for doc in found:
            self._domains[doc["domain_name"]] = (self._DOMAIN, int(doc['node_id']),
                                                 self._domains[doc["domain_name"]][self._DOMAINS_LIST],
                                                 self._domains[doc["domain_name"]][self._DOMAIN_NAMES_LIST]
                                                 )
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

    def _give_ids_to_dummy_domains(self):

        dummy_id = 0
        for key in self._domains.keys():
            if self._domains[key][self._DOMAINS_ID] == -1:
                self._domains[key] = replace(self._domains[key],self._DOMAINS_ID,dummy_id) #(self._DUMMY, dummy_id, self._domains[key][self._DOMAINS_LIST])
                dummy_id += 1

                #based on the chosen mode dummy domains are created or not
                if self._mode == self.LONE_CNAMES or len(self._domains[key][self._DOMAINS_LIST]) > 1:
                    self._dum_d_names.append(key)
                    self._dum_d_depth.append(domain_depth(key))


    def _match_entries_with_same_cname(self):

        cursor = self._collection.aggregate(self._pipeline, batchSize=10000)

        for doc in cursor:
            if doc.get('dns'):
                if doc['dns']['CNAME']['value'] not in self._domains:
                    self._domains[doc['dns']['CNAME']['value']] = (
                        self._DUMMY,
                        -1,
                        [int(doc['node_id'])],
                        [str(doc['domain_name'])]
                    )
                else:
                    self._domains[doc['dns']['CNAME']['value']][self._DOMAINS_LIST].append(int(doc['node_id']))
                    self._domains[doc['dns']['CNAME']['value']][self._DOMAIN_NAMES_LIST].append(str(doc['domain_name']))

        MyLogger.get_instance().log("Stored all CNAME domains in the internal structure")
        self._find_cnames_in_db()
        self._give_ids_to_dummy_domains()
        MyLogger.get_instance().log("Found all CNAME domains that are also in the database")
        cursor.close()

    def _compute(self):
        MyLogger.get_instance().log("Starting to match CNAME entries...")
        self._match_entries_with_same_cname()
        MyLogger.get_instance().log("Creating CNAME edges...")
        self._create_edges()
        MyLogger.get_instance().log("All CNAME edges created")
        self._submit_result()
        MyLogger.get_instance().log("Submitted all CNAME edges")
        del self._u, self._v, self._du, self._dum_dv, self._domains
