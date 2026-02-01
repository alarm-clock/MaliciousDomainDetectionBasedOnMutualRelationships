#!/bin/bash
#PBS -N graph_creation_full_new_domains
#PBS -q default
#PBS -l select=1:ncpus=4:mem=300gb:ngpus=0:scratch_local=2gb
#PBS -l walltime=04:00:00

source /storage/brno2/home/xbukas00/.node_bashrc

CONTAINER=$BRNO_HOME/images/dgl_mongo.sif
PROJECT_DIR=$BRNO_HOME/diplomka/DeepWalkTesting
RUN_SCRIPT=$PROJECT_DIR/testmain.py

trap 'clean_scratch' TERM EXIT

echo Starting main script...
#singularity exec $CONTAINER python3 $RUN_SCRIPT --dataset $SCRATCHDIR/dataset_config.json --export $BRNO_HOME/diplomka/ful.dgld --remove_free_nodes
singularity exec -B $BRNO_HOME/mongodb_files:/data/db  $CONTAINER $PROJECT_DIR/run_scripts/singularity_exec_graph_c.sh
