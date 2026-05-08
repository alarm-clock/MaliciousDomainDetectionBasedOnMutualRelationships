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

from domain_evaluation.EvaluationObjects import EvaluationResult
from graph_repository.dataset_creator.common.Graph import regenerate_train_test_mask
from graph_repository.workers.common.GraphTypes import NodeTypes, EdgeTypes
from misc.Logger import MyLogger
import torch.multiprocessing as mp


PRODUCTION = True
TESTING = False


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
        path_names: list[str],
        mode: bool,
        scale: bool = True) :

    cpu_device = th.device('cpu')
    train_mask = g.ndata['train_mask']['d'].to(cpu_device)
    classify_mask = g.ndata['test_mask']['d'].to(cpu_device)
    labels = g.ndata['l']['d'].to(cpu_device)
    results_dict = {}

    avg_0 = []
    avg_1 = []

    for cnt, model_embedding in enumerate(embeddings):
        result = _train_regress(model_embedding, train_mask, classify_mask, labels, scale)

        if mode == TESTING:
            results_dict[path_names[cnt]] = result[0]

        avg_0.append(result[0][0])
        avg_1.append(result[0][1])


    avg_mal = sum(avg_0) / len(avg_0)
    abg_ben = sum(avg_1) / len(avg_1)
    results_dict['AVERAGE'] = numpy.array([avg_mal, abg_ben])

    if mode == TESTING:
        concat_embeds = th.cat(embeddings, dim=1)
        result_concat = _train_regress(concat_embeds, train_mask, classify_mask, labels, scale)
        results_dict['CONCAT'] = result_concat[0]

    return results_dict['AVERAGE'] if mode == PRODUCTION else results_dict

def _train_metapath2vec(model_loader: tuple[MetaPath2Vec, DataLoader, str], device: th.device, lr: float, cnt: int) -> tuple[th.Tensor, list[float], str]:
    """

    :param model_loader:
    :param device:
    :param lr:
    :param cnt:
    :return:
    """
    MyLogger.get_instance().log(f"Working on model {cnt}")
    model, dataloader, path_name = model_loader
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

    return d_emb, loss_cum, path_name

def _train_metapath2vec_safe(
        device: th.device,
        lr: float,
        cnt: int,
        g: dgl.DGLHeteroGraph,
        m_path: list[str],
        w_size: int = 1,
        emb_dim: int = 64,
        neg_size: int = 5
) -> tuple[th.Tensor, list[float], str] | None:

    try:
        model = MetaPath2Vec(g, m_path, window_size=w_size, emb_dim=emb_dim, negative_size=neg_size)
    except Exception as e:
        MyLogger.get_instance().log_error(str(e))
        MyLogger.get_instance().log_warning(f"Ommiting metapath {m_path} because there are no edges of given type")
        return None
    model.to(device)
    dataloader = DataLoader(torch.arange(g.num_nodes(ntype='d')), batch_size=128, shuffle=True, collate_fn=model.sample)
    path_name = m_path[0].split('_')[0]

    return _train_metapath2vec((model, dataloader, path_name), device,lr,cnt)

def _gen_embeds_parallel_safe(
        device: th.device,
        g: dgl.DGLHeteroGraph,
        m_paths: list[list[str]],
        w_size: int = 1,
        emb_dim: int = 64,
        neg_size: int = 5,
        lr: float = 0.01
) -> tuple[list[th.Tensor], list[list[float]], list[str]]:

    with mp.Pool(processes=3) as pool:
        results = pool.starmap(_train_metapath2vec_safe, [(device, lr, cnt, g, path, w_size, emb_dim, neg_size) for cnt, path in enumerate(m_paths)])

    filt_res = []

    for res in results:
        if res is None:
            continue
        filt_res.append(res)

    return zip(*filt_res)

def _gen_embeds_parallel(models: list[tuple[MetaPath2Vec, DataLoader, str]], device: th.device, lr=0.01) -> tuple[list[th.Tensor], list[list[float]], list[str]]:
    """
    Function which generates embeddings using provided models in parallel
    :param models: List of models and their dataloaders for walk generating
    :param device: Device on which model is located
    :param lr: Learning rate
    :return: Embeddings and loss values for each model
    """

    with mp.Pool(processes=3) as pool:
        results = pool.starmap(_train_metapath2vec, [(model, device, lr, cnt) for cnt, model in enumerate(models)])

    return zip(*results)

def _generate_embeddings(models: list[tuple[MetaPath2Vec, DataLoader]], device: th.device, lr=0.01) -> tuple[list[th.Tensor], list[list[float]]]:
    """
    Method that uses models to generate embeddings, where they are generated one after the other
    :param models: List of models and their dataloaders for walk generating
    :param device: Device on which model is located
    :param lr: Learning rate
    :return: Embeddings and loss values for each model
    """

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
        w_size: int = 1,
        emb_dim: int = 64,
        neg_size: int = 5) -> tuple[list[tuple[MetaPath2Vec, DataLoader, str]], list[str]]:
    """
    Method that creates model for each metapath on given graph and device
    :param m_paths: List of metapaths
    :param g: Graph with which model will work
    :param device: Device on which model will run, must be same as graph
    :param w_size: Window size
    :param emb_dim: Embeddings dimension
    :param neg_size: Negative sample size
    :return: Tuple[ models and their dataloader for generating random walks, used paths]
    """
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
        path_name = path[0].split('_')[0]
        models.append((model, dataloader, path_name))
        paths.append(path_name)

    return models, paths


def get_class_counts(g: dgl.DGLHeteroGraph):
    labels = g.ndata['l']['d']
    return np.unique(labels[g.ndata['train_mask']['d']].numpy(), return_counts=True)


def check_for_duplicity(g: dgl.DGLHeteroGraph) -> bool | tuple:
    """
    Method that checks if number of labels is correct, and if there is enough domain nodes for model to work with
    :param g: Graph that will be checked
    :return: Tuple [prob. mal., prob. ben., cnt. mal., cnt. ben.] if graph domain nodes have only one label, True if graph is correct
    otherwise False
    """

    if len(g.nodes(ntype='d')) < 2:
        MyLogger.get_instance().log_warning("Need at least 2 domain nodes")
        return False

    unique_labels, counts = get_class_counts(g)

    if len(unique_labels) < 2:
        MyLogger.get_instance().log(
            f"All neighboring nodes in sampled neighborhood are of class: {'benign' if unique_labels[0] == 1 else 'malicious'}"
        )
        return float(unique_labels[0] == 0), float(unique_labels[0] == 1), int(counts[0]) if unique_labels[0] == 0 else 0, int(counts[0]) if unique_labels[0] == 1 else 0

    return True

def classify_domain(g: dgl.DGLHeteroGraph, eval_result: EvaluationResult, mode: bool = PRODUCTION, no_need_for_correct_check: bool = False) -> bool:
    """
    Method for classifying domain based on its relations with other domains in graph using metapath2vec model with multiple meta-paths
    :param g: Graph containing evaluated domain (train set to false and test set to true) and its neighborhood
    :param eval_result: EvaluationResult object into which result will be stored
    :param mode: Flag indicating if results of all possible classifier outputs should be stored into result or not (default is to not store all possible results)
    :param no_need_for_correct_check: Flag indicating that function can omit graph correctness check, note that if graph is not correct this function will fail and raises exception
    :return: True on successful evaluation, False otherwise
    """

    if not no_need_for_correct_check:
        check_result = check_for_duplicity(g)

        if isinstance(check_result, tuple):
            eval_result.set_probability(check_result[0],check_result[1])
            eval_result.set_counts(check_result[2], check_result[3])
            return True
        else:
            if not check_result:
                return False

    _, counts = get_class_counts(g)

    device = th.device('cpu')  #th.device('cuda' if th.cuda.is_available() else 'cpu')
    MyLogger.get_instance().log(
        f"This device does {'' if th.cuda.is_available() else 'not'} have GPU, chosen device is {device}")
    g = g.to(device)

    paths = [[f"{EdgeTypes.CNAME.value}_{NodeTypes.DOMAIN.dgl}_{NodeTypes.DOMAIN.dgl}"] * 6,
             [f"{EdgeTypes.SUBDOMAIN.value}_{NodeTypes.DOMAIN.dgl}_{NodeTypes.DOMAIN.dgl}"] * 6,
             [f"{EdgeTypes.TRANSLATES.value}_{NodeTypes.DOMAIN.dgl}_{NodeTypes.IP.dgl}",
              f"{EdgeTypes.TRANSLATES.value}_{NodeTypes.IP.dgl}_{NodeTypes.DOMAIN.dgl}"] * 4,
             ]
    #models, used_paths = _create_models_for_meta_paths(paths, g, device)
    #embeds, _, path_names = _gen_embeds_parallel(models, device) #_generate_embeddings(models, g, device)
    embeds, _, path_names = _gen_embeds_parallel_safe(device, g, paths)

    res = _train_log_regress_and_cls(g, embeds, path_names, mode)

    eval_result.set_counts(counts[0], counts[1])
    if mode == PRODUCTION:
        eval_result.set_probability(res[0],res[1])
    else:
        eval_result.set_other_probs(res)
    return True