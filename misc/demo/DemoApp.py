import dgl
from misc.Logger import MyLogger
from dataset_parsers.Graph import get_nodes_connected_component
import pymongo
from misc.helper_func import connect_to_db_from_conf


def classify_domain(g: dgl.DGLGraph, domain: str, collection: pymongo.collection.Collection):

    db_entry = collection.find_one({'domain_name': domain})

    if db_entry is None:
        print("domain not found")
        return

    node_id = int(db_entry['node_id'])
    kokot_id = 0

    for node in list(g.nodes()):
        orig = int(g.ndata[dgl.NID][node])
        if orig == node_id:
            kokot_id = node

    print("kokot_id: " + str(kokot_id))
    print(f"n nodes: {g.num_nodes()}")
    scc = get_nodes_connected_component(g, kokot_id)
    with open("scc_nodes.txt", "w") as f:
        for node in list(scc.nodes()):
            f.write(str(int(node)) + "\n")

    print(f"n nodes: {scc.num_nodes()}")
    print(scc.edges())
    print(scc.nodes())
    print(scc.ndata['label'])

    return

#m.gr-cdn-9.com

def app_loop(g: dgl.DGLGraph, db_config: str, domain: str|None = None) -> None:

    collection = connect_to_db_from_conf(db_config)
    if domain is not None:
        classify_domain(g, domain, collection)
        return

    while True:
        query = input("Enter a domain (type 'quit' to quit): ").strip()

        if query == 'quit':
            break

        classify_domain(g, query, collection)


    return