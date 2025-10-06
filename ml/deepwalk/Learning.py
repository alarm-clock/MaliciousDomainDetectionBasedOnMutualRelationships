import dgl
from dgl.nn.pytorch import DeepWalk
import torch as th
import sklearn.linear_model as sk

import ml.deepwalk.Walks as Walks


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



    train_mask = g.ndata['train_mask']
    test_mask = g.ndata['test_mask']
    X = model.node_embed.weight.detach()
    y = g.ndata['label']
    clf = sk.LogisticRegression().fit(X[train_mask].numpy(), y[train_mask].numpy())
    score = clf.score(X[test_mask].numpy(), y[test_mask].numpy())

    print(score)
