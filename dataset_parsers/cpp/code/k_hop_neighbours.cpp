#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <pybind11/stl.h>

#include <vector>
#include <stdio.h>
#include <random>

namespace py = pybind11;

void print_vector(std::vector<int64_t> vec, int64_t depth)
{
    printf("Next for depth %ld:\n\t",depth);
    for(auto nd: vec)
    {
        printf("%ld,",nd);
    }
    printf("\n");
}

std::vector<int64_t> khop_neighbours( py::array_t<int64_t> indptr, py::array_t<int64_t> indices, int64_t nd, int64_t max_depth, int64_t too_much_limit, double sample)
{
    auto indptr_buf = indptr.unchecked<1>();
    auto indices_buf = indices.unchecked<1>();

    int64_t num_nodes = indptr_buf.shape(0) - 1;

    std::vector<char> visited(num_nodes, 0);
    std::vector<int64_t> frontier, next;
    std::vector<int64_t> result;

    frontier.push_back(nd);
    visited[nd] = 1;
    result.push_back(nd);

    py::gil_scoped_release release;
    std::random_device rd;
    std::mt19937 gen(rd());
    std::uniform_real_distribution<> dis(0.0, 1.0);

    for (int depth = 0; depth < max_depth; depth++)
    {
        next.clear();
        for (auto u : frontier) {
            for (int64_t i = indptr_buf(u); i < indptr_buf(u + 1); i++)
            {
                bool too_many = (indptr_buf(u+1) - indptr_buf(u)) >= too_much_limit;
                int64_t v = indices_buf(i);
                if (!visited[v])
                {
                    visited[v] = 1;
                    if(too_many)
                    {
                        if(dis(gen) > sample) continue;
                    }
                    next.push_back(v);
                    result.push_back(v);
                }
            }
        }
        //print_vector(next,depth);
        frontier.swap(next);
        if (frontier.empty()) break;
    }

    return result;
}

PYBIND11_MODULE(k_hop_neighbours, m)
{
    m.def("k_hop_neighbours", &khop_neighbours, "Return all nodes within <= k hops from seed using CSR");
}
