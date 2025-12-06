#import warnings
#warnings.filterwarnings("ignore", message="Error getting driver and runtime versions")

import dgl
#import matplotlib
import matplotlib.pyplot as plt
#import matplotlib.cm as cm
import matplotlib.patches as patches
import networkx as nx
import numpy as np
#import cudf as cdf
#import cugraph as cug
#import datashader as ds
#import datashader.transfer_functions as tf
#import pandas as pd

def plot_graph(g: dgl.DGLGraph, export: bool, filename: str = "graph.png" ):

    G = dgl.to_networkx(g, edge_attrs=['weight'])
    fig ,ax = plt.subplots(figsize=(15, 7))

    cmap = {0: 'red', 1:"green"}
    labels = np.array(g.ndata['label'])
    colors = [cmap[lab] for lab in labels]

    pos = nx.spring_layout(G, seed=42)
    nx.draw_networkx_nodes(G, pos, ax=ax , node_size=700, node_color=colors)
    nx.draw_networkx_edges(G, pos, ax=ax , edge_color='black', width=2)
    edge_labels = nx.get_edge_attributes(G, 'weight')

    edge_labels = {k: v.item() if hasattr(v,"item") else v for k, v in edge_labels.items()}

    nx.draw_networkx_edge_labels(G, pos, ax=ax, edge_labels=edge_labels)
    nx.draw_networkx_labels(G, pos, ax=ax, font_size=20, font_family="sans-serif")
    ax.axis('off')

    handles = [patches.Patch(color='red', label='Malign domain'),
               patches.Patch(color='green', label='Benign domain')]
    plt.legend(handles=handles, loc='upper right', frameon=True, title='Legend')

    if export:

        fig.savefig(filename, bbox_inches='tight', dpi=300, format='png')
    else:
        plt.show()
    plt.close()

"""
def export_graph_gpu(g: dgl.DGLGraph, filename: str = "graph.png" ):

    src, dst = g.edges()
    df = cdf.DataFrame({'src':src.cpu().numpy(), 'dst':dst.cpu().numpy()})
    G = cug.Graph()
    G.from_cudf_edgelist(df, 'src', 'dst')
    pos = cug.force_atlas2(G, max_iter=800, gravity=0.4, lin_log_mode=True,outbound_attraction_distribution=True,edge_weight_influence=1.0)


    labels = g.ndata['label']
    df = pd.DataFrame({
        'x': pos['x'].to_pandas().astype(float),
        'y': pos['y'].to_pandas().astype(float),
        'label': labels,
    })
    df['label'] = df['label'].astype('category')

    edges_df = pd.DataFrame({
        'x': np.concatenate([df['x'].iloc[src].values, df['x'].iloc[dst].values]),
        'y': np.concatenate([df['y'].iloc[src].values,df['y'].iloc[dst].values]),
        #'edge_id': np.repeat(np.arange(len(src)), 2)
    })
    #print("_________________________________________________")
    cvs = ds.Canvas(plot_width=500, plot_height=500)
    agg_nodes = cvs.points(df, 'x', 'y', ds.count_cat('label'))
    agg_edges = cvs.line(edges_df, 'x', 'y')
    img_edges = tf.shade(agg_edges,color_key={0: 'white'}, how='linear')
    img_nodes = tf.shade(tf.spread(agg_nodes, px=1), color_key={0: 'red', 1: 'green'}, how='eq_hist')
    final_img = tf.stack( img_nodes) #img_edges
    tf.set_background(final_img, color='white').to_pil().save(filename)
"""

def plot_loss(losses: list[float], avg_losses: list[float]):

    plt.figure(figsize=(15, 7))
    plt.plot(losses, label='Batch loss', alpha=0.5)
    plt.plot( range(len(losses)), avg_losses, label='Average loss', linestyle='--', color='red')
    plt.xlabel('Iterations/epoch')
    plt.ylabel('Loss')
    plt.legend()
    plt.grid(True)
    plt.savefig('/storage/brno2/home/xbukas00/loss.png', bbox_inches='tight', dpi=300, format='png')
    return

