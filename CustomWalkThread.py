import threading
import dgl
import random
import torch as th


class WalksGenerator(threading.Thread):

    def __init__(self, list_lock: threading.Lock, w: list[list[int]], g: dgl.DGLGraph, w_len: int):
        super().__init__()
        self._list_lock = list_lock
        self._g = g
        self._w = w
        self._w_len = w_len

    def _pick_based_on_jacc(self, neighbors: list[int]) -> int:

        jaccs = [self._g.edata['weight'][n] for n in neighbors]

        return random.choices(neighbors, weights=jaccs,k=1)[0]

    def _random_walk(self, nd: int) -> list[int]:

        walk: list[int] = [nd]
        current = nd

        cnt = 0
        for _ in range(self._w_len - 1):
            cnt += 1
            neighbors: th.Tensor = self._g.successors(current)
            if neighbors.numel() != 0:
                current = self._pick_based_on_jacc(neighbors.tolist())
                walk.append(current)
            else:
                break

        return walk

    def _return_res(self, walks: list[list[int]]) -> None:
        self._list_lock.acquire()
        self._w.extend(walks)
        self._list_lock.release()

    def run(self):

        walks = []
        for nd in self._g.nodes().tolist():
            walks.append(self._random_walk(nd))

        self._return_res(walks)
