import copy
import json
from dgl import DGLHeteroGraph
from pymongo import MongoClient
from functools import partial
from graph_repository.workers.common.DatasetWorker import DATASET_WORKER_REGISTRY
from graph_repository.dataset_creator.common.LabelExtractor import LabelExtractor
from graph_repository.workers.common.GraphTypes import NodeTypes, EdgeTypes
from graph_repository.dataset_creator.common.Graph import create_dgl_graph
from graph_repository.dataset_creator.DGLImporter import export_dgl_graph
from misc.Logger import MyLogger
from misc.PackageImporter import import_all_modules_from_package
from graph_repository.graph_repo_misc import parse_ranges
from graph_repository.Neo4jDBDriver import Neo4jDBDriver, CouldNotConnect
import torch as th
from threading import Lock
import sys

import traceback

class DatasetImporter:
    """
    Class for creating graph from the dataset stored in MongoDB and either returning it in DGL format or storing it into
    Neo4j DB. It serves as dispatcher for workers in `dataset_edge_workers` module.
    """

    _for_dgl = True

    def __init__(self, edge_types: str | None = None, ranges: str  | None = None, no_lone_nd: bool = False,
                 client: str = 'localhost',
                 port: int = 27017, db: str = "datasets", collection: str = "domains", pwd: str = None,
                 user: str = None, neo4j_conf: str | None = None):
        """
        Creates `DatasetImporter` instance that connects to MongoDB, prepares shared parts of aggregation pipeline, and finaly
        scans all available edge workers and their options.
        :param edge_types: `str` with edge types that will be created in format `\"edge_type1,edge_type2,...\"`. Workers declare available edge types.
        :param ranges: `str` with domain `node_id` ranges that will be used to create graph in format `\"bottom1,top1,bottom1,top2,...\"`
        :param no_lone_nd: `Deprecated`
        :param client: `str`
        :param port: `int`
        :param db: `str` database name
        :param collection: `str` collection name
        :param pwd: `str` password for connecting to database instance
        :param user: `str` user for connecting to database instance
        """

        self._neo4j_conf = neo4j_conf
        if pwd is not None and user is not None:
            self.client = MongoClient(f"mongodb://{user}:{pwd}@{client}:{port}/{db}")
        else:
            self.client = MongoClient(client, port)
        self._db = self.client[db]
        self._collection = self._db[collection]
        self._no_lone_nd = no_lone_nd

        self._label_worker: LabelExtractor | None = None
        self._edge_type_workers = []
        self._known_edges = []

        import_all_modules_from_package(
            "graph_repository.workers.dataset_edge_workers",
            DATASET_WORKER_REGISTRY,
            self._known_edges
        )

        self._err = False
        self._ranges, max_id = self.create_or_conditions(ranges)

        if self._ranges is None:
            self._err = True
            return

        if max_id == 2 ** 32:
            max_nd_id_doc = self._collection.find_one(sort=[("node_id", -1)])
            max_id = int(max_nd_id_doc["node_id"])

        self._n_nodes = self._collection.count_documents({}) if ranges is None else max_id

        self._edges: dict[tuple[str, str, str], tuple[th.Tensor, th.Tensor]] = {}

        self._edges_neo4j: dict[tuple[str, str, str], list[dict]] = {}

        self._e_data: dict[str, dict[tuple[str, str, str], th.Tensor]] = {}

        self._e_data_neo4j: dict[tuple[str, str, str], tuple[str, th.Tensor]] = {}

        #val name     #nd type, data
        self._n_data: dict[str, dict[str, list]] = {} #must be a list because in neo I can store string but in dgl I can't so while I gather this information for dgl I must filter all lists of strings

        self._n_data_neo4j: dict[str, list[dict]] = {}

        self._num_of_nodes_dict: dict[str, int] = {NodeTypes.DOMAIN.dgl: self._n_nodes}

        self._submit_lock = Lock()

        converted_e_types = self._parse_edge_types(edge_types)
        if converted_e_types is None:
            return

        self._edges_for_creation = self._check_edge_strs_and_get_cls(converted_e_types)

        if self._edges_for_creation is None:
            self._err = True

    @classmethod
    def from_config(cls, config: str, edge_types: str | None = None, ranges: str | None = None,
                    no_lone_nd: bool = False, neo_config: str | None = None):
        """
        Creates `DatabaseImporter` instance with MongoDb configuration stored in config
        :param config: `str` path to file containing connection MongoDB details in json format
        :param edge_types: `str` with edge types that will be created in format `\"edge_type1,edge_type2,...\"`. Workers declare available edge types.
        :param ranges: `str` with domain `node_id` ranges that will be used to create graph in format `\"bottom1,top1,bottom1,top2,...\"`
        :param no_lone_nd: `Deprecated`
        :return: Initialized instance of DatasetImporter class
        """
        with open(config) as f:
            conf = json.load(f)

            if conf.get('pwd'):
                return cls(edge_types, ranges, no_lone_nd, conf["client"], conf["port"], conf["db"], conf["collection"],
                           conf["pwd"], conf["user"], neo_config)
            else:
                return cls(edge_types, ranges, no_lone_nd, conf["client"], conf["port"], conf["db"], conf["collection"], neo4j_conf=neo_config)

    def _parse_edge_types(self, edge_types: str | None) -> list[str] | None:
        """
        Method for parsing edge types from string into list of types
        :param edge_types: `str` with edge types that will be created in format `\"edge_type1,edge_type2,...\"`. Workers declare available edge types.
        :return: List with edge types
        """

        if edge_types is None:
            return []

        res = []
        splited_types = edge_types.split(',')

        if len(splited_types) == 1 and splited_types[0] == 'all':
            return [ f'{worker_name}_all' for worker_name in DATASET_WORKER_REGISTRY.keys()]

        for edge_type_str in splited_types:
            edge_type_str = edge_type_str.strip()

            if edge_type_str == 'all':
                MyLogger.get_instance().log_error(f"All option must be used alone!!!")
                print("All option must be used alone!!!",file=sys.stderr)
                self._err = True
                return None

            res.append(edge_type_str)

        return res

    def _check_edge_strs_and_get_cls(self, edge_strs: list[str]) -> list[tuple[str, dict]] | None:
        """
        Method that checks if edge_types are available and extracts worker details for them, and if at least one edge type was given
        :param edge_strs: List of edge types that will be checked
        :return: List of tuples[class name, class kwargs] on success otherwise None
        """
        if len(edge_strs) <= 0:
            opt = ""
            for _, e_type, _ in self._known_edges:
                opt += (e_type + ',')

            print(f"Must specify at least one edge type, available edge types are: {opt[:-1]}", file=sys.stderr)
            return None

        edges_with_kwargs = []

        for edge_str in edge_strs:

            e_tup = next((tup for tup in self._known_edges if tup[1] == edge_str), None)

            if e_tup is None:
                print(f"Unknown edge type: {edge_str}", file=sys.stderr)
                MyLogger.get_instance().log_error(f"Unknown edge type: {edge_str}")
                return None

            cls, _, kwargs = e_tup
            edges_with_kwargs.append((cls, kwargs))

        return edges_with_kwargs

    @staticmethod
    def create_or_conditions(ranges: str | None) -> tuple[list | None, int]:
        """
        Method that creates or conditions (node_id filter) for mongodb aggregation pipeline
        :param ranges: `str` with domain `node_id` ranges that will be used to create graph in format `\"bottom1,top1,bottom1,top2,...\"`
        :return: Tuple[ list of tuples [bottom,top] or None if ranges were in incorrect format, Max node_id]
        """
        try:
            ranges_list = parse_ranges(ranges)
        except ValueError as _:
            return None, -1

        if ranges_list is None:
            MyLogger.get_instance().log("Heterograph is using all collection entries to create graph")
            return [], 0

        MyLogger.get_instance().log("Heterograph is using entries with node_id in ranges intervals: " + str(ranges))
        or_conditions = [{"node_id": {"$gte": start, "$lte": end}} for start, end in ranges_list]
        return [{"$match": {"$or": or_conditions}}], ranges_list[len(ranges_list) - 1][1]

    def _filter_and_convert_n_data_for_dgl(self) -> dict[str, dict[str, th.Tensor]]:
        """
        Method that converts node_data into from lists into tensors, list of data types that are not supported by tensor will not be converted
        :return: Node data in DGL format stored in tensors
        """

        res = {}

        for data_type, val in self._n_data.items():

            try:
                tensor_dict = {}
                for n_t, data in val.items():

                    tensor_dict[n_t] = th.Tensor(data)

                res[data_type] = tensor_dict

            except Exception:
                MyLogger.get_instance().log_warning(f"Could not convert {data_type} for dgl because it is not numeric")

        return res

    def _store_num_nodes(self,t: NodeTypes, n: int) -> None:
        """
        Method for storing number of nodes of given node type
        :param t: `NodeTypes` Node type
        :param n: `int` number of nodes
        :return: None
        """

        if self._num_of_nodes_dict.get(t.dgl) is None:
            self._num_of_nodes_dict[t.dgl] = n
        elif n > self._num_of_nodes_dict[t.dgl]:
            self._num_of_nodes_dict[t.dgl] = n


    def _store_n_data_mongo(self, n_t: str, n_data: dict[str, list]) -> None:
        """
        Method for storing node data
        :param n_t: `NodeTypes` Node type
        :param n_data: `dict[str, list]` with node data
        :return: None
        """

        for data_type, data in n_data.items():

            if self._n_data.get(data_type) is None:
                self._n_data[data_type] = {n_t: data}

            else:
                self._n_data[data_type][n_t] = data

    def _store_n_data_neo4j(self, n_t: str, n_data: dict[str, list]) -> None:

        keys = list(n_data.keys())
        rows = [dict(zip(keys, values)) for values in zip(*n_data.values())]

        if "node_id" not in keys:

            for cnt, row in enumerate(rows):
                row["node_id"] = cnt


        if self._n_data_neo4j.get(n_t) is None:
            self._n_data_neo4j[n_t] = rows

        else:
            if len(rows) != len(self._n_data_neo4j[n_t]):
                print("Length of stored rows and n_data list does not match!!!!",file=sys.stderr)
                MyLogger.get_instance().log_error(f"Length of stored rows and n_data list does not match!!!!")
                self._err = True
                return

            for cnt in range(len(rows)):
                self._n_data_neo4j[n_t][cnt] = self._n_data_neo4j[n_t][cnt] | rows[cnt]


    def _store_n_data(self, n_t: NodeTypes, n_data: dict[str, list]) -> None:

        if self._for_dgl:
            self._store_n_data_mongo(n_t.dgl, n_data)
        else:
            self._store_n_data_neo4j(n_t.neo4j, n_data)

    def _store_edge(self,e_type: tuple[NodeTypes,EdgeTypes,NodeTypes], u: list[int], v: list[int], e_data: tuple[str, list] | None = None) -> None:

        if self._for_dgl:
            e_type_dgl = (e_type[0].dgl, e_type[1].value, e_type[2].dgl)
            self._edges[e_type_dgl] = (th.Tensor(u).to(th.int), th.Tensor(v).to(th.int))
            if e_data is not None:
                name, data = e_data
                self._e_data[name] = {e_type_dgl: th.Tensor(data)}

        else:
            rows = []
            e_type_neo4j = (e_type[0].neo4j, e_type[1].value, e_type[2].neo4j)
            for cnt in range(len(u)):

                if e_data is None:
                    rows.append({"u": u[cnt], "v": v[cnt]})
                else:
                    rows.append({"u": u[cnt], "v": v[cnt], e_data[0]: e_data[1][cnt]})

            self._edges_neo4j[e_type_neo4j] = rows

    def submit_edges(self, u: list[int], v: list[int], u_t: NodeTypes, e_t: EdgeTypes, v_t: NodeTypes,
                     u_data: dict[str, list] | None = None, e_data: tuple[str, list] | None = None,
                     v_data: dict[str, list] | None = None) -> None:
        """
        Method for submitting created edges, node data, and edge data. This method can be called asynchronously from workers.
        :param u: `list[int]` of edge starts
        :param v: `list[int]` of edge ends
        :param u_t: `NodeTypes` Node type of u
        :param e_t: `EdgeTypes` Edge type
        :param v_t: `NodeTypes` Node type of v
        :param u_data: `dict[str, list]` with node data for u, str is name of the data, list must be the same length as u
        :param e_data: `dict[str, list]` with edge data, str is name of the data, list must be the same length as both u and v
        :param v_data: `dict[str, list]` with node data for v, str is name of the data, list must be the same length as v
        :return: None
        """

        self._submit_lock.acquire()
        e_type_tup = (u_t, e_t, v_t)
        try:
            MyLogger.get_instance().log(f"Receiving {len(u)} edges for {u_t.neo4j}-{e_t.value}->{v_t.neo4j}, e_data is {e_data[0] if e_data is not None else None}, u_data is {[key for key in u_data.keys()] if u_data is not None else None}, v_data is {[key for key in v_data.keys()] if v_data is not None else None}")
            self._store_edge(e_type_tup, u, v, e_data)

            if u_data is not None:
                self._store_n_data(u_t, u_data)
            if v_data is not None:
                self._store_n_data(v_t, v_data)

            if len(u) > 0 and len(v) > 0:
                self._store_num_nodes(u_t, max(u) + 1) #number of nodes must be larger than max id
                self._store_num_nodes(v_t, max(v) + 1)

        except Exception as e:
            MyLogger.get_instance().log_error(str(e))
            print(traceback.print_exc())
            self._err = True

        self._submit_lock.release()

    def _wait_on_workers(self):
        """
        Method for waiting on all workers
        :return: None
        """
        for worker in self._edge_type_workers:
            worker.join()

        self._label_worker.join()
        labels = self._label_worker.result
        self._store_n_data(NodeTypes.DOMAIN, labels)

    def _start_workers(self) -> None:
        """
        Method for starting the workers with their configuration that will create given edge types. Workers are stored in _edge_type_workers
        :return: None
        """

        for cls, kwargs in self._edges_for_creation:
            worker_cls = DATASET_WORKER_REGISTRY.get(cls)

            if not worker_cls:
                MyLogger.get_instance().log_error(f"Could not find worker class for worker type: {cls} which is very strange")
                self._err = True
                return

            MyLogger.get_instance().log(f"Starting worker {cls}...")
            if kwargs is not None:
                worker = worker_cls(self.submit_edges, self._collection, copy.deepcopy(self._ranges), **kwargs)
            else:
                worker = worker_cls(self.submit_edges, self._collection, copy.deepcopy(self._ranges))

            worker.start()
            self._edge_type_workers.append(worker)

        MyLogger.get_instance().log(f"Starting label extractor...")
        self._label_worker = LabelExtractor.for_dgl(self._collection, self._n_nodes) if self._for_dgl else LabelExtractor.for_neo4j(self._collection, copy.deepcopy(self._ranges))
        self._label_worker.start()

    def _debug_edges_by_type(self):
        MyLogger.get_instance().log_debug("Printing debug info ->", False)
        MyLogger.get_instance().log_debug(
            f"Used ranges are: {self._ranges}" if len(self._ranges) != 0 else "No ranges were used", False, False)
        MyLogger.get_instance().log_debug("Edges by edge types:", False, False)

        for edge_type, edges in self._edges.items():
            MyLogger.get_instance().log_debug(f"Edge type {edge_type[0]} -> {edge_type[1]} -> {edge_type[2]} :", False, False)
            MyLogger.get_instance().log_debug(f"Length of U = {len(edges[0])} and length of V = {len(edges[1])}", False,
                                              False)
            MyLogger.get_instance().log_debug(f"{edges[0]}", False, False)
            MyLogger.get_instance().log_debug(f"{edges[1]}", False, False)

        for key, val in self._n_data.items():
            MyLogger.get_instance().log_debug(f"{key}: {val}", False, False)

        for key, val in self._e_data.items():
            MyLogger.get_instance().log_debug(f"{key}: {val}", False, False)

    def _create_graph_from_dataset(self) -> None:
        """
        Method for creating graph from dataset. Graph structure is stored in instance attributes.
        :return: None
        """

        if self._err:
            return

        MyLogger.get_instance().log("Creating Heterograph...")
        self._start_workers()

        if self._err:
            #TODO stop workers on error
            return

        self._wait_on_workers()
        return

    @staticmethod
    def _create_domain_name_indexes(driver: Neo4jDBDriver) -> bool:

        dummy_labels = NodeTypes.get_supporting_dummies_n_t()
        dummy_labels.append(NodeTypes.DOMAIN)
        dummy_labels.append(NodeTypes.DUMMY_DOMAIN)

        for label in dummy_labels:
            query = f"""
            CREATE INDEX Domain_Name_Index_{label.neo4j} 
            IF NOT EXISTS
            FOR (d: {label.neo4j})
            ON (d.domain_name);
            """

            driver.execute_write(query)

        try:
            driver.wait_for_index_creation(["Domain_Name_Index_"+label.neo4j for label in dummy_labels],10.0)
        except Exception:
            return False

        return True

    @staticmethod
    def replace_other_dummies_with_default_dummy_domain(driver: Neo4jDBDriver) -> None:

        dummy_labels =  NodeTypes.get_supporting_dummies_n_t()
        if not driver.check_label_exists(NodeTypes.DUMMY_DOMAIN):
            MyLogger.get_instance().log_debug("There is no dummy domain in graph, creating node_id counter for them")
            driver.check_and_create_node_id_cnt(NodeTypes.DUMMY_DOMAIN)

        DatasetImporter._create_domain_name_indexes(driver)

        MyLogger.get_instance().log_debug(f"Found service dummy domains in graph are {dummy_labels}")

        for label in dummy_labels:

            MyLogger.get_instance().log(f"Converting {label} domains to {NodeTypes.DUMMY_DOMAIN.neo4j}...")

            #TODO if something here stops working most likely the problem will be free node id query and locks
            #input("wait: ")
            query = f"""
            CALL apoc.periodic.iterate(
                "MATCH (n: {label.neo4j}) RETURN n",
                "
                    MERGE (du_match: {NodeTypes.DUMMY_DOMAIN.neo4j} {{domain_name: n.domain_name}})
                    ON CREATE
                        SET du_match.node_id = null,
                            du_match.graph_version = 1,
                            du_match.depth = n.depth,
                            du_match.parent_domains = n.parent_domains
                    WITH n, du_match
        
                    CALL(du_match){{
                        WITH du_match
                        WHERE du_match.node_id IS NULL
                
                        {Neo4jDBDriver.get_free_node_id_query(NodeTypes.DUMMY_DOMAIN, True)}
                    
                        SET du_match.node_id = free_node_id        
                    }}
                
                {Neo4jDBDriver.get_node_replace_query('n', 'du_match', label)} 
                ",
                {{
                    batchsize: 1,
                    parallel: false,
                    batchMode: 'SINGLE'
                }}
            ) YIELD batch
            RETURN batch
            """

            max_id = driver.get_max_id_of_node_type(label)
            if max_id is None:
                continue

            res = driver.execute_write(query)
            MyLogger.get_instance().log(str(res[0]))

        MyLogger.get_instance().log("Converted all service dummy nodes")
        return

    def _import_into_neo4j(self):

        if self._neo4j_conf is None:
            print("Neo4j connection config file not provided, exiting!", file=sys.stderr)
            MyLogger.get_instance().log_error("Neo4j connection config file not provided, exiting!")
            return

        try:
            client = Neo4jDBDriver.from_config(self._neo4j_conf)
        except CouldNotConnect:
            return

        if client is None:
            return

        client.set_new_graph_version_node(1)
        client.set_new_current_graph_version_node(1)

        for n_t, rows in self._n_data_neo4j.items():

            if len(rows) < 1:
                continue

            MyLogger.get_instance().log(f"Creating {len(rows)} {n_t} nodes in neo4j")
            #items_str = ",".join([str(key) + ": row." + str(key) for key in list(rows[0].keys())])

            constraint_query = f"""
            CREATE CONSTRAINT {n_t}_unique_node_id_version_combo
            IF NOT EXISTS
            FOR (t:{n_t})
            REQUIRE (t.node_id, t.graph_version) IS UNIQUE
            """
            client.execute_write(constraint_query)

            pre_filled = partial(client.create_nodes,n_t)
            client.send_query_in_batches_func(pre_filled, rows)

            index_query = f"""
            CREATE INDEX {n_t}NodeIdIndex
            IF NOT EXISTS
            FOR (n:{n_t})
            ON (n.node_id);
            """
            client.execute_write(index_query)
            client.check_and_create_node_id_cnt(n_t,client.get_max_id_of_node_type(n_t) + 1)

        client.wait_for_index_creation([n_t+"NodeIdIndex" for n_t in self._n_data_neo4j.keys()])

        for edge_type, edges in self._edges_neo4j.items():

            if len(edges) == 0:
                continue

            u_t, e_t, v_t = edge_type

            MyLogger.get_instance().log(f"Creating {len(edges)} {u_t}-{e_t}->{v_t} edges in neo4j")

            param_name = ""
            for key in edges[0].keys():
                if key != "u_id" and key != "v_id": param_name = key

            weight_option = Neo4jDBDriver.EdgeCreationQueryOptions.WEIGHT_NO_REVERSE if param_name != "" else Neo4jDBDriver.EdgeCreationQueryOptions.NO_WEIGHT_NO_REVERSE
            edge_creation_option = {
                Neo4jDBDriver.E_NODE_T1: u_t,
                Neo4jDBDriver.E_NODE_T2: v_t,
                Neo4jDBDriver.E_OPTION: weight_option,
                Neo4jDBDriver.E_EDGE_VALUE_NAME: param_name,
                Neo4jDBDriver.E_EDGE_T: e_t,
                Neo4jDBDriver.E_MATCH1: "node_id",
                Neo4jDBDriver.E_MATCH2: "node_id",
                Neo4jDBDriver.E_VERSION: 1,
                Neo4jDBDriver.E_NO_DUP: True
            }

            pre_filled = partial(client.create_edges,edge_creation_option)
            client.send_query_in_batches_func(pre_filled, edges)

        self.replace_other_dummies_with_default_dummy_domain(client)
        MyLogger.get_instance().log("Created whole graph")
        client.close()
        return

    def _add_maintenance_values_to_nodes(self):

        for n_t in self._n_data_neo4j.keys():
            for cnt in range(len(self._n_data_neo4j[n_t])):
                self._n_data_neo4j[n_t][cnt] = self._n_data_neo4j[n_t][cnt] | ({'graph_version': 1, 'temporary': False} if n_t == NodeTypes.DOMAIN.neo4j else {'graph_version': 1})

    def create_graph_and_import_to_neo4j(self):

        if self._neo4j_conf is None:
            print("Neo4j connection config not provided, exiting!", file=sys.stderr)
            MyLogger.get_instance().log_error("Neo4j connection config not provided, exiting!")

        if self._err:
            return

        self._for_dgl = False
        self._create_graph_from_dataset()

        if self._err:
            return

        self._add_maintenance_values_to_nodes()
        self._import_into_neo4j()


    def create_dgl_graph(self, export: str | None = None) -> DGLHeteroGraph | None:
        """
        Method for creating dgl_graph from dataset.
        :param export: `str | None` Path where dgl graph will be stored, None if it is not to be saved
        :return: `DGLHeteroGraph | None` Graph on success otherwise None
        """

        if self._err:
            return None

        self._create_graph_from_dataset()

        if self._err:
            return None

        self._debug_edges_by_type()
        g = create_dgl_graph(self._edges, self._filter_and_convert_n_data_for_dgl(), self._e_data,self._num_of_nodes_dict)

        if export is not None:
            export_dgl_graph(g, export)

        return g