from queue import PriorityQueue
from typing import TYPE_CHECKING, Optional
from graph_repository.Neo4jDBClient import Neo4jDBClient
from graph_repository.graph_main.graph_editing.EditConsumer import edit_loop, FinishType
from threading import Event, Thread
from graph_repository.graph_main.graph_editing.common.GraphRequest import GraphRequest, FinishRequest
from misc.Logger import MyLogger


class GraphRepository:

    _repository_instance_ = None

    def __new__(cls, *args, **kwargs):
        if GraphRepository._repository_instance_ is None:
            cls._repository_instance_ = super().__new__(cls)
            cls._repository_instance_._initialized = False

        return cls._repository_instance_

    def __init__(self, neo4j_conf: str):
        if not self._initialized:
            self._initialized = True
            self._request_q: PriorityQueue[GraphRequest | None] = PriorityQueue()
            self._neo4j_conf = neo4j_conf
            self._worker_stop_event = Event()
            self._stop_event = Event()
            self._edit_worker = Thread(target=edit_loop,args=(self._worker_stop_event,self._request_q, self._neo4j_conf), daemon=True)
            self._edit_worker.start()

    @staticmethod
    def get_instance(neo4j_conf: str| None = None):
        if GraphRepository._repository_instance_ is None:
            if neo4j_conf is not None:
                GraphRepository(neo4j_conf)
            else:
                return None
        return GraphRepository._repository_instance_

    def stop(self, finish_all_submitted_edits: FinishType = FinishType.FINISH_NONE) -> None:

        MyLogger.get_instance().log("Graph repository is being shut down")
        self._stop_event.set()

        if finish_all_submitted_edits == FinishType.FINISH_NONE:
            self._worker_stop_event.set()
        elif finish_all_submitted_edits == FinishType.FINISH_CURRENT:
            self._request_q.get_nowait()
            self._request_q.task_done()

        self._request_q.put(FinishRequest())
        self._edit_worker.join() #no timeout because I need to wait if worker is wrapping up and potentially finishing all work
                                 #maybe I will give it some time limit just in case

        #TODO add removal of temporary nodes, add optional cleaning of all other graph versions
        #add option to wait on all active evaluations or just fuck em
        return

    def get_neo4j_driver(self) -> Neo4jDBClient:
        return Neo4jDBClient.from_config(self._neo4j_conf)

    def add_request_to_queue(self, request):
        if self._stop_event.is_set():
            raise RuntimeError('Graph repository is in process of stopping or it has already stopped')
        self._request_q.put(request)

