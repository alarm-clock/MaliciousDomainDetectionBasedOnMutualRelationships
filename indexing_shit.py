import pymongo
from pymongo import MongoClient
from helper_func import get_ips_from_record

client = MongoClient('localhost', 27017)
db = client['datasets']
coll = db['domains']
#cnt = 0

#for doc in coll.find({},{"_id": 1}):
#    coll.update_one({"_id": doc["_id"]},{"$set": {"node_id": cnt}})
#    cnt += 1


#coll.create_index([("node_id", pymongo.ASCENDING)], unique=True)

cnt = 0
cnt2 = 0
for doc in coll.find():
    ips = get_ips_from_record(doc)

    if ips is not None and len(ips) > 0:
        if ips[0] == "0.0.0.0":
            continue
        neighbors = coll.find({'dns.A': {'$in': ips}})

        n_l = neighbors.to_list()

        if len(n_l) == 0:
            cnt += 1
        else:
            cnt2 += 1

        print(f"no n: {cnt}, n: {cnt2}")
