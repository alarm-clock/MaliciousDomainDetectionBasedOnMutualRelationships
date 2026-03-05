from typing import Any
from misc.PackageImporter import get_options_from_registry
from graph_repository.workers.common.EditWorker import EDIT_WORKER_REGISTRY
from graph_repository.Neo4jDBClient import Neo4jDBClient




def temporary_add_domain(domain: dict[str, Any],  driver: Neo4jDBClient) -> str:

    available_options = []
    get_options_from_registry(EDIT_WORKER_REGISTRY, available_options)



    return ""