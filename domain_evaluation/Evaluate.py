import csv
import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Semaphore
from typing import Any
import dgl
from pymongo import MongoClient
from domain_evaluation.EvaluationObjects import EvaluationJob, EvaluationResult
from domain_evaluation.Metapath2vec.Learning import classify_domain, check_for_duplicity, PRODUCTION, TESTING
from graph_repository.graph_main.GraphRepository import GraphRepository
from misc.Logger import MyLogger

def _check_domains_neighborhood_maliciousness(tmp_nd_id: int, job: EvaluationJob, repository: GraphRepository, start_t: float) -> None:
    """
    Method that checks what percentage of direct neighbors in graphs are benign and which malicious. Direct is here meant
    as one "meta-path" hop, meaning that in this relation d1->ip->d2 is d2 direct neighbor of d1
    :param tmp_nd_id: Nod's id in graph
    :param job: job of which domain is part of
    :param repository: graph repository used to communicate with database
    :param start_t: start time of job used to set correct times
    :return: Nothing, sets correct states in job
    """

    checking_start_t = time.time()
    job.set_state(EvaluationJob.EvaluationState.CAL_NEIGH_MAL)

    try:
        res = repository.get_neighbors_maliciousness(tmp_nd_id)
    except Exception as e:
        MyLogger.get_instance().log_error(f"job {job.id}: Exception occurred while getting neighborhood stats: {e}")
        job.set_error(f"Exception occurred while getting neighborhood stats: {e}")
        return

    job.result.set_times(time.time() - checking_start_t, EvaluationResult.Times.CALC_NEIGH_M_T)

    if res is None:
        job.set_error("Could not connect to the database")
        return

    b_perc, m_perc = res

    job.result.set_1_hop_perc(m_perc,b_perc)
    if b_perc == 1.0 or m_perc == 1.0:
        MyLogger.get_instance().log(f"job {job.id}: Domain {job.domain_name} has only {'benign' if b_perc == 1.0 else 'malicious'} direct neighbors in graph")
        job.result.set_probability(m_perc, b_perc)
        job.result.set_times(time.time() - start_t, EvaluationResult.Times.END_T)
        job.set_state(EvaluationJob.EvaluationState.FINISHED)

    return


def _insert_node_into_graph(job: EvaluationJob, repository: GraphRepository) -> int:
    """
    Method that inserts domain into graph as temporary domain
    :param job: Job of which domain is part of
    :param repository: reference to graph repository
    :return: Temporary node id on success, when node was not inserted into graph returns -1 and sets correct job states
    """

    domain: dict[str, Any] = job.domain

    if repository is None:
        job.set_error("There is no graph repository instance")
        return -1

    #print("Temporary adding domain into graph...")
    MyLogger.get_instance().log_debug(f"job {job.id}: Temporary adding domain {domain['domain_name']} into graph...")
    tmp_node_id = repository.temporary_add_domain(domain, job.id)

    if tmp_node_id is None:
        #MyLogger.get_instance().log(f"Domain {domain['domain_name']} has no neighbours in graph!")
        job.result.set_no_neighbor()
        job.set_state(EvaluationJob.EvaluationState.FINISHED)
        return -1
    elif tmp_node_id == GraphRepository.TMP_ADD_STOP:
        job.set_error("Graph repository is stopping")
        return -1
    elif tmp_node_id == GraphRepository.TMP_ADD_NO_DB_ERR:
        job.set_error("Graph repository can not connect to the database")
        return -1

    MyLogger.get_instance().log_debug(f"job {job.id}: Domain {domain['domain_name']} has been inserted into graph")
    return tmp_node_id

def _get_graph(job: EvaluationJob, repository: GraphRepository, tmp_node_id: int) -> dgl.DGLHeteroGraph | None:
    """
    Function that will get domain's k-hop neighborhood from the graph
    :param job: `EvaluationJob` which holds domain whose k-hop neighborhood will be returned
    :param repository: `GraphRepository` used to communicate with database
    :return: `dgl.DGLHeteroGraph` graph on success, True if domain has no neighbors in graph, False if error occurs
    """

    MyLogger.get_instance().log_debug(f'job {job.id}: Extracting k-hop neighbors...')

    try:
        job.set_state(EvaluationJob.EvaluationState.GETTING_GRAPH)
        graph = repository.get_k_hop_neighborhood_dgl(tmp_node_id, True)
    except Exception as e:
        MyLogger.get_instance().log_error(f"job {job.id}:  Exception occurred while getting k hop neighborhood dgl: {e}")
        job.set_error(f"Exception occurred while getting k hop neighborhood dgl: {e}")
        return None

    return graph

def _check_domain_in_graph(job: EvaluationJob, repository: GraphRepository) -> None:

    job.set_state(EvaluationJob.EvaluationState.CHECKING_NODE_IN_G)
    domain = repository.get_domain(job.domain_name)

    if domain is None:
        return

    MyLogger.get_instance().log(f"job {job.id}: Domain {job.domain_name} found in graph with label: {'benign' if domain['label'] == 1 else 'malicious'}")
    job.result.set_probability(domain['label'] == 0, domain['label'] == 1)
    job.result.set_in_graph()
    job.set_state(EvaluationJob.EvaluationState.FINISHED)
    return

def _check_for_duplicity(eval_job: EvaluationJob, g: dgl.DGLHeteroGraph, start_t: float) -> None:

    res = check_for_duplicity(g)

    if type(res) is tuple:
        eval_job.result.set_times(time.time() - start_t, EvaluationResult.Times.END_T)
        p_m, p_b, n_m, n_b = res
        eval_job.result.set_probability(p_m, p_b)
        eval_job.result.set_counts(n_m, n_b)
        eval_job.set_state(EvaluationJob.EvaluationState.FINISHED)
        return

    if not res:
        eval_job.result.set_times(time.time() - start_t, EvaluationResult.Times.END_T)
        eval_job.set_state(EvaluationJob.EvaluationState.FINISHED)
        return

    return



def _wait_on_gpu(eval_job: EvaluationJob, gpu_semaphore: Semaphore) -> None:
    """
    Method that waits on gpu and calculates time spent waiting on gpu
    :param eval_job: Domain evaluation job
    :param gpu_semaphore: Semaphore on which job will wait on gpu
    :return: Nothing
    """

    MyLogger.get_instance().log(f"job {eval_job.id}: Domain {eval_job.domain_name} is waiting on GPU")
    eval_job.set_state(EvaluationJob.EvaluationState.WAITING_ON_GPU)
    wait_start = time.time()
    gpu_semaphore.acquire()
    eval_job.result.set_times(time.time() - wait_start, EvaluationResult.Times.WAITING_ON_GPU_T)
    eval_job.set_state(EvaluationJob.EvaluationState.EVALUATING)
    MyLogger.get_instance().log(f"job {eval_job.id}: Starting to classify domain {eval_job.domain_name}...")



def evaluate_domain_metapath2vec(eval_job: EvaluationJob, gpu_semaphore: Semaphore, return_result: bool = False) -> None | EvaluationJob:
    """
    Method that evaluates domain using metapath2vec model with multiple metapaths, but also by checking simple stats
    of evaluated domain's neighborhood
    :param eval_job: Job of which domain will be evaluated
    :param gpu_semaphore: Semaphore used to limit number of jobs that can concurrently use GPU
    :param return_result: Flag indicating whether to return result or not (result being reference to ``eval_job``)
    :return: Nothing of `EvaluationJob` if ``return_result`` flag is true
    """

    start_t = time.time()
    repository = GraphRepository.get_instance()

    #check if domain is in graph, if yes return ground truth
    _check_domain_in_graph(eval_job, repository)

    if eval_job.is_finished():
        eval_job.result.set_times(time.time() - start_t, EvaluationResult.Times.END_T)
        return eval_job if return_result else None

    #insert domain into graph
    tmp_node_id = _insert_node_into_graph(eval_job, repository)

    if eval_job.is_finished():
        eval_job.result.set_times(time.time() - start_t, EvaluationResult.Times.END_T)
        return eval_job if return_result else None

    #check domains direct neighborhood, if there is only one type of label, return it
    #TODO check how much percentage can be lowered while still being correct
    _check_domains_neighborhood_maliciousness(tmp_node_id, eval_job, repository, start_t)

    if eval_job.is_finished():
        repository.delete_temporary_domain(tmp_node_id, eval_job.id)
        eval_job.result.set_times(time.time() - start_t, EvaluationResult.Times.END_T)
        return eval_job if return_result else None

    #get dgl graph
    graph_start_t = time.time()
    g = _get_graph(eval_job, repository, tmp_node_id)
    eval_job.result.set_times(time.time() - graph_start_t, EvaluationResult.Times.GOT_GRAPH_T)

    repository.delete_temporary_domain(tmp_node_id, eval_job.id)

    if g is None:
        eval_job.result.set_times(time.time() - start_t, EvaluationResult.Times.END_T)
        return eval_job if return_result else None

    _check_for_duplicity(eval_job,g,start_t)
    if eval_job.is_finished():
        return eval_job if return_result else None

    _wait_on_gpu(eval_job, gpu_semaphore)

    try:
        class_start = time.time()
        classify_domain(g, eval_job.result, PRODUCTION if not return_result else TESTING, True)

    except Exception as e:
        MyLogger.get_instance().log_error(f"Exception occurred while classifying domain {eval_job.domain_name}: {e}...")
        eval_job.set_error(f"Exception occurred while classifying domain {eval_job.domain_name}: {e}")
        eval_job.result.set_times(time.time() - start_t, EvaluationResult.Times.END_T)
        return eval_job if return_result else None
    finally:
        gpu_semaphore.release()

    eval_job.result.set_times(time.time() - start_t, EvaluationResult.Times.END_T)
    eval_job.result.set_times(time.time() - class_start, EvaluationResult.Times.CLASSIFICATION_T)
    eval_job.set_state(EvaluationJob.EvaluationState.FINISHED)

    return eval_job if return_result else None

#tuple[tuple | None, dict[str, Any], float, float, float, float]
def parse_evaluation_result(eval_result: EvaluationJob, csv_writer) -> None:
    csv_arr = eval_result.to_text_csv_output()
    csv_writer.writerow(csv_arr)

def write_csv_header(csv_writer) -> None:
    csv_writer.writerow(
        ["domain_name",'fin_state', "label", "no_neighbor", "already_in_graph", "n_good", "n_bad", "n_total", '1_hop_mal_p',
         '1_hop_ben_p','m_p_CNAME', 'b_p_CNAME', 'CNAME_pred', 'CNAME_c', 'm_p_SUBD', "b_p_SUBD", "SUBD_pred", "SUBD_c",
         "m_p_IP", "b_p_IP", 'IP_pred', "IP_c", 'm_p_AVG', 'b_p_AVG', "AVG_pred", "AVG_c", 'm_p_CAT', 'b_p_CAT', 'CAT_pred',
         'CAT_c','end_t', 'got_graph_t', 'calc_neigh_stats_t', 'wait_t', 'class_t']
    )

def _gen_job_from_domain_data(domain: dict[str, Any]) -> EvaluationJob:

    job = EvaluationJob(domain['domain_name'],test_label=str(domain['label']).find('benign') != -1, timeout=-1)
    domain.pop('label')
    job.set_domain_data(domain)
    return job


def parallel_test(provider, class_out_f_name: str) -> None:

    eval_lock = threading.Semaphore(16)
    with open(class_out_f_name, 'w') as f:

        csv_writer = csv.writer(f)
        write_csv_header(csv_writer)

        with ThreadPoolExecutor(max_workers=16) as executor:
            futures = [executor.submit(evaluate_domain_metapath2vec, _gen_job_from_domain_data(domain) , eval_lock, True) for domain in provider]

            cnt = 0
            for future in as_completed(futures):
                res = future.result()

                parse_evaluation_result(res, csv_writer)
                cnt += 1

                if cnt % 50 == 0:
                    MyLogger.get_instance().log_debug("Syncing output")
                    f.flush()
                    os.fsync(f.fileno())


def test_from_collection(path_to_config: str, class_out_f_name: str, filter_train: bool) -> None:

    with open(path_to_config,'r') as f:
        conf = json.load(f)

    client = MongoClient(conf["client"], conf["port"])
    db = client[conf["db"]]
    collection = db[conf["collection"]]

    # pick domains that are malicious [{"$match": {"train": False, "label": { "$not": {"$regex": "benign", "$options": "i"}}}}]
    agg_filt = [{"$match": {"train": False}}] if filter_train else []
    cursor = collection.aggregate(agg_filt, batchSize=1000)

    parallel_test(cursor, class_out_f_name)