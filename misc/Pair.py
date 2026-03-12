from typing import Any


def replace(t: tuple, pos: int, val: tuple | Any) -> tuple:
    return t[:pos] + (val if type(val) == tuple else (val,)) + t[pos + 1:]

class Pair:
    __slots__ = ["first","second"]

    def __init__(self, first, second) -> None:
        self.first = first
        self.second = second