#!/bin/bash
#PBS -N test_metapath2vec
#PBS -q gpu
#PBS -l select=1:ncpus=4:mem=50gb:ngpus=1:scratch_local=2gb
#PBS -l walltime=06:00:00

source /storage/brno2/home/xbukas00/.node_bashrc
CONTAINER=$BRNO_HOME/images/dgl_mongo_cpp_neo4j.sif
PROJECT_DIR=$BRNO_HOME/diplomka/DeepWalkTesting
RUN_SCRIPT=$PROJECT_DIR/testmain.py
trap 'clean_scratch' TERM EXIT
singularity exec $MONGO_SING_BIND $PROXY_BIND $CONTAINER $PROJECT_DIR/run_scripts/singularity_exec_gen_eval.sh