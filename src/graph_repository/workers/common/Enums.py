"""
File: Enums.py
Author: Jozef Michal Bukas <xbukas00@stud.fit.vutbr.cz>
"""
from enum import Enum

class EditTypes(Enum):
    IGNORE_NEW = 0
    IGNORE_EXISTING = 1
    UPDATE = 2

class CallbackWhen(Enum):
    BEFORE_NODES = 0
    BETWEEN_NODES_EDGES = 1
    AFTER_EDGES = 2