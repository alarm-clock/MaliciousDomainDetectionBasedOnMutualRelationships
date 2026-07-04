"""
File: GraphRepositoryABI.py
Author: Jozef Michal Bukas <xbukas00@stud.fit.vutbr.cz>
Date: 1.2.2026
Brief: File that holds graph repository implementation
"""

import uuid
from queue import PriorityQueue
from typing import Any
import dgl
from api.app_api import ApiOptions
from api.config.config import Config
from graph_repository.Neo4jDBDriver import Neo4jDBDriver
from graph_repository.graph_main.GraphRepository import GraphRepository
from graph_repository.graph_main.conversion.FormatConverting import convert_form_neo4j_to_dgl, prepare_dgl_g_for_ml
from graph_repository.graph_main.graph_editing.EditConsumer import edit_loop, FinishType
from threading import Event, Thread, Lock
from graph_repository.graph_main.graph_editing.common.GraphRequest import GraphRequest, FinishRequest
from graph_repository.graph_main.graph_editing.common.RequestStates import RequestStates
from graph_repository.graph_main.graph_repo.Transaction import Transaction
from graph_repository.graph_main.tmp.TmpAdd import add_temporary_domain
from graph_repository.workers.common.GraphTypes import NodeTypes
from misc.Logger import MyLogger
from misc.PackageImporter import import_all_modules_from_package


class GraphRepositoryABI(GraphRepository):
    """
    Class that represents main graph repository implementation coordinating edit requests,
    transactions, temporary nodes, and graph retrieval operations
    """

    def __init__(self, neo4j_conf: str):
        """
        Method that initializes graph repository implementation and starts edit worker if enabled
        :param neo4j_conf: `str` path to Neo4j configuration file
        :return: None
        """

        self._initialized = True
        self._request_q: PriorityQueue[GraphRequest | None] = PriorityQueue[GraphRequest | None]()
        self._neo4j_conf = neo4j_conf
        self._worker_stop_event = Event()
        self._stop_event = Event()
        import_all_modules_from_package("graph_repository.workers.edit_node_edge_workers")
        import_all_modules_from_package("graph_repository.workers.tmp")

        d_option = ApiOptions.from_str(Config.get_instance().server_conf.deploy_option)

        if d_option == ApiOptions.WHOLE_APP or d_option == ApiOptions.GRAPH_REPOSITORY or ApiOptions.READ_AND_GRAPH_REPO or ApiOptions.READ:

            self._edit_worker = Thread(target=edit_loop,args=(self._worker_stop_event,self._request_q, self._neo4j_conf), daemon=True)
            self._edit_worker.start()

        else:
            self._edit_worker = None

        self._state_dict: dict[str, GraphRequest] = {}
        self._state_dict_lock = Lock()

        # job id   [version, number of tmp domains]
        self._transaction_context: dict[str, Transaction] = {}
        self._transaction_context_operations_cnt = 0
        self._transaction_context_lock = Lock()


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

        if self._edit_worker is not None:
            self._edit_worker.join()  # no timeout because I need to wait if worker is wrapping up and potentially finishing all work
            # maybe I will give it some time limit just in case

        driver = self.get_neo4j_driver()
        driver.delete_all_tmp_nodes()

        #TODO add optional cleaning of all other graph versions
        return

    def get_neo4j_driver(self) -> Neo4jDBDriver | None:
        """
        Method that returns Neo4jDBDriver instance used to communicate with database
        :return: Neo4jDBDriver instance or None if it does not connect to database
        """
        return Neo4jDBDriver.from_config(self._neo4j_conf)

    #TODO add deletion of edit requests that did not started yet

    def add_request_to_queue(self, request) -> None:
        """
        Method that adds edit request to queue
        :param request: Add, Edit, or Delete request
        :return: Nothing
        """
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
        """
        Method that returns edit request state
        :param job_id: Request ID
        :return: Request state or None if it does not exist
        """
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
        """
        Method that deletes all finished requests
        :return: Nothing
        """
        with self._state_dict_lock:
            jobs_for_deleting = []
            for job_id, req in self._state_dict.items():
                state = req.state
                if state == RequestStates.DONE or state == RequestStates.TIMEOUT or state == RequestStates.CANCELED or state == RequestStates.ERROR:
                    jobs_for_deleting.append(job_id)

            for job_id in jobs_for_deleting:
                de = self._state_dict.pop(job_id)
                del de

    def _inc_transaction_op_cnt(self) -> None:
        """
        Method that is invoked after every operation with transaction dict and every 128 operations it checks
        if transaction length is over time limit (currently 20 mins). Note that transaction may exist longer then
        given limit but for duration of limit graph repository guaranties that tmp_domains and their graph version
        won't be deleted, after given limit it is undefined how long will transaction exists. This approach
        was chosen to reflect possible differences in load of graph repository. This way if there is no load, transaction
        can live for long time but with high load it may be deleted right after the limit.

        After limit has passed, and it is checked by this method, all tmp domains of this transaction will be deleted.
        :return: Nothing
        """

        self._transaction_context_operations_cnt = (self._transaction_context_operations_cnt + 1) & ((2**8) - 1)
        if not self._transaction_context_operations_cnt:
            MyLogger.get_instance().log("Checking all transactions if they are under time limit")

            driver = self.get_neo4j_driver()
            if driver is None:
                return

            keys_for_del = []
            for key, transaction in self._transaction_context.items():
                if transaction.is_over_time():
                    MyLogger.get_instance().log_warning(f"Transaction {transaction.job_id} was over time limit and therefore it and all of it's tmp domains are deleted")
                    transaction.delete_all_tmp_nodes(driver)
                    driver.end_transaction(transaction.version)
                    keys_for_del.append(key)

            driver.close()
            for key in keys_for_del:
                self._transaction_context.pop(key, None)

    def _find_job(self, job_id: str) -> Transaction | None:
        """
        Method that finds transaction with given job_id
        :param job_id: ID of transaction
        :return: Transaction if it exists else None
        """
        with self._transaction_context_lock:
            data = self._transaction_context.get(job_id, None)
            self._inc_transaction_op_cnt()

        return data

    def _insert_job(self, job_id: str, data: Transaction) -> None:
        """
        Method that inserts transaction
        :param job_id: ID of transaction
        :param data: data object
        :return: Nothing
        """
        with self._transaction_context_lock:
            self._transaction_context[job_id] = data
            self._inc_transaction_op_cnt()

    def _remove_job(self, job_id: str) -> None:
        """
        Method that removes transaction
        :param job_id: ID of transaction
        :return: Nothing
        """
        with self._transaction_context_lock:
            self._transaction_context.pop(job_id, None)
            self._inc_transaction_op_cnt()

    def create_transaction(self) -> tuple[str | int] | None:
        """
        Method that creates transaction
        :return: transation id and graph version
        """

        driver = self.get_neo4j_driver()
        if driver is None:
            return None

        version = driver.start_new_transaction_on_curr_g_vers()
        job_id = str(uuid.uuid4())
        transaction = Transaction(job_id, version)
        self._insert_job(job_id, transaction)
        return job_id, version

    def delete_transaction(self, job_id: str) -> None:
        """
        Method that deletes transaction
        :param job_id: id of transaction
        :return: Nothing
        """

        transaction = self._find_job(job_id)
        driver = self.get_neo4j_driver()
        if transaction is None or driver is None:
            return

        transaction.delete_all_tmp_nodes(driver)
        self._remove_job(job_id)

    def _remove_tmp_from_transaction(self, job_id: str, driver: Neo4jDBDriver, node_id: int | None) -> None:
        """
        Method that removes temporary domain from transaction
        :param job_id: id of transaction
        :param driver: Neo4jDriver driver
        :param node_id: node_id of temporary domain that will be disassociated with this transaction
        :return: Nothing
        """
        transaction = self._find_job(job_id)
        if transaction is None:
            return

        if node_id is not None:
            transaction.remove_tmp_node_from_transaction(node_id)

        if transaction.empty:
            MyLogger.get_instance().log(f"Transaction {job_id} is being deleted")
            driver.end_transaction(transaction.version)
            self._remove_job(job_id)

        return

    def _add_tmp_node_to_transaction(self, job_id: str, node_id: int) -> None:
        """
        Method that adds temporary domain to transaction
        :param job_id: id of transaction
        :param node_id: node_id of temporary domain that is associated with this transaction
        :return: Nothing
        """

        transaction = self._find_job(job_id)
        if transaction is None:
            return

        transaction.add_tmp_node_to_transaction(node_id)

    def find_domain(self, domain_name: str, version: int | None = None) -> dict[str, Any] | None:
        """
        Method that finds domain by name in selected or current graph version
        :param domain_name: `str` searched domain name
        :param version: `int | None` optional graph version
        :return: `dict[str, Any] | None` found domain data or None
        """
        driver = self.get_neo4j_driver()
        if driver is None:
            return None

        res = driver.find_node(
            {'domain_name': domain_name},
            NodeTypes.DOMAIN,
            version if version is not None else Neo4jDBDriver.VERSION_CURR
        )
        if type(res) is not dict:
            return None

        return res

    def temporary_add_domain(self, domain: dict[str, Any], job_id: str | None) -> int | None:
        """
        Method that ads temporary domain into graph
        :param domain: Dictionary with temporary domain data (e.g. domain name, ip address, cname...)
        :param job_id: Job with which domain will be associated, if ``None`` is passed there is no guarantee that
            domain's graph version won't be deleted while domain exists in graph
        :return: Domains node_id in graph, TMP_ADD_STOP if graph repository is stopped, TMP_ADD_NO_DB_ERR if graph repository can not connect to
            database, None if domain has no neighbor in graph
        """

        if self._stop_event.is_set():
            MyLogger.get_instance().log("Graph repository is being shut down, can not add tmp domain")
            return self.TMP_ADD_STOP

        driver = self.get_neo4j_driver()

        if driver is None:
            return self.TMP_ADD_NO_DB_ERR

        if job_id is not None:

            transaction = self._find_job(job_id)

            if transaction is None:
                version = driver.start_new_transaction_on_curr_g_vers()
                self._insert_job(job_id, Transaction(job_id, version))
            else:
                version = transaction.version

        else:
            version = driver.get_current_active_graph_version()

        domain_id = add_temporary_domain(domain, version, driver)

        if domain_id is None and job_id is not None:
            self._remove_tmp_from_transaction(job_id, driver, None)  # if there is no other domain in transaction, delete it

        driver.close()
        return domain_id

    #def add_temporary_domains(self, domains: list[dict[str, Any]], job_id: str | None) -> list[int | None]:

    def get_domain(self, domain_name: str) -> dict[str, Any] | None:
        """
        Method that gets domain from graph
        :param domain_name: Domain name that will be found
        :return: Dict with domain data or None if not found or can not connect to database
        """

        driver = self.get_neo4j_driver()
        if driver is None:
            return None

        return driver.get_domain_from_graph(domain_name)

    def delete_temporary_domain(self, tmp_nd_id: int, job_id: str | None) -> None:
        """
        Method that deletes temporary domain from graph
        :param tmp_nd_id: node_id of deleted temporary domain
        :param job_id: id of job with which is temporary domain associated
        :return: Nothing
        """

        driver = self.get_neo4j_driver()
        if driver is None:
            return

        MyLogger.get_instance().log(f"Deleting temporary domain with id {tmp_nd_id} for job context {job_id}")
        if job_id is not None:
            self._remove_tmp_from_transaction(job_id, driver, tmp_nd_id)
            MyLogger.get_instance().log_debug(f"Deleting tmp node f{tmp_nd_id}")
            driver.delete_node({'node_id': tmp_nd_id}, NodeTypes.TMP_DOMAIN.neo4j)

        driver.close()
        return

    def get_neighbors_maliciousness(self, tmp_nd_id: int) -> tuple[float, float] | None:
        """
        Method that returns maliciousness of all neighbours in one meta-path-hop- distance
        :param tmp_nd_id: Node id of evaluated domain
        :return: `tuple[ malicious%, benign%] or None if not found
        """

        driver = self.get_neo4j_driver()
        if driver is None:
            return None

        return driver.get_neighborhood_maliciousness({'node_id': tmp_nd_id, 'label': NodeTypes.TMP_DOMAIN.neo4j})

    def get_k_hop_neighborhood_dgl(self, tmp_node_id: int, for_ml: bool = False) -> dgl.DGLHeteroGraph:
        """
        Method that returns temporary nodes k-hop neighborhood graph
        :param tmp_node_id: node_id of temporary node
        :param for_ml: flag indicating if dgl graph should be prepared for machine learning
        :return: K-hop neighborhood heterograph, on error raise RuntimeError
        """

        if self._stop_event.is_set():
            MyLogger.get_instance().log_warning("Graph repository is being shut down, can not get k_hop_neigborhood")
            raise RuntimeError('Graph repository is being shut down')

        driver = self.get_neo4j_driver()
        if driver is None:
            raise RuntimeError('Can not connect to database')

        max_depth = Config.get_instance().graph_repo_conf.k_hop_neigh_params.max_depth
        max_sample = Config.get_instance().graph_repo_conf.k_hop_neigh_params.max_sample_size
        seed = Config.get_instance().graph_repo_conf.k_hop_neigh_params.walk_seed

        graph = driver.get_k_hop_neighborhood_universal(
            {"label": NodeTypes.TMP_DOMAIN.neo4j, "node_id": tmp_node_id}, 3, 1500, seed, False)

        driver.close()
        graph = convert_form_neo4j_to_dgl(True, graph)
        return prepare_dgl_g_for_ml(graph) if for_ml else graph