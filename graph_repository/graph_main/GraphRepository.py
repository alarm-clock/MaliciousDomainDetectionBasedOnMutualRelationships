from queue import PriorityQueue
from typing import Any
from graph_repository.Neo4jDBClient import Neo4jDBClient
from graph_repository.graph_main.graph_editing.EditConsumer import edit_loop, FinishType
from threading import Event, Thread, Lock
from graph_repository.graph_main.graph_editing.common.GraphRequest import GraphRequest, FinishRequest
from graph_repository.graph_main.graph_editing.common.RequestStates import RequestStates
from graph_repository.graph_main.tmp.TmpAdd import add_temporary_domain
from misc.Logger import MyLogger
from misc.PackageImporter import import_all_modules_from_package

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
            import_all_modules_from_package("graph_repository.workers.edit_node_edge_workers")
            self._edit_worker = Thread(target=edit_loop,args=(self._worker_stop_event,self._request_q, self._neo4j_conf), daemon=True)
            self._edit_worker.start()

            self._state_dict: dict[str, GraphRequest] = {}
            self._state_dict_lock = Lock()

    @staticmethod
    def get_instance(neo4j_conf: str| None = None):
        if GraphRepository._repository_instance_ is None:
            if neo4j_conf is not None:
                GraphRepository(neo4j_conf)
            else:
                return None
        return GraphRepository._repository_instance_

    def stop(self, finish_all_submitted_edits: FinishType = FinishType.FINISH_NONE) -> None:
        """
        Method that coordinates stopping of core functionality
        :param finish_all_submitted_edits: Enum specifying how to finish unfinished requests, default is to delete all
        :return: None
        """

        MyLogger.get_instance().log("Graph repository is being shut down...")
        self._stop_event.set()

        if finish_all_submitted_edits == FinishType.FINISH_NONE:
            MyLogger.get_instance().log("No currently working edit will be finished")
            self._worker_stop_event.set()
        elif finish_all_submitted_edits == FinishType.FINISH_CURRENT:
            MyLogger.get_instance().log("Currently working edit will be finished")
            while not self._request_q.empty():
                self._request_q.get_nowait()
                self._request_q.task_done()
        else:
            MyLogger.get_instance().log("All edits that are in queue will be finished before shut down")

        self._request_q.put(FinishRequest())
        self._edit_worker.join() #no timeout because I need to wait if worker is wrapping up and potentially finishing all work
                                 #maybe I will give it some time limit just in case

        #TODO add removal of temporary nodes, add optional cleaning of all other graph versions
        #add option to wait on all active evaluations or just fuck em
        return

    def get_neo4j_driver(self) -> Neo4jDBClient | None:
        #maybe I should add check that if graph repo is stopping then it should not give any client
        #on the other hand if edits are to be finished then they need client.
        return Neo4jDBClient.from_config(self._neo4j_conf)

    def add_request_to_queue(self, request):
        if self._stop_event.is_set():
            request.state = RequestStates.TIMEOUT
            MyLogger.get_instance().log_warning(f"Graph repository is in process of stopping or it has already stopped - {request.id}")
            raise RuntimeError(f'Graph repository is in process of stopping or it has already stopped - {request.id}')

        with self._state_dict_lock:
            self._state_dict[request.id] = request

        request.state = RequestStates.FILTER
        request.filter()

        if request.get_n_domains() == 0:
            MyLogger.get_instance().log(f"Request {request.id} has no domains after filtering")
            request.state = RequestStates.DONE
            return

        MyLogger.get_instance().log_debug(f"Adding request {request.id} to queue")
        self._request_q.put(request)
        request.state = RequestStates.IN_QUEUE

    def get_request_state(self, job_id: str) -> RequestStates | None:
        with self._state_dict_lock:
            if self._state_dict.get(job_id) is None:
                return None

            job = self._state_dict[job_id]
            state = job.state
            if state == RequestStates.DONE or state == RequestStates.TIMEOUT or state == RequestStates.CANCELED or state == RequestStates.ERROR:
                req_for_del = self._state_dict.pop(job_id)
                del req_for_del

        return state

    def delete_finished_request(self) -> None:
        with self._state_dict_lock:
            jobs_for_deleting = []
            for job_id, req in self._state_dict.items():
                state = req.state
                if state == RequestStates.DONE or state == RequestStates.TIMEOUT or state == RequestStates.CANCELED or state == RequestStates.ERROR:
                    jobs_for_deleting.append(job_id)

            for job_id in jobs_for_deleting:
                de = self._state_dict.pop(job_id)
                del de

    def temporary_add_domain(self, domain: dict[str, Any]) -> int:

        if self._stop_event.is_set():
            MyLogger.get_instance().log("Graph repository is being shut down, can not add tmp domain")
            return -1

        driver = self.get_neo4j_driver()
        domain_id = add_temporary_domain(domain, driver)
        driver.close()

        return domain_id
