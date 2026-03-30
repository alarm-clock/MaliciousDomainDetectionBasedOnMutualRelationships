import threading
import time
from queue import PriorityQueue, Empty
from graph_repository.graph_main.graph_editing.common.GraphRequest import GraphRequest, FinishRequest
from graph_repository.Neo4jDBDriver import Neo4jDBDriver
from graph_repository.graph_main.graph_editing.common.Exceptions import TooManyVersions, Neo4jIndexError
from graph_repository.graph_main.graph_editing.common.RequestStates import RequestStates
from misc.Logger import MyLogger
from enum import Enum

class FinishType(Enum):
    FINISH_ALL = 0
    FINISH_CURRENT = 1
    FINISH_NONE = 2

def _handle_request(request: GraphRequest, stop_event: threading.Event, driver_conf_file: str) -> None:
    """
    Function that handles edit request. It creates new version of graph, runs edit, starts relearning methods and
    finally sets new current version of graph and finishes.
    :param request: ``GraphRequest`` object that holds edit data and algorithm for graph editing
    :param stop_event: ``threading.Event`` object that signals whether to stop editing, because of limit of concurrent
    graph versions there is chance that this function might be stuck on graph copy for a while so if application ends
    it will stop editing
    :return: None
    """
    MyLogger.get_instance().log(f"Handling request {request.id}")
    request.state = RequestStates.IN_PROGRESS
    request.filter()

    if request.get_n_domains() == 0:
        MyLogger.get_instance().log(f"Request {request.id} has no domains after filtering")
        request.state = RequestStates.DONE
        return

    driver: Neo4jDBDriver = Neo4jDBDriver.from_config(driver_conf_file)
    cnt = 0
    waiting_on_copy = True
    new_version = -1
    while waiting_on_copy:
        if stop_event.is_set():
            request.cancel()
            MyLogger.get_instance().log_warning(f"Edit request handler was stopped before it could finish request")
            driver.close()
            return

        try:
            new_version = driver.create_new_version_mirror_of_graph()
            waiting_on_copy = False
        except TooManyVersions:
            cnt += 1
            if cnt == 8:
                MyLogger.get_instance().log(f"There are too many versions of graph, graph editing is halted")
                cnt = 0

            time.sleep(10.0)
            continue

        except Neo4jIndexError as err:
            MyLogger.get_instance().log_error(str(err))
            return

    if stop_event.is_set():
        request.cancel()
        driver.delete_graph_version(new_version)
        driver.close()
        return

    if not request.edit(new_version):
        driver.delete_graph_version(new_version)
        driver.close()
        return

    #TODO here is where I will add relearning and other stuff for models or something, I dunno

    driver.set_new_current_graph_version_node(new_version)
    driver.close()

    return


def edit_loop(stop_event: threading.Event, queue: PriorityQueue[GraphRequest], driver_conf_file: str) -> None:
    """
    Function that periodically checks `queue`, takes edit requests from it and executes them. This function should be executed on separate thread.
    :param driver_conf_file: `str` path to neo4j configuration file
    :param stop_event: ``threading.Event`` that signalizes that `edit_loop` should be finished. Alternatively you can pass None as request and it will have same effect.
    :param queue: ``PriorityQueue`` that holds edit requests from which edit_loop takes requests
    :return: None
    """

    while not stop_event.is_set():

        try:
            request = queue.get(timeout=15.0) #todo make this editable in configuration
        except Empty:
            driver = Neo4jDBDriver.from_config(driver_conf_file)
            driver.delete_unused_graph_versions()
            driver.close()
            continue  #try getting new task again

        if type(request) == FinishRequest:
            MyLogger.get_instance().log(f"Edit_loop was signalized to finish by sending None request")
            break

        if request.is_canceled():
            MyLogger.get_instance().log(f"Edit request {request.id} is canceled ")
        else:
            _handle_request(request, stop_event, driver_conf_file)

        queue.task_done()

    MyLogger.get_instance().log(f"Edit loop has gracefully stopped")
    return
