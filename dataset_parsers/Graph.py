import torch as th
import dgl
import networkx as nx
from dataset_parsers.dglGraph.ExportGraph import export_graph
from misc.Logger import MyLogger

def gen_train_test_masks(n_nodes: int) -> tuple[th.Tensor, th.Tensor]:
    train_mask = th.rand(n_nodes) < 0.9
    test_mask = th.tensor([not bool(m) for m in train_mask], dtype=th.bool)

    return train_mask, test_mask


def regenerate_train_test_mask(g: dgl.DGLGraph):
    train, test = gen_train_test_masks(g.num_nodes())

    #if g.is_homogeneous:
    g.ndata['train_mask'] = train
    g.ndata['test_mask'] = test
    #else:
    #    g.ndata['train_mask'] = {'d':train}
    #    g.ndata['test_mask'] = {'d':test}

def create_graph(u: th.Tensor, v: th.Tensor, jacc: th.Tensor, labels: th.Tensor, num_nodes: int) -> dgl.DGLGraph:
    g = dgl.graph((u, v), num_nodes=num_nodes)

    g.edata['weight'] = jacc
    g.ndata['label'] = labels

    regenerate_train_test_mask(g)

    g = dgl.add_reverse_edges(g,copy_ndata=True,copy_edata=True)

    return g

def create_hetero_graph(edges: dict[tuple[str,str,str], tuple[th.Tensor, th.Tensor]], weights: dict[ tuple[str,str,str], th.Tensor] | None, labels: list[int], num_nodes: int | None = None) -> dgl.DGLGraph:

    if num_nodes is None:
        g = dgl.heterograph(edges)
    else:
        g = dgl.heterograph(edges, num_nodes_dict={'d':num_nodes})
    g.ndata['label'] = th.tensor(labels).to(th.int)
    if weights is not None:
        g.edata['weight'] = weights

    regenerate_train_test_mask(g)

    return g

def get_in_out_degrees(g: dgl.DGLGraph) -> tuple[th.Tensor, th.Tensor]:

    if g.is_homogeneous:
        return g.in_degrees(), g.out_degrees()
    else:
        indexes = th.tensor(range(g.number_of_nodes()), dtype=th.int32)
        in_d = th.zeros(g.number_of_nodes(), dtype=th.int32)
        out_d = th.zeros(g.number_of_nodes(), dtype=th.int32)

        for e_type in g.etypes:
            in_d.index_add_(0, indexes, g.in_degrees(etype=e_type))
            out_d.index_add_(0, indexes, g.out_degrees(etype=e_type))

        return in_d, out_d #dns, datasets

def remove_given_nodes(g: dgl.DGLGraph, isolated_nodes: th.Tensor) -> dgl.DGLGraph:

    if g.is_homogeneous:
        return dgl.remove_nodes(g, isolated_nodes)
    else:
        return dgl.remove_nodes(g, isolated_nodes, ntype='d', store_ids=True)

def remove_isolated_nodes(g: dgl.DGLGraph) -> dgl.DGLGraph:

    ins, out = get_in_out_degrees(g)

    isolated_nodes = th.nonzero((ins == 0) & (out == 0), as_tuple=True)[0].to(th.int32)

    return remove_given_nodes(g, isolated_nodes)

def get_connected_components(g: dgl.DGLGraph, without_isolated_nodes: bool = True) :#-> list[dgl.DGLGraph]:

    if without_isolated_nodes:
        g = remove_isolated_nodes(g)

    nx_g = dgl.to_networkx(g).to_undirected()
    components = list(nx.connected_components(nx_g))

    res = [ dgl.node_subgraph(g,list(c)) for c in components]

    return res

def get_nodes_connected_component(g: dgl.DGLGraph, nd: int, etypes: list[str] | None) -> dgl.DGLGraph:

    scc = dfs(g, nd, etypes)
    return  dgl.node_subgraph(g, scc, store_ids=True)

def get_and_export_connected_components(g: dgl.DGLGraph, export_prefix: str, without_isolated_nodes: bool = True) -> None:
    
    if without_isolated_nodes:
        g = remove_isolated_nodes(g)

    nx_g = dgl.to_networkx(g).to_undirected()
    components = list(nx.connected_components(nx_g))

    for cnt, c in enumerate(components):

        n_comp = dgl.node_subgraph(g,list(c))
        export_graph(n_comp, export_prefix + f"{cnt}" + '.dglg')

    return

def dfs(g: dgl.DGLGraph, start: int, etypes: list[str] | None = None) -> list[int]:
    visited = set()
    in_stack = set()
    in_stack.add(start)
    stack = [(start, 0)]
    if etypes is None:
        etypes = g.etypes

    while stack:
        node, depth = stack.pop()
        #print(f"{len(stack)}")
        if node in visited:
            continue

        visited.add(node)
        if depth >= 4:
            continue

        for etype in etypes:
            for v_t in g.successors(node, etype=etype):
                v = int(v_t)
                if v not in in_stack:
                    in_stack.add(v)
                    stack.append((v, depth + 1))


    return list(visited)
