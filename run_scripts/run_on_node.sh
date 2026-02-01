#!/bin/bash
#PBS -N graph_editing
#PBS -q default
#PBS -l select=1:ncpus=2:mem=50gb:ngpus=0:scratch_local=10gb
#PBS -l walltime=00:15:00

source /storage/brno2/home/xbukas00/.node_bashrc

CONTAINER=$BRNO_HOME/images/dgl_mongo.sif
PROJECT_DIR=$BRNO_HOME/diplomka/DeepWalkTesting
RUN_SCRIPT=$PROJECT_DIR/testmain.py

trap 'clean_scratch' TERM EXIT

echo Starting main script...
#singularity exec $CONTAINER python3 $RUN_SCRIPT --dataset $SCRATCHDIR/dataset_config.json --export $BRNO_HOME/diplomka/ful.dgld --remove_free_nodes
#singularity exec $CONTAINER $PROJECT_DIR/run_scripts/singularity_exec.sh
singularity exec $CONTAINER python3 $RUN_SCRIPT --dglformat $PROJECT_DIR/../dglGraphs/hetero_200k_all.dglg -rm_iso_nds -e $PROJECT_DIR/../dglGraphs/hetero_200k_all_no_iso.dglg
