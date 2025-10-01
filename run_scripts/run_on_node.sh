#!/bin/bash
#PBS -N graph_creating_f_dset_job
#PBS -q default
#PBS -l select=1:ncpus=20:mem=150gb:ngpus=0:scratch_local=30gb
#PBS -l walltime=05:40:00

source /storage/brno2/home/xbukas00/.node_bashrc

CONTAINER=$BRNO_HOME/images/test_image.sif
PROJECT_DIR=$BRNO_HOME/diplomka/DeepWalkTesting
RUN_SCRIPT=$PROJECT_DIR/testmain.py

trap 'clean_scratch' TERM EXIT

echo Starting main script...
#singularity exec $CONTAINER python3 $RUN_SCRIPT --dataset $SCRATCHDIR/dataset_config.json --export $BRNO_HOME/diplomka/ful.dgld --remove_free_nodes
singularity exec $CONTAINER $PROJECT_DIR/run_scripts/singularity_exec.sh
