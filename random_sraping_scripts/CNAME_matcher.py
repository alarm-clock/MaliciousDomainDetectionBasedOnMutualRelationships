from pymongo import MongoClient
from concurrent.futures import ThreadPoolExecutor

def find_in_db(domain: str, collection) -> tuple[int, str] | None:

    doc = collection.find_one({"domain_name": domain})
    if doc is None:
        return None
    else:
        return doc["node_id"], domain

def main():

    client = MongoClient('localhost', 27017)
    db = client['datasets']
    collection = db['domains']
    cursor = collection.find({}, {'_id': 0, "dns.CNAME.value": 1, "node_id": 1, "label": 1}, batch_size=10000)

    domains = {}
    for doc in cursor:
        if doc.get('dns'):
            if doc['dns']['CNAME']['value'] not in domains:
                domains[doc['dns']['CNAME']['value']] = [(int(doc['node_id']), True if doc['label'] == 'benign_2310' else False)]
            else:
                domains[doc['dns']['CNAME']['value']].append((int(doc['node_id']), True if doc['label'] == 'benign_2310' else False))

    doms_in_dset ={}
    with ThreadPoolExecutor(max_workers=16) as executor:
        futures = [executor.submit(find_in_db, d, collection) for d in domains.keys()]

        for future in futures:
            result = future.result()
            if result is not None:
                doms_in_dset[result[1]] = result[0]

    cnt = 0
    for key in domains.keys():

        print(f"Domain {key}", end="")
        if doms_in_dset.get('key') is not None:
            cnt += 1
            print(f" is in dset with id {doms_in_dset[key]}:")
        else:
            print(":")

        for d in domains[key]:
            print(f"{d[0]}, ", end='')
        print("")
        for d in domains[key]:
            print(f"{d[1]}, ", end='')
        print("")


    print(f"\n\n{doms_in_dset.keys().__len__()} domains are in dset out of {collection.count_documents({})} documents.")
if __name__ == "__main__":
    main()