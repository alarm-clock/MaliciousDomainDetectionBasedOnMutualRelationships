import threading
from misc.Logger import MyLogger
from graph_repository.graph_repo_misc import add_project_into_pipeline
from concurrent.futures import ThreadPoolExecutor
from pymongo.collection import Collection


# noinspection DuplicatedCode
class LabelExtractor(threading.Thread):

    _n_nodes = 0
    _ranges = {}
    _dgl = True
    result: dict[str, list] | None = None
    _project = []
    _filter = {}

    def __init__(self, collection: Collection):
        super().__init__()
        self._collection = collection
        #self._n_nodes = n_nodes


    @classmethod
    def for_dgl(cls, collection: Collection, n_nodes: int):
        instance = cls(collection)
        instance._n_nodes = n_nodes
        instance._dgl = True
        instance._project = [{"$match": { "node_id": {"$lte": n_nodes}}}]
        instance._filter = {'_id': 0, 'label': 1, 'node_id': 1}
        return instance

    @classmethod
    def for_neo4j(cls, collection: Collection, ranges):
        instance = cls(collection)
        instance._ranges = ranges
        instance._dgl = False
        instance._project = ranges
        instance._filter = {'_id': 0, 'label': 1, 'node_id': 1, 'domain_name': 1}

        return instance

    def _parse_label(self, doc) -> tuple[int, int] | tuple[int, int, str] :

        if self._dgl:
            return int(doc['node_id']), int(doc['label'].find("benign") != -1)
        else:
            return int(doc['node_id']), int(doc['label'].find("benign") != -1), str(doc['domain_name'])

    def _store_result_for_neo(self, data: list) -> None:

        self.result = {'label': [], 'node_id': [], 'domain_name': []}

        for node_id, label, domain_name in data:
            self.result['node_id'].append(node_id)
            self.result['label'].append(label)
            self.result['domain_name'].append(domain_name)

        return

    def run(self):

        MyLogger.get_instance().log("Getting labels...")
        #project = [{"$match": { "node_id": {"$lte": self._n_nodes}}}] if self._dgl else self._ranges
        add_project_into_pipeline(self._filter, self._project)
        labels_w_ids = []
        cursor = self._collection.aggregate(self._project, batchSize=10000)

        with ThreadPoolExecutor(max_workers=20) as executor:
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
