#!/bin/bash
#
#run on backround
mongod --dbpath $MONGO_DBPATH --bind_ip 127.0.0.1 --port 27017 > /dev/null 2>&1 &
