import torch
import torch as th
from dataset_parsers.raw.Node import Node

def convert_to_dgl(g_old: list[Node]) -> tuple[th.Tensor, th.Tensor, th.Tensor, th.Tensor]:

    u, v, jacc, label = th.tensor([]), th.tensor([]), th.tensor([]), th.tensor([])

    for nd in g_old:

        if nd.b:
            b = th.ones(1)
        else:
            b = th.zeros(1)

        label = th.cat((label,b)).to(th.int)

        if not nd.neighbors():
            continue

        target_ids_t, target_jacc_t = zip(*nd.neighbors())

        v_ext = th.tensor(list(target_ids_t))
        jacc_ext = th.tensor(list(target_jacc_t))
        u_ext = th.full((len(nd.neighbors()),), nd.id)

        u = th.cat((u,u_ext)).to(torch.long)
        v = th.cat((v,v_ext)).to(torch.long)
        jacc = th.cat((jacc,jacc_ext)).to(torch.double)

    return u, v, jacc, label
