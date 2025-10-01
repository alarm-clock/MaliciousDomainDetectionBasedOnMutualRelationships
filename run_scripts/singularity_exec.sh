#!/bin/bash

source /storage/brno2/home/xbukas00/.node_bashrc
PROJECT_DIR=$BRNO_HOME/diplomka/DeepWalkTesting
RUN_SCRIPT=$PROJECT_DIR/testmain.py
GRAPH_EXPORT_PATH=$PROJECT_DIR/../dglGraphs

echo Copying datasets into cratch
$PROJECT_DIR/run_scripts/copy_datasets_to_scratch.sh  

python3 $RUN_SCRIPT --dataset $SCRATCHDIR/dataset_config.json --export $GRAPH_EXPORT_PATH/fullgraphwmalw_no_iso.dglg --rm_iso_nds
