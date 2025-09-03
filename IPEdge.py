from numbers import Number


class IPEdge:

    def __init__(self, ip: int):
        self.ip = ip
        self._domains: list[int] = []

    def add_domain(self, domain):
        self._domains.append(domain)

    def get_domains(self) -> list[int]:
        return self._domains