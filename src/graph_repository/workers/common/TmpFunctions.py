"""
File: TmpFunctions.py
Author: Jozef Michal Bukas <xbukas00@stud.fit.vutbr.cz>
"""
from typing import Any, Callable
from graph_repository.Neo4jDBDriver import Neo4jDBDriver

EDGES_T = list[tuple[list[dict], dict[str,Any]]]
TMP_FUNC_T = Callable[[dict, int, int, Neo4jDBDriver], tuple[list[dict], dict[str, Any]] | EDGES_T | None]

TMP_REGISTRY: dict[str, TMP_FUNC_T] = {}

def register(f_name: str, fun: TMP_FUNC_T ) -> None:
    """
    Method to register a filter
    :param f_name:
    :param fun:
    :return:
    """
    TMP_REGISTRY[f_name] = fun