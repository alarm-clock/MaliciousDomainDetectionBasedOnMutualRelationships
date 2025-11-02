#!/bin/bash

source /storage/brno2/home/xbukas00/.node_bashrc
PROJECT_DIR=$BRNO_HOME/diplomka/DeepWalkTesting
RUN_SCRIPT=$PROJECT_DIR/testmain.py
GRAPH_EXPORT_PATH=$PROJECT_DIR/../dglGraphs
LOG_DIR=$PROJECT_DIR/../logs

#echo Copying datasets into cratch
#$PROJECT_DIR/run_scripts/copy_datasets_to_scratch.sh  

mongod --dbpath $MONGO_DBPATH --bind_ip 127.0.0.1 --port 27017 > /dev/null 2>&1 &

python3 $RUN_SCRIPT -db $PROJECT_DIR/db_config.json --heterograph cname,subdomain_of,ipv4 --export $GRAPH_EXPORT_PATH/hetero_full_cname_subdomain2_ipv4.dglg  --log_file $LOG_DIR/hetero_full_cname_subdomain2_ipv4.log

mongod --dbpath $MONGO_DBPATH --port 27017 --shutdown
