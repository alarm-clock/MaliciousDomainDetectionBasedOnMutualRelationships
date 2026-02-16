#!/bin/bash

cd dataset_parsers/cpp
python3.10 setup.py build_ext --inplace
cd ../..