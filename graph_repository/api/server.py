from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Any
from threading import Thread
from graph_repository.Neo4jDBClient import Neo4jDBClient
from graph_repository.graph_main.GraphRepository import GraphRepository
from graph_repository.graph_main.graph_editing.requests.AddRequest import AddRequest
from graph_repository.graph_main.graph_editing.requests.DeleteRequest import DeleteRequest
from graph_repository.graph_main.graph_editing.requests.EditRequest import EditRequest
from graph_repository.graph_main.graph_editing.common.RequestPriority import RequestPriority
app = FastAPI()


class DomainDict(BaseModel):
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
    `domains`: list of JSON objects with domain data \n
    `priority`: priority of given request. Values from 0 to 3 with lower value having bigger priority \n
    `timeout`: time after which, if request is not finished it will fail and will be dropped
    """
    domains: List[DomainDict]
    priority: RequestPriority | None = None
    timeout: float | None = None

@app.post("/add")
async def add_req(req: AddReq):
    """
    Endpoint for adding domains that are not in the graph, if there is high possibility that you will add domains that
    are already in graph then use `/update` endpoint instead, this endpoint drops duplicate domains
    """

    domains = [domain_dict.model_dump() for domain_dict in req.domains]
    if req.priority is None: req.priority = RequestPriority.LOW

    if req.timeout is None:
        add_request = AddRequest(domains, req.priority)
    else:
        add_request = AddRequest(domains, req.priority, req.timeout)

    job_id = add_request.id
    state = add_request.state
    th = Thread(target=add_request.submit, args=(GraphRepository.get_instance(),), daemon=True)
    th.start()
    return {"job_id": job_id, "state": state.value}


@app.post("/update")
async def update_req(req: AddReq):
    """
    Endpoint for updating domains in graph, if there is high possibility that you will add domains that are
    already in graph then use this endpoint (even when you have new nodes)
    """

    domains = [domain_dict.model_dump() for domain_dict in req.domains]
    if req.priority is None: req.priority = RequestPriority.LOW

    if req.timeout is None:
        update_request = AddRequest(domains, req.priority)
    else:
        update_request = AddRequest(domains, req.priority, req.timeout)

    job_id = update_request.id
    state = update_request.state
    th = Thread(target=update_request.submit, args=(GraphRepository.get_instance(),), daemon=True)
    th.start()
    return {"job_id": job_id, "state": state.value}


class DeleteReq(BaseModel):
    """
    `domains`: list of JSON objects with domain names for deleting in format {domain_name: "sweet.dreams.eu"}
    `priority`: priority of given request. Values from 0 to 3 with lower value having bigger priority
    `timeout`: time after which, if request is not finished it will fail and will be dropped
    """
    domains: list[dict[str, str]]
    priority: RequestPriority | None = None
    timeout: float | None = None

@app.delete("/delete")
async def delete_req(req: DeleteReq):
    """
    Endpoint for deleting domains
    """

    if req.priority is None: req.priority = RequestPriority.LOW

    if req.timeout is None:
        delete_request = DeleteRequest(req.domains, req.priority)
    else:
        delete_request = DeleteRequest(req.domains, req.priority, req.timeout)

    job_id = delete_request.id
    state = delete_request.state
    th = Thread(target=delete_request.submit, args=(GraphRepository.get_instance(),), daemon=True)
    th.start()
    return {"job_id": job_id, "state": state.value}


@app.get("/job_status/{req_id}")
async def job_status(req_id: str):
    """
    Endpoint for getting request status
    """

    repo = GraphRepository.get_instance()
    print(repo)
    status = GraphRepository.get_instance().get_request_state(req_id)
    if status is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"job_id": req_id, "status": status}

@app.delete("/rm_fin")
async def rm_fin_req():
    """
    This is mine and mine only
    """
    GraphRepository.get_instance().delete_finished_request()
    return


class ReadQuery(BaseModel):
    query: str
    data_name: str | None = None
    data: Any | None = None

@app.post("/read_query")
async def query_req(query: ReadQuery):
    """
    Endpoint for executing read queries in graph
    """
    driver: Neo4jDBClient = GraphRepository.get_instance().get_neo4j_driver()

    if query.data_name is None or query.data is None:
        res = driver.execute_read(query)
    else:
        res = driver.execute_read(query, **{query.data_name: query.data})

    return {"query_result": res}
