import dgl
from misc.Logger import MyLogger
from dataset_parsers.Graph import get_nodes_connected_component
import pymongo
from misc.helper_func import connect_to_db_from_conf
from ml.deepwalk.Learning import classify_node


def classify_domain(g: dgl.DGLGraph, domain: str, collection: pymongo.collection.Collection, etypes: list[str] | None):

    db_entry = collection.find_one({'domain_name': domain})

    if db_entry is None:
        print("domain not found")
        return

    node_id = int(db_entry['node_id'])
    #kokot_id = 0

    #for node in list(g.nodes()):
    #    orig = int(g.ndata[dgl.NID][node])
    #    if orig == node_id:
    #        kokot_id = int(node)

    scc = get_nodes_connected_component(g, node_id, etypes) #kokot_id

    if len(scc.nodes()) == 0:
        print("This domain does not have any connection to another domain")
        return

    good = 0
    all_cnt = len(scc.nodes())
    for val in scc.ndata['label']:
        good += int(val)

    bad = all_cnt - good
    print(f'good: {good}   , bad: {bad}')

    final_id = 0
    for node in list(scc.nodes()):
        orig = int(scc.ndata[dgl.NID][node])
        if orig == node_id:
            final_id = int(node)

    classify_node(scc, final_id)

    return

#m.gr-cdn-9.com  12272
#dns.forcorpor.com  2
#nymo.ee asi kurva vela
#pub-c2e1b1db2dee4661b1d7f11393de5fb8.r2.dev

def app_loop(g: dgl.DGLGraph, db_config: str, etypes: str|None = None, domain: str|None = None) -> None:

    collection = connect_to_db_from_conf(db_config)

    etp_arr = []

    if etypes is not None:
        splited_types = etypes.split(',')
        for edge_type_str in splited_types:
            edge_type_str = edge_type_str.strip()
            etp_arr.append(edge_type_str)
    else:
        etp_arr = None

    if domain is not None:
        classify_domain(g, domain, collection, etp_arr)
        return

    while True:
        query = input("Enter a domain (type 'quit' to quit): ").strip()

        if query == 'quit':
            break

        classify_domain(g, query, collection, etp_arr)


    return
