import dgl
import torch
from dgl.nn.pytorch import DeepWalk
import torch as th
import sklearn.linear_model as sk
from sklearn.metrics import f1_score
from misc.Visualize import plot_loss
from misc.Logger import MyLogger
import numpy as np


def get_etype_subgraphs(g: dgl.DGLGraph) -> dict[str, dgl.DGLGraph]:
    MyLogger.get_instance().log("Getting edge type ids...")
    homo_g = dgl.to_homogeneous(g)
    etype_eids = {}
    for e_type in g.etypes:
        eids_homo = homo_g.edata[dgl.ETYPE] == g.get_etype_id(e_type)
        etype_eids[e_type] = torch.nonzero(eids_homo, as_tuple=False).squeeze().to(th.int32)

    MyLogger.get_instance().log("Generating homogenous subgraphs for given edge type...")
    e_type_subgraphs = {
        e_type: dgl.edge_subgraph(homo_g, etype_eids[e_type])
        for e_type in g.etypes
    }

    return e_type_subgraphs


def test_result(g: dgl.DGLGraph, model: DeepWalk) -> None:
    train_mask = g.ndata['train_mask']
    test_mask = g.ndata['test_mask']
    X = model.node_embed.weight.detach()
    y = g.ndata['label']
    clf = sk.LogisticRegression().fit(X[train_mask].numpy(), y[train_mask].numpy())
    score = clf.score(X[test_mask].numpy(), y[test_mask].numpy())
    y_pred = clf.predict(X[test_mask].numpy())
    f1 = f1_score(y[test_mask].numpy(), y_pred, average='macro')
    print(f1)
    print(score)

    MyLogger.get_instance().log(str(f1))
    MyLogger.get_instance().log(str(score))

def train_hetero(g: dgl.DGLGraph, num_of_epochs: int = 10, num_of_epoch_walks: int = 5, w_len: int = 12, lr: float = 0.001) -> tuple[DeepWalk, list[float], list[float]]:
    num_of_total_walks_in_epoch = len(g.etypes) * num_of_epoch_walks
    model = DeepWalk(g, window_size=5, walk_length=w_len) #w_len - 1

    optimizer = th.optim.SparseAdam(model.parameters(), lr=lr)

    e_type_subgraphs = get_etype_subgraphs(g)

    losses = []
    avg_losses = []
    MyLogger.get_instance().log("Generated all subgraphs, starting training...")
    print("Generated all subgraphs, starting training...")
    for epoch in range(num_of_epochs):
        MyLogger.get_instance().log(f'Epoch {epoch}...')
        print(f'Epoch {epoch + 1}...')
        total_loss = 0.0
        for cnt in range(num_of_epoch_walks):
            for e_type, type_subgraph in e_type_subgraphs.items():
                if e_type == "ipv4":
                    walks, _ = dgl.sampling.random_walk(type_subgraph,type_subgraph.nodes(),length=w_len,prob='weight')
                else:
                    walks, _ = dgl.sampling.random_walk(type_subgraph, type_subgraph.nodes(), length=w_len)

                loss = model(walks)
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()

                total_loss += loss.item()
                losses.append(loss.item())

                MyLogger.get_instance().log(f"Epoch {epoch + 1}/{num_of_epochs}, Step {cnt + 1}/{num_of_epoch_walks}, walk for e_type {e_type}, Loss: {loss.item():.4f}")
                print(f"Epoch {epoch + 1}/{num_of_epochs}, Step {cnt + 1}/{num_of_epoch_walks}, walk for e_type {e_type}, Loss: {loss.item():.4f}")

        avg_loss = total_loss / num_of_total_walks_in_epoch
        avg_losses.extend([avg_loss] * num_of_total_walks_in_epoch)
        MyLogger.get_instance().log(f"Epoch {epoch + 1} finished, Avg Loss = {avg_loss:.4f}")

    return model, losses, avg_losses

def classify_node(g: dgl.DGLGraph, nd: int) -> bool:

    train_mask = torch.ones(len(g.nodes()), dtype=torch.bool) #[1] * len(g.nodes())
    train_mask[nd] = False
    classify_mask = ~train_mask
    y = g.ndata['label']
    unique_values = np.unique(y[train_mask].numpy())
    print(unique_values)

    if len(unique_values) == 1:
        print(f"All neighboring nodes in scc are of class: {'benign' if unique_values[0] == 1 else 'malignant'}")

    model, l, al = train_hetero(g,4,3,9,0.02)
    plot_loss(l,al)

    x = model.node_embed.weight.detach()
    clf = sk.LogisticRegression().fit(x[train_mask].numpy(), y[train_mask].numpy())

    result = clf.predict(x[classify_mask].numpy())
    print(result)

    return False


def train_and_test_model(g: dgl.DGLGraph) -> None:

    model, losses, avg_losses = train_hetero(g)
    plot_loss(losses, avg_losses)
    test_result(g, model)

def train(g: dgl.DGLGraph):
    model = DeepWalk(g, walk_length=12)
    optimizer = th.optim.SparseAdam(model.parameters(), lr=0.01)
    num_of_epochs = 6

    for epoch in range(num_of_epochs):
        print(f'Epoch {epoch}...')
        total_loss = 0.0
        for cnt in range(5):

            print(f'Generating walks...')
            walks, _ = dgl.sampling.random_walk(g,g.nodes(),length=12,prob='weight')
            print(f'Finished generating walks...')

            loss = model(walks)
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

            total_loss += loss.item()

            print(f"Epoch {epoch + 1}/{6}, Step {cnt + 1}/{5}, Loss: {loss.item():.4f}")

        avg_loss = total_loss / 5
        print(f"Epoch {epoch + 1} finished, Avg Loss = {avg_loss:.4f}")



    test_result(g, model)


