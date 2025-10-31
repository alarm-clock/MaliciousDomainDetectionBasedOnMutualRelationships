import array
import copy
import threading
import ijson
import json as jslib
from dataset_parsers.Graph import create_graph
from dataset_parsers.raw.Node import Node
from dataset_parsers.raw.IPEdge import IPEdge
from dataset_parsers.raw.ParallelDatasetWorker import ParallelDatasetWorker
from dataset_parsers.raw.ParallelEdgeConnectorWorker import ParallelEdgeConnectorWorker
from misc.Logger import MyLogger
import torch as th
import dgl
import pymongo
from misc.helper_func import add_project_into_pipeline, add_sort_into_pipeline


class DatasetJsonParser:

    def __init__(self, config: str = 'dataset_config.json'):

        self._chunk_size = 25000
        self.worker_limit = 10
        self.num_of_w = 0

        self.conf = config
        self.list_of_ips: dict[int,IPEdge] = {}
        self.list_of_nodes: list[Node] = []
        self.domains: list[tuple[int,str]] = []
        self._u = array.array('I')#th.tensor([])
        self._v = array.array('I')#th.tensor([])
        self._jacc = array.array('d')#th.tensor([])
        self._labels = []#th.tensor([])
        self._curr_node_id = 0
        self._curr_start_cnt = 0

        self.workers = []
        self._ip_lock = threading.Lock()
        self._nodes_lock = threading.Lock()
        self._domains_lock = threading.Lock()
        self._tensor_lock = threading.Lock()
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
        #self.max_w_semaphore.release()
        self._nodes_lock.release()

    def add_domains_conc(self, new_domains: list[tuple[int,str]]) -> None:
        self._domains_lock.acquire()
        self.domains.extend(new_domains)
        self._domains_lock.release()

    def add_tensor_conc(self, u: array.array, v: array.array, jacc: array.array, lab: list ) -> None:#u: th.Tensor, v: th.Tensor, jacc: th.Tensor, lab: th.Tensor) -> None:
        self._tensor_lock.acquire()
        self._u.extend(u) #= #th.cat((self._u,u)).to(th.long)
        self._v.extend(v) #= #th.cat((self._v,v)).to(th.long)
        self._jacc.extend(jacc) #= #th.cat((self._jacc,jacc)).to(th.double)
        self._labels.extend(lab) #= #th.cat((self._labels,lab)).to(th.int)
        self._tensor_lock.release()

    def _create_and_send_edge_workers(self, parallel: bool):
        print("Adding edges to graph")
        d = True
        for cnt in range(0, len(self.list_of_nodes), self._chunk_size):
            worker = ParallelEdgeConnectorWorker(self, self.list_of_nodes[cnt:cnt + self._chunk_size], d, parallel)
            d = False
            self.workers.append(worker)
            worker.start()

        self._wait_on_workers()

    def _add_edges(self, parallel: bool) -> dgl.DGLGraph | None:

        self._create_and_send_edge_workers(parallel)

        print("Graph complete, enjoy")
        num_of_nodes = len(self.list_of_nodes)

        self.list_of_nodes.clear()
        self.domains.clear()
        self.list_of_ips.clear()

        try:
            g = create_graph(th.Tensor(self._u).to(th.int),th.Tensor(self._v).to(th.int),th.Tensor(self._jacc).to(th.float),th.Tensor(self._labels).to(th.int),num_of_nodes)
        except Exception as e:
            print(e)
            g = None

        return g

    def _send_batch(self, batch: list, b: bool) -> None:

        #self.max_w_semaphore.acquire()

        #print(f'Sending batch to new worker, current start is: {self._curr_start_cnt}, size is: {len(batch)}')
        new_worker = ParallelDatasetWorker(self, self._curr_start_cnt, copy.deepcopy(batch), b)
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
            self.domains = sorted(self.domains, key=lambda domain: domain[0])

            print(f'Finished parsing {json_file_path}')

    def _parse_json_file_w_ranges(self,json_file_path: str, b: bool, ranges: list[tuple[int,int]]) -> None:

        with open(json_file_path, 'r') as file:
            print(f'Parsing {json_file_path}')
            items = ijson.items(file, 'item')
            batch = []

            cnt = 0
            range_counter = 0
            all_ranges_used = False
            for item in items:

                if all_ranges_used:
                    break

                if not all_ranges_used and cnt >= ranges[range_counter][0]:
                    batch.append(item)

                if len(batch) >= self._chunk_size:
                    self._send_batch(batch, b)
                    batch.clear()

                if not all_ranges_used and cnt >= ranges[range_counter][1]:
                    self._send_batch(batch, b)
                    batch.clear()

                    range_counter += 1
                    all_ranges_used = False if range_counter < len(ranges) else True

                cnt += 1

            if not all_ranges_used:
                self._send_batch(batch, b)
                batch.clear()

            self._wait_on_workers()
            self.list_of_nodes = sorted(self.list_of_nodes, key=lambda node: node.id)
            self.domains = sorted(self.domains, key=lambda domain: domain[0])


    def _parse_json_datasets(self,json_datasets: list[tuple[str,bool,list[tuple[int,int] | None]]]):

        for path, benign, ranges in json_datasets:

            if ranges is None:
                self._parse_json_file(path, benign)
            else:
                self._parse_json_file_w_ranges(path, benign, ranges)


    @staticmethod
    def _parse_config_ranges(ranges) -> list[tuple[int,int]] | None:

        if ranges is None or ranges == []:
            return None

        parsed_ranges = []
        for cnt in range(0,len(ranges),2):
            start = ranges[cnt]
            end = ranges[cnt + 1]

            if start > end:
                raise ValueError(f'Parsing ranges error: Start {start} is greater than end {end}')
            if end < 0 or start < 0:
                raise ValueError(f'Parsing ranges error: One of the numbers in ranges is negative')

            parsed_ranges.append((int(ranges[cnt]),int(ranges[cnt+1])))

        return parsed_ranges

    def _read_config(self) -> list[tuple[str,bool,list[tuple[int,int]] | None]]:

        datasets = []
        conf = []
        with open (self.conf, 'r') as config_file:
            conf = jslib.load(config_file)


        for record in conf:
            if record['use']:
                path = record['path']
                benign = record['benign']
                ranges = self._parse_config_ranges(record['ranges'])

                datasets.append((path,benign,ranges))

        return datasets

    def parse(self) -> tuple[dgl.DGLGraph | None, list[tuple[int,str]]]:

        dsets = self._read_config()
        self._parse_json_datasets(dsets)
        g = self._add_edges(False)

        return g, self.domains

    def _send_db_batch(self, batch: list) -> None:

        new_worker = ParallelDatasetWorker(self, int(batch[0]['node_id']), copy.deepcopy(batch), True, True)
        new_worker.start()
        self.workers.append(new_worker)


    def _parse_db(self, collection, ranges: list):

        add_project_into_pipeline({'_id': 0, 'domain_name': 1, 'dns.A': 1, 'ip_data': 1, 'node_id': 1 }, ranges)
        add_sort_into_pipeline({'node_id': pymongo.ASCENDING}, ranges)
        cursor = collection.aggregate(ranges, batchSize=25000 )

        batch = []
        cnt = 0
        for record in cursor:
            batch.append(record)

            if cnt >= self._chunk_size:
                self._send_db_batch(batch, True)
                batch.clear()
                cnt = 0

        if len(batch) > 0:
            self._send_db_batch(batch)

        cursor.close()
        self._wait_on_workers()
        self.list_of_nodes = sorted(self.list_of_nodes, key=lambda node: node.id)

    def _add_db_edges(self, dispatcher):

        self._create_and_send_edge_workers(True)
        MyLogger.get_instance().log("Finished creating ipv4 edges")
        self.list_of_nodes.clear()
        self.domains.clear()
        self.list_of_ips.clear()

        g = dgl.graph((th.tensor(self._u).to(th.int), th.tensor(self._v).to(th.int)))
        g.edata['weight'] = th.tensor(self._jacc).to(th.float)

        MyLogger.get_instance().log("Creating reverse ipv4 edges")
        g = dgl.add_reverse_edges(g, copy_ndata=True, copy_edata=True)
        MyLogger.get_instance().log("Finished creating reverse ipv4 edges")

        u_th, v_th = g.edges()

        jacc_th = g.edata['weight']
        u, v, jacc = list(u_th), list(v_th), list(jacc_th)

        dispatcher.submit_edges(u, v, 'ipv4', jacc)



    def parse_from_db(self, dispatcher, collection, ranges: list):

        MyLogger.get_instance().log("Started parsing ipv4 relations, starting workers...")
        self._parse_db(collection, ranges)
        MyLogger.get_instance().log("Started to create ipv4 edges, starting workers...")
        self._add_db_edges(dispatcher)

        #with open("out.txt", 'w') as f:

        #    for nd in self.list_of_nodes:
        #        print(f'nd {nd.id} - {nd.domain}\nNeighbors: ', file=f)
        #        for neighbor in nd.neighbors():
        #            print(f'{neighbor[0]} - j={neighbor[1]}', file=f)

        #        print('\n', file=f)



##            for line in config_file:
#                line = line.strip()

#                if line[0] == '#':
#                    continue

 #               splt = line.split()
#                is_bening = splt[1].strip() == 'b'
#                datasets.append((splt[0],is_bening))
#                print(f'{splt[0]} is {is_bening}')
