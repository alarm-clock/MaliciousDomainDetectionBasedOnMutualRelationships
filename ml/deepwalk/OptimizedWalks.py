import dgl
import numpy as np
from dgl import DGLGraph
import torch as th
from numba import njit, prange


def gen_alias_and_prob_tables(weights: list[float]) -> tuple[np.ndarray, np.ndarray]:
    if len(weights) == 0:
        return np.empty(0, dtype=np.float32), np.empty(0, dtype=np.float32)

    probs = np.array(weights, dtype=np.float64)
    probs_sum = np.sum(probs)

    if probs_sum == 0:
        probs = np.ones(len(weights), dtype=np.float64) / len(weights)
    else:
        probs = probs / probs_sum

    probs = probs * len(weights)

    alias_table = np.empty(len(weights), dtype=np.int32)
    underfull = []
    overfull = []

    for i, probability in enumerate(probs):
        if probability < 1:
            underfull.append(i)
        else:
            overfull.append(i)

    while underfull and overfull:
        u = underfull.pop()
        o = overfull.pop()
        alias_table[u] = o
        probs[o] = probs[o] - (1.0 - probs[u])

        if probs[o] < 1.0:
            underfull.append(o)
        else:
            overfull.append(o)

    #walker-vose method ending because it is impossible to set prob table on exactly one
    for rest in overfull + underfull:
        probs[rest] = 1
        alias_table[rest] = rest

    return probs, alias_table


def get_neighbors_and_weights_lists(g: dgl.DGLGraph) -> tuple[list[tuple[int, th.Tensor]], list[list[float]]]:
    neighbors: list[tuple[int, th.Tensor]] = []
    for nd in g.nodes():
        neighbors.append((nd, DGLGraph.successors(g, nd)))

    weights: list[list[float]] = []
    for u, vs in neighbors:
        edge_ids = DGLGraph.edge_ids(g, [u] * len(vs), vs, False)
        weights.append([g.edata['weight'][e_id] for e_id in edge_ids])

    return neighbors, weights


def precompute_data_for_walks(g: dgl.DGLGraph) -> None:
    neighbors, weights = get_neighbors_and_weights_lists(g)
    probs = np.empty(len(neighbors), dtype=np.float32)
    alias = np.empty(len(neighbors), dtype=np.int32)

    N = len(neighbors) - 1
    for u in range(N):
        if len(neighbors[u][1]) == 0:
            continue

        nd_p, nd_a = gen_alias_and_prob_tables(weights[u])
        probs[u] = nd_p
        alias[u] = nd_a

    g.ndata['prob'] = probs
    g.ndata['alias'] = alias


@njit(parallel=True)
def generate_walks(starts: list[int], walk_length: int, neighbors: list[th.Tensor], probs: np.ndarray, alias: np.ndarray, result: th.Tensor) -> None:
    n_walks = len(starts)
    for cnt in prange(n_walks):
        curr = starts[cnt]
        result[cnt, 0] = curr
        for step in range(1, walk_length):
            if len(neighbors[curr]) == 0:
                result[cnt, step] = curr
                continue

            x = int(np.floor(np.random.rand() * len(neighbors[curr])))

            if np.random.rand() < probs[cnt, x]:
                nxt = neighbors[curr][x]
            else:
                nxt = neighbors[curr][alias[x]]

            result[cnt, step] = nxt
            curr = nxt
