from typing import Any
import dgl
import numpy
import numpy as np
import torch
import torch as th
from torch.optim import SparseAdam
from torch.utils.data import DataLoader
from dgl.nn.pytorch import MetaPath2Vec
import sklearn.linear_model as sk
from sklearn.preprocessing import StandardScaler
from graph_repository.workers.common.GraphTypes import NodeTypes, EdgeTypes
from misc.Logger import MyLogger
import torch.multiprocessing as mp

STANDALONE = 0
STANDALONE_CONCAT = 1
CONCAT = 2
AVERAGE = 3
ALL = 4


def _train_regress(model_embedding: th.Tensor, train_mask,
                   classify_mask: th.Tensor, labels: th.Tensor, scale: bool) -> th.Tensor:
    if scale:
        model_embedding = StandardScaler().fit_transform(model_embedding.detach().numpy())
    clf = sk.LogisticRegression(max_iter=130).fit(model_embedding[train_mask], labels[train_mask].detach().numpy())
    result = clf.predict_proba(model_embedding[classify_mask])
    return result


def _train_log_regress_and_cls(
        g: dgl.DGLHeteroGraph,
        embeddings: list[th.Tensor],
        mode: int,
        scale: bool = True) :

    cpu_device = th.device('cpu')
    train_mask = g.ndata['train_mask']['d'].to(cpu_device)
    classify_mask = g.ndata['test_mask']['d'].to(cpu_device)
    labels = g.ndata['l']['d'].to(cpu_device)
    results_dict = {}

    if mode == STANDALONE or mode == STANDALONE_CONCAT or mode == AVERAGE or mode == ALL:
        avg_0 = []
        avg_1 = []

        for cnt, model_embedding in enumerate(embeddings):
            result = _train_regress(model_embedding, train_mask, classify_mask, labels, scale)
            print(result[0])
            results_dict[f'STANDALONE_{cnt}'] = result[0]
            avg_0.append(result[0][0])
            avg_1.append(result[0][1])

        if mode == AVERAGE or mode == ALL:
            avg_mal = sum(avg_0) / len(avg_0)
            abg_ben = sum(avg_1) / len(avg_1)
            results_dict['AVERAGE'] = numpy.array([avg_mal, abg_ben])
            print(numpy.array([avg_mal, abg_ben]))

    if mode == STANDALONE_CONCAT or mode == CONCAT or mode == ALL:
        concat_embeds = th.cat(embeddings, dim=1)
        result_concat = _train_regress(concat_embeds, train_mask, classify_mask, labels, scale)
        print(result_concat[0])
        results_dict['CONCAT'] = result_concat[0]

    return results_dict

def _train_metapath2vec(model_loader: tuple[MetaPath2Vec, DataLoader], device: th.device, lr: float, cnt: int) -> tuple[th.Tensor, list[float]]:
    #print(f"Model {cnt}")
    MyLogger.get_instance().log(f"Working on model {cnt}")
    model, dataloader = model_loader
    optimizer = SparseAdam(model.parameters(), lr=lr)
    loss_cum = []

    for epoch in range(5):
        for pos_u, pos_v, neg_v in dataloader:
            pos_u = pos_u.to(device)
            pos_v = pos_v.to(device)
            neg_v = neg_v.to(device)

            loss = model(pos_u, pos_v, neg_v)
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            #print(f"Model {cnt}, epoch {epoch} - loss: {loss.item()}")
            loss_cum.append(loss.item())

        MyLogger.get_instance().log(f"Model {cnt} epoch {epoch} loss {loss_cum[-1]}")

    d_node_ids = torch.LongTensor(model.local_to_global_nid['d']).to(device)
    d_emb = model.node_embed(d_node_ids).detach().cpu()  # model.node_embed(d_node_ids)
    MyLogger.get_instance().log(f"Model {cnt} done")

    return d_emb, loss_cum

def _gen_embeds_parallel(models: list[tuple[MetaPath2Vec, DataLoader]], device: th.device, lr=0.01) -> tuple[list[th.Tensor], list[list[float]]]:

    with mp.Pool(processes=3) as pool:
        results = pool.starmap(_train_metapath2vec, [(model, device, lr, cnt) for cnt, model in enumerate(models)])

    return zip(*results)

def _generate_embeddings(models: list[tuple[MetaPath2Vec, DataLoader]], device: th.device, lr=0.01) -> tuple[list[th.Tensor], list[list[float]]]:

    embeds = []
    loss_arr = []
    cnt = 0
    for model, dataloader in models:
        print(f"Model {cnt}")
        MyLogger.get_instance().log(f"Working on model {cnt}")
        optimizer = SparseAdam(model.parameters(), lr=lr)
        loss_cum = []

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
                loss_cum.append(loss.item())

            MyLogger.get_instance().log(f"Model {cnt} epoch {epoch} loss {loss_cum[-1]}")

        d_node_ids = torch.LongTensor(model.local_to_global_nid['d']).to(device)
        d_emb = model.node_embed(d_node_ids).to(th.device('cpu'))  #model.node_embed(d_node_ids)
        embeds.append(d_emb)
        loss_arr.append(loss_cum)
        print(f'Model {cnt} done')
        MyLogger.get_instance().log(f"Model {cnt} done")
        cnt += 1

    return embeds, loss_arr


def _create_models_for_meta_paths(
        m_paths: list[list[str]],
        g: dgl.DGLHeteroGraph,
        device: th.device,
        w_size: int = 2,
        emb_dim: int = 64,
        neg_size: int = 5) -> tuple[list[tuple[MetaPath2Vec, DataLoader]], list[str]]:
    models = []
    paths = []
    for path in m_paths:

        try:
            model = MetaPath2Vec(g, path, window_size=w_size, emb_dim=emb_dim, negative_size=neg_size)
        except Exception as e:
            MyLogger.get_instance().log_error(str(e))
            MyLogger.get_instance().log_warning(f"Ommiting metapath {path} because there are no edges of given type")
            continue
        model.to(device)
        dataloader = DataLoader(torch.arange(g.num_nodes(ntype='d')), batch_size=128, shuffle=True,collate_fn=model.sample)
        models.append((model, dataloader))
        paths.append(path[0].split('_')[0])

    return models, paths


def get_class_counts(g: dgl.DGLHeteroGraph):
    labels = g.ndata['l']['d']
    return np.unique(labels[g.ndata['train_mask']['d']].numpy(), return_counts=True)


def check_for_duplicity(g: dgl.DGLHeteroGraph) -> bool | tuple:
    if len(g.nodes(ntype='d')) < 2:
        MyLogger.get_instance().log_warning("Need at least 2 domain nodes")
        return False

    unique_labels, counts = get_class_counts(g)

    if len(unique_labels) < 2:
        MyLogger.get_instance().log(
            f"All neighboring nodes in sampled neighborhood are of class: {'benign' if unique_labels[0] == 1 else 'malicious'}"
        )
        return {"cname": (float(unique_labels[0] == 0), float(unique_labels[0] == 1))}, [], int(
            unique_labels[0] == 0), int(unique_labels[0] == 1), []

    return True

def classify_domain(g: dgl.DGLHeteroGraph, mode: int = STANDALONE_CONCAT, no_need_for_correct_check: bool = False) -> Any | None:

    if not no_need_for_correct_check:
        check_result = check_for_duplicity(g)
        if type(check_result) == tuple:
            return check_result
        else:
            if not check_result:
                return None

    _, counts = get_class_counts(g)

    device = th.device('cuda' if th.cuda.is_available() else 'cpu')
    MyLogger.get_instance().log(
        f"This device does {'' if th.cuda.is_available() else 'not'} have GPU, chosen device is {device}")
    g = g.to(device)

    paths = [[f"{EdgeTypes.CNAME.value}_{NodeTypes.DOMAIN.dgl}_{NodeTypes.DOMAIN.dgl}"] * 8,
             [f"{EdgeTypes.SUBDOMAIN.value}_{NodeTypes.DOMAIN.dgl}_{NodeTypes.DOMAIN.dgl}"] * 8,
             [f"{EdgeTypes.TRANSLATES.value}_{NodeTypes.DOMAIN.dgl}_{NodeTypes.IP.dgl}",
              f"{EdgeTypes.TRANSLATES.value}_{NodeTypes.IP.dgl}_{NodeTypes.DOMAIN.dgl}"] * 4,
             ]
    models, used_paths = _create_models_for_meta_paths(paths, g, device)
    embeds, loss_arr = _gen_embeds_parallel(models, device) #_generate_embeddings(models, g, device)
    res = _train_log_regress_and_cls(g, embeds, mode)

    return res, loss_arr, counts[0], counts[1], used_paths
