from typing import Any
from domain_evaluation.Metapath2vec.Learning import classify_domain
from graph_repository.graph_main.GraphRepository import GraphRepository
from graph_repository.Neo4jDBDriver import Neo4jDBDriver
from graph_repository.workers.common.GraphTypes import NodeTypes


def evaluate_domain_meta_path2vec(domain: dict[str, Any]) -> None:

    repository: GraphRepository = GraphRepository.get_instance()

    if repository is None:
        return

    tmp_node_id = repository.temporary_add_domain(domain)
    graph = repository.get_k_hop_neighborhood_dgl(tmp_node_id,True)
    repository.delete_temporary_domain(tmp_node_id)
    classify_domain(graph)
