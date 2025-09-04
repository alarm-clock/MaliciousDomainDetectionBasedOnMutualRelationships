import copy
import threading
import ijson
from Node import Node
from IPEdge import IPEdge
from ParallelDatasetWorker import ParallelDatasetWorker
from ParallelEdgeConnectorWorker import ParallelEdgeConnectorWorker
import time

class DatasetJsonParser:

    def __init__(self, config: str = 'dataset_config.txt'):

        self._chunk_size = 25000
        self.worker_limit = 10
        self.num_of_w = 0

        self.conf = config
        self.list_of_ips: dict[int,IPEdge] = {}
        self.list_of_nodes: list[Node] = []
        self._curr_node_id = 0
        self._curr_start_cnt = 0

        self.workers = []
        self._ip_lock = threading.Lock()
        self._nodes_lock = threading.Lock()
        self.max_w_semaphore = threading.Semaphore(value=self.worker_limit)
        self.___debug_lock = threading.Lock()

    #def debug_fun____(self, t, start_id) -> None:
    #    end = time.perf_counter()
    #    self.___debug_lock.acquire()
    #    print(f'[{start_id}] finished with time {end-t}')
    #    self.___debug_lock.release()

    def add_ips_conc(self, new_ips: dict[int,IPEdge]) -> None:
        self._ip_lock.acquire()

        for ip in new_ips.values():
            if ip.ip not in self.list_of_ips:
                self.list_of_ips[ip.ip] = ip
            else:
                self.list_of_ips[ip.ip].add_domains(ip.get_domains())

        self._ip_lock.release()

    def add_nodes_conc(self, new_nodes: list[Node]) -> None:
        self._nodes_lock.acquire()
        self.list_of_nodes.extend(new_nodes)
        self.max_w_semaphore.release()
        self._nodes_lock.release()

    def _add_edges(self) -> None:

        print("Adding edges to graph")
        for cnt in range(0, len(self.list_of_nodes), self._chunk_size):
            worker = ParallelEdgeConnectorWorker(self,self.list_of_nodes[cnt:cnt+self._chunk_size])
            self.workers.append(worker)
            worker.start()

        self._wait_on_workers()

        print("Graph complete, enjoy")

    def _send_batch(self, batch: list, b: bool) -> None:

        self.max_w_semaphore.acquire()

        print(f'Sending batch to new worker, current start is: {self._curr_start_cnt}, size is: {len(batch)}')
        new_worker = ParallelDatasetWorker(self, self._curr_start_cnt, copy.deepcopy(batch), self._chunk_size,b)
        self.workers.append(new_worker)
        new_worker.start()
        self._curr_start_cnt += len(batch)

    def _wait_on_workers(self) -> None:
        for worker in self.workers:
            worker.join()

    def _parse_json_file(self,json_file_path, b) -> None:
        with open(json_file_path, 'r') as file:

            print(f'Parsing {json_file_path}')
            items = ijson.items(file, 'item')
            batch = []

            cnt = 0
            for item in items:
                batch.append(item)
                cnt += 1

                if cnt == self._chunk_size:
                    self._send_batch(batch, b)
                    batch.clear()
                    cnt = 0

            if len(batch) > 0:
                self._send_batch(batch, b)

            self._wait_on_workers()
            self.list_of_nodes = sorted(self.list_of_nodes, key=lambda node: node.id)

            cnt = 0
            for kokot in self.list_of_nodes:
                print(f'{kokot.id} -> {cnt},')
                cnt += 1

            print(f'Finished parsing {json_file_path}')

    def _parse_json_datasets(self,json_datasets):

        for path, benign in json_datasets:
            self._parse_json_file(path, benign)



    def _read_config(self) -> list[tuple]:

        datasets = []
        with open (self.conf, 'r') as config_file:
            for line in config_file:
                line = line.strip()

                if line[0] == '#':
                    continue

                splt = line.split(' ')
                is_bening = splt[1].strip() == 'b'
                datasets.append((splt[0],is_bening))
                print(f'{splt[0]} is {is_bening}')

        return datasets

    def parse(self):
        dsets = self._read_config()
        self._parse_json_datasets(dsets)
        self._add_edges()

        with open("out.txt", 'w') as f:

            for nd in self.list_of_nodes:
                print(f'nd {nd.id} - {nd.domain}\nNeighbors: ', file=f)
                for neighbor in nd.neighbors():
                    print(f'{neighbor[0]} - j={neighbor[1]}', file=f)

                print('\n', file=f)
