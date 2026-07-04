"""
File: data_structures.py
Author: Jozef Michal Bukas <xbukas00@stud.fit.vutbr.cz>
Date: 29.12.2025
Brief: File that contains helper tuple replacement function and simple Pair container class
"""

from typing import Any


def replace(t: tuple, pos: int, val: tuple | Any) -> tuple:
    """
    Function that replaces item at given position in tuple with provided value
    :param t: `tuple` input tuple
    :param pos: `int` position of the item to replace
    :param val: `tuple | Any` replacement value
    :return: `tuple` tuple with replaced element
    """
    return t[:pos] + (val if type(val) == tuple else (val,)) + t[pos + 1:]


class Pair:
    """
    Class that represents a simple pair of values
    """

    __slots__ = ["first", "second"]

    def __init__(self, first, second) -> None:
        """
        Method that initializes pair values
        :param first: first stored value
        :param second: second stored value
        :return: None
        """
        self.first = first
        self.second = second