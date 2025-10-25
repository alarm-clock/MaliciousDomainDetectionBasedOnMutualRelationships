import sys

import dgl
import torch as th
from dgl.data.utils import save_graphs, load_graphs
from pathlib import Path

def export_graph(g: dgl.DGLGraph, filename: str) -> None:

    g_labels = {'glabel': th.tensor([1])}
    save_graphs(filename=filename,g_list=[g],labels=g_labels)

def load_graph(filename: str) -> dgl.DGLGraph | None:

    if not Path(filename).is_file():
        print(f'File {filename} not found.', file=sys.stderr)
        return None

    g = load_graphs(filename)[0][0]  #it says it returns list of graphs but in reality it returns tuple with list

    return g