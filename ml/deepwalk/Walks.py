from dataset_parsers.raw.Node import Node
import random
import dgl
import torch as th
import threading
from ml.deepwalk.CustomWalkThread import WalksGenerator


def pick_based_on_jacc(g: dgl.DGLGraph, neighbors: list[int]) -> int:
    jaccs = [g.edata['weight'][n] for n in neighbors]
    sum_of_all_n = sum(jaccs)

    x = random.uniform(0, sum_of_all_n)
    acc: float = 0.0
    for cnt in range(len(jaccs)):
        acc += jaccs[cnt]

        if x <= acc:
            return neighbors[cnt]

    return -1


def random_walk(g: dgl.DGLGraph, nd: int, w_len: int) -> list[int]:
    walk: list[int] = [nd]
    current = nd

    cnt = 0
    for _ in range(w_len - 1):
        cnt += 1
        neighbors: th.Tensor = g.successors(current)
        if neighbors.numel() != 0:
            current = pick_based_on_jacc(g, neighbors.tolist())
            walk.append(current)
        else:
            break

    return walk


def generate_walks_tensor(g: dgl.DGLGraph, n_walks: int, w_len: int) -> th.Tensor:
    walks = []
    for _ in range(n_walks):
        for nd in g.nodes().tolist():
            walks.append(random_walk(g, nd, w_len))

    return th.tensor(walks)

def generate_walks_tensor_parallel(g: dgl.DGLGraph, n_walks: int, w_len: int) -> th.Tensor:
    walks = []
    generators = []
    list_lock = threading.Lock()
    for _ in range(n_walks):
        generator = WalksGenerator(list_lock, walks, g, w_len)
        generator.start()
        generators.append(generator)

    for g in generators:
        g.join()

    return th.tensor(walks)


def create_tc_p(walks: list[list[Node]], w_size: int) -> list[tuple[Node, Node]]:
    p = []
    for walk in walks:
        for cnt in range(len(walk)):
            t = walk[cnt]
            for cnt2 in range(max(0, cnt - w_size), min(len(walk), cnt + w_size)):
                if cnt != cnt2:
                    c = walk[cnt2]
                    p.append((t, c))
    return p
