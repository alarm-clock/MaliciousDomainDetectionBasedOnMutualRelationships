import pygtrie
from pymongo import MongoClient
from concurrent.futures import ThreadPoolExecutor

def reverse(d):
    parts = d['domain_name'].strip().rstrip('.').split('.')
    return int(d['node_id']), '.'.join(reversed(parts))

def main():
    client = MongoClient('localhost', 27017)
    db = client['datasets']
    collection = db['domains']

    cursor = collection.find({},{'_id':0,'domain_name':1, 'node_id':1}, batch_size=10000)
    domains = []

    with ThreadPoolExecutor(max_workers=16) as executor:
        futures = [executor.submit(reverse, d) for d in cursor]

        for future in futures:
            result = future.result()
            if result:
                domains.append(result)

    domain_id_dict = {}
    for domain in domains:
        domain_id_dict[domain[1]] = domain[0]

    trie = pygtrie.StringTrie(separator='.')
    subs = {}

    for domain in domains:
        print(trie)
        if trie.has_key(domain[1]):
            #print(f"{domain[1]} is superdomain")
            children = list(trie.keys(prefix=domain[1]))
            children_ids = [ domain_id_dict[child] for child in children]
            if subs[domain[0]] is None:
                subs[domain[0]] = children_ids
            else:
                subs[domain[0]].extend(children_ids)

        parent = trie.longest_prefix(domain[1])

        if parent:
            #print(f"{domain[1]} is subdomain of {parent.key}")
            parent_id = domain_id_dict[parent.key]
            if parent_id not in subs:
                subs[parent_id] = [domain[0]]
            else:
                subs[parent_id].append(domain[0])

        trie[domain[1]] = True

        domain_parts = domain[1].split('.')
        domain = '.'.join(domain_parts[:2])
        trie[domain] = True
        for cnt in range(1, len(domain_parts)):
            domain = domain + '.' + domain_parts[cnt]
            trie[domain] = True




if __name__ == "__main__":
    main()