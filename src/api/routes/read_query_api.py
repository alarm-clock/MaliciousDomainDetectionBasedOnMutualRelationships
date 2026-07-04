"""
File: read_query_api.py
Author: Jozef Michal Bukas <xbukas00@stud.fit.vutbr.cz>
Date: 02.01.2026
Brief: File that contains API endpoint for executing read-only Cypher queries
    against graph repository and returning raw query results
"""

from fastapi import HTTPException, APIRouter
from graph_repository.Neo4jDBDriver import Neo4jDBDriver
from graph_repository.graph_main.GraphRepository import GraphRepository
from neo4j.exceptions import ClientError, TransactionError, DatabaseError, CypherSyntaxError
from pydantic import BaseModel
from typing import Any
router = APIRouter()


class ReadQuery(BaseModel):
    """
    Class that represents request body for read query execution in graph repository.
    """

    """
    `query` query string
    `data` dictionary with variable name ($variable is in dict just variable) and value for that variable
    """
    query: str
    data: dict[str, Any] | None = None


@router.post("/read_query")
async def query_req(query: ReadQuery):
    """
    Method that executes read-only Cypher query in graph repository
    :param query: `ReadQuery` object containing Cypher query string and optional query parameters
    :return: `dict` dictionary containing raw query result returned by Neo4j driver
    :raises HTTPException: if graph repository is shutting down, query is invalid,
        writing is attempted, or database execution fails
    """

    """
    Endpoint for executing read queries in graph, query_result is not edited in no way
    """
    # Obtain Neo4j driver instance from shared graph repository.
    driver: Neo4jDBDriver = GraphRepository.get_instance().get_neo4j_driver()

    # Reject query execution when graph repository is already being shut down.
    if driver is None:
        raise HTTPException(status_code=503, detail="Graph repository is being shut down")

    try:
        # Execute query without parameters when no parameter dictionary was provided.
        if query.data is None:
            res = driver.execute_read(query.query)
        else:
            # Execute query with unpacked parameter dictionary.
            res = driver.execute_read(query.query, **query.data)

    except TransactionError as t_e:
        raise HTTPException(status_code=401, detail=str(t_e))
    except CypherSyntaxError as cy_e:
        raise HTTPException(status_code=400, detail=str(cy_e))
    except DatabaseError as db_e:
        raise HTTPException(status_code=500, detail=str(db_e))
    except ClientError as ce:
        # Explicitly reject attempts to use write operations through read-only endpoint.
        if ce.code == "Neo.ClientError.Statement.AccessMode":
            raise HTTPException(status_code=401, detail="Writing is not allowed")

        raise HTTPException(status_code=400, detail=str(ce))
    except Exception as ex:
        raise HTTPException(status_code=400, detail=str(ex))


    return {"query_result": res}