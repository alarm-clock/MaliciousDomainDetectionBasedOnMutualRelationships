"""
File: RequestStates.py
Author: Jozef Michal Bukas <xbukas00@stud.fit.vutbr.cz>
Date: 27.03.2026
Brief: File that contains enumeration of graph request lifecycle states used
    during request submission, filtering, queueing, execution, and termination
"""

from enum import Enum


class RequestStates(Enum):
    """
    Class that represents lifecycle states of graph-editing requests
    """

    SUBMITTED = "submitted"
    PRE_FILTER = "pre_filter"
    IN_QUEUE = "in_queue"
    FILTER = "filter"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    ERROR = "error"
    TIMEOUT = "timeout"
    CANCELED = "canceled"