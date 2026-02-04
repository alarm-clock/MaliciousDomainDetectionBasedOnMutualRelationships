#!/bin/bash

source /storage/brno2/home/xbuka00/.node_bashrc
set -euo pipefail

CPP_SOURCE=$BRNO_HOME/diplomka/DeepWalkTesting/dataset_parsers/cpp
SETUP_SCRIPT_PATH=$CPP_SOURCE/setup.py

RUN_ID="$(date +%Y%m%d_%H%M%S)_$$"
ARCH="$(uname -m)"
RUN_NAME=$1

BUILD_DIR="${SCRATCH}/${RUN_NAME}_${RUN_ID}${ARCH}"
mkdir -p "${BUILD_DIR}"

python3 $SETUP_SCRIPT_PATH build_ext --build-lib "${BUILD_DIR}" --build-temp "${BUILD_DIR}/temp"
export PYTHONPATH="${BUILD_DIR}:${PYTHONPATH}"
