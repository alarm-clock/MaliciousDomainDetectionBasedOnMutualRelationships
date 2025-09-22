import threading
import pymongo
from dataset_parsers.raw.ParallelEdgeConnectorWorker import calc_jaccard_f_l
from misc.helper_func import get_ips_from_record



class ParallelDBParser(threading.Thread):

    def __init__(self, dispatcher, start: int, size: int, coll: pymongo.collection.Collection):
        super().__init__()
        self._start = start
        self._end = start + size
        self._coll = coll
        self._dispatcher = dispatcher


    def run(self):

        u, v, jacc, label = [], [], [], []

        for node_id in range(self._start, self._end):
            doc = self._coll.find_one({"node_id": node_id})

            ips = get_ips_from_record(doc)

            if ips is not None and len(ips) > 0:
                cursor = self._coll.find({"dns.A" : {"$in" : ips}})

                cnt2 = 0
                for res in cursor:
                    cnt2 += 1
                    v.append(int(res["node_id"]))
                    jacc.append(calc_jaccard_f_l(ips,get_ips_from_record(res)))

                u.extend([node_id] * cnt2)

            doc_label: str = doc["label"]
            label.append(int(doc_label.find("benign") != -1))

            self._dispatcher.store_results(u, v, jacc, label)

