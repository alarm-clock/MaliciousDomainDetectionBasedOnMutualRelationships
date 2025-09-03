

class Node:

    def __init__(self, node_id: int, domain: str, ip: list[int], b: bool, neighbours: list[int]):
        self.id = node_id
        self.domain = domain
        self.ip = ip
        self.b = b
        self.neighbours = neighbours

    def neighbors(self):
        return self.neighbours

    def add_neighbours(self, neighbours: list[int]):

        neighbours.pop(neighbours.index(self.id))
        for neighbour in neighbours:
            if neighbour not in self.neighbours:
                self.neighbours.append(neighbour)