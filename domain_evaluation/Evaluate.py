import csv
import json
from typing import Any

from pymongo import MongoClient

from domain_evaluation.Metapath2vec.Learning import classify_domain
from graph_repository.graph_main.GraphRepository import GraphRepository
from misc.Logger import MyLogger


def evaluate_domain_meta_path2vec(domain: dict[str, Any]) -> tuple |None:

    repository: GraphRepository = GraphRepository.get_instance()

    if repository is None:
        return None

    print("Temporary adding domain into graph...")
    MyLogger.get_instance().log(f"Temporary adding domain {domain['domain_name']} into graph...")
    tmp_node_id = repository.temporary_add_domain(domain)

    if tmp_node_id is None:
        print("Domain has no neighbors in graph!")
        return None

    MyLogger.get_instance().log(f'Domain node {tmp_node_id} temporary added to graph, extracting k-hop neighbors...')

    try:
        graph = repository.get_k_hop_neighborhood_dgl(tmp_node_id,True)
    except Exception as e:
        MyLogger.get_instance().log_error(f"Exception occured while gettign k hop neighborhood dgl: {e}")
        return None
    finally:
        repository.delete_temporary_domain(tmp_node_id)

    MyLogger.get_instance().log("Starting to classify node")
    res_tup = classify_domain(graph, 4) #all
    if res_tup is None:
        return None

    res, loss_arr, cnt_bad, cnt_good, used_paths = res_tup

    MyLogger.get_instance().log(f"Domain {domain['domain_name']}: \n\t{res}")
    return res, loss_arr, cnt_bad, cnt_good, used_paths

def evaluate_domain_metapath2vec_mult(domains: list[dict[str, Any]]) -> None:

    for domain in domains:
        evaluate_domain_meta_path2vec(domain)


def test(provider, class_out_f_name: str) -> None:

    existing_result_providers = ['cname','subdomain','translates','avg','cat']
    with open(class_out_f_name, 'w') as f:

        csv_writer = csv.writer(f)
        csv_writer.writerow(
            ["id", "domain_name", "label", "n_good", "n_bad", "n_total", 'm_p_CNAME','b_p_CNAME','CNAME_pred',
             'CNAME_c','m_p_SUBD',"b_p_SUBD","SUBD_pred","SUBD_c","m_p_IP","b_p_IP",'IP_pred',"IP_c",
             'm_p_AVG','b_p_AVG',"AVG_pred","AVG_c",'m_p_CAT','b_p_CAT','CAT_pred','CAT_c']
        )

        for cnt, domain in enumerate(provider):

            domain_name = domain['domain_name']
            label_str: str =  domain['label']
            label = int(label_str.find('benign') != -1)

            res = evaluate_domain_meta_path2vec(domain)

            if res is None:
                #-1 for prediction and correct means that there was no classification therefore no result
                csv_writer.writerow(
                    [cnt, domain_name, label, 0, 0, 0, 0.0, 0.0, -1,-1, 0.0, 0.0, -1,-1, 0.0, 0.0, -1,-1, 0.0, 0.0, -1,-1, 0.0, 0.0, -1,-1]
                )
                continue
            results, loss_arr, cnt_bad, cnt_good, used_paths = res

            cnt_total = cnt_good + cnt_bad
            write_list = [cnt, domain_name, label, cnt_good, cnt_bad, cnt_total]

            used_paths.extend(['avg', 'cat'])

            cnt2 = 0
            cnt_providers = 0
            for result in results.values():

                if used_paths[cnt2] != existing_result_providers[cnt_providers]:
                    idx = existing_result_providers.index(used_paths[cnt2])
                    for _ in range(idx - cnt_providers):
                        write_list.extend([0.0,0.0,-1,-1])
                    cnt_providers = idx

                #print(result)
                m_prob = result[0]
                b_prob = result[1]
                prediction = int(b_prob > 0.5)
                correct = int(label == prediction)

                write_list.extend([m_prob, b_prob, prediction, correct])
                cnt2 += 1
                cnt_providers += 1

            csv_writer.writerow(write_list)
            if cnt % 30 == 0:
                f.flush()

def test_from_collection(path_to_config: str, class_out_f_name: str) -> None:

    with open(path_to_config,'r') as f:
        conf = json.load(f)

    client = MongoClient(conf["client"], conf["port"])
    db = client[conf["db"]]
    collection = db[conf["collection"]]

    cursor = collection.find([{"$match" :{"train": True}}], batchSize=1000)

    test(cursor, class_out_f_name)