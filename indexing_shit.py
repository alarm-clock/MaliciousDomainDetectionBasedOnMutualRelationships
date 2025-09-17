import pymongo
from pymongo import MongoClient

client = MongoClient('localhost', 27017)
db = client['datasets']
coll = db['domains']
cnt = 0

for doc in coll.find({},{"_id": 1}):
    coll.update_one({"_id": doc["_id"]},{"$set": {"node_id": cnt}})
    cnt += 1


coll.create_index([("node_id", pymongo.ASCENDING)], unique=True)