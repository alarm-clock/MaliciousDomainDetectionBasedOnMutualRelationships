import copy
import csv
import os
import threading
import time
from typing import Any
import requests
import json
import random
import string
import ipaddress
import argparse
import time as t
from tqdm import tqdm
from domain_evaluation.Evaluate import evaluate_domain_metapath2vec
from domain_evaluation.EvaluationObjects import EvaluationJob
from graph_repository.Neo4jDBDriver import Neo4jDBDriver, COPY_ON_WRITE_TIMES
from graph_repository.graph_main.graph_editing.EditConsumer import _handle_request
from graph_repository.graph_main.graph_editing.common.RequestPriority import RequestPriority
from graph_repository.graph_main.graph_editing.requests.EditRequest import EditRequest

SIZES = [10, 50, 100, 250, 500, 750, 1000, 2000, 5000, 10000]
BASE_TLDS = ["com", "cz", "sk", "at", "net", "org","us", "ru", "co", "uk", "hu", "de", "edu", "ro", "co.uk", "mil", "gov" ]

#used_domains = set()
all_domains = []
shared_ipv4_pool = []
shared_ipv6_pool = []

rng = random.Random(42)

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
    if rng.random() < 0.5:  # 10% chance
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
        "label": "benign" if rng.random() < 0.5 else "malicious",
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


from pathlib import Path

import matplotlib.pyplot as plt


def visualize_test_results(
        req_times: list[float],
        node_cnts: list[int],
        edge_cnts: list[int],
        eval_times: list[float],
        eval_mod: int,
        out_dir: str = "figures",
) -> None:
    """
    Creates visualization figures for:

    Request times:
    - vs node counts
    - vs edge counts
    - vs total graph size (nodes + edges)

    Evaluation times:
    - vs node counts
    - vs edge counts
    - vs total graph size

    Combined plots:
    - request + evaluation vs node counts
    - request + evaluation vs edge counts
    - request + evaluation vs total graph size
    """

    # ---------------------------------------------------------
    # Validation
    # ---------------------------------------------------------

    if not (
            len(req_times)
            == len(node_cnts)
            == len(edge_cnts)
    ):
        raise ValueError(
            "req_times, node_cnts and edge_cnts "
            "must have same length"
        )

    if eval_mod <= 0:
        raise ValueError("eval_mod must be > 0")

    edge_cnts = [e//2 for e in edge_cnts]
    eval_n_cnts = node_cnts #[::eval_mod]
    eval_e_cnts = edge_cnts #[::eval_mod]

    expected_eval_len = len(eval_n_cnts)

    if len(eval_times) != expected_eval_len:
        raise ValueError(
            f"eval_times length ({len(eval_times)}) "
            f"does not match expected length "
            f"({expected_eval_len}) "
            f"for eval_mod={eval_mod}"
        )

    # ---------------------------------------------------------
    # Prepare output directory
    # ---------------------------------------------------------

    output_path = Path(out_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # ---------------------------------------------------------
    # Derived metrics
    # ---------------------------------------------------------

    total_sizes = [
        n + e
        for n, e in zip(node_cnts, edge_cnts)
    ]

    eval_total_sizes = [
        n + e
        for n, e in zip(eval_n_cnts, eval_e_cnts)
    ]

    # ---------------------------------------------------------
    # Plot helpers
    # ---------------------------------------------------------

    def save_single_plot(
            x_data,
            y_data,
            xlabel: str,
            ylabel: str,
            title: str,
            filename: str,
    ) -> None:

        # Filter out Y values > 50
        filtered = [
            (x, y)
            for x, y in zip(x_data, y_data)
            if y <= 50
        ]

        filtered = filtered[::20]

        if not filtered:
            return

        filtered_x, filtered_y = zip(*filtered)

        plt.figure(figsize=(10, 6))

        plt.plot(
            filtered_x,
            filtered_y,
            marker="o",
        )

        plt.xlabel(xlabel)
        plt.ylabel(ylabel)
        plt.title(title)

        plt.grid(True)

        plt.tight_layout()

        plt.savefig(output_path / filename)

        plt.close()

    def save_combined_plot(
            x1_data,
            y1_data,
            x2_data,
            y2_data,
            xlabel: str,
            title: str,
            filename: str,
    ) -> None:

        # Filter request data
        filtered_req = [
            (x, y)
            for x, y in zip(x1_data, y1_data)
            if y <= 50
        ][::20]

        # Filter evaluation data
        filtered_eval = [
            (x, y)
            for x, y in zip(x2_data, y2_data)
            if y <= 50
        ][::20]

        plt.figure(figsize=(10, 6))

        if filtered_req:
            req_x, req_y = zip(*filtered_req)

            plt.plot(
                req_x,
                req_y,
                marker="o",
                label="Request Time",
            )

        if filtered_eval:
            eval_x, eval_y = zip(*filtered_eval)

            plt.plot(
                eval_x,
                eval_y,
                marker="o",
                label="Evaluation Time",
            )

        plt.xlabel(xlabel)
        plt.ylabel("Time (s)")
        plt.title(title)

        plt.legend()
        plt.grid(True)

        plt.tight_layout()

        plt.savefig(output_path / filename)

        plt.close()

    # ---------------------------------------------------------
    # Request time plots
    # ---------------------------------------------------------

    save_single_plot(
        node_cnts,
        req_times,
        "Node Count",
        "Request Time (s)",
        "Request Time vs Node Count",
        "req_vs_nodes.png",
    )

    save_single_plot(
        edge_cnts,
        req_times,
        "Edge Count",
        "Request Time (s)",
        "Request Time vs Edge Count",
        "req_vs_edges.png",
    )

    save_single_plot(
        total_sizes,
        req_times,
        "Nodes + Edges",
        "Request Time (s)",
        "Request Time vs Total Graph Size",
        "req_vs_total.png",
    )

    # ---------------------------------------------------------
    # Evaluation time plots
    # ---------------------------------------------------------

    save_single_plot(
        eval_n_cnts,
        eval_times,
        "Node Count",
        "Evaluation Time (s)",
        "Evaluation Time vs Node Count",
        "eval_vs_nodes.png",
    )

    save_single_plot(
        eval_e_cnts,
        eval_times,
        "Edge Count",
        "Evaluation Time (s)",
        "Evaluation Time vs Edge Count",
        "eval_vs_edges.png",
    )

    save_single_plot(
        eval_total_sizes,
        eval_times,
        "Nodes + Edges",
        "Evaluation Time (s)",
        "Evaluation Time vs Total Graph Size",
        "eval_vs_total.png",
    )

    # ---------------------------------------------------------
    # Combined plots
    # ---------------------------------------------------------

    save_combined_plot(
        node_cnts,
        req_times,
        eval_n_cnts,
        eval_times,
        "Node Count",
        "Request vs Evaluation Time (Nodes)",
        "combined_nodes.png",
    )

    save_combined_plot(
        edge_cnts,
        req_times,
        eval_e_cnts,
        eval_times,
        "Edge Count",
        "Request vs Evaluation Time (Edges)",
        "combined_edges.png",
    )

    save_combined_plot(
        total_sizes,
        req_times,
        eval_total_sizes,
        eval_times,
        "Nodes + Edges",
        "Request vs Evaluation Time (Total Graph Size)",
        "combined_total.png",
    )

    print(
        f"Saved all figures to: "
        f"{output_path.resolve()}"
    )

def parse_csv(file_path: str):
    req_times: list[float] = []
    node_cnts: list[int] = []
    edge_cnts: list[int] = []
    eval_times: list[float] = []

    with open(file_path, "r") as f:
        reader = csv.reader(f)
        reader.__next__()
        for row in reader:
            req_times.append(float(row[0]))
            node_cnts.append(int(row[1]))
            edge_cnts.append(int(row[2]))
            eval_times.append(float(row[3]))

    visualize_test_results(req_times, node_cnts, edge_cnts, eval_times, 9)

def direct_test(neo4j_conf: str, stable: str) -> None:
    stop_event = threading.Event()
    gpu_sem = threading.Semaphore(16)

    N = 5000
    n = 1000
    eval_mod = 10

    req_times = []
    node_cnts = []
    edge_cnts = []
    eval_times = []

    with open(stable, "r") as f:
        data = json.load(f)

    domains = data["domains"]
    req = EditRequest(domains,RequestPriority.CRITICAL,-1)
    req._first_filter = False
    _handle_request(req,stop_event,neo4j_conf)

    domain ={
        "domain_name": "test.domain.for.eval.test",
        "dns":{
            "A": ["84.21.198.54","49.212.238.9"],
            "CNAME": "ywoih.qwhebv.riz.xrbxkbbspq.x.test"
        }
    }

    with open("res_times2.csv", "w") as f:
        writer = csv.writer(f)
        writer.writerow(["iteration","req_time","n_cnt","e_cnt","eval_time"])
        for cnt in range(N):
            generated_domains = generate_json(n)['domains']
            req = EditRequest(generated_domains, RequestPriority.CRITICAL,-1)
            req._first_filter = False
            n_cnt, e_cnt = Neo4jDBDriver.from_config(neo4j_conf).get_node_and_edge_cnt()
            start_t = time.time()
            _handle_request(req,stop_event,neo4j_conf)
            time_taken = time.time() - start_t
            req_times.append(time_taken)
            node_cnts.append(n_cnt)
            edge_cnts.append(e_cnt)

            if cnt % eval_mod == 0:
                dom_copy = copy.deepcopy(domain)
                job = EvaluationJob(str(dom_copy['domain_name']),timeout=-1)
                job.set_domain_data(dom_copy)
                eval_start_t = time.time()
                evaluate_domain_metapath2vec(job,gpu_sem)
                eval_time_taken = time.time() - eval_start_t
                eval_times.append(eval_time_taken)
                writer.writerow([time_taken,n_cnt,e_cnt,eval_time_taken])
            else:
                writer.writerow([time_taken,n_cnt,e_cnt,eval_times[-1]])

            if cnt % 50 == 0:
                f.flush()
                os.fsync(f.fileno())

            time.sleep(1.0)

    visualize_test_results(req_times,node_cnts,edge_cnts,eval_times,eval_mod)

def direct_test_of_copy_on_write(neo4j_conf: str, out: str) -> None:
    stop_event = threading.Event()

    N = 100
    n = 100

    with open(out, "w") as f:
        writer = csv.writer(f)
        writer.writerow(["copy_time","n_cnt","e_cnt"])
        for cnt in range(N):
            generated_domains = generate_json(n)['domains']
            req = EditRequest(generated_domains, RequestPriority.CRITICAL,-1)
            req._first_filter = False
            n_cnt, e_cnt = Neo4jDBDriver.from_config(neo4j_conf).get_node_and_edge_cnt(cnt)
            _handle_request(req,stop_event,neo4j_conf)
            writer.writerow([COPY_ON_WRITE_TIMES[-1],n_cnt,e_cnt])
            f.flush()
            os.fsync(f.fileno())

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

def count_numbers_between_ranges(ranges_str: str) -> int:
    nums = list(map(int, ranges_str.split(",")))

    if len(nums) % 2 != 0:
        raise ValueError("Input must contain even number of integers")

    total = 0

    # Iterate over ranges pairwise
    for i in range(1, len(nums) - 2, 2):
        end_current = nums[i]
        start_next = nums[i + 1]

        # Count numbers strictly between ranges
        gap = start_next - end_current - 1

        if gap > 0:
            total += gap

    print(total)
    return total

if __name__ == '__main__':
    #main()
    #parse_csv("../../res_times.csv")
    #parse_csv("res_times_meta.csv")
    count_numbers_between_ranges("1234,4333,4998,22445,25166,40196,41657,49145,51838,61171,63495,85151,85170,87668,90752,94877,96952,101990,104799,120096,121997,127064,130032,151533,154823,159501,161651,168626,168688,174635,175209,189648,190941,195897,196749,202964,206575,215731,216037,222532,223230,226356,228170,236572,236971,247755,248175,255079,259235,277970,279108,291367,294942,316336,317713,325191,326929,332762,336030,345797,347881,355791,358780,360221,363448,381388,386915,401406,404283,420504,425266,432827,435192,449644,453857,475641,481385,498453,501295,506329,511329,514246,516545,522629,529422,532441,536113,558385,559173,568102,571089,573482,574012,576570,586895,589841,593774,595811,600481,607894")