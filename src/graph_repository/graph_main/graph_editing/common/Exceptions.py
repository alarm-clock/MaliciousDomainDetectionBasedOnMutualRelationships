"""
File: exceptions.py
Author: Jozef Michal Bukas <xbukas00@stud.fit.vutbr.cz>
Date: 27.03.2026
Brief: File that contains custom exception classes used in graph versioning and Neo4j index management
"""

class TooManyVersions(Exception):
    """
    Method that represents an error raised when too many graph versions exist at the same time
    """

    def __init__(self):
        """
        Method that initializes the exception with a fixed error message
        :return: None
        """
        super().__init__("Too many concurrent versions of graph. Maximum allowed number of coexisting version is 3.")


class Neo4jIndexError(Exception):
    """
    Method that represents an error raised when Neo4j index creation fails
    """

    def __init__(self, name: str | None = None):
        """
        Method that initializes the exception with an optional index name
        :param name: `str | None` name of the index that caused the error
        :return: None
        """
        message = f"Neo4j experienced error when creating index {name}" if name is not None else f"Neo4j experienced error when creating index"
        super().__init__(message)