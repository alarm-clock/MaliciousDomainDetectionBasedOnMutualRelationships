import uuid
from enum import Enum


class EvaluationState(Enum):
    SUBMITTED = 0
    IN_QUEUE = 1
    GETTING_GRAPH = 2
    WAITING_ON_GPU = 3
    EVALUATING = 4
    FINISHED = 5
    ERROR = 6

class EvaluationJob:

    def __init__(self, domain: str):
        self._state = EvaluationState.SUBMITTED
        self._id = str(uuid.uuid4())
        self._domain = domain
        self._result = None

    @property
    def state(self) -> EvaluationState:
        return self._state

    @property
    def domain(self) -> str:
        return self._domain

    @property
    def id(self) -> str:
        return self._id

    @property
    def result(self) -> 'EvaluationJob':
        return self._result

    def set_state(self, state: EvaluationState):
        if state >= self._state:
            self._state = state

        raise ValueError("Can not return back when setting state")

    def set_result