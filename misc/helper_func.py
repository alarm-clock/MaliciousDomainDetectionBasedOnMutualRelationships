import copy
import sys
from misc.Logger import MyLogger
from pymongo import MongoClient
import array
import json

def get_ips_from_record(doc) -> list[str]:
    ips = doc['dns']['A']
    ip_data_ip = doc['ip_data']
    if ip_data_ip is not None:
        ip_data_ip = ip_data_ip[0]['ip']

    if ips is None and ip_data_ip is not None:
        ips = [ip_data_ip]
    elif ip_data_ip is not None and ip_data_ip not in ips:
        ips.append(ip_data_ip)

    return ips

def add_project_into_pipeline( project_body: dict, pipeline: list):
    pipeline.append({"$project": project_body})

def add_sort_into_pipeline( sort_body: dict, pipeline: list):
    pipeline.append({"$sort": sort_body})

def parse_ranges(ranges: str | None) -> list[tuple[int, int]] | None:

    if ranges is None:
        return None

    split_ranges = ranges.split(',')

    if len(split_ranges) % 2 != 0:
        print("The ranges provided are not even", file=sys.stderr)
        MyLogger.get_instance().log("The ranges provided are not even")
        return None

    max = 0
    ranges: list[tuple[int, int]] = []
    for cnt in range(0, len(split_ranges), 2):
        start, end = split_ranges[cnt], split_ranges[cnt + 1]
        start_n, end_n = int(start), int(end)

        if start_n > end_n:
            errstr = f"Start index in ranges is greater the end index: {start_n} > {end_n}"
            MyLogger.get_instance().log(errstr)
            print(errstr,file=sys.stderr)
            raise ValueError
        if start_n < 0 or end_n < 0:
            errstr = f"Either starting index or ending index in ranges is negative: {start_n} or {end_n}"
            MyLogger.get_instance().log(errstr)
            print(errstr,file=sys.stderr)
            raise ValueError
        if start_n < max or end_n < max:
            errstr = f"Ranges must be in ascending order. Tuple ({start_n},{end_n}) is smaller then current max value: {max}"
            MyLogger.get_instance().log(errstr)
            print(errstr,file=sys.stderr)
            raise ValueError

        max = end_n
        ranges.append((start_n, end_n))

    return ranges

def create_reverse_edges(u: array.array, v: array.array, weight: array.array | None = None) -> None:

    tmp_v = copy.deepcopy(v)
    v.extend(u)
    u.extend(tmp_v)
    if weight is not None:
        weight.extend(weight)

    del tmp_v


def connect_to_db(client: str = 'localhost', port: int = 27017, db: str = "datasets", collection: str = "domains",
                   pwd: str = None, user: str = None):
    if pwd is not None and user is not None:
        client = MongoClient(f"mongodb://{user}:{pwd}@{client}:{port}/{db}")
    else:
        client = MongoClient(client, port)
    db = client[db]
    collection = db[collection]

    return collection

def connect_to_db_from_conf(config: str):
    with open(config) as f:
        conf = json.load(f)

        if conf.get('pwd'):
            return connect_to_db(conf["client"], conf["port"], conf["db"], conf["collection"], conf["pwd"],
                           conf["user"])
        else:
            return connect_to_db(conf["client"], conf["port"], conf["db"], conf["collection"])