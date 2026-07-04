"""
File: LabelExtractor.py
Author: Jozef Michal Bukas <xbukas00@stud.fit.vutbr.cz>
Date: 22.02.2026
Brief: File that contains threaded label extractor used for collecting labels
    and related domain metadata from MongoDB for DGL and Neo4j graph creation
"""

import threading
from misc.Logger import MyLogger
from graph_repository.graph_repo_misc import add_project_into_pipeline, get_domains_parent_domains, domain_depth
from concurrent.futures import ThreadPoolExecutor
from pymongo.collection import Collection


# noinspection DuplicatedCode
class LabelExtractor(threading.Thread):
    """
    Class that extracts labels and related node metadata from MongoDB collection
    in a background thread
    """

    _n_nodes = 0
    _ranges = {}
    _dgl = True
    result: dict[str, list] | None = None
    _project = []
    _filter = {}

    def __init__(self, collection: Collection):
        """
        Method that initializes label extractor with MongoDB collection
        :param collection: `Collection` MongoDB collection containing dataset documents
        :return: None
        """
        super().__init__()
        self._collection = collection
        #self._n_nodes = n_nodes

    @classmethod
    def for_dgl(cls, collection: Collection, n_nodes: int):
        """
        Method that creates label extractor configured for DGL export
        :param collection: `Collection` MongoDB collection containing dataset documents
        :param n_nodes: `int` maximal node id range for DGL processing
        :return: Initialized `LabelExtractor` instance
        """
        instance = cls(collection)
        instance._n_nodes = n_nodes
        instance._dgl = True
        instance._project = [{"$match": {"node_id": {"$lte": n_nodes}}}]
        instance._filter = {'_id': 0, 'label': 1, 'node_id': 1}
        return instance

    @classmethod
    def for_neo4j(cls, collection: Collection, ranges):
        """
        Method that creates label extractor configured for Neo4j export
        :param collection: `Collection` MongoDB collection containing dataset documents
        :param ranges: aggregation pipeline range filters
        :return: Initialized `LabelExtractor` instance
        """
        instance = cls(collection)
        instance._ranges = ranges
        instance._dgl = False
        instance._project = ranges
        instance._filter = {'_id': 0, 'label': 1, 'node_id': 1, 'domain_name': 1}

        return instance

    def _parse_label(self, doc) -> tuple[int, int] | tuple[int, int, int, str, list[str]]:
        """
        Method that parses one MongoDB document into label tuple for DGL or Neo4j
        :param doc: MongoDB document with label information
        :return: parsed tuple with node label data
        """

        if self._dgl:
            return int(doc['node_id']), int(doc['label'].find("benign") != -1)
        else:
            domain_name = str(doc['domain_name'])
            parent_domains = get_domains_parent_domains(domain_name)
            depth = domain_depth(domain_name)

            return int(doc['node_id']), int(doc['label'].find("benign") != -1), depth, domain_name, parent_domains

    def _store_result_for_neo(self, data: list) -> None:
        """
        Method that stores parsed label tuples into Neo4j-oriented dictionary format
        :param data: `list` parsed label tuples
        :return: None
        """

        self.result = {'label': [], 'node_id': [], 'depth': [], 'domain_name': [], "parent_domains": []}

        for node_id, label, depth, domain_name, parent_domains in data:
            self.result['node_id'].append(node_id)
            self.result['label'].append(label)
            self.result['domain_name'].append(domain_name)
            self.result['parent_domains'].append(parent_domains)
            self.result['depth'].append(depth)

        return

    def run(self):
        """
        Method that executes threaded label extraction workflow
        :return: None
        """

        MyLogger.get_instance().log("Getting labels...")
        #project = [{"$match": { "node_id": {"$lte": self._n_nodes}}}] if self._dgl else self._ranges
        add_project_into_pipeline(self._filter, self._project)
        labels_w_ids = []
        cursor = self._collection.aggregate(self._project, batchSize=10000)

        with ThreadPoolExecutor(max_workers=16) as executor:
            futures = [executor.submit(self._parse_label, doc) for doc in cursor]

            for future in futures:
                result = future.result()
                if result:
                    labels_w_ids.append(result)

        labels_w_ids = sorted(labels_w_ids, key=lambda x: x[0])  #sort by node id

        if not self._dgl:
            self._store_result_for_neo(labels_w_ids)
            return

        _ , labels = zip(*labels_w_ids)

        MyLogger.get_instance().log("Got and sorted all labes")
        cursor.close()
        self.result = {'label': list(labels)}