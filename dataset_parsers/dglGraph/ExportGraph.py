import sys

import dgl
import torch as th
from dgl.data.utils import save_graphs, load_graphs
from misc.Logger import MyLogger
from pathlib import Path

def export_graph(g: dgl.DGLGraph, filename: str) -> None:

    MyLogger.get_instance().log(f"Exporting graph to file {filename}")
    g_labels = {'glabel': th.tensor([1])}
    save_graphs(filename=filename,g_list=[g],labels=g_labels)
    MyLogger.get_instance().log("Finished exporting graph")

def load_graph(filename: str) -> dgl.DGLGraph | None:

    MyLogger.get_instance().log(f"Loading graph from file {filename}")
    if not Path(filename).is_file():
        print(f'File {filename} not found.', file=sys.stderr)
        MyLogger.get_instance().log(f"File {filename} not found!")
        return None

    try:
        g = load_graphs(filename)[0][0]  #it says it returns list of graphs but in reality it returns tuple with list
    except Exception as e:
        MyLogger.get_instance().log(f"Failed to load graph from file {filename}")
        MyLogger.get_instance().log(repr(e))
        return None

    MyLogger.get_instance().log(f"Loaded graph from file")
    return g
