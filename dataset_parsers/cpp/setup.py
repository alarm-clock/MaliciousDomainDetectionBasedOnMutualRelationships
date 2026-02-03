from setuptools import setup
from pybind11.setup_helpers import Pybind11Extension

setup(
    name="k_hop_neighbours",
    ext_modules=[
        Pybind11Extension(
            "k_hop_neighbours",
            ["code/k_hop_neighbours.cpp"],
            cxx_std=17,
            extra_compile_args=["-O2"],
        )
    ]
)