import dgl
from misc.Logger import MyLogger
from old.dataset_parsers.Graph import get_nodes_connected_component
import pymongo
from old.misc.helper_func import connect_to_db_from_conf
from old.ml.deepwalk.Learning import classify_node
import csv

def classify_domain_from_id(g: dgl.DGLGraph, node_id: int, etypes: str|None) -> tuple[int, int, float, float] | None:

    scc = get_nodes_connected_component(g, node_id, etypes) #kokot_id

    if len(scc.nodes()) < 2:
        MyLogger.get_instance().log(f"{node_id} has no neighbours in the graph")
        #print("This domain does not have any connection to another domain")
        return None

    good = 0
    all_cnt = len(scc.nodes())
    for val in scc.ndata['label']:
        good += int(val)

    bad = all_cnt - good
    MyLogger.get_instance().log(f"{node_id} has {good} good neighbours and {bad} bad neighbours")
    #print(f'good: {good}   , bad: {bad}')

    final_id = 0
    for node in list(scc.nodes()):
        orig = int(scc.ndata[dgl.NID][node])
        if orig == node_id:
            final_id = int(node)

    res = classify_node(scc, final_id)

    del scc

    if res is None:
        return None

    malicious, benign = res
    return good, bad, malicious, benign

def classify_domain_from_db(g: dgl.DGLGraph, domain: str, collection: pymongo.collection.Collection, etypes: list[str] | None):

    db_entry = collection.find_one({'domain_name': domain})

    if db_entry is None:
        print("domain not found")
        return

    node_id = int(db_entry['node_id'])
    classify_domain_from_id(g, node_id, etypes)
    return



#m.gr-cdn-9.com  12272
#dns.forcorpor.com  2
#nymo.ee asi kurva vela
#pub-c2e1b1db2dee4661b1d7f11393de5fb8.r2.dev

def test_checker(g: dgl.DGLGraph, domain_file: str) -> None:
    with open(domain_file, 'r') as f:
        for line in f:
            data = line.split(' ')
            node_id = int(data[1])
            scc = get_nodes_connected_component(g, node_id, None)

            if len(scc.nodes()) < 2:
                print(f"{node_id} has no neighbours in the graph")
                # print("This domain does not have any connection to another domain")
                continue

            good = 0
            all_cnt = len(scc.nodes())
            for val in scc.ndata['label']:
                good += int(val)

            bad = all_cnt - good
            print(f"{node_id} has {good} good neighbours and {bad} bad neighbours")


def domain_checker(g: dgl.DGLGraph, domain_file: str, etypes: str|None) -> None:

    output_file = domain_file.rsplit('.', 1)[0] + '_out.csv'

    with open(output_file, 'w') as of:

        csv_writer = csv.writer(of)
        csv_writer.writerow(
            ['node_id','domain_name','n_good','n_bad','n_total','malicious_prob','benign_prob','prediction','orig_label','correct']
        )

        with open(domain_file, 'r') as f:
            lines = 0
            for line in f:
                data = line.split(' ')
                name = data[0]
                node_id = int(data[1])
                label = int(data[2])
                #print(f"Evaluating domain {name} with node_id: {node_id}")
                MyLogger.get_instance().log(f"Evaluating domain {name} with node_id: {node_id}")

                res = classify_domain_from_id(g, node_id, etypes)

                if res is None:
                    csv_writer.writerow([node_id,name,0,0,0,0.0,0.0,-1,label,-1])
                    continue

                n_good, n_bad, malicious, benign = res
                if label == 1:
                    n_good -= 1
                else:
                    n_bad -= 1

                total = n_good + n_bad
                prediction = int(benign > 0.5)
                correct = int(prediction == label)

                csv_writer.writerow([node_id,name,n_good,n_bad,total,malicious,benign,prediction,label,correct])
                lines += 1
                if lines % 30 == 0:
                    f.flush()

    return

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
        classify_domain_from_db(g, domain, collection, etp_arr)
        return

    while True:
        query = input("Enter a domain (type 'quit' to quit): ").strip()

        if query == 'quit':
            break

        classify_domain_from_db(g, query, collection, etp_arr)


    return
