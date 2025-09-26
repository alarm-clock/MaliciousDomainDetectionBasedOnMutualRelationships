#!/bin/bash
#PBS -N graph_testing_job
#PBS -q
#PBS -l select=1:ncpus=20:mem=50gb:ngpus=0:scratch_local=20gb
#PBS -l walltime=01:30:00


source /storage/brno2/home/xbukas00/.node_bashrc

CONTAINER=$BRNO_HOME/images/test_image.sif
JSON_DATASET_PATH=$BRNO_HOME/diplomka/DeepWalkTesting/dataset_config.json

trap 'clean_scratch' TERM EXIT

singularity exec