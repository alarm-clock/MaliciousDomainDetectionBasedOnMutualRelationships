from typing import Any
from graph_repository.graph_main.graph_editing.common.GraphRequest import GraphRequest
from graph_repository.graph_main.graph_editing.common.RequestPriority import RequestPriority
from graph_repository.graph_main.graph_editing.common.RequestStates import RequestStates
from graph_repository.workers.common.GraphTypes import NodeTypes
from graph_repository.Neo4jDBClient import Neo4jDBClient
from graph_repository.workers.common.Enums import EditTypes, CallbackWhen
from graph_repository.workers.common.EditWorker import EDIT_WORKER_REGISTRY, EditWorker
from graph_repository.graph_main.GraphRepository import GraphRepository
from graph_repository.graph_main.graph_editing.DomainFiltering import basic_filter_domains
from misc.Pair import replace
from misc.Logger import MyLogger
from misc.PackageImporter import get_options_from_registry
from threading import Lock
import json


class AddRequest(GraphRequest):
    _EDGE_DATA_LOCATION = 1
    _E_EDGES_LOC = 1
    _E_QUERY_LOC = 0
    _N_NODES_LOC = 2
    _N_EDIT_T_LOC = 1
    _N_NODE_T_LOC = 0

    #TODO how to parse data for the graph
    def __init__(self, domains: list[dict], priority: RequestPriority, timeout: float = 1200.0):
        super().__init__(domains, priority, timeout, basic_filter_domains)

        #               group       node_type   edit_type     rows
        self._nodes: dict[str, tuple[NodeTypes, EditTypes, list[dict]]] = {}

        #               group     query[q_str, unwind name] |  params for e creation, edges
        self._edges: dict[str, tuple[tuple[str, str] | dict[str, Any], list[dict]]] = {}

        #              group (str)  tuple[callback | None, callback | None, callback | None]
        self._callbacks: dict = {}

        self._du_domains: set[str] = set()

        self._req_callbacks: list[tuple[str, list[EditWorker.ReqCallbacks]]] = []

        self._nodes_lock = Lock()
        self._edges_lock = Lock()
        self._callback_lock = Lock()

    #@classmethod
    #def from_csv_file

    def submit_callback(self, callback, when: CallbackWhen, group: str):
        self._callback_lock.acquire()

        if self._callbacks.get(group) is None:
            default_tuple = (None, None, None)
            self._callbacks[group] = default_tuple

        MyLogger.get_instance().log_debug(f"Receiving callback {str(callback)} from group {group}")
        self._callbacks[group] = replace(self._callbacks[group], when.value, callback)

        self._callback_lock.release()

    def _parse_submitted_du_domains(self, nodes: list[dict]) -> None:

        for node in nodes:
            domain_name = node['domain_name']
            if domain_name not in self._du_domains:
                if self._nodes.get('du_domains_group') is None:
                    self._nodes['du_domains_group'] = (NodeTypes.DUMMY_DOMAIN, EditTypes.IGNORE_NEW, [node])
                else:
                    self._nodes['du_domains_group'][self._N_NODES_LOC].append(node)

        return

    def _add_node_ids_to_du_domains(self) -> None:

        driver: Neo4jDBClient = GraphRepository.get_instance().get_neo4j_driver()
        if self._nodes.get('du_domains_group') is None:
            return

        free_ids = driver.get_free_node_id(NodeTypes.DUMMY_DOMAIN,
                                           len(self._nodes['du_domains_group'][self._N_NODES_LOC]))

        if type(free_ids) != int:
            for cnt, node in enumerate(self._nodes['du_domains_group'][self._N_NODES_LOC]):
                node['node_id'] = free_ids[cnt]
        else:
            self._nodes['du_domains_group'][self._N_NODES_LOC][0]['node_id'] = free_ids

        return

    def submit_nodes(self, nodes: list[dict], node_type: NodeTypes, group: str, edit_type: EditTypes) -> None:
        self._nodes_lock.acquire()

        MyLogger.get_instance().log_debug(f"Receiving {len(nodes)} nodes of type {node_type.value} from group {group}")

        if node_type == NodeTypes.DUMMY_DOMAIN:
            self._parse_submitted_du_domains(nodes)

        elif self._nodes.get(group) is None:
            self._nodes[group] = (node_type, edit_type, nodes)
        else:
            self._nodes[group][self._N_NODES_LOC].extend(nodes)

        self._nodes_lock.release()

    def submit_edges(self, edges: list[dict], edge_creation_query: tuple[str, str] | dict[str, Any], group: str):

        self._edges_lock.acquire()

        MyLogger.get_instance().log_debug(f"Receiving {len(edges)} edges from group {group}")

        if self._edges.get(group) is None:
            self._edges[group] = (edge_creation_query, edges)
        else:
            self._edges[group][self._EDGE_DATA_LOCATION].extend(edges)

        self._edges_lock.release()

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
                MyLogger.get_instance().log_warning(
                    "Do not use ALL option in combination with other options. Ignoring ALL option!")
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
                MyLogger.get_instance().log_error(
                    f"For some reason could not find worker {worker_name} even though it was registered")
                error = True
                break

            options = self._build_callback_options(req_callbacks)
            cls_instance = cls(self._domains, version, **options)
            is_thread = cls_instance.compute()

            if is_thread:
                workers_list.append(cls_instance)

        self._wait_on_workers(workers_list)
        return error

    def _add_maintenance_values_to_nodes(self, version: int) -> None:
        for n_t, _, nodes in self._nodes.values():
            for cnt in range(len(nodes)):
                nodes[cnt] = nodes[cnt] | (
                    {'graph_version': version, 'temporary': False} if n_t == NodeTypes.DOMAIN.value else {
                        'graph_version': version})

    #todo add option to just create node and edge without any other calculation because why the fuck not
    def _create_nodes(self, driver: Neo4jDBClient, version: int) -> None:

        self._add_node_ids_to_du_domains()
        self._add_maintenance_values_to_nodes(version)

        for group, data in self._nodes.items():
            MyLogger.get_instance().log_debug(f"Creating nodes for group {group}")
            #print(group, data[self._N_NODES_LOC])
            driver.create_nodes(data[self._N_NODE_T_LOC], data[self._N_NODES_LOC], data[self._N_EDIT_T_LOC])

        MyLogger.get_instance().log_debug(f"Created all {len(self._nodes.keys())} nodes")
        return

    def _create_edges(self, driver: Neo4jDBClient) -> None:

        for group, edges in self._edges.items():
            #print(group, edges)
            MyLogger.get_instance().log_debug(f"Creating edges for {group}")
            driver.create_edges(edges[self._E_QUERY_LOC], edges[self._E_EDGES_LOC])

        MyLogger.get_instance().log_debug(f"Created all {len(self._edges.keys())} edges")
        driver.wait_for_index_creation(None)
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
        self._stop_wait()

        if self._canceled:
            MyLogger.get_instance().log_debug(
                f"Add request {self.id} is canceled before it could edit but after graph copy was created")
            if self.state != RequestStates.TIMEOUT:
                self.state = RequestStates.CANCELED
            del self._domains
            return False

        get_options_from_registry(EDIT_WORKER_REGISTRY, self._req_callbacks)
        if self._dispatch_workers(version):
            self.state = RequestStates.ERROR
            del self._domains
            return False

        self._edit_graph(version)
        self.state = RequestStates.DONE
        del self._domains, self._nodes, self._edges, self._du_domains
        return True
