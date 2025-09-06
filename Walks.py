from Node import Node
import random

def pick_based_on_jacc(neighbors: list[tuple[int,float]]) -> int:

    idxs, list_of_jacc = zip(*neighbors)
    sum_of_all_n = sum(list_of_jacc)

    x = random.uniform(0, sum_of_all_n)

    acc: float = 0.0
    for cnt in range(len(list_of_jacc)):
        acc += list_of_jacc[cnt]

        if x <= acc:
            return idxs[cnt]

    return -1

def random_walk(g: list[Node], nd: Node, w_len: int) -> list[Node]:
    walk = [nd]
    for _ in range(w_len - 1):
        neighbors = nd.neighbors()
        if neighbors:
          walk.append(g[pick_based_on_jacc(neighbors)])
        else:
            break

    return walk

def generate_walks(g: list[Node], n_walks: int, w_len: int ) -> list[list[Node]]:
    walks = []
    for _ in range(n_walks):
        for nd in g:      #maybe I should uniformly choose the root
            walks.append(random_walk(g, nd, w_len))

    return walks

def create_tc_p(walks: list[list[Node]], w_size: int) -> list[tuple[Node,Node]]:

    p = []
    for walk in walks:
        for cnt in range(len(walk)):
            t = walk[cnt]
            for cnt2 in range (max(0,cnt - w_size), min(len(walk), cnt + w_size)):
                if cnt != cnt2:
                    c = walk[cnt2]
                    p.append((t,c))
    return p