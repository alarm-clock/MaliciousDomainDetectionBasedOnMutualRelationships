#!/bin/bash

source /storage/brno2/home/xbukas00/.node_bashrc
PROJECT_DIR=$BRNO_HOME/diplomka/DeepWalkTesting
RUN_SCRIPT=$PROJECT_DIR/testmain.py
GRAPH_EXPORT_PATH=$PROJECT_DIR/../dglGraphs
PLOT_EXPORT_PATH=$PROJECT_DIR/../plots

#echo Copying datasets into cratch
#$PROJECT_DIR/run_scripts/copy_datasets_to_scratch.sh  

#python3 $RUN_SCRIPT --dataset $SCRATCHDIR/dataset_config.json --export $GRAPH_EXPORT_PATH/fullgraphwmalw_no_iso.dglg --rm_iso_nds
#python3 $RUN_SCRIPT --dglformat $PROJECT_DIR/../dglGraphs/fullgraph_no_iso.dglg -l 
python3 $RUN_SCRIPT --dglformat $PROJECT_DIR/../dglGraphs/hetero_full_all.dglg --log_file $PROJECT_DIR/../logs/learning_hetero_full_all.log --learn
