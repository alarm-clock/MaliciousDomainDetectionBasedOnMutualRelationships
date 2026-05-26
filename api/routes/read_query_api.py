from fastapi import HTTPException, APIRouter
from graph_repository.Neo4jDBDriver import Neo4jDBDriver
from graph_repository.graph_main.GraphRepository import GraphRepository
from neo4j.exceptions import ClientError, TransactionError, DatabaseError, CypherSyntaxError
from pydantic import BaseModel
from typing import List, Any
router = APIRouter()

class ReadQuery(BaseModel):
    """
    `query` query string
    `data` dictionary with variable name ($variable is in dict just variable) and value for that variable
    """
    query: str
    data: dict[str, Any] | None = None

@router.post("/read_query")
async def query_req(query: ReadQuery):
    """
    Endpoint for executing read queries in graph, query_result is not edited in no way
    """
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