"""
File: EvaluationApp.py
Author: Jozef Michal Bukas <xbukas00@stud.fit.vutbr.cz>
Date: 21.4.2026
Brief: File containing evaluation application singleton class which implements application loop
"""
import csv
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from queue import Queue

from api.config.config import Config
from domain_evaluation.Evaluate import evaluate_domain_metapath2vec, parse_evaluation_result, write_csv_header
from domain_evaluation.EvaluationObjects import EvaluationJob, EvaluationResult
from graph_repository.graph_main.GraphRepository import GraphRepository
from threading import Semaphore, Event, Lock, Thread
from data_extraction.dnsExtractor import extract_dns_sync, DnsErr
from misc.Logger import MyLogger
import pandas as pd


class EvaluationApp:
    """
    Class that implements evaluation application singleton class
    """

    _evaluation_app_instance_ = None

    _RESULT_REMOVAL_TIME = 1200.0

    def __init__(self, graph_repository: GraphRepository, max_evaluations: int = 16, max_gpu_evaluations: int = 16):

        if self._evaluation_app_instance_ is None:
            self._repository = graph_repository
            self._evaluation_semaphore = Semaphore(max_evaluations)
            self._gpu_semaphore = Semaphore(max_gpu_evaluations)
            self._results: dict[str, EvaluationJob] = {}
            #self._uuid_domain_map: dict[str, str] = {}
            self._results_lock = Lock()

            self._job_queue = Queue()
            self._stop_event = Event()
            self._n_eval_thrds = max_evaluations

            self._executor = ThreadPoolExecutor(max_workers=max_evaluations, thread_name_prefix='EvaluationThread')
            for _ in range(max_evaluations):
                self._executor.submit(self._worker)

            Thread(target=self._remove_finished_jobs, name='ResultRemovalThread', daemon=True).start()
            EvaluationApp._evaluation_app_instance_ = self
            self._RESULT_REMOVAL_TIME = Config.get_instance().eval_app_conf.result_removal_time

    @classmethod
    def get_instance(cls) -> 'EvaluationApp | None':
        return cls._evaluation_app_instance_

    def stop(self):

        MyLogger.get_instance().log("Evaluation app is stopping after stop() was called")
        self._job_queue.mutex.acquire()
        for job in self._job_queue.queue:
            job.stop_wait()
            job.set_state(EvaluationJob.EvaluationState.TIMEOUT)
            self._job_queue.task_done()

        self._job_queue.mutex.release()

        self._stop_event.set()

        for _ in range(self._n_eval_thrds):
            self._job_queue.put(None)

        self._executor.shutdown()
        MyLogger.get_instance().log("Evaluation app is stopped")

    def _remove_finished_jobs(self) -> None:

        while not self._stop_event.is_set():
            self._results_lock.acquire()

            curr_time = time.time()
            for key, job in self._results.items():

                if job.is_finished():
                    if curr_time - job.finish_time > self._RESULT_REMOVAL_TIME:
                        self._results.pop(key, None)
                        #self._uuid_domain_map.pop(job.domain_name, None)

            self._results_lock.release()
            self._stop_event.wait(self._RESULT_REMOVAL_TIME)  #either wait 20 mins for next iteration or finish waiting when stop event is set


    def _evaluate_domain(self, job: EvaluationJob) -> None:
        """
        Method for domain evaluation, waits for the result
        :param job: `EvaluationJob` with domain that will be evaluated
        :return: Object with evalution result
        """

        job.set_state(EvaluationJob.EvaluationState.EXTRACTING_DATA)
        domain_data = extract_dns_sync(job.domain_name)
        if isinstance(domain_data, DnsErr):
            job.set_error(str(domain_data))
            return

        job.set_domain_data(domain_data)
        evaluate_domain_metapath2vec(job, self._evaluation_semaphore)
        MyLogger.get_instance().log_evaluation_result(job)

    def evaluate_domain(self, domain: str, force: bool = False) -> EvaluationResult | None:

        if force:
            job = EvaluationJob(domain)
            self._evaluate_domain(job)
            return job.result
        else:

            job_id = self.evaluate_domain_async(domain)

            while True:
                job = self._results.get(job_id, None)
                if job is None:
                    return None

                if job.is_finished():
                    return job.result


    def _worker(self):
        while not self._stop_event.is_set():
            job: EvaluationJob = self._job_queue.get()
            if job is None:
                MyLogger.get_instance().log("Evaluation app is stopped so worker thread is also stopping after receiving job None")
                break

            if job.state == EvaluationJob.EvaluationState.TIMEOUT or job.state == EvaluationJob.EvaluationState.ERROR:
                MyLogger.get_instance().log_debug(f"job {job.id} was taken from queue in state {job.state}")
                self._job_queue.task_done()
                continue

            self._evaluate_domain(job)
            self._job_queue.task_done()

    def get_job(self, job_id: str) -> EvaluationJob | None:

        self._results_lock.acquire()

        job = self._results.get(job_id, None)
        if job is not None and job.is_finished():
            self._results.pop(job_id)

        self._results_lock.release()

        return job

    """
    def _find_domain_in_results(self, domain: str) -> EvaluationResult | None:

        res_id = self._uuid_domain_map.get(domain, None)
        if res_id is None:
            return None

        result = self._results.get(res_id, None)
        if result is None:
            return None

        return result.result

    #def _copy_result(self, job: EvaluationJob, result: EvaluationResult) -> None:
    """

    def evaluate_domain_async(self, domain: str, timeout: float | None = None) -> str:

        job = EvaluationJob(domain) if timeout is None else EvaluationJob(domain, timeout=timeout)
        job.set_state(EvaluationJob.EvaluationState.SUBMITTED)

        #with self._results_lock:
        #    result = self._find_domain_in_results(domain)

        #if result is not None:

        self._results_lock.acquire()
        self._results[job.id] = job
        #self._uuid_domain_map[domain] = job.id
        self._results_lock.release()
        self._job_queue.put(job)

        return job.id



def submit_domain(eval_job: EvaluationJob, csv_writer, write_lock: threading.Lock) -> None:

    eval_app = EvaluationApp.get_instance()
    if eval_app is None:
        return

    eval_app._evaluate_domain(eval_job)

    with write_lock:
        parse_evaluation_result(eval_job,csv_writer)


def test_from_parquet(path_to_file: str, class_out_f_name: str) -> None:
    df = pd.read_parquet(path_to_file)
    df = df[['domain_name', 'label']]
    df['label'] = df['label'].map({
        'good':'benign',
        'bad':'malicious'
    })

    jobs = []
    for domain in df.itertuples(index=False):
        job = EvaluationJob(domain.domain_name, timeout=-1, test_label= domain.label == 'benign')
        jobs.append(job)

    write_lock = threading.Lock()
    with open(class_out_f_name, 'w') as f:
        writer = csv.writer(f)
        write_csv_header(writer)
        with ThreadPoolExecutor(max_workers=4) as executor:
            for job in jobs:
                executor.submit(submit_domain, job, writer, write_lock)

    EvaluationApp.get_instance().stop()