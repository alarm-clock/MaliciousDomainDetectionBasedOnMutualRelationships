"""
File: EvaluationObjects.py
Author: Jozef Michal Bukas <xbukas00@stud.fit.vutbr.cz>
Date: 14.02.2026
Brief: File that contains evaluation result and evaluation job classes used to store
    classification output, timing statistics, processing state, timeout handling,
    and CSV export of evaluation results
"""

import time
import uuid
from enum import Enum
from threading import Event, Thread
from typing import Any

from graph_repository.workers.common.GraphTypes import EdgeTypes
from misc.Logger import MyLogger



class EvaluationResult:
    """
    Class that represents result of one domain evaluation, including probabilities,
    neighbor statistics, timing information, and optional per-provider outputs.
    """

    class Times(Enum):
        """
        Class that represents identifiers of timing fields stored in `EvaluationResult`.
        """
        END_T = "_end_t"
        GOT_GRAPH_T = "_got_graph_t"
        WAITING_ON_GPU_T = "_waiting_t"
        CLASSIFICATION_T = "_class_t"
        CALC_NEIGH_M_T = "_calc_neigh_stats"

    def __init__(self, maliciousness_threshold: float = 0.5):
        """
        Method that initializes empty evaluation result object
        :param maliciousness_threshold: `float` threshold above which domain is considered malicious
        :return: None
        """
        self._thresh = maliciousness_threshold
        self._p_m = 0.0
        self._p_b = 0.0
        self._n_m = 0
        self._n_b = 0
        self._1_hop_mal = 0.0
        self._1_hop_ben = 0.0
        self._end_t = 0.0
        self._got_graph_t = 0.0
        self._calc_neigh_stats = 0.0
        self._wait_t = 0.0
        self._class_t = 0.0
        self._no_neighbor = False
        self._in_graph = False
        self._other_probs: dict[str, Any] | None = None
        self.success = True
        self.error_descr = ""

    @property
    def malicious(self) -> bool:
        """
        Method that returns whether domain is classified as malicious
        :return: `bool` True if malicious probability is above configured threshold, otherwise False
        """
        return self._p_m >= self._thresh

    @property
    def get_probability(self) -> tuple[float, float]:
        """
        Method that returns stored malicious and benign probabilities
        :return: `tuple[float, float]` malicious and benign probability
        """
        return self._p_m, self._p_b

    @property
    def get_n_counts(self) -> tuple[int, int, int]:
        """
        Method that returns malicious, benign, and total neighbor counts
        :return: `tuple[int, int, int]` malicious count, benign count, and total count
        """
        return self._n_m, self._n_b, self._n_b + self._n_m

    @property
    def get_times(self) -> tuple[float, float, float, float, float]:
        """
        Method that returns stored timing statistics of evaluation process
        :return: `tuple[float, float, float, float, float]` end time, graph extraction time,
            neighborhood stats time, waiting time, and classification time
        """
        return self._end_t, self._got_graph_t, self._calc_neigh_stats, self._wait_t, self._class_t

    @property
    def get_other_probs(self) -> dict[str, Any] | None:
        """
        Method that returns optional dictionary of alternative classification outputs
        :return: `dict[str, Any] | None` provider-specific results or None
        """
        return self._other_probs

    @property
    def no_neighbor(self) -> bool:
        """
        Method that returns whether evaluated domain had no graph neighbors
        :return: `bool` True if domain has no neighbors, otherwise False
        """
        return self._no_neighbor

    @property
    def in_graph(self) -> bool:
        """
        Method that returns whether evaluated domain was already present in graph
        :return: `bool` True if domain already exists in graph, otherwise False
        """
        return self._in_graph

    @property
    def get_1_hop_perc(self) -> tuple[float, float]:
        """
        Method that returns one-hop neighborhood malicious and benign percentages
        :return: `tuple[float, float]` malicious and benign neighborhood percentages
        """
        return self._1_hop_mal, self._1_hop_ben

    @property
    def to_dict(self) -> dict[str, Any]:
        """
        Method that returns basic evaluation result as dictionary
        :return: `dict[str, Any]` dictionary representation of evaluation result
        """
        return {
            'in_graph': self.in_graph,
            'no_neighbor': self.no_neighbor,
            'malicious': self.malicious,
            'prob_mal': self._p_m,
            'prob_ben': self._p_b,
            'n_mal': self._n_m,
            'n_ben': self._n_b
        }

    def set_no_neighbor(self) -> None:
        """
        Method that marks result as having no graph neighbors
        :return: None
        """
        self._no_neighbor = True

    def set_in_graph(self) -> None:
        """
        Method that marks result as already existing in graph
        :return: None
        """
        self._in_graph = True

    def is_empty(self) -> bool:
        """
        Method that checks whether result still contains only default values
        :return: `bool` True if result is empty, otherwise False
        """
        return self._n_b == 0 and self._n_m == 0 and self._n_b == 0 and self._p_m == 0.0 and self._p_b == 0.0 and self._other_probs is None

    def set_times(self, time: float, which: Times) -> None:
        """
        Method that stores selected timing value into result
        :param time: `float` measured time value
        :param which: `Times` identifier specifying which timing field should be updated
        :return: None
        """
        setattr(self, which.value, time)

    def set_counts(self, n_m: int, n_b: int) -> None:
        """
        Method that stores malicious and benign neighbor counts
        :param n_m: `int` number of malicious neighbors
        :param n_b: `int` number of benign neighbors
        :return: None
        """
        self._n_m = int(n_m)
        self._n_b = int(n_b)

    def set_probability(self, p_m: float, p_b: float) -> None:
        """
        Method that stores malicious and benign classification probabilities
        :param p_m: `float` malicious probability
        :param p_b: `float` benign probability
        :return: None
        """
        self._p_m = float(p_m)
        self._p_b = float(p_b)

    def set_1_hop_perc(self,m_p: float, b_p: float) -> None:
        """
        Method that stores one-hop neighborhood malicious and benign percentages
        :param m_p: `float` malicious percentage in one-hop neighborhood
        :param b_p: `float` benign percentage in one-hop neighborhood
        :return: None
        """
        self._1_hop_mal = m_p
        self._1_hop_ben = b_p

    def set_other_probs(self, other_probs: dict[str, Any]) -> None:
        """
        Method that stores detailed provider-specific classification outputs
        :param other_probs: `dict[str, Any]` dictionary of additional probabilities
        :return: None
        """
        self._other_probs = other_probs

    def set_error(self, error_description: str) -> None:
        """
        Method that marks result as failed and stores error description
        :param error_description: `str` textual description of evaluation error
        :return: None
        """
        self.error_descr = error_description
        self.success = False


class EvaluationJob:
    """
    Class that represents one submitted domain evaluation job, including state,
    timing, timeout thread, result object, and export helpers.
    """

    class EvaluationState(Enum):
        """
        Class that represents processing states of evaluation job.
        """
        SUBMITTED = 0
        IN_QUEUE = 1
        EXTRACTING_DATA = 2
        CHECKING_NODE_IN_G = 3
        CAL_NEIGH_MAL = 4
        GETTING_GRAPH = 5
        WAITING_ON_GPU = 6
        EVALUATING = 7
        FINISHED = 8
        TIMEOUT = 9
        ERROR = 10

        def __str__(self) -> str:
            """
            Method that converts evaluation state into human-readable text
            :return: `str` textual representation of current evaluation state
            """
            if self == EvaluationJob.EvaluationState.SUBMITTED:
                return "Submitted"
            elif self == EvaluationJob.EvaluationState.IN_QUEUE:
                return "In Queue"
            elif self == EvaluationJob.EvaluationState.EXTRACTING_DATA:
                return "Extracting Data"
            elif self == EvaluationJob.EvaluationState.GETTING_GRAPH:
                return "Getting Graph"
            elif self == EvaluationJob.EvaluationState.CHECKING_NODE_IN_G:
                return "Checking if domain exists ing graph"
            elif self == EvaluationJob.EvaluationState.CAL_NEIGH_MAL:
                return "Calculating domains direct neighborhood maliciousness"
            elif self == EvaluationJob.EvaluationState.WAITING_ON_GPU:
                return "Waiting on GPU"
            elif self == EvaluationJob.EvaluationState.EVALUATING:
                return "Evaluating"
            elif self == EvaluationJob.EvaluationState.FINISHED:
                return "Finished"
            elif self == EvaluationJob.EvaluationState.TIMEOUT:
                return "Timeout"
            elif self == EvaluationJob.EvaluationState.ERROR:
                return "Error"

            raise ValueError()


    def __init__(self, domain: str, *, malicious_threshold: float = 0.5, timeout: float = 1200.0, test_label: bool | None = None):
        """
        Method that initializes evaluation job and optionally starts timeout thread
        :param domain: `str` domain name that should be evaluated
        :param malicious_threshold: `float` threshold above which result is considered malicious
        :param timeout: `float` timeout in seconds after which job is marked as timed out
        :param test_label: `bool | None` optional expected label used in testing mode
        :return: None
        """
        self._state = EvaluationJob.EvaluationState.SUBMITTED
        self._id = str(uuid.uuid4())
        self._domain_name = domain
        self._domain_data: dict[str, Any] = {}
        self._result = EvaluationResult(malicious_threshold)
        self._error_description = ""
        self._finish_time: float | None = None
        self._test_label = test_label
        self._timeout = timeout
        self._timeout_event = Event()

        # Start timeout watcher thread only for positive timeout values.
        if timeout > 0.0:
            Thread(target=self._timeout_thrd, daemon=True, name=f'EvaluationTimeout{self._id}').start()

    @property
    def state(self) -> EvaluationState:
        """
        Method that returns current job state
        :return: `EvaluationState` current evaluation job state
        """
        return self._state

    @property
    def domain(self) -> dict[str, Any]:
        """
        Method that returns stored domain data
        :return: `dict[str, Any]` domain data associated with job
        """
        return self._domain_data

    @property
    def domain_name(self) -> str:
        """
        Method that returns evaluated domain name
        :return: `str` domain name
        """
        return self._domain_name

    @property
    def id(self) -> str:
        """
        Method that returns unique identifier of evaluation job
        :return: `str` job identifier
        """
        return self._id

    @property
    def result(self) -> EvaluationResult:
        """
        Method that returns evaluation result object associated with job
        :return: `EvaluationResult` evaluation result object
        """
        return self._result

    @property
    def finish_time(self) -> float | None:
        """
        Method that returns job finish time if job has already finished
        :return: `float | None` finish timestamp or None
        """
        return self._finish_time

    @property
    def error_description(self) -> str:
        """
        Method that returns stored job error description
        :return: `str` textual description of job error
        """
        return self._error_description

    def is_finished(self) -> bool:
        """
        Method that checks whether job is already in terminal state
        :return: `bool` True if job is finished, failed, or timed out, otherwise False
        """
        return (self._state == EvaluationJob.EvaluationState.FINISHED or
                self._state == EvaluationJob.EvaluationState.ERROR or
                self._state == EvaluationJob.EvaluationState.TIMEOUT)

    def set_error(self, error_description: str) -> None:
        """
        Method that marks job as failed and stores error description
        :param error_description: `str` textual description of error
        :return: None
        """
        MyLogger.get_instance().log_error(f" job {self._id}  error: {error_description}")
        self._error_description = error_description
        self._state = EvaluationJob.EvaluationState.ERROR
        self._finish_time = time.time()
        self.result.set_error(self._error_description)

    def stop_wait(self) -> None:
        """
        Method that stops timeout waiting thread by signaling timeout event
        :return: None
        """
        self._timeout_event.set()

    def set_state(self, state: EvaluationState) -> None:
        """
        Method that updates job state while preventing backward state transitions
        :param state: `EvaluationState` new job state
        :return: None
        :raises ValueError: if state transition would move job backwards
        """
        if state.value >= self._state.value:
            MyLogger.get_instance().log_debug(f" job {self._id} state: {state.value}")
            self._state = state

            # Store finish time once job enters terminal state.
            if self.is_finished():
                self._finish_time = time.time()

            # Stop timeout waiting once actual evaluation starts.
            elif state == EvaluationJob.EvaluationState.EXTRACTING_DATA:
                self.stop_wait()

            return

        raise ValueError("Can not return back when setting state")

    def set_result(self, result: EvaluationResult) -> None:
        """
        Method that sets evaluation result object if it was not initialized yet
        :param result: `EvaluationResult` result object that should be assigned
        :return: None
        """
        if self._result is None:
            self._result = result

    def set_domain_data(self, domain_data: dict[str, Any]) -> None:
        """
        Method that stores domain data associated with evaluation job
        :param domain_data: `dict[str, Any]` domain data to store
        :return: None
        """
        self._domain_data = domain_data

    def _timeout_thrd(self) -> None:
        """
        Method that waits for timeout expiration and marks job as timed out if needed
        :return: None
        """
        if not self._timeout_event.wait(self._timeout):
            MyLogger.get_instance().log_warning(f" job {self._id} timed out")
            self.set_state(EvaluationJob.EvaluationState.TIMEOUT)
            self.result.set_error("Timeout")

    __EXISTING_RESULT_PROVIDERS = {EdgeTypes.CNAME.value: (10, 14),
                                   EdgeTypes.SUBDOMAIN.value : (14, 18),
                                   EdgeTypes.TRANSLATES.value: (18, 22),
                                   'AVERAGE': (22, 26),
                                   'CONCAT': (26, 30)}

    def to_text_csv_output(self) -> list[Any]:
        """
        Method that converts evaluation job and its result into CSV row representation
        :return: `list[Any]` list of values formatted for CSV output
        """

        csv_list: list[Any] = [self.domain_name, str(self.state), self._test_label, self.result.no_neighbor, self.result.in_graph]
        csv_list.extend(self.result.get_n_counts)
        csv_list.extend(self.result.get_1_hop_perc)

        #Default values where -1 indicates that model was not used to determine domain's maliciousness
        csv_list.extend([0.0, 0.0, -1, -1, 0.0, 0.0, -1, -1, 0.0, 0.0, -1, -1, 0.0, 0.0, -1, -1, 0.0, 0.0, -1, -1])

        if self.result.get_other_probs is not None:

            # Fill CSV segments with provider-specific outputs when testing mode stored all predictions.
            for provider, result in self.result.get_other_probs.items():
                m_prob = result[0]
                b_prob = result[1]
                prediction = int(b_prob > 0.5)
                correct = int(int(self._test_label)== prediction)

                start_idx, end_idx = self.__EXISTING_RESULT_PROVIDERS[provider]
                csv_list[start_idx: end_idx] = [m_prob, b_prob, prediction, correct]
        else:
            # Otherwise fill only average result section.
            m_prob, b_prob = self.result.get_probability
            prediction = int(b_prob > 0.5)
            correct = int(int(self._test_label) == prediction)
            start_idx, end_idx = self.__EXISTING_RESULT_PROVIDERS['AVERAGE']
            csv_list[start_idx: end_idx] = [m_prob, b_prob, prediction, correct]


        csv_list.extend(self.result.get_times)

        return csv_list