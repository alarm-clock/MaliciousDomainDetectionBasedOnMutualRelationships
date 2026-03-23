from typing import Any, Callable
from graph_repository.Neo4jDBClient import Neo4jDBClient

EDGES_T = list[tuple[list[dict], dict[str,Any]]]
TMP_FUNC_T = Callable[[dict, int, int, Neo4jDBClient], tuple[list[dict], dict[str, Any]] | EDGES_T | None]

TMP_REGISTRY: dict[str, TMP_FUNC_T] = {}

def register(f_name: str, fun: TMP_FUNC_T ) -> None:
    TMP_REGISTRY[f_name] = fun