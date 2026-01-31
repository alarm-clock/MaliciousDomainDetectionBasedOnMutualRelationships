import csv
import json

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

def convertToJson(csv_file: str, json_file: str) -> None:

    domain_list: list[dict] = []
    node_id = 0

    with open(csv_file) as csvfile:
        reader = csv.reader(csvfile)
        next(reader)

        for row in reader:
            domain_name = row[1]
            label = "benign_2310" if float(row[2]) < 0.5 else "malicious_not_specified"
            a, aaaa = parse_ips(row[3])
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

def main():
    csv_file = "../../../../Downloads/domains-20260112-214249.csv"
    convertToJson(csv_file, "../../datasets/domains-20260112-214249_from_0.json")

if __name__ == "__main__":
    main()