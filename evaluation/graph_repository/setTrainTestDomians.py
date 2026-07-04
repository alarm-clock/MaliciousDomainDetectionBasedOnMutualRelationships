"""
File: set_train_test.py
Author: Jozef Michal Bukas <xbukas00@stud.fit.vutbr.cz>
Date: 22.01.2026
Brief: File that contains helper methods for generating train/test node-id ranges
    and updating MongoDB collection documents with corresponding train split flags
"""

import argparse
import json
import random

import pymongo
from pymongo import MongoClient


def generateRanges(n: int, n_ranges: int, prob: float = 0.75) -> list[tuple[int,int]]:
    """
    Method that generates disjoint node-id ranges whose total covered size approximates
    selected probability of all available nodes
    :param n: `int` total number of nodes/documents
    :param n_ranges: `int` number of ranges to generate
    :param prob: `float` target fraction of nodes that should belong to train split
    :return: `list[tuple[int, int]]` generated inclusive index ranges
    """

    target = int(n * prob)
    lengths = [random.random() for _ in range(n_ranges)]
    total_lengths = sum(lengths)

    lengths = [max(1,int((l/total_lengths) * target)) for l in lengths ]

    lengths[0] += target - sum(lengths)

    ranges = []
    curr = 0

    for cnt, length in enumerate(lengths):
        if length <= 0:
            continue

        cnt_rem = len(lengths) - cnt
        rem_space = n - curr - sum(lengths[cnt:]) - (cnt_rem - 1)
        avg_gap = max(0, rem_space // cnt_rem) if cnt_rem > 0 else 0

        gap_between_range = random.randint(0,avg_gap)
        curr += gap_between_range

        end = curr + length - 1
        if end >= n:
            end = n - 1
            if end < curr:
                break

        ranges.append((curr, end))
        curr = end + 1

    return ranges


def setTrainTestTODomains(ranges: list[tuple[int,int]], collection: pymongo.collection.Collection) -> None:
    """
    Method that resets all documents to test split and then marks selected node-id ranges as train split
    :param ranges: `list[tuple[int, int]]` inclusive node-id ranges that should be marked as training data
    :param collection: `pymongo.collection.Collection` MongoDB collection with domain documents
    :return: None
    """

    collection.update_many({}, {'$set': {"train": False}})

    or_conditions = [{"node_id": {"$gte": start, "$lte": end}} for start, end in ranges]

    if or_conditions is None:
        return

    filt  = {"$or": or_conditions}

    collection.update_many(filt, {"$set": {"train": True}})

    return


def main():
    """
    Method that parses CLI arguments, loads MongoDB configuration, and either clears
    or creates train/test split flags in configured collection
    :return: None
    """

    parser = argparse.ArgumentParser()
    parser.add_argument("mogno_db_conf",metavar='MONGO_CONF_FILE', type=str)
    parser.add_argument("-c",action="store_true",help="clean mongo")

    args = parser.parse_args()

    with open(args.mogno_db_conf) as f:
        conf = json.load(f)

    client = MongoClient(conf["client"], conf["port"])
    db = client[conf["db"]]
    collection = db[conf["collection"]]

    if args.c:
        collection.update_many({}, {"$unset": {"train": ""}})
        return

    ranges = generateRanges(collection.count_documents({}), 3,0.75)
    setTrainTestTODomains(ranges, collection)

    ranges_str=""

    for start, end in ranges:
        ranges_str += f"{start},{end},"

    ranges_str = ranges_str[:-1]
    print(ranges_str)

    return

if __name__ == "__main__":
    main()