"""
File: __init__.py
Author: Jozef Michal Bukas <jozefmbukas@gmail.com>
Date: 24.7.2026
Brief: Init file for tmp edge workers that scans and registers all tmp edge algorithms into registry
"""
import importlib
import inspect
import pkgutil
from typing import Any, Callable
from graph_repository.Neo4jDBDriver import Neo4jDBDriver

EDGES_T = list[tuple[list[dict], dict[str,Any]]]
TMP_FUNC_T = Callable[[dict, int, int, Neo4jDBDriver], tuple[list[dict], dict[str, Any]] | EDGES_T | None]

TMP_REGISTRY: dict[str, TMP_FUNC_T] = {}

for _, name, _ in pkgutil.iter_modules(__path__):
    module = importlib.import_module(f"{__name__}.{name}")

    for f_name, func in inspect.getmembers(module, inspect.isfunction):
        if f_name.startswith("tmp_"):
            TMP_REGISTRY[f_name] = func