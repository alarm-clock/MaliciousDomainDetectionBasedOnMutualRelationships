from graph_repository.workers.common.GraphTypes import NodeTypes
import torch as th
import dgl

def generate_masks(n_nodes: int) -> tuple[th.Tensor, th.Tensor]:
    train_mask = th.rand(n_nodes) < 0.9
    test_mask = th.tensor([not bool(train_flag) for train_flag in train_mask], dtype=th.bool)

    return train_mask, test_mask

def regenerate_train_test_mask(g: dgl.DGLHeteroGraph) -> None:

    train_mask, test_mask = generate_masks(g.num_nodes(NodeTypes.DOMAIN.value))

    g.ndata['train_mask'] = {NodeTypes.DOMAIN.value: train_mask} if len(g.ntypes) > 1 else train_mask
    g.ndata['test_mask'] = {NodeTypes.DOMAIN.value: test_mask} if len(g.ntypes) > 1 else test_mask

    return

def create_dgl_graph(
        edges: dict[tuple[str,str,str], tuple[th.Tensor, th.Tensor]],
        n_data: dict[str, dict[str, th.Tensor]],
        e_data: dict[str, dict[tuple[str,str,str], th.Tensor]],
        num_nodes: dict[str, int] | None = None) -> dgl.DGLHeteroGraph:

    if num_nodes is None:
        g = dgl.heterograph(edges)
    else:
        g = dgl.heterograph(edges, num_nodes_dict = num_nodes)

    node_types = g.ntypes
    edge_types = g.etypes

    for data_type, data_dict in n_data.items():
        g.ndata[data_type] = data_dict if len(node_types) > 1 else data_dict[node_types[0]]

    for data_type, data_dict in e_data.items():
        g.edata[data_type] = data_dict if len(edge_types) > 1 else data_dict[next(iter(data_dict.keys()))]
                                                        # edge can and will only hold one value therefore there is only one key

    regenerate_train_test_mask(g)

    return g

def remove_lonely_nodes(self, edge_types: list[str] | None = None):
    pass

def k_hop_neighbors(self, edge_types: list[str] | None = None):
    pass