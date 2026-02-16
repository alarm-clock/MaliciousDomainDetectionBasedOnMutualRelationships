

class Node:

    def __init__(self, node_id: int, domain: str, ip: list[int], b: bool, neighbours: list[tuple[int, float]]) -> None:
        self.id = node_id
        self.domain = domain
        self.ip = ip
        self.b = b
        self.neighbours = neighbours

    def neighbors(self):
        return self.neighbours

    def add_neighbours(self, neighbours: list[tuple[int, float]]) -> None:

        for neighbour in neighbours:
            if neighbour not in self.neighbours and neighbour[0] != self.id:
                self.neighbours.append(neighbour)