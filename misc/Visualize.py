import dgl
import matplotlib.pyplot as plt
import matplotlib.cm as cm
import networkx as nx
import numpy as np


def plot_graph(g: dgl.DGLGraph, export: bool, filename: str = "graph.png" ):

    G = dgl.to_networkx(g, edge_attrs=['weight'])
    fig ,ax = plt.subplots(figsize=(15, 7))

    cmap = cm.get_cmap('Set1')
    labels = np.array(g.ndata['label'])

    pos = nx.spring_layout(G, seed=42)
    nx.draw_networkx_nodes(G, pos, ax=ax , node_size=700, node_color=labels, cmap=cmap)
    nx.draw_networkx_edges(G, pos, ax=ax , edge_color='black', width=2)
    edge_labels = nx.get_edge_attributes(G, 'weight')

    edge_labels = {k: v.item() if hasattr(v,"item") else v for k, v in edge_labels.items()}

    nx.draw_networkx_edge_labels(G, pos, ax=ax, edge_labels=edge_labels)
    nx.draw_networkx_labels(G, pos, ax=ax, font_size=20, font_family="sans-serif")
    ax.axis('off')

    if export:

        fig.savefig(filename, bbox_inches='tight', dpi=300, format='png')
    else:
        plt.show()
    plt.close()
