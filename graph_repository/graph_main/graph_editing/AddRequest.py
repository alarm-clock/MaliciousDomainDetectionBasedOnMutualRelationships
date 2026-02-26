from typing import Any
import pkgutil
import importlib
from graph_repository.graph_main.graph_editing.common.GraphRequest import GraphRequest
from graph_repository.graph_main.graph_editing.common.RequestPriority import RequestPriority
from graph_repository.workers.common.GraphTypes import NodeTypes
from graph_repository.Neo4jDBClient import Neo4jDBClient
from graph_repository.workers.common.Enums import EditTypes, CallbackWhen
from graph_repository.workers.common.EditWorker import EDIT_WORKER_REGISTRY, EditWorker
from graph_repository.graph_main.GraphRepository import GraphRepository
from misc.Pair import replace
from misc.Logger import MyLogger
from threading import Lock
import json

#TODO everything must be done with CURRENT version of the graph!!!
#new graph version will be done outside of this class in the thread that will run this

class AddRequest(GraphRequest):
    #tim padom potrebujem to spravit ze sa mi parsnu data podobne ako v dataset importery a daju sa do formatu ze
    # #mozem ich mozem fuknut do query

    _NODE_DATA_LOCATION = 1
    _EDGE_DATA_LOCATION = 1
    _E_EDGES_LOC = 1
    _E_QUERY_LOC = 0
    _N_NODES_LOC = 2
    _N_EDIT_T_LOC = 1
    _N_NODE_T_LOC = 0

    #TODO how to parse data for the graph
    def __init__(self, domains: list[dict], priority: RequestPriority, timeout: float = 600.0):
        super().__init__(priority, timeout)
        self._domains = domains

        #               group       node_type   edit_type     rows
        self._nodes: dict[str, tuple[NodeTypes, EditTypes, list[dict]]] = {}

        #               group     query[q_str, unwind name] |  params for e creation, edges
        self._edges: dict[str, tuple[tuple[str, str] | dict[str, Any], list[dict]]] = {}

        #              group (str)  tuple[callback | None, callback | None, callback | None]
        self._callbacks: dict = {}

        self._req_callbacks: list[tuple[str, list[EditWorker.ReqCallbacks]]] = []

        self._nodes_lock = Lock()
        self._edges_lock = Lock()
        self._callback_lock = Lock()

    @classmethod
    def from_json_file(cls, json_file: str, priority: RequestPriority, timeout: float = 600.0):

        with open(json_file) as f:
            doms = json.load(f)
            if type(doms) != list:
                doms = [doms]

        return cls(doms, priority, timeout)

    @classmethod
    def from_json_str(cls, json_str: str, priority: RequestPriority, timeout: float = 600.0):
        doms = json.loads(json_str)
        if type(doms) != list:
            doms = [doms]

        return cls(doms, priority, timeout)

    #@classmethod
    #def from_csv_file

    def submit_callback(self, callback, when: CallbackWhen, group: str):
        self._callback_lock.acquire()

        if self._callbacks.get(group) is None:
            default_tuple = (None, None, None)
            self._callbacks[group] = default_tuple

        replace(self._callbacks[group], when.value, callback)

        self._callback_lock.release()

    def submit_nodes(self, nodes: list[dict], node_type: NodeTypes, group: str, edit_type: EditTypes) -> None:
        self._nodes_lock.acquire()

        if self._nodes.get(group) is None:
            self._nodes[group] = (node_type, edit_type, nodes)
        else:
            self._nodes[group][self._NODE_DATA_LOCATION].extend(nodes)

        self._nodes_lock.release()

    def submit_edges(self, edges: list[dict], edge_creation_query: tuple[str, str] | dict[str, Any], group: str):

        self._edges_lock.acquire()

        if self._edges.get(group) is None:
            self._edges[group] = (edge_creation_query, edges)
        else:
            self._edges[group][self._EDGE_DATA_LOCATION].extend(edges)

        self._edges_lock.release()

    def _register_workers(self):
        """
        Method for loading worker modules and storing their callback requirements in attribute `_req_callbacks`
        :return: None
        """

        import graph_repository.workers.dataset_edge_workers

        for _, module_name, _ in pkgutil.iter_modules(graph_repository.workers.dataset_edge_workers.__path__):
            importlib.import_module(f"graph_repository.workers.dataset_edge_workers.{module_name}")

        classes = ""
        for cls in EDIT_WORKER_REGISTRY.values():
            self._req_callbacks.extend(cls.available_options)
            classes += f"{cls.worker_name},"

        MyLogger.get_instance().log_debug(f"Loaded workers: {classes[:-1]} from module dataset_edge_workers")

    def _build_callback_options(self, options: list[EditWorker.ReqCallbacks]) -> dict[str, Any]:

        available_callbacks = {
            EditWorker.ReqCallbacks.NODE: self.submit_nodes,
            EditWorker.ReqCallbacks.EDGE: self.submit_edges,
            EditWorker.ReqCallbacks.CALLBACK: self.submit_callback,
        }
        options_dict = {}

        if len(options) == 1 and options[0] == EditWorker.ReqCallbacks.ALL:
            options = list(available_callbacks.keys())

        for option in options:
            if option == EditWorker.ReqCallbacks.ALL:
                MyLogger.get_instance().log_warning("Do not use ALL option in combination with other options. Ignoring all option!")
                continue

            options_dict[option.value] = available_callbacks[option]

        return options_dict

    def _wait_on_workers(self, worker_list: list[EditWorker]) -> None:

        for worker in worker_list:
            worker.join()

    def _dispatch_workers(self, version: int) -> bool:

        workers_list: list[EditWorker] = []
        error = False

        for worker_name, req_callbacks in self._req_callbacks:
            cls = EDIT_WORKER_REGISTRY.get(worker_name)

            if cls is None:
                MyLogger.get_instance().log_error(f"For some reason could not find worker {worker_name} even though it was registered")
                error = True
                break

            options = self._build_callback_options(req_callbacks)
            cls_instance = cls(self._domains, version, **options)
            is_thread = cls_instance.compute()

            if is_thread:
                workers_list.append(cls_instance)

        self._wait_on_workers(workers_list)
        return error

    def _add_maintenace_values_to_nodes(self, version: int) -> None:
        for n_t, _, nodes in self._nodes.values():
            for cnt in range(len(nodes)):
                nodes[cnt] = nodes[cnt] | ({'graph_version': version, 'temporary': False} if n_t == NodeTypes.DOMAIN.value else {'graph_version': version})


    #todo add option to just create node and edge without any other calculation because why the fuck not
    def _create_nodes(self, driver: Neo4jDBClient, version: int) -> None:

        self._add_maintenace_values_to_nodes(version)

        for group, data in self._nodes.items():
            MyLogger.get_instance().log_debug(f"Creating nodes for group {group}")
            driver.create_nodes(data[self._N_NODE_T_LOC],data[self._N_NODES_LOC],data[self._N_EDIT_T_LOC])

        MyLogger.get_instance().log_debug(f"Created all {len(self._nodes.keys())} nodes")
        return

    def _create_edges(self, driver: Neo4jDBClient) -> None:

        for group, edges in self._edges.items():
            MyLogger.get_instance().log_debug(f"Creating edges for {group}")
            driver.create_edges(edges[self._E_EDGES_LOC], edges[self._E_QUERY_LOC])

        MyLogger.get_instance().log_debug(f"Created all {len(self._edges.keys())} edges")
        return

    def _run_callbacks(self, which: CallbackWhen) -> None:

        for group, callbacks in self._callbacks.items():
            callback = callbacks[which.value]
            if callback is not None:
                MyLogger.get_instance().log_debug(f"Running callback for {group} at {which}...")
                callback()

    def _edit_graph(self, version: int):

        driver = GraphRepository.get_instance().get_neo4j_driver()
        self._run_callbacks(CallbackWhen.BEFORE_NODES)
        self._create_nodes(driver, version)
        self._run_callbacks(CallbackWhen.BETWEEN_NODES_EDGES)
        self._create_edges(driver)
        self._run_callbacks(CallbackWhen.AFTER_EDGES)
        driver.close()

    def edit(self, version: int) -> bool:

        if self._canceled:
            MyLogger.get_instance().log_debug(f"Request {self.id} is canceled before it could edit but after graph copy was created")
            return False

        self._register_workers()
        if self._dispatch_workers(version):
            return False

        self._edit_graph(version)
        return True