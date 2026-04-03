#!/bin/bash

source /storage/brno2/home/xbukas00/.node_bashrc
PROJECT_DIR=$BRNO_HOME/diplomka/DeepWalkTesting
RUN_SCRIPT=$PROJECT_DIR/testmain.py
GRAPH_EXPORT_PATH=$PROJECT_DIR/../dglGraphs
LOG_DIR=$PROJECT_DIR/../logs

cd $PROJECT_DIR

ssh -i $BRNO_HOME/.metacentrum_neo4j_db_cloud1.pem -o UserKnownHostsFile=$BRNO_HOME/.ssh/known_hosts -f -N -D 1080 ubuntu@78.128.235.105

if [ $? -eq 0 ]; then
	echo "Established connection with router server"
else
	echo "Could not establish connection with router server!"
	exit 1
fi

RANGES="$(python3 -m evaluation.graph_repository.setTrainTestDomians  $PROJECT_DIR/mongo_config.json)"

proxychains python3 -m graph_repository.graph_repo_main --mongo_db  $PROJECT_DIR/mongo_config.json --neo_db $PROJECT_DIR/neo4j_config.json -l $LOG_DIR/graph_to_neo4j.log -ll "DEBUG"  import_db --neo -e all -r $RANGES
echo $RANGES > $RESULT_EXPORT_PATH/used_ranges.txt
proxychains python3 -m main --mongo_db  $PROJECT_DIR/mongo_config.json --neo_db $PROJECT_DIR/neo4j_config.json -l $LOG_DIR/eval.log -ll "DEBUG" classify -m --test $RESULT_EXPORT_PATH/result.csv

mongod --dbpath $MONGO_DBPATH --bind_ip 127.0.0.1 --port 27017 > /dev/null 2>&1 &

mongod --dbpath $MONGO_DBPATH --port 27017 --shutdown
pkill -f "ssh .* -D 1080"

exit 0
