import ipaddress
import json
import ijson
from Node import Node
from IPEdge import IPEdge

# chcem nacitat dataset na viacerych vlaknach
# povedze ze na 20, tim padom potrebujem rozdelit pracu medzi n vlakien: pocet json entries / n
# vlakno bude mat svoje ID ako int od 0 do n-1
# vlakno bude pracovat na zaznamoch od n* pocet zaznamov na jedno vlakno do (n+1) * pzjv - 1
# domenovy zaznam dostane ID podla svojho poradia v datasete
# problem je ze domeny od roznych workerov sa mozu prekladat na stejnu adresu
# tim padom sa IPecky musia ukladat do osobytnej hash tabulky
# na konci ked worker dopracuje tak sa vojde do krytickej sekcie kde si bude porovnavat svoje IPcky
# s uz ulozenymi IPckami, ak najde tak updatne existujucu inak prida ako novu
# takto sa skonci cast nacitania vstupu
# nasledne sa vytvoria novy workery ktory si znova rovnako rozdelia Domeny (uzly grafu)
# kazdy uzol si najde v hash tabulke svoje IPcky a ulozi si svojich susedov


class DatasetJsonParser:

    def __init__(self, config: str = 'dataset_config.txt'):
        self.conf = config
        self.list_of_ips: list[IPEdge] = []
        self.list_of_nodes: list[Node] = []
        self._curr_node_id = 0
        self._curr_ip_id = 0

    def _get_ip(self, ip: int) -> IPEdge | None:
        for item in self.list_of_ips:
            if item.ip == ip:
                return item

        return None

    def _add_ips_to_list(self, ips: list[int], domain: int) -> list[int]:

        ip_ids: list[int] = []

        for ip in ips:
            edge = self._get_ip(ip)

            if edge is None:
                new = IPEdge(self._curr_ip_id, ip)
                new.add_domain(domain)
                self.list_of_ips.append(new)

                ip_ids.append(self._curr_ip_id)
                self._curr_ip_id += 1
            else:
                edge.add_domain(domain)
                ip_ids.append(edge.id)

        return ip_ids

    def _add_edges(self) -> None:
        for nd in self.list_of_nodes:
            for ip in nd.ip:
                ip_edge = self.list_of_ips[ip]
                nd.add_neighbours(ip_edge.domains)
                print(f'Domain: {nd.domain}\n   Domain ID: {nd.id}\n   Neighbours: {ip_edge.domains}\n   IPS:{nd.ip}')



    def _parse_json_file(self,json_file_path, b):
        with open(json_file_path, 'r') as file:

            print(f'Parsing {json_file_path}')
            items = ijson.items(file, 'item')

            for item in items:

                ips: list[int] = []
                ip_strs: list[str] = item['dns']['A']

                if ip_strs is not None:
                    for ip_str in ip_strs:
                        ips.append(int(ipaddress.ip_address(ip_str)))

                ip_ids = self._add_ips_to_list(ips, self._curr_node_id)

                domain = item['domain_name']
                nd = Node(self._curr_node_id, domain, ip_ids, b,[])
                self.list_of_nodes.append(nd)

                self._curr_node_id += 1

    def _parse_json_datasets(self,json_datasets):

        for path, benign in json_datasets:
            self._parse_json_file(path, benign)


    def _read_config(self) -> list[tuple]:

        datasets = []
        with open (self.conf, 'r') as config_file:
            for line in config_file:
                line = line.strip()
                splt = line.split(' ')
                is_bening = splt[1].strip() == 'b'
                datasets.append((splt[0],is_bening))
                print(f'{splt[0]} is {is_bening}')

        return datasets

    def parse(self):
        dsets = self._read_config()
        self._parse_json_datasets(dsets)
        self._add_edges()

def main():
    json_dataset = DatasetJsonParser()
    json_dataset.parse()

main()