from typing import Any

from graph_repository.graph_main.graph_editing.common.GraphRequest import GraphRequest
from graph_repository.graph_main.graph_editing.common.RequestPriority import RequestPriority
from graph_repository.workers.common.GraphTypes import NodeTypes
from graph_repository.Neo4jDBClient import Neo4jDBClient
from graph_repository.workers.common.Enums import EditTypes, CallbackWhen
from misc.Pair import replace
from threading import Lock
import json


#TODO it must query graph to create edges for given node
#TODO everything must be done with CURRENT version of the graph!!!

class AddRequest(GraphRequest):
    #tim padom potrebujem to spravit ze sa mi parsnu data podobne ako v dataset importery a daju sa do formatu ze
    # #mozem ich mozem fuknut do query

    _NODE_DATA_LOCATION = 1
    _EDGE_DATA_LOCATION = 1

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

    #todo add option to just create node and edge without any other calculation because why the fuck not
    def _create_nodes(self):
        pass

    def _create_edges(self):
        pass

    def edit(self):
        pass
