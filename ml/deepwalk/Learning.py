import dgl
import torch
from dgl.nn.pytorch import DeepWalk
import torch as th
import sklearn.linear_model as sk
from sklearn.metrics import f1_score

from misc.Visualize import plot_loss


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

def train_hetero(g: dgl.DGLGraph):
    num_of_epochs = 10
    w_len = 12
    model = DeepWalk(g, walk_length=w_len)
    optimizer = th.optim.SparseAdam(model.parameters(), lr=0.05)
    homo_g = dgl.to_homogeneous(g)

    etype_eids = {}
    for e_type in g.etypes:
        eids_homo = homo_g.edata[dgl.ETYPE] == g.get_etype_id(e_type)
        etype_eids[e_type] = torch.nonzero(eids_homo, as_tuple=False).squeeze().to(th.int32)

    e_type_subgraphs = {
        e_type: dgl.edge_subgraph(homo_g, etype_eids[e_type])
        for e_type in g.etypes
    }


    losses = []
    avg_losses = []

    for epoch in range(num_of_epochs):
        print(f'Epoch {epoch}...')
        total_loss = 0.0
        for cnt in range(5):
            for e_type, type_subgraph in e_type_subgraphs.items():
                walks, _ = dgl.sampling.random_walk(type_subgraph, type_subgraph.nodes(), length=w_len)

                loss = model(walks)
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()

                total_loss += loss.item()
                losses.append(loss.item())

                print(f"Epoch {epoch + 1}/{6}, Step {cnt + 1}/{5}, walk for e_type {e_type}, Loss: {loss.item():.4f}")

        avg_loss = total_loss / (5 * len(g.etypes))
        avg_losses.append(avg_loss)
        print(f"Epoch {epoch + 1} finished, Avg Loss = {avg_loss:.4f}")

    plot_loss(losses,avg_losses)
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


