"""
File: graph_repository/dataset_creator/dataset_edge_workers/CertificateWorker.py
System module: graph_repository
Author: Jozef Michal Bukas
Email: xbukas00@stud.fit.vutbr.cz
Date: 15.7.2026
Description: Class used for parallel creation of Certificate edges from dataset
"""
from graph_repository.workers.common.DatasetWorker import DatasetWorker
from graph_repository.graph_repo_misc import parse_cert
from misc.Logger import MyLogger
from graph_repository.workers.common.GraphTypes import NodeTypes, EdgeTypes, NODE_ID, CERT_CN, CERT_ORG, CERT_SUBJ_K_ID, CERT_BEFORE, CERT_AFTER, CERT_HASH
from pymongo.collection import Collection


class CertificateWorker(DatasetWorker):
    worker_name = 'certificate'
    available_options = [
        (worker_name,worker_name,None),
        (worker_name, f'{worker_name}_all',None)
    ]

    _project = {'_id': 0, 'node_id': 1, "domain_name": 1, 'tls': 1}

    def __init__(self, submit_callback_method, collection: Collection, ranges: list) -> None:
        super().__init__(submit_callback_method, collection, ranges, self._project, [NodeTypes.CERTIFICATE])
        self._certs: dict[str, int] = {}
        self._cert_id_cnt = 0

    def _submit_results(self) -> None:
        self._submit_callback_method(
            self._u,
            self._v,
            NodeTypes.CERTIFICATE,
            EdgeTypes.HAS_CERTIFICATE,
            NodeTypes.DOMAIN,
            u_data=self._n_data[NodeTypes.CERTIFICATE]
        )
        self._submit_callback_method(
            self._v,
            self._u,
            NodeTypes.DOMAIN,
            EdgeTypes.HAS_CERTIFICATE,
            NodeTypes.CERTIFICATE,
        )

    def _store_cert_data(self, data: tuple[str, str, str, float, float], cert_hash: str) -> int:

        if cert_hash in self._certs:
            return self._certs[cert_hash]

        cert_id = self._cert_id_cnt
        self._cert_id_cnt += 1

        cn, org, subj_id, start, end = data
        self._n_data.store_n_data(NodeTypes.CERTIFICATE, {
            NODE_ID: cert_id,
            CERT_CN: cn,
            CERT_ORG: org,
            CERT_SUBJ_K_ID: subj_id,
            CERT_BEFORE: start,
            CERT_AFTER: end,
            CERT_HASH: cert_hash
        })

        self._certs[cert_hash] = cert_id
        return cert_id


    def _find_entries_and_create_edges(self) -> None:

        cursor = self._collection.aggregate(self._pipeline, batchSize=25000)

        for doc in cursor:

            if doc['tls'] is None:
                continue

            domain_id = doc['node_id']
            cert_hash, ca, data = parse_cert(doc)
            cert_id = self._store_cert_data(data, cert_hash)
            self._u.append(cert_id)
            self._v.append(domain_id)

        del self._certs

    def _compute(self) -> None:
        self._find_entries_and_create_edges()
        self._submit_results()