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
BASE_TLDS = ["com", "cz", "sk", "at", "net", "org","us", "ru", "co", "uk", "hu", "de", "edu", "ro", "co.uk", "mil", "gov" ]

#used_domains = set()
all_domains = []
shared_ipv4_pool = []
shared_ipv6_pool = []

rng = random.Random()

def rand_label(min_len=1, max_len=10):
    letters = string.ascii_lowercase
    return "".join(rng.choice(letters) for _ in range(rng.randint(min_len, max_len)))


def random_ipv4():
    return str(ipaddress.IPv4Address(rng.getrandbits(32)))


def random_ipv6():
    return str(ipaddress.IPv6Address(rng.getrandbits(128)))


def generate_unique_domain():
    """Generate domain that is globally unique"""
    while True:

        # 60% chance to create subdomain of existing domain
        if all_domains and rng.random() < 0.6:
            parent = rng.choice(all_domains)
            domain = f"{rand_label()}.{parent}"

        else:
            depth = rng.randint(1, 4)
            labels = [rand_label() for _ in range(depth)]
            domain = ".".join(labels + [rng.choice(BASE_TLDS)])

        #if domain not in used_domains:
        #used_domains.add(domain)
        all_domains.append(domain)
        return domain


def generate_dns():
    dns = {}

    # Occasionally create a new shared IP group
    if rng.random() < 0.1:  # 10% chance
        group_size = rng.randint(1, 100)

        shared_ip4 = random_ipv4()
        shared_ip6 = random_ipv6()

        shared_ipv4_pool.extend([shared_ip4] * group_size)
        shared_ipv6_pool.extend([shared_ip6] * group_size)

    # A records
    n = rng.randint(0, 10)
    if n > 0:
        ips = set()

        for _ in range(n):
            if shared_ipv4_pool and rng.random() < 0.5:
                ips.add(rng.choice(shared_ipv4_pool))
            else:
                ips.add(random_ipv4())

        dns["A"] = list(ips)

    # AAAA records
    n = rng.randint(0, 10)
    if n > 0:
        ips = set()

        for _ in range(n):
            if shared_ipv6_pool and rng.random() < 0.5:
                ips.add(rng.choice(shared_ipv6_pool))
            else:
                ips.add(random_ipv6())

        dns["AAAA"] = list(ips)

    return dns


def generate_domain_record():
    domain = generate_unique_domain()

    dns = generate_dns()

    # Optional CNAME
    if rng.random() < 0.4 and all_domains:
        target = rng.choice(all_domains)
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

def send(req_body: dict[str, Any], pbar, pbar_add: int, url) -> None:
    response = requests.post(url, json=req_body)
    print(response)
    pbar.update(pbar_add)

def gen_send(N: int, size: int, interval: int, url, time) -> None:

    pbar = tqdm(total=N)
    for cnt in range(N):
        req_size = random.randint(size - interval, size + interval)
        request_body = generate_json(req_size)

        send(request_body,pbar,1,url)
        t.sleep(time)

def load_send(url: str, file: str, size: int, interval: int, time) -> None:

    with open(file, "r") as f:
        data = json.load(f)

    n_domains = len(data["domains"])
    domains = data["domains"]
    pbar = tqdm(total=n_domains)

    cnt = 0
    while cnt < n_domains:
        req_size = random.randint(size - interval, size + interval)
        next_cnt = cnt + req_size
        domains_for_send = domains[cnt:next_cnt]
        send({"domains": domains_for_send},pbar,req_size,url)
        t.sleep(time)
        cnt = next_cnt


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-m',type=str, default="send", choices=["send","save","load","load-and-generate"],help="Program mode")
    parser.add_argument('-f',type=str, default="domains.json", help="File name")
    parser.add_argument("-n", type=int, help="Number of requests to generate", default=1)
    parser.add_argument("-s", type=int, help="Number of domains to generate in one request", default=1000)
    parser.add_argument("-i", type=int, help="+- size interval around 'size' from which size will be randomly chosen", default=0)
    parser.add_argument("-t",type=float, help="Time between requests in seconds",default=5.00)
    parser.add_argument('-rs',type=int, help="RNG seed", default=42)
    parser.add_argument("-a",type=str, help="Host name",default="localhost")
    parser.add_argument("-p",type=int, help="Port number",default=8000)
    args = parser.parse_args()

    N = args.n
    size = args.s
    interval = args.i
    time = args.t
    host = args.a
    port = args.p
    file = args.f
    mode = args.m
    seed = args.rs

    global rng
    rng = random.Random(seed)

    url = f"http://{host}:{port}/update"

    if mode == "save":
        dset = generate_json(size)

        with open(file, "w") as f:
            json.dump(dset, f)

        return

    if mode == 'send':
        gen_send(N,size,interval,url,time)

    if mode == 'load':
        load_send(url, file, size, interval, time)

    if mode == 'load-and-generate':
        load_send(url, file, size, interval, time)
        gen_send(N, size, interval, url, time)

    return

if __name__ == '__main__':
    main()
