
def replace(t: tuple, pos: int, val) -> tuple:
    return t[:pos] + val + t[pos:]

class Pair:
    __slots__ = ["first","second"]

    def __init__(self, first, second) -> None:
        self.first = first
        self.second = second