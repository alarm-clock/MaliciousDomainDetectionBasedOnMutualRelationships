import threading
from dataset_parsers.raw.DatasetJsonParser import DatasetJsonParser

class IPV4ParallelAPI(threading.Thread):

    def __init__(self, dispatcher, collection):
        super().__init__()

        self.dispatcher = dispatcher
        self.collection = collection

    def run(self):

        parser = DatasetJsonParser()
        parser.parse_from_db(self.dispatcher, self.collection)

