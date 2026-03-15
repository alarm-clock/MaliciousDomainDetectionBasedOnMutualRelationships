from enum import Enum

class RequestStates(Enum):

    SUBMITTED = "submitted"
    PRE_FILTER = "pre_filter"
    IN_QUEUE = "in_queue"
    FILTER = "filter"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    ERROR = "error"
    TIMEOUT = "timeout"
    CANCELED = "canceled"