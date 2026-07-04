"""
File: RequestPriority.py
Author: Jozef Michal Bukas <xbukas00@stud.fit.vutbr.cz>
Date: 27.03.2026
Brief: File that contains enumeration of request priorities used for ordering
    graph-editing requests in processing queue
"""

from enum import Enum


class RequestPriority(Enum):
    """
    Class that represents priority levels of graph-editing requests
    """

    CRITICAL = 0
    HIGH = 1
    MEDIUM = 2
    LOW = 3