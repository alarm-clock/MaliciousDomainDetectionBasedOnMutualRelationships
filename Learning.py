import dgl
from dgl.nn.pytorch import DeepWalk
import torch as th
import sklearn.linear_model as sk

import Walks

def train(g: dgl.DGLGraph):

    model = DeepWalk(g,walk_length=32)
    optimizer = th.optim.SparseAdam(model.parameters(), lr=0.01)
    num_of_epochs = 5

    for epoch in range(num_of_epochs):
        print(f'Epoch {epoch}...')
        for cnt in range(20):
            print(f'Epoch {epoch} walk batch {cnt}...')
            walks = Walks.generate_walks_tensor(g, 128, 32)
            #print(walks)
            loss = model(walks)
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

    train_mask = g.ndata['train_mask']
    test_mask = g.ndata['test_mask']
    X = model.node_embed.weight.detach()
    y = g.ndata['label']
    clf = sk.LogisticRegression().fit(X[train_mask].numpy(), y[train_mask].numpy())
    score = clf.score(X[test_mask].numpy(), y[test_mask].numpy())

    print(score)