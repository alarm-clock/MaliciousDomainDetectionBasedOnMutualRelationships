from typing import Any
import requests
import json
import random
import string
import ipaddress
import argparse
import time as t
from tqdm import tqdm

SIZES = [10, 50, 100, 250, 500, 750, 1000, 2000, 5000, 10000]
BASE_TLDS = ["com", "cz", "sk", "at", "net", "org","us", "ru", "co", "uk", "hu", "de", "edu" ]

#used_domains = set()
all_domains = []


def rand_label(min_len=1, max_len=10):
    letters = string.ascii_lowercase
    return "".join(random.choice(letters) for _ in range(random.randint(min_len, max_len)))


def random_ipv4():
    return str(ipaddress.IPv4Address(random.getrandbits(32)))


def random_ipv6():
    return str(ipaddress.IPv6Address(random.getrandbits(128)))


def generate_unique_domain():
    """Generate domain that is globally unique"""
    while True:

        # 60% chance to create subdomain of existing domain
        if all_domains and random.random() < 0.6:
            parent = random.choice(all_domains)
            domain = f"{rand_label()}.{parent}"

        else:
            depth = random.randint(1, 4)
            labels = [rand_label() for _ in range(depth)]
            domain = ".".join(labels + [random.choice(BASE_TLDS)])

        #if domain not in used_domains:
        #used_domains.add(domain)
        all_domains.append(domain)
        return domain


def generate_dns():
    dns = {}

    # A records
    n = random.randint(0, 10)
    if n > 0:
        dns["A"] = list({random_ipv4() for _ in range(n)})

    # AAAA records
    n = random.randint(0, 10)
    if n > 0:
        dns["AAAA"] = list({random_ipv6() for _ in range(n)})

    return dns


def generate_domain_record():
    domain = generate_unique_domain()

    dns = generate_dns()

    # Optional CNAME
    if random.random() < 0.4 and all_domains:
        target = random.choice(all_domains)
        if target != domain:
            dns["CNAME"] = target

    return {
        "domain_name": domain,
        "label": "benign",
        "other_data": rand_label(20, 40),
        "dns": dns
    }


def generate_dataset(size):
    for _ in range(size):
        yield generate_domain_record()


def generate_json(size: int) -> dict[str, Any]:

    domains = []

    for record in generate_dataset(size):
        domains.append(record)

    return {"domains": domains}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-n", type=int, help="Number of requests to generate", default=1)
    parser.add_argument("-s", type=int, help="Number of domains to generate in one request", default=10)
    parser.add_argument("-i", type=int, help="+- size interval around 'size' from which size will be randomly chosen", default=0)
    parser.add_argument("-t",type=float, help="Time between requests in seconds",default=5.00)
    parser.add_argument("-a",type=str, help="Host name",default="localhost")
    parser.add_argument("-p",type=int, help="Port number",default=8000)
    args = parser.parse_args()

    N = args.n
    size = args.s
    interval = args.i
    time = args.t
    host = args.a
    port = args.p

    url = f"http://{host}:{port}/update"
    pbar = tqdm(total=N)

    for cnt in range(N):
        req_size = random.randint(size - interval, size + interval)
        request_body = generate_json(req_size)

        response = requests.post(url, json=request_body)
        print(response)
        pbar.update(1)
        t.sleep(time)

    return

if __name__ == '__main__':
    main()
