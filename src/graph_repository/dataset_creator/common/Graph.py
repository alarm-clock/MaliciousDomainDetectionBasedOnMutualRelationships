"""
File: Graph.py
Author: Jozef Michal Bukas <xbukas00@stud.fit.vutbr.cz>
Date: 22.02.2026
Brief: File that contains helper functions and type aliases for creating DGL
    heterographs, generating train/test masks, and handling homogeneous-like
    graphs through heterogeneous graph interface
"""

from graph_repository.workers.common.GraphTypes import NodeTypes, EdgeTypes
import torch as th
import dgl


E_T_DGL = tuple[str, str, str]
EDGES_T_DGL = dict[E_T_DGL, tuple[th.Tensor, th.Tensor]]
N_DATA_T_DGL = dict[str, dict[str, th.Tensor]]
E_DATA_T_DGL = dict[str, dict[E_T_DGL, th.Tensor]]

def generate_masks(n_nodes: int) -> tuple[th.Tensor, th.Tensor]:
    """
    Function that generates random train and test masks for given number of nodes
    :param n_nodes: `int` number of nodes for which masks will be generated
    :return: `tuple[th.Tensor, th.Tensor]` train mask and test mask
    """
    train_mask = th.rand(n_nodes) < 0.9
    test_mask = th.tensor([not bool(train_flag) for train_flag in train_mask], dtype=th.bool)

    return train_mask, test_mask

def regenerate_train_test_mask(g: dgl.DGLHeteroGraph) -> None:
    """
    Function that regenerates train and test masks for domain nodes in given graph
    :param g: `dgl.DGLHeteroGraph` graph whose masks will be regenerated
    :return: None
    """

    train_mask, test_mask = generate_masks(g.num_nodes(NodeTypes.DOMAIN.dgl))

    g.ndata['train_mask'] = {NodeTypes.DOMAIN.dgl: train_mask} if len(g.ntypes) > 1 else train_mask
    g.ndata['test_mask'] = {NodeTypes.DOMAIN.dgl: test_mask} if len(g.ntypes) > 1 else test_mask

    return

def generate_train_mask_classification(g: dgl.DGLHeteroGraph, classified_nd_id: int) -> None:
    """
    Function for generating train mask for classification
    :param g: graph for which nodes masks will be created
    :param classified_nd_id: node_id of domain that is classified
    :return: None
    """
    train_mask = th.ones(g.num_nodes(NodeTypes.DOMAIN.dgl)).to(th.bool)
    train_mask[classified_nd_id] = False
    classification_mask = th.tensor([not bool(train_flag) for train_flag in train_mask], dtype=th.bool)

    g.ndata['train_mask'] = {NodeTypes.DOMAIN.dgl: train_mask} if len(g.ntypes) > 1 else train_mask
    g.ndata['test_mask'] = {NodeTypes.DOMAIN.dgl: classification_mask} if len(g.ntypes) > 1 else classification_mask

def check_if_g_is_hetero(edges: EDGES_T_DGL) -> bool:
    """
    Function that checks if created graph is homogenous or heterogeneous
    :param edges: Edges from which graph will be created
    :return: True if graph is heterogeneous otherwise false
    """

    seen_n_t: set[str] = set()

    for u_t, _, v_t in edges.keys():

        if u_t not in seen_n_t:
            seen_n_t.add(u_t)

        if v_t not in seen_n_t:
            seen_n_t.add(v_t)

    return len(seen_n_t) > 1

def add_diff_n_t_to_g(edges: EDGES_T_DGL) -> None:
    """
    Function which adds 2 nodes of type maintenance so that graph will be "heterogeneous" in libraries eyes. This function
    Exists solely because it is easier to ass two not used nodes then rewriting a lot of system logic to call DGl's methods
    differently based on if graph is heterogeneous or homogeneous. Heterogeneous graph is generalization of homogeneous
    graphs so only reason that they do it like this must be optimization. But for me, it adds no time for me to be noticeable
    enough to rewrite whole logic (I mean there is no time difference whatsoever).
    :param edges: Edge from which graph will be added
    :return: None
    """

    edges[(NodeTypes.MAINTENANCE.dgl, EdgeTypes.NULL.value, NodeTypes.MAINTENANCE.dgl)] = (th.Tensor([0]).to(th.int32), th.Tensor([1]).to(th.int32))

def create_dgl_graph(
        edges: EDGES_T_DGL,
        n_data: N_DATA_T_DGL | None = None,
        e_data: E_DATA_T_DGL | None = None,
        num_nodes: dict[str, int] | None = None,
        generate_train_mask: bool = False) -> dgl.DGLHeteroGraph:
    """
    Function for creating dgl heterograph
    :param edges: dictionary of (u,v) tuples with canonical edge type as key
    :param n_data: dictionary with data names as keys and dictionaries with values for given node type as values, defaults to None
    :param e_data: dictionary with data names as keys and dictionaries with values for given edge type as values, defaults to None
    :param num_nodes: number of nodes for given node type, optional, use only if you want to have more nodes than there already are,
        defaults to None, must be >= than the largest node id of given node type, defaults to None
    :param generate_train_mask: flag indicating if train/test masks should be generated, defaults to False
    :return: dgl heterograph
    """

    if not check_if_g_is_hetero(edges):
        add_diff_n_t_to_g(edges)

    if num_nodes is None:
        g = dgl.heterograph(edges)
    else:
        g = dgl.heterograph(edges, num_nodes_dict=num_nodes)

    node_types = g.ntypes
    edge_types = g.etypes

    if n_data is not None:
        for data_type, data_dict in n_data.items():
            g.ndata[data_type] = data_dict if len(node_types) > 1 else data_dict[node_types[0]]

    if e_data is not None:
        for data_type, data_dict in e_data.items():
            g.edata[data_type] = data_dict if len(edge_types) > 1 else data_dict[next(iter(data_dict.keys()))]
            # edge can and will only hold one value therefore there is only one key

    if generate_train_mask: regenerate_train_test_mask(g)

    return g

def remove_lonely_nodes(self, edge_types: list[str] | None = None):
    """
    Method placeholder for removing lonely nodes from graph
    :param edge_types: `list[str] | None` optional list of edge types to consider
    :return: None
    """
    pass

def k_hop_neighbors(self, edge_types: list[str] | None = None):
    """
    Method placeholder for obtaining k-hop neighbors in graph
    :param edge_types: `list[str] | None` optional list of edge types to consider
    :return: None
    """
    pass