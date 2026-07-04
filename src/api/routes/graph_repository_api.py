"""
File: graph_repository_api.py
Author: Jozef Michal Bukas <xbukas00@stud.fit.vutbr.cz>
Date: 02.01.2026
Brief: File that contains API endpoints for graph repository operations, including
    asynchronous adding, updating, deleting of domains, request status lookup,
    and retrieval of system and graph statistics
"""

from fastapi import HTTPException, APIRouter
from pydantic import BaseModel
from typing import List
from threading import Thread
from graph_repository.graph_main.GraphRepository import GraphRepository
from graph_repository.graph_main.graph_editing.requests.AddRequest import AddRequest
from graph_repository.graph_main.graph_editing.requests.DeleteRequest import DeleteRequest
from graph_repository.graph_main.graph_editing.requests.EditRequest import EditRequest
from graph_repository.graph_main.graph_editing.common.RequestPriority import RequestPriority
from misc.Logger import MyLogger
from misc.MemMonitor import enough_memory

router = APIRouter()


class DomainDict(BaseModel):
    """
    Class that represents domain object used in graph repository add and update requests.
    """

    """
    `domain_name`: domain name \n
    `label`: domain label. Domain is considered benign if label has substring "benign" \n
    `dns`: domain's dns data in JSON format. System currently uses only A, AAAA, and CNAME
    """
    domain_name: str
    label: str
    dns: dict | None = None


class AddReq(BaseModel):
    """
    Class that represents request body for adding or updating domains in graph repository.
    """

    """
    `domains`: list of JSON objects with domain data \n
    `priority`: priority of given request. Values from 0 to 3 with lower value having bigger priority \n
    `timeout`: time after which, if request is not finished it will fail and will be dropped
    """
    domains: List[DomainDict]
    priority: RequestPriority | None = None
    timeout: float | None = None


@router.post("/add")
async def add_req(req: AddReq):
    """
    Method that creates asynchronous request for adding domains into graph repository
    :param req: `AddReq` object containing domain data, optional request priority, and optional timeout
    :return: `dict` dictionary containing identifier and initial state of created add request
    :raises HTTPException: if server is temporarily overloaded
    """

    """
    Endpoint for adding domains that are not in the graph, if there is high possibility that you will add domains that
    are already in graph then use `/update` endpoint instead, this endpoint drops duplicate domains
    """
    if not enough_memory():
        raise HTTPException(status_code=503, detail="Server is temporary overloaded. Please, try again later.")

    # Convert validated request models into plain dictionaries expected by graph request object.
    domains = [domain_dict.model_dump() for domain_dict in req.domains]
    if req.priority is None: req.priority = RequestPriority.LOW

    # Create add request according to whether custom timeout was provided.
    if req.timeout is None:
        add_request = AddRequest(domains, req.priority)
    else:
        add_request = AddRequest(domains, req.priority, req.timeout)

    job_id = add_request.id
    state = add_request.state

    # Run graph modification request asynchronously in separate daemon thread.
    th = Thread(target=add_request.submit, args=(GraphRepository.get_instance(),), daemon=True)
    th.start()

    return {"job_id": job_id, "state": state.value}


@router.post("/update")
async def update_req(req: AddReq):
    """
    Method that creates asynchronous request for updating domains in graph repository
    :param req: `AddReq` object containing domain data, optional request priority, and optional timeout
    :return: `dict` dictionary containing identifier and initial state of created update request
    :raises HTTPException: if server is temporarily overloaded
    """

    """
    Endpoint for updating domains in graph, if there is high possibility that you will add domains that are
    already in graph then use this endpoint (even when you have new nodes)
    """

    if not enough_memory():
        raise HTTPException(status_code=503, detail="Server is temporary overloaded. Please, try again later.")

    # Convert validated request models into plain dictionaries expected by graph request object.
    domains = [domain_dict.model_dump() for domain_dict in req.domains]
    if req.priority is None: req.priority = RequestPriority.LOW

    # Create update request according to whether custom timeout was provided.
    if req.timeout is None:
        update_request = EditRequest(domains, req.priority)
    else:
        update_request = EditRequest(domains, req.priority, req.timeout)

    job_id = update_request.id
    state = update_request.state

    # Run graph modification request asynchronously in separate daemon thread.
    th = Thread(target=update_request.submit, args=(GraphRepository.get_instance(),), daemon=True)
    th.start()

    return {"job_id": job_id, "state": state.value}


class DeleteReq(BaseModel):
    """
    Class that represents request body for deleting domains from graph repository.
    """

    """
    `domains`: list of JSON objects with domain names for deleting in format {domain_name: "sweet.dreams.eu"}
    `priority`: priority of given request. Values from 0 to 3 with lower value having bigger priority
    `timeout`: time after which, if request is not finished it will fail and will be dropped
    """
    domains: list[dict[str, str]]
    priority: RequestPriority | None = None
    timeout: float | None = None


@router.delete("/delete")
async def delete_req(req: DeleteReq):
    """
    Method that creates asynchronous request for deleting domains from graph repository
    :param req: `DeleteReq` object containing domains to delete, optional request priority, and optional timeout
    :return: `dict` dictionary containing identifier and initial state of created delete request
    """

    """
    Endpoint for deleting domains
    """

    if req.priority is None: req.priority = RequestPriority.LOW

    # Create delete request according to whether custom timeout was provided.
    if req.timeout is None:
        delete_request = DeleteRequest(req.domains, req.priority)
    else:
        delete_request = DeleteRequest(req.domains, req.priority, req.timeout)

    job_id = delete_request.id
    state = delete_request.state

    # Run graph modification request asynchronously in separate daemon thread.
    th = Thread(target=delete_request.submit, args=(GraphRepository.get_instance(),), daemon=True)
    th.start()

    return {"job_id": job_id, "state": state.value}


@router.get("/job_status/{req_id}")
async def job_status(req_id: str):
    """
    Method that returns current state of graph repository request with given identifier
    :param req_id: `str` identifier of previously submitted graph repository request
    :return: `dict` dictionary containing job identifier and current request status
    :raises HTTPException: if request with given identifier does not exist
    """

    """
    Endpoint for getting request status
    """

    status = GraphRepository.get_instance().get_request_state(req_id)
    if status is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"job_id": req_id, "status": status}


@router.delete("/rm_fin")
async def rm_fin_req():
    """
    Method that removes finished requests from internal graph repository request storage
    :return: None
    """

    """
    This is mine and mine only
    """
    GraphRepository.get_instance().delete_finished_request()
    return


@router.get("/info")
async def sys_info():
    """
    Method that returns basic request-processing, memory, and graph statistics
    :return: `dict` dictionary containing request statistics, memory information,
        processing time statistics, and graph node and edge counts
    """
    # Load aggregated request and memory statistics from logger instance.
    n_r, n_f, n_t, m_p, m_a, t_a, t_l = MyLogger.get_instance().log_stats()

    # Obtain active graph version and graph size statistics from Neo4j driver.
    driver = GraphRepository.get_instance().get_neo4j_driver()
    curr_version = driver.get_current_active_graph_version()
    n_cnt, e_cnt = driver.get_node_and_edge_cnt(curr_version)
    driver.close()

    return {"Requests": {"Total": n_r, "Finished": n_f, "Timeout": n_t},
            "Memory": {"Used%": m_p, "Available": m_a},
            "Time": {"Avg": t_a, "Last": t_l},
            "Counts": {"Nodes": n_cnt, "Edges": e_cnt}
            }

"""
class ReadQuery(BaseModel):
    ""
    `query` query string
    `data` dictionary with variable name ($variable is in dict just variable) and value for that variable
    ""
    query: str
    data: dict[str, Any] | None = None

@router.post("/read_query")
async def query_req(query: ReadQuery):
    ""
    Endpoint for executing read queries in graph, query_result is not edited in no way
    ""
    driver: Neo4jDBDriver = GraphRepository.get_instance().get_neo4j_driver()

    if driver is None:
        raise HTTPException(status_code=503, detail="Graph repository is being shut down")

    try:
        if query.data is None:
            res = driver.execute_read(query.query)
        else:
            res = driver.execute_read(query.query, **query.data)
    except TransactionError as t_e:
        raise HTTPException(status_code=401, detail=str(t_e))
    except CypherSyntaxError as cy_e:
        raise HTTPException(status_code=400, detail=str(cy_e))
    except DatabaseError as db_e:
        raise HTTPException(status_code=500, detail=str(db_e))
    except ClientError as ce:
        if ce.code == "Neo.ClientError.Statement.AccessMode":
            raise HTTPException(status_code=401, detail="Writing is not allowed")

        raise HTTPException(status_code=400, detail=str(ce))
    except Exception as ex:
        raise HTTPException(status_code=400, detail=str(ex))


    return {"query_result": res}

class PutTmpDomainsModel(BaseModel):
    domains: list[str]


@router.post("/put_tmp_domians")
async def put_tmp_domains(domains_obj: PutTmpDomainsModel):

    domains = domains_obj.domains

    driver: Neo4jDBDriver = GraphRepository.get_instance().get_neo4j_driver()

    if driver is None:
        raise HTTPException(status_code=503, detail="Graph repository is being shut down")

    job_id =

"""