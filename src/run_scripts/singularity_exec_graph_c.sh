#!/bin/bash

source /storage/brno2/home/xbukas00/.node_bashrc
PROJECT_DIR=$BRNO_HOME/diplomka/DeepWalkTesting
RUN_SCRIPT=$PROJECT_DIR/testmain.py
GRAPH_EXPORT_PATH=$PROJECT_DIR/../dglGraphs
LOG_DIR=$PROJECT_DIR/../logs

#echo Copying datasets into cratch
#$PROJECT_DIR/run_scripts/copy_datasets_to_scratch.sh  

cd $PROJECT_DIR

mongod --dbpath $MONGO_DBPATH --bind_ip 127.0.0.1 --port 27017 > /dev/null 2>&1 &
neo4j start

python3 -m graph_repository.graph_repo_main --mongo_db  $PROJECT_DIR/mongo_config.json --neo_db $PROJETC_DIR/neo4j_config.json -l $LOG_DIR/graph_to_neo4j.log import_db --neo -e all

mongod --dbpath $MONGO_DBPATH --port 27017 --shutdown
neo4j stop
