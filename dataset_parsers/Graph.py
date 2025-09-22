import torch as th
import dgl

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