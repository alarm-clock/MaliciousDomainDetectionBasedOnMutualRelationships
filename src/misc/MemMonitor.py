"""
File: memory_utils.py
Author: Jozef Michal Bukas <xbukas00@stud.fit.vutbr.cz>
Date: 29.12.2025
Brief: File that contains helper function for checking whether enough system memory is available
"""

import psutil

GB = 1024**3


def enough_memory() -> bool:
    """
    Method that checks whether the system has enough available memory for execution
    :return: `bool` True if available memory is greater than 4 GB, otherwise False
    """
    mem = psutil.virtual_memory()
    available = mem.available / GB

    return available > 4  # GB