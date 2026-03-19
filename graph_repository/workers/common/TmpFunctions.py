from typing import Any, Callable
from graph_repository.Neo4jDBClient import Neo4jDBClient

TMP_REGISTRY: dict[str, Callable[[dict, int, Neo4jDBClient], tuple[list[dict], dict[str, Any]] | list[tuple[list[dict], dict[str,Any]]] | None]] = {}

def register(f_name: str,
             fun: Callable[[dict, int, Neo4jDBClient], tuple[list[dict], dict[str, Any]] | list[tuple[list[dict], dict[str,Any]]] | None]
             ) -> None:
    TMP_REGISTRY[f_name] = fun