import csv
import json
import argparse
import sys

DOMAIN_NAME = 1
PROBABILITY = 2
MAL_TRESH = 0.5
IP_LIST = 3

def parse_ips(list_of_ips_str: str) -> tuple[list[str], list[str]]:
    a = []
    aaaa = []
    for ip in list_of_ips_str[1:len(list_of_ips_str) - 1].split(","):
        ip_no_prefix = ip.split("/")[0][1:]

        if ":" in ip_no_prefix:
            aaaa.append(ip_no_prefix)
        else:
            a.append(ip_no_prefix)


    return a, aaaa

def convert_to_json(csv_file: str, json_file: str, start_id: int = 0) -> None:

    domain_list: list[dict] = []
    node_id = start_id

    with open(csv_file) as csvfile:
        reader = csv.reader(csvfile)
        next(reader)

        for row in reader:
            domain_name = row[DOMAIN_NAME]
            label = "benign_2310" if float(row[PROBABILITY]) < MAL_TRESH else "malicious_not_specified"
            a, aaaa = parse_ips(row[IP_LIST])
            domain_list.append(
                {
                    "domain_name": domain_name,
                    "dns": {
                        "A": a,
                        "AAAA": aaaa
                    },
                    "label": label,
                    "node_id": node_id,
                    "notes": "Not from zendoro"}
            )
            node_id += 1

    with open(json_file, "w") as outfile:
        json.dump(domain_list, outfile, indent=2)

    return

def convert_to_classification_list(csv_file: str, out_file: str, start_id: int = 0) -> None:

    with open(csv_file) as csvfile:
        with open(out_file, "w") as outfile:
            reader = csv.reader(csvfile)
            next(reader)
            node_id = start_id

            for row in reader:
                outfile.write(f"{row[DOMAIN_NAME]} {node_id} {int( float(row[PROBABILITY]) < MAL_TRESH)}\n")
                node_id += 1

    return

def main():

    parser = argparse.ArgumentParser()
    parser.add_argument('csv_file', type=str, help='Path to csv file')
    parser.add_argument('out_name', type=str, help='Output name (without extension)')
    parser.add_argument('-j', action="store_true", help='Convert to json for database')
    parser.add_argument('-c', action="store_true", help='Convert to classification list for database')
    parser.add_argument('start_id', nargs="?", type=int, help='Start ID', default=0)
    args = parser.parse_args()

    csv_file = args.csv_file
    out_name = args.out_name

    if args.j:
        convert_to_json(csv_file, f'{out_name}.json', start_id=args.start_id)
    elif args.c:
        convert_to_classification_list(csv_file, f'{out_name}.txt', start_id=args.start_id)
    else:
        print("WTF bro :(", file=sys.stderr)

if __name__ == "__main__":
    main()