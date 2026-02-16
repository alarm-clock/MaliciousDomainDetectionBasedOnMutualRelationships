import threading
from old.dataset_parsers.raw.DatasetJsonParser import DatasetJsonParser

class IPV4ParallelAPI(threading.Thread):

    def __init__(self, dispatcher, collection, ranges: list):
        super().__init__()

        self.dispatcher = dispatcher
        self.collection = collection
        self.ranges = ranges

    def run(self):

        parser = DatasetJsonParser()
        parser.parse_from_db(self.dispatcher, self.collection, ranges=self.ranges)

