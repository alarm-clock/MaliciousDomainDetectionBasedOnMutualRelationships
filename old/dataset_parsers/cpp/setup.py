import os
from setuptools import setup
from pybind11.setup_helpers import Pybind11Extension

WHERE = os.environ.get("WHERE") == "Local"
if WHERE:
    path_to_source = "code/k_hop_neighbours.cpp"
else:
    path_to_source = "/storage/brno2/home/xbukas00/diplomka/DeepWalkTesting/dataset_parsers/cpp/code/k_hop_neighbours.cpp"

setup(
    name="k_hop_neighbours",
    ext_modules=[
        Pybind11Extension(
            "k_hop_neighbours",
            [path_to_source],
            cxx_std=17,
            extra_compile_args=["-O2"],
        )
    ]
)