import torch as th
import dgl
import networkx as nx

def gen_train_test_masks(n_nodes: int) -> tuple[th.Tensor, th.Tensor]:
    train_mask = th.rand(n_nodes) < 0.9
    test_mask = th.tensor([not bool(m) for m in train_mask], dtype=th.bool)

    return train_mask, test_mask

def create_graph(u: th.Tensor, v: th.Tensor, jacc: th.Tensor, labels: th.Tensor, num_nodes: int) -> dgl.DGLGraph:
    g = dgl.graph((u, v), num_nodes=num_nodes)

    g.edata['weight'] = jacc
    g.ndata['label'] = labels

    train_mask, test_mask = gen_train_test_masks(num_nodes)
    g.ndata['train_mask'] = train_mask
    g.ndata['test_mask'] = test_mask

    g = dgl.add_reverse_edges(g,copy_ndata=True,copy_edata=True)

    return g

def remove_isolated_nodes(g: dgl.DGLGraph) -> dgl.DGLGraph:

    ins = g.in_degrees()
    out = g.out_degrees()

    isolated_nodes = th.nonzero((ins == 0) & (out == 0), as_tuple=True)[0]

    new_g = dgl.remove_nodes(g, isolated_nodes)
    return new_g

def get_connected_components(g: dgl.DGLGraph, without_isolated_nodes: bool = True) :#-> list[dgl.DGLGraph]:

    if without_isolated_nodes:
        g = remove_isolated_nodes(g)

    nx_g = dgl.to_networkx(g).to_undirected()
    components = list(nx.connected_components(nx_g))

    res = [ dgl.node_subgraph(g,list(c)) for c in components]

    return res
