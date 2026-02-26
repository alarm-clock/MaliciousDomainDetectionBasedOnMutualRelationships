
class TooManyVersions(Exception):
    def __init__(self):
        super().__init__("Too many concurrent versions of graph. Maximum allowed number of coexisting version is 3.")

class Neo4jIndexError(Exception):
    def __init__(self, name: str | None = None):
        message = f"Neo4j experienced error when creating index {name}" if name is not None else f"Neo4j experienced error when creating index"
        super().__init__(message)