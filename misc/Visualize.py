import dgl
import matplotlib.pyplot as plt
import networkx as nx

def plot_graph(g: dgl.DGLGraph ):

    G = dgl.to_networkx(g, edge_attrs=['weight'])
    plt.figure(figsize=(15, 7))

    pos = nx.spring_layout(G, seed=42)
    nx.draw_networkx_nodes(G, pos , node_size=700, node_color='orange')
    nx.draw_networkx_edges(G, pos , edge_color='black', width=2)
    edge_labels = nx.get_edge_attributes(G, 'weight')

    edge_labels = {k: v.item() if hasattr(v,"item") else v for k, v in edge_labels.items()}

    nx.draw_networkx_edge_labels(G, pos , edge_labels=edge_labels)
    nx.draw_networkx_labels(G, pos, font_size=20, font_family="sans-serif")
    plt.axis('off')
    plt.show()