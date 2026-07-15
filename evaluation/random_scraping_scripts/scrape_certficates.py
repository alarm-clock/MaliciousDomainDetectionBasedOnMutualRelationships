import json
from typing import Any
import hashlib
from pymongo import MongoClient

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


def main():
    client = MongoClient('localhost', 27017)
    db = client['datasets']
    collection = db['domains']

    project = {'_id': 0, 'node_id': 1, "domain_name": 1, 'tls': 1}

    cursor = collection.find({}, project)

    certificate_hashes: dict[str, list[tuple[str, str]]] = {}
    public_key_ids: dict[str, list[str]] = {}

    for doc in cursor:
        domain_name = doc['domain_name']
        node_id = doc['node_id']
        tls_data = doc['tls']
        print(f"Processing {domain_name} {node_id}")
        if tls_data is None:
            continue

        entity_cert_data = tls_data['certificates'][0]
        cn = entity_cert_data['common_name']
        org = entity_cert_data['organization']
        start = entity_cert_data['validity_start']
        end = entity_cert_data['validity_end']
        auth_Id, subj_Id, ca = parse_extensions(entity_cert_data['extensions'])

        data_hash = hashlib.sha256(f"{cn}_{org}_{start}_{end}".encode()).hexdigest()

        certificate_hashes.setdefault(data_hash, []).append((domain_name, subj_Id))
        public_key_ids.setdefault(subj_Id, []).append(domain_name)

    with open('certificate_hashes.json', 'w') as outfile:
        json.dump(certificate_hashes, outfile)

    with open('public_key_ids.json', 'w') as outfile:
        json.dump(public_key_ids, outfile)

    text = f"""
avg_cert_h_n_domains = {sum([len(val) for val in certificate_hashes.values()]) / len(certificate_hashes)}
avg_subj_Id_n_domains = {sum([len(val) for val in public_key_ids.values()]) / len(public_key_ids)}
max_cert_h_n_domains = {max([len(val) for val in certificate_hashes.values()])}
min_cert_h_n_domains = {min([len(val) for val in certificate_hashes.values()])}
max_subj_Id_n_domains = {max([len(val) for val in public_key_ids.values()])}
min_subj_Id_n_domains = {min([len(val) for val in public_key_ids.values()])}
    """

    print(text)
    return

if __name__ == '__main__':
    main()