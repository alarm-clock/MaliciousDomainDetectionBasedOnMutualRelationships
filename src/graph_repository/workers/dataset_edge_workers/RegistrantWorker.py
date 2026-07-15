"""
Author: Jozef Michal Bukas <jozefmbukas@gmail.com>
"""
from graph_repository.workers.common.DatasetWorker import DatasetWorker
from misc.Logger import MyLogger
from graph_repository.workers.common.GraphTypes import NodeTypes, EdgeTypes, REG_NAME, NODE_ID
from pymongo.collection import Collection


class RegistrantWorker(DatasetWorker):

    worker_name = 'registrant'
    available_options = [
        (worker_name,worker_name,None),
        (worker_name, f'{worker_name}_all',None)
    ]

    _project = {'_id': 0, 'rdap.entities.registrant': 1, 'node_id': 1}
    _reg_name_str = 'name'
    _reg_id_str = 'reg_id'

    def __init__(self, submit_callback_method, collection: Collection, ranges: list):
        super().__init__(submit_callback_method, collection, ranges, self._project, [NodeTypes.REGISTRANT])
        self._registrant_data: dict[str, list] = {self._reg_name_str: [], self._reg_id_str: []}
        self._reg_id_dict: dict[str, int] = {}
        self._reg_id_cnt = 0

    def _store_results(self) -> None:

        self._submit_callback_method(
            self._u, self._v, NodeTypes.DOMAIN, EdgeTypes.REGISTERED, NodeTypes.REGISTRANT,
            None, None, self._n_data.get_n_data(NodeTypes.REGISTRANT)
        )
        self._submit_callback_method(
            self._v, self._u, NodeTypes.REGISTRANT, EdgeTypes.REGISTERED, NodeTypes.DOMAIN,
            None, None, None
        )

    def _store_registrant(self, registrant: str) -> int:

        registrant_id = self._reg_id_dict.get(registrant)
        if registrant_id is None:
            registrant_id = self._reg_id_cnt
            self._reg_id_cnt += 1

            self._reg_id_dict[registrant] = registrant_id
            self._n_data.store_n_data(NodeTypes.REGISTRANT, {REG_NAME: registrant, NODE_ID: registrant_id})

        return registrant_id

    def _find_entries(self) -> None:

        cursor = self._collection.aggregate(self._pipeline, batchSize=25000)

        for doc in cursor:
            domain_id = int(doc['node_id'])
            registrant = str(doc['rdap.entities.registrant'])
            registrant_id = self._store_registrant(registrant)
            self._u.append(domain_id)
            self._v.append(registrant_id)

    def _compute(self):
        self._find_entries()
        self._store_results()