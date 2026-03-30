import dgl
import networkx as nx
import numpy as np
import torch
import torch as th
from torch.optim import SparseAdam
from torch.utils.data import DataLoader
from dgl.nn.pytorch import MetaPath2Vec
import sklearn.linear_model as sk
from graph_repository.workers.common.GraphTypes import NodeTypes, EdgeTypes
from misc.Logger import MyLogger


def _train_log_regres_and_cls(g: dgl.DGLHeteroGraph, embeddings: list[th.Tensor]):

    cpu_device = th.device('cpu')
    train_mask = g.ndata['train_mask']['d'].to(cpu_device)
    classify_mask = g.ndata['test_mask']['d'].to(cpu_device)
    labels = g.ndata['l']['d'].to(cpu_device)

    for model_embedding in embeddings:
        clf = sk.LogisticRegression().fit(model_embedding[train_mask].detach().numpy(), labels[train_mask].detach().numpy())
        result = clf.predict_proba(model_embedding[classify_mask].detach().numpy())
        print(result)


def _generate_embeddings(models: list[MetaPath2Vec], g: dgl.DGLHeteroGraph, device: th.device, lr=0.01) -> list:

    print(g.device)
    print(next(models[0].parameters()).device)

    embeds = []
    cnt = 0
    for model in models:
        print(f"Model {cnt}")
        dataloader = DataLoader(torch.arange(g.num_nodes(ntype='d')),batch_size=128,shuffle=True,collate_fn=model.sample)
        optimizer = SparseAdam(model.parameters(), lr=lr)

        for epoch in range(5):
            for pos_u, pos_v, neg_v in dataloader:
                pos_u = pos_u.to(device)
                pos_v = pos_v.to(device)
                neg_v = neg_v.to(device)

                loss = model(pos_u, pos_v, neg_v)
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()
                print(f"Model {cnt}, epoch {epoch} - loss: {loss.item()}")

        d_node_ids = torch.LongTensor(model.local_to_global_nid['d']).to(device)
        d_emb = model.node_embed(d_node_ids).to(th.device('cpu'))  #model.node_embed(d_node_ids)
        embeds.append(d_emb)
        print(f'Model {cnt} done')
        cnt += 1

    return embeds

def _create_models_for_meta_paths(
        m_paths: list[list[str]],
        g: dgl.DGLHeteroGraph,
        device: th.device,
        w_size: int = 3,
        emb_dim: int = 64,
        neg_size: int = 5) -> list[MetaPath2Vec]:

    models = []
    for path in m_paths:
        model = MetaPath2Vec(g, path, window_size=w_size,emb_dim=emb_dim,negative_size=neg_size)
        model.to(device)
        models.append(model)

    return models


def classify_domain(g: dgl.DGLHeteroGraph) -> tuple[float, float] | None:

    if len(g.nodes(ntype='d')) < 2:
        MyLogger.get_instance().log_warning("Need at least 2 domain nodes")
        return None

    labels = g.ndata['l']['d']
    unique_labels, counts = np.unique(labels[g.ndata['train_mask']['d']].numpy(), return_counts=True)
    print(counts)
    if len(unique_labels) < 2:
        MyLogger.get_instance().log(
            f"All neighboring nodes in sampled neighborhood are of class: {'benign' if unique_labels[0] == 1 else 'malicious'}"
        )
        return float(unique_labels[0] == 0), float(unique_labels[0] == 1)

    device = th.device('cuda' if th.cuda.is_available() else 'cpu')
    g = g.to(device)

    paths = [[f"{EdgeTypes.CNAME.value}_{NodeTypes.DOMAIN.dgl}_{NodeTypes.DOMAIN.dgl}"] * 8,
             [f"{EdgeTypes.SUBDOMAIN.value}_{NodeTypes.DOMAIN.dgl}_{NodeTypes.DOMAIN.dgl}"] * 8,
             [f"{EdgeTypes.TRANSLATES.value}_{NodeTypes.DOMAIN.dgl}_{NodeTypes.IP.dgl}",
              f"{EdgeTypes.TRANSLATES.value}_{NodeTypes.IP.dgl}_{NodeTypes.DOMAIN.dgl}"] * 4,
             ]
    models = _create_models_for_meta_paths(paths, g, device)

    embeds = _generate_embeddings(models, g, device)
    _train_log_regres_and_cls(g, embeds)

    return None