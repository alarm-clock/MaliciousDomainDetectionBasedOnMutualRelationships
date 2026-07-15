from pymongo import MongoClient
from neo4j import GraphDatabase, Driver
from neo4j.exceptions import AuthError, ServiceUnavailable
import sys
import array
from misc.Logger import MyLogger
import copy
import json
from typing import Any
import hashlib

def get_ips_from_record(doc) -> list[str]:
    ips = doc['dns']['A']
    ip_data_ip = None

    if doc.get('ip_data'):
        ip_data_ip = doc['ip_data']
        if ip_data_ip is not None:
            ip_data_ip = ip_data_ip[0]['ip']

    if ips is None and ip_data_ip is not None:
        ips = [ip_data_ip]
    elif ip_data_ip is not None and ip_data_ip not in ips:
        ips.append(ip_data_ip)

    return ips

def get_registrant_from_record(domain: dict[str, Any]) -> str | None:
    registrant = domain.get('rdap', {}).get('entities', {}).get('registrant', None)

    if registrant is None:
        registrant = domain.get('registrant', None)

    return registrant

_auth_key_Id = 'authorityKeyIdentifier'
_subj_key_Id = 'subjectKeyIdentifier'
_basic_const = 'basicConstraints'
__not_ca = 'CA:FALSE'

def parse_extensions(extensions: list[dict[str, Any]]) -> tuple[str, str, bool]:

    auth_Id = ''
    subj_Id = ''
    ca = False

    for extension in extensions:
        name = extension['name']
        val = extension['value']

        if name == _auth_key_Id: auth_Id = val
        elif name == _subj_key_Id: subj_Id = val
        elif name == _basic_const: ca = val != __not_ca

    return auth_Id, subj_Id, ca
def generate_certificate_hash(cn: str, org: str, subj_key_id: str, start: float, end: float) -> str:
    return hashlib.sha256(f"{cn}|{org}|{subj_key_id}|{start}|{end}".encode()).hexdigest()

def parse_cert(tls_data: dict[str, Any]) -> tuple[str, bool, tuple[str, str, str, float, float]]:

    entity_cert_data = tls_data['certificates'][0]
    cn = entity_cert_data['common_name']
    org = entity_cert_data['organization']
    start = entity_cert_data['validity_start']
    end = entity_cert_data['validity_end']
    auth_id, subj_id, ca = parse_extensions(entity_cert_data['extensions'])
    cert_hash = generate_certificate_hash(auth_id, subj_id, subj_id, start, end)

    return cert_hash, ca, (cn, org, subj_id, start, end)

def tls_data_in_presence(domain: dict[str, Any]) -> bool:
    return domain.get('tls') is not None

def add_project_into_pipeline(project_body: dict, pipeline: list):
    pipeline.append({"$project": project_body})


def add_sort_into_pipeline(sort_body: dict, pipeline: list):
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

        if end == "inf":
            start_n, end_n = int(start), 2 ** 32  # there never will be so many domains
        else:
            start_n, end_n = int(start), int(end)

        if start_n > end_n:
            errstr = f"Start index in ranges is greater the end index: {start_n} > {end_n}"
            MyLogger.get_instance().log(errstr)
            print(errstr, file=sys.stderr)
            raise ValueError
        if start_n < 0 or end_n < 0:
            errstr = f"Either starting index or ending index in ranges is negative: {start_n} or {end_n}"
            MyLogger.get_instance().log(errstr)
            print(errstr, file=sys.stderr)
            raise ValueError
        if start_n < max or end_n < max:
            errstr = f"Ranges must be in ascending order. Tuple ({start_n},{end_n}) is smaller then current max value: {max}"
            MyLogger.get_instance().log(errstr)
            print(errstr, file=sys.stderr)
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

def get_neo4j_driver(config: str) -> Driver | None:

    host = ''
    user = ''
    port = 0
    pwd = ''

    with open(config, mode='r') as f:
        conf = json.load(f)
        host = conf['host']
        user = conf['user']
        port = conf['port']
        pwd = conf['pwd']

    MyLogger.get_instance().log(f"Trying to connect to Neo4j db at {host}:{port} with user {user}...")
    try:
        driver = GraphDatabase.driver(f'{host}:{port}', auth=(user, pwd))
    except ServiceUnavailable as err:
        MyLogger.get_instance().log(f"Could not connect to Neo4j with error: {err}")
        print(err, file=sys.stderr)
        return None

    try:
        driver.verify_connectivity()
    except AuthError as err:
        MyLogger.get_instance().log(f"Authentication failed when connecting to Neo4j: {err}")
        print(err, file=sys.stderr)
        return None

    MyLogger.get_instance().log("Connected to Neo4j database")
    return driver

def intersection(set1: list, set2: list) -> list:
    return [item for item in set1 if item in set2]

def calc_jaccard(set1: list, set2: list) -> float:
    int_len = len(intersection(set1, set2))
    return int_len / (len(set1) + len(set2) - int_len)


def get_domains_parent_domains(domain: str) -> list[str]:
    domain_name = str(domain)
    parts = domain_name.split(".")[1:]  # no domain itself
    suffixes = []
    for cnt in range(len(parts) - 1):  # no tld
        suffixes.append('.'.join(parts[cnt:]))

    return suffixes

def reverse_domain(domain: str) -> str:
    return '.'.join(reversed(domain.strip().rstrip('.').split('.')))

def domain_depth(domain: str) -> int:
    return domain.count('.')