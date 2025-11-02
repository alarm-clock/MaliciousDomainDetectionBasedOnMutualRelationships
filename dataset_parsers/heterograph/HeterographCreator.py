import copy
import json
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from dgl import DGLGraph
from pymongo import MongoClient
import torch as th
from dataset_parsers.Graph import create_hetero_graph
from dataset_parsers.heterograph.SubdomainEdge import SubdomainEdge
from dataset_parsers.heterograph.CNAMEEdge import CNAMEEdge
from dataset_parsers.db.ParallelDBParser import ParallelDBParser
from dataset_parsers.heterograph.ipv4_parallel_api import IPV4ParallelAPI
from misc.Logger import MyLogger
from misc.helper_func import parse_ranges, add_project_into_pipeline
import traceback

class HeterographCreator:

    def __init__(self, edge_types: str | None = None, ranges: str | None = None, no_lone_nd: bool = False, client: str = 'localhost', port: int = 27017, db: str = "datasets", collection: str = "domains", pwd: str = None,
                 user: str = None):

        if pwd is not None and user is not None:
            self.client = MongoClient(f"mongodb://{user}:{pwd}@{client}:{port}/{db}")
        else:
            self.client = MongoClient(client, port)
        self._db = self.client[db]
        self._collection = self._db[collection]
        self._no_lone_nd = no_lone_nd
        self._edge_type_workers = []

        self._ranges, max_id = self._create_or_conditions(ranges)
        self._n_nodes = self._collection.count_documents({}) if ranges is None else max_id

        self._edges: dict[tuple[str,str,str], tuple[th.Tensor, th.Tensor]] = {}
        self._weights: dict[tuple[str,str,str], th.Tensor] = {}
        self._submit_lock = threading.Lock()
        self._known_edges = ['subdomain','subdomain_of','cname','ipv4']
        self._edge_types: list[str] = []

        self._err = False

        if edge_types is not None:
            self._parse_edge_types(edge_types)

    def _parse_edge_types(self, edge_types: str) -> None:
        splited_types = edge_types.split(',')
        for edge_type_str in splited_types:
            edge_type_str = edge_type_str.strip()
            self._edge_types.append(edge_type_str)

    @staticmethod
    def _create_or_conditions(ranges: str | None) -> tuple[list | None, int]:
        try:
            ranges_list = parse_ranges(ranges)
        except ValueError as _:
            return None, -1

        if ranges_list is None:
            MyLogger.get_instance().log("Heterograph is using all collection entries to create graph")
            return [], 0

        MyLogger.get_instance().log("Heterograph is using entries with node_id in ranges intervals: " + str(ranges))
        or_conditions = [ {"node_id": {"$gte": start, "$lte": end}} for start, end in ranges_list ]
        return [{"$match": {"$or": or_conditions}}], ranges_list[len(ranges_list)-1][1]

    @classmethod
    def from_config(cls, config: str, edge_types: str | None = None, ranges: str | None = None, no_lone_nd: bool = False):

        with open(config) as f:
            conf = json.load(f)

            if conf.get('pwd'):
                return cls(edge_types, ranges, no_lone_nd, conf["client"], conf["port"], conf["db"], conf["collection"], conf["pwd"],
                           conf["user"])
            else:
                return cls(edge_types, ranges ,no_lone_nd, conf["client"], conf["port"], conf["db"], conf["collection"])

    def identify(self) -> str:
        return 'HeterographCreator'

    def submit_edges(self, u: list[int], v: list[int], edge_type: str, weights: list | None = None) -> None:

        self._submit_lock.acquire()
        try:
            self._edges[("d",edge_type,"d")] = (th.Tensor(u).to(th.int), th.Tensor(v).to(th.int))
            if weights is not None:
                self._weights[("d",edge_type,"d")] = th.Tensor(weights).to(th.float)
            print(f"All edges of type {edge_type} were created")
        except Exception as e:
            MyLogger.get_instance().log(repr(e))
            self._err = True
        self._submit_lock.release()

    def _check_edge_strs(self, edge_strs: list[str]) -> bool:

        if len(edge_strs) <= 0:
            print("Must specify at least one edge type, available edge types are: cname, subdomain, subdomain_of, ipv4", file=sys.stderr)
            return False

        for edge_str in edge_strs:
            if edge_str not in self._known_edges:
                print(f"Unknown edge type: {edge_str}", file=sys.stderr)
                MyLogger.get_instance().log(f"Unknown edge type: {edge_str}")
                return False

        return True

    def _get_subdomain_edges(self, do_subdomain: bool, do_subdomain_of: bool):

        sub_edge = SubdomainEdge(self, self._collection, copy.deepcopy(self._ranges), do_subdomain, do_subdomain_of)
        sub_edge.start()
        self._edge_type_workers.append(sub_edge)

    def _get_cname_edges(self):
        cname_edge = CNAMEEdge(self, self._collection, copy.deepcopy(self._ranges))
        cname_edge.start()
        self._edge_type_workers.append(cname_edge) #

    def _get_ipv4_edges(self):

        parallel_ipv4_parser = IPV4ParallelAPI(self, self._collection, copy.deepcopy(self._ranges))
        parallel_ipv4_parser.start()
        self._edge_type_workers.append(parallel_ipv4_parser)

    def _parse_label(self, doc) -> tuple[int, int]:
        return int(doc['node_id']), int(doc['label'].find("benign") != -1)

    def _get_labels(self) -> list[int]:

        MyLogger.get_instance().log("Getting labels...")
        project = [{"$match": { "node_id": {"$lte": self._n_nodes}}}]
        add_project_into_pipeline({'_id': 0, 'label': 1, 'node_id': 1}, project)
        labels_w_ids: list[tuple[int, int]] = []
        cursor = self._collection.aggregate(project, batchSize=10000)

        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(self._parse_label, doc) for doc in cursor]

            for future in futures:
                result = future.result()
                if result:
                    labels_w_ids.append(result)

        labels_w_ids = sorted(labels_w_ids, key=lambda x: x[0])  #sort by node id

        _ , labels = zip(*labels_w_ids)
        MyLogger.get_instance().log("Got and sorted all labes")
        cursor.close()
        return list(labels)

    def _debug_edges_by_type(self):
        MyLogger.get_instance().debug_log("Printing debug info ->", False)
        MyLogger.get_instance().debug_log(f"Used ranges are: {self._ranges}" if len(self._ranges) != 0 else "No ranges were used", False, False)
        MyLogger.get_instance().debug_log("Edges by edge types:", False, False)

        for edge_type, edges in self._edges.items():
            MyLogger.get_instance().debug_log(f"Edge type {edge_type[1]}:",False, False)
            MyLogger.get_instance().debug_log(f"Length of U = {len(edges[0])} and length of V = {len(edges[1])}",False, False)
            MyLogger.get_instance().debug_log(f"{edges[0]}",False, False)
            MyLogger.get_instance().debug_log(f"{edges[1]}",False, False)


    def createHeterograph(self, edge_types: list[str] | None = None) -> DGLGraph | None:

        if self._ranges is None:
            return None
        if edge_types is None:
            edge_types = self._edge_types
        if not self._check_edge_strs(edge_types):
            return None

        MyLogger.get_instance().log("Creating Heterograph...")

        if "subdomain" in edge_types:
            MyLogger.get_instance().log("Creating subdomain edges" + " and subdomain_of edges" if 'subdomain_of' in edge_types else "")
            self._get_subdomain_edges(True, 'subdomain_of' in edge_types)
        elif 'subdomain_of' in edge_types:
            MyLogger.get_instance().log("Creating subdomain_of edges")
            self._get_subdomain_edges(False, True)
        if 'cname' in edge_types:
            MyLogger.get_instance().log("Creating cname edges")
            self._get_cname_edges()
        if 'ipv4' in edge_types:
            MyLogger.get_instance().log("Creating ipv4 edges")
            self._get_ipv4_edges()

        for w in self._edge_type_workers:
            w.join()

        if self._err:
            return None

        MyLogger.get_instance().log("Created all edges...")
        labels= self._get_labels()
        weights = self._weights if self._weights.keys().__len__() != 0 else None

        #self._debug_edges_by_type()

        try:

            MyLogger.get_instance().log("Creating dgl heterograph...")
            if not self._ranges:
                g = create_hetero_graph(self._edges, weights , labels, self._n_nodes)
            else:
                g = create_hetero_graph(self._edges, weights, labels)
            MyLogger.get_instance().log("Created dgl heterograph")
        except Exception as e:
            traceback.print_exc()
            MyLogger.get_instance().log(repr(e))
            g = None

        return g
