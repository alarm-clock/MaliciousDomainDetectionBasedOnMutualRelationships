import csv
import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any
import dgl
from pymongo import MongoClient

from domain_evaluation.Metapath2vec.Learning import classify_domain, check_for_duplicity
from graph_repository.graph_main.GraphRepository import GraphRepository
from misc.Logger import MyLogger

__EXISTING_RESULT_PROVIDERS = ['cname', 'subdomain', 'translates', 'avg', 'cat']

def get_graph(domain: dict[str, Any]) -> dgl.DGLHeteroGraph | None:
    repository: GraphRepository = GraphRepository.get_instance()

    if repository is None:
        return None

    print("Temporary adding domain into graph...")
    MyLogger.get_instance().log(f"Temporary adding domain {domain['domain_name']} into graph...")
    tmp_node_id = repository.temporary_add_domain(domain)

    if tmp_node_id is None:
        #MyLogger.get_instance().log(f"Domain {domain['domain_name']} has no neighbours in graph!")
        return None

    MyLogger.get_instance().log(f'Domain node {tmp_node_id} temporary added to graph, extracting k-hop neighbors...')

    try:
        graph = repository.get_k_hop_neighborhood_dgl(tmp_node_id, True)
    except Exception as e:
        MyLogger.get_instance().log_error(f"Exception occurred while getting k hop neighborhood dgl: {e}")
        return None
    finally:
        repository.delete_temporary_domain(tmp_node_id)

    return graph

def evaluate_domain_metapath2vec(domain: dict[str, Any], lock: threading.Semaphore | None) -> tuple[tuple |None, dict[str, Any], float, float, float, float]:

    start_t = time.time()
    g = get_graph(domain)
    got_graph_t = time.time() - start_t

    if g is None:
        return None, domain, got_graph_t, got_graph_t, 0, 0

    res = check_for_duplicity(g)

    if type(res) is tuple:
        end_t = time.time() - start_t
        return res, domain, end_t, got_graph_t, 0, 0
    if not res:
        end_t = time.time() - start_t
        return None, domain, end_t, got_graph_t, 0 ,0

    if lock is not None:
        MyLogger.get_instance().log(f"Domain {domain['domain_name']} is waiting on GPU")
        wait_start = time.time()
        lock.acquire()
        wait_t = time.time() - wait_start
    else:
        wait_start = 0
        wait_t = 0
    MyLogger.get_instance().log(f"Starting to classify domain {domain['domain_name']}...")

    try:
        class_start = time.time()
        res_tup = classify_domain(g, 4, True) #all
        class_t = time.time() - class_start

    except Exception:
        MyLogger.get_instance().log_error(f"Exception occurred while classifying domain {domain['domain_name']}...")
        end_t = time.time() - start_t
        return None, domain, end_t, got_graph_t, wait_t, 0
    finally:
        if lock is not None:
            lock.release()

    end_t = time.time() - start_t
    if res_tup is None:
        return None, domain,  end_t, got_graph_t, wait_t, class_t

    res, loss_arr, cnt_bad, cnt_good, used_paths = res_tup
    MyLogger.get_instance().log(f"Domain {domain['domain_name']}: \n\t{res}")

    return (res, loss_arr, cnt_bad, cnt_good, used_paths), domain, end_t, got_graph_t, wait_t, class_t


def evaluate_domain_metapath2vec_mult(domains: list[dict[str, Any]]) -> None:

    for domain in domains:
        res = evaluate_domain_metapath2vec(domain,None)
        print(res)

def parse_evaluation_result(eval_result: tuple[tuple | None, dict[str, Any], float, float, float, float], csv_writer) -> None:

    res, domain, end_t, got_graph_t, wait_t, class_t = eval_result
    domain_name = domain['domain_name']
    label_str: str = domain['label']
    label = int(label_str.find('benign') != -1)
    cnt = int(domain['node_id'])

    if res is None:
        # -1 for prediction and correct means that there was no classification therefore no result
        csv_writer.writerow(
            [cnt, domain_name, label, 0, 0, 0, 0.0, 0.0, -1, -1, 0.0, 0.0, -1, -1, 0.0, 0.0, -1, -1, 0.0, 0.0, -1, -1, 0.0, 0.0, -1, -1, end_t, got_graph_t, wait_t, class_t]
        )
        return

    results, loss_arr, cnt_bad, cnt_good, used_paths = res

    cnt_total = cnt_good + cnt_bad
    write_list = [cnt, domain_name, label, cnt_good, cnt_bad, cnt_total]

    used_paths.extend(['avg', 'cat'])

    cnt2 = 0
    cnt_providers = 0
    for result in results.values():

        if used_paths[cnt2] != __EXISTING_RESULT_PROVIDERS[cnt_providers]:
            idx = __EXISTING_RESULT_PROVIDERS.index(used_paths[cnt2])
            for _ in range(idx - cnt_providers):
                write_list.extend([0.0, 0.0, -1, -1])
            cnt_providers = idx

        # print(result)
        m_prob = result[0]
        b_prob = result[1]
        prediction = int(b_prob > 0.5)
        correct = int(label == prediction)

        write_list.extend([m_prob, b_prob, prediction, correct])
        cnt2 += 1
        cnt_providers += 1

    write_list.extend([end_t, got_graph_t, wait_t, class_t])
    csv_writer.writerow(write_list)

def _write_csv_header(csv_writer) -> None:
    csv_writer.writerow(
        ["id", "domain_name", "label", "n_good", "n_bad", "n_total", 'm_p_CNAME', 'b_p_CNAME', 'CNAME_pred',
         'CNAME_c', 'm_p_SUBD', "b_p_SUBD", "SUBD_pred", "SUBD_c", "m_p_IP", "b_p_IP", 'IP_pred', "IP_c",
         'm_p_AVG', 'b_p_AVG', "AVG_pred", "AVG_c", 'm_p_CAT', 'b_p_CAT', 'CAT_pred', 'CAT_c',
         'end_t', 'got_graph_t', 'wait_t', 'class_t']
    )


def parallel_test(provider, class_out_f_name: str, provider_has_node_id: bool) -> None:

    eval_lock = threading.Semaphore(3)
    with open(class_out_f_name, 'w') as f:

        csv_writer = csv.writer(f)
        _write_csv_header(csv_writer)

        with ThreadPoolExecutor(max_workers=12) as executor:
            futures = [executor.submit(evaluate_domain_metapath2vec, domain, eval_lock) for domain in provider]

            cnt = 0
            for future in as_completed(futures):
                res = future.result()
                if not provider_has_node_id:
                    res[1]['node_id'] = cnt

                parse_evaluation_result(res, csv_writer)
                cnt += 1

                if cnt % 50 == 0:
                    MyLogger.get_instance().log("Syncing output")
                    f.flush()
                    os.fsync(f.fileno())

def test(provider, class_out_f_name: str, provider_has_node_id: bool) -> None:

    with open(class_out_f_name, 'w') as f:

        csv_writer = csv.writer(f)
        _write_csv_header(csv_writer)

        for cnt, domain in enumerate(provider):

            res, _, e_t, g_t, w_t, c_t = evaluate_domain_metapath2vec(domain, None)

            if not provider_has_node_id:
                domain['node_id'] = cnt

            parse_evaluation_result((res, domain, e_t, g_t, w_t , c_t), csv_writer)

            if cnt % 50 == 0:
                f.flush()
                os.fsync(f.fileno())

def test_from_collection(path_to_config: str, class_out_f_name: str, parallel: bool, filter_train: bool) -> None:

    with open(path_to_config,'r') as f:
        conf = json.load(f)

    client = MongoClient(conf["client"], conf["port"])
    db = client[conf["db"]]
    collection = db[conf["collection"]]

    # pick domains that are malicious [{"$match": {"train": False, "label": { "$not": {"$regex": "benign", "$options": "i"}}}}]
    agg_filt = [{"$match": {"train": False}}] if filter_train else []
    cursor = collection.aggregate(agg_filt, batchSize=1000)

    if parallel:
        parallel_test(cursor, class_out_f_name, True)
    else:
        test(cursor, class_out_f_name, True)