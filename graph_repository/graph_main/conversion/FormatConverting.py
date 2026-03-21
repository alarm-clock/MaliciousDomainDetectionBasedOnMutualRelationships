from typing import Any
from graph_repository.dataset_creator.common.Graph import create_dgl_graph, EDGES_T_DGL, N_DATA_T_DGL, E_T_DGL
from dgl import DGLHeteroGraph
import torch as th
from graph_repository.workers.common.GraphTypes import NodeTypes
from misc.Pair import replace

_ET_U_T = 0
_ET_E_T = 1
_ET_V_T = 2
_U_POS = 0
_V_POS = 1
_FROM = 0
_TO = 2
_E_T = tuple[NodeTypes, str, NodeTypes]
_EDGES_T = dict[_E_T, tuple[list[int], list[int]]]
_ID_MAP_T = dict[tuple[NodeTypes, int], int]
_ID_CNT_T = dict[NodeTypes, int]
_N_DATA_T = dict[str, dict[str, list]]

def _convert_id(id_cnt: _ID_CNT_T, id_map: _ID_MAP_T, n_t: NodeTypes, node_id: int) -> int:

    if id_map.get((n_t, node_id)) is not None:
        return id_map[(n_t, node_id)]

    try:
        new_node_id = id_cnt[n_t]
        id_cnt[n_t] += 1
        id_map[(n_t, node_id)] = new_node_id
    except KeyError:
        id_cnt[n_t] = 1
        new_node_id = 0

    return new_node_id

def _get_rev_e_t(e_t: _E_T) -> _E_T:
    return e_t[_ET_V_T], e_t[_ET_E_T], e_t[_ET_U_T]

def _e_t_to_full_str(e_t: _E_T) -> E_T_DGL:
    return e_t[_ET_U_T].dgl, e_t[_ET_E_T], e_t[_ET_V_T].dgl

def _add_edge(edges: _EDGES_T,
        id_cnt: _ID_CNT_T,
        id_map: _ID_MAP_T,
        e_t: _E_T,
        u: dict[str, Any],
        v: dict[str, Any],
        gen_rev_edges: bool
) -> tuple[int,int]:
    u_conv_id = _convert_id(id_cnt, id_map, u['nt'], u['nid'])
    v_conv_id = _convert_id(id_cnt, id_map, v['nt'], u['nid'])

    try:
        edges[e_t][_U_POS].append(u_conv_id)
        edges[e_t][_V_POS].append(v_conv_id)

    except KeyError:
        edges[e_t] = ([u_conv_id], [v_conv_id])

    if gen_rev_edges:
        rev_e_t = _get_rev_e_t(e_t)
        try:
            edges[rev_e_t][_U_POS].append(v_conv_id)
            edges[rev_e_t][_V_POS].append(u_conv_id)

        except KeyError:
            edges[rev_e_t] = ([v_conv_id], [u_conv_id])

    return u_conv_id, v_conv_id

def _check_if_n_data_already_stored(n_data: _N_DATA_T, n_t: str, new_node_id: int) -> bool:

    try:
        return len(n_data[list(n_data.keys())[0]][n_t]) >= new_node_id
    except KeyError:
        return False

def _store_n_data(n_data: _N_DATA_T, n: dict[str, Any], new_n_id: int) -> None:

    n_t = NodeTypes.from_neo4j_to_dgl(n['nt'])
    if _check_if_n_data_already_stored(n_data, n_t, new_n_id): return

    for key, val in n.items():
        if key != "nt":
            try:
                type_dictionary = n_data[key]
            except KeyError:
                n_data[key] = {}
                type_dictionary = n_data[key]

            try:
                type_dictionary[n_t].append(val)
            except KeyError:
                type_dictionary[n_t] = [val]


def _map_data_types_to_torch(d_type: type) -> th._C.dtype:

    if d_type == int:
        return th.int32
    if d_type == float:
        return th.double
    if d_type == bool:
        return th.bool
    raise TypeError("Can only convert numbers and bool")

def _create_graph(edges: _EDGES_T, n_data: _N_DATA_T) -> DGLHeteroGraph:

    edges_dgl: EDGES_T_DGL = {}

    for e_t, e_tup in edges.items():
        edges_dgl[_e_t_to_full_str(e_t)] = (th.Tensor(e_tup[_U_POS]).to(th.int32), th.Tensor(e_tup[_V_POS]).to(th.int32))

    n_data_dgl: N_DATA_T_DGL = {}

    for key, val_dicts in n_data.items():
        for n_t, val in val_dicts.items():
            n_data_dgl[key][n_t] = th.Tensor(val).to(_map_data_types_to_torch(type(val[0])))

    return create_dgl_graph(edges_dgl, n_data_dgl)

def convert_form_neo4j_to_dgl(graph: list[dict], gen_rev_edges: bool) -> DGLHeteroGraph:
    """
    Function for converting neo4j graph to dgl heterograph
    :param graph: `list[dict]` where each list element is row (`dict`) with keys `u`, `v` and `et` where
        `u` and `v` are dictionaries that must at least hold keys `nt` (node type) and `nid` (node_id) and
        `et` (edge type) is string. If any of those is missing then KeyError is raised. Note that `u` and `v`
        hold more values than those that are required, you must handle
    :param gen_rev_edges: `bool` flag specifying that to each edge reverse edge should be created
    :return: `DGLHeteroGraph` instance that is original graph in dgl format
    """

    edges: _EDGES_T= {}
    n_data: _N_DATA_T = {}
    id_map: _ID_MAP_T = {}
    id_cnt: _ID_CNT_T = {}

    for row in graph:
        u = row["u"]
        v = row["v"]
        e_t = (NodeTypes.from_str(u['nt']), row['et'], NodeTypes.from_str(v['nt']))

        u_c_id, v_c_id = _add_edge(edges, id_cnt, id_map, e_t, u, v, gen_rev_edges)
        _store_n_data(n_data,u,u_c_id)
        _store_n_data(n_data,v,v_c_id)

    return _create_graph(edges, n_data)


def _replace_tmp_for_d(graph: DGLHeteroGraph, e_t: E_T_DGL, from_f: bool, tmp_domain_d_id: int) -> None:

    d_e_t = replace(e_t, _FROM if from_f else _TO, NodeTypes.DOMAIN.dgl)

    tmp_u: th.Tensor
    tmp_v: th.Tensor
    tmp_u, tmp_v = graph.edges(etype=e_t)

    if from_f:
        graph.add_edges(th.Tensor([tmp_domain_d_id] * len(tmp_u)), tmp_v, etype=d_e_t)
    else:
        graph.add_edges(tmp_u, th.Tensor([tmp_domain_d_id] * len(tmp_v)), etype=d_e_t)

    return

def prepare_dgl_g_for_ml(graph: DGLHeteroGraph) -> None:
    """
    Function for preparing dgl graph for metapath2vec, mainly changing tmp domain into regular one, note that
    this function only works correctly if there is only one tmp domain (there is no reason for existence of two
    tmp domains in one graph)
    :param graph: `DglHeteroGraph` instance that is original graph in dgl format that will be updated in-place
    :return: None
    """

    tmp_domain_d_id = graph.num_nodes(NodeTypes.DOMAIN.dgl)
    tmp_domain_data = {key: val[0] for key, val in graph.nodes[NodeTypes.TMP_DOMAIN.dgl].items()}
    graph.add_nodes(1, data=tmp_domain_data, ntype=NodeTypes.DOMAIN.dgl)


    for e_t in graph.canonical_etypes:
        if e_t[_ET_U_T] == NodeTypes.TMP_DOMAIN.dgl:
            _replace_tmp_for_d(graph, e_t, from_f=True, tmp_domain_d_id=tmp_domain_d_id)

        if e_t[_ET_V_T] == NodeTypes.TMP_DOMAIN.dgl:
            _replace_tmp_for_d(graph, e_t, from_f=False, tmp_domain_d_id=tmp_domain_d_id)

    graph.remove_nodes(0,ntype=NodeTypes.TMP_DOMAIN.dgl)
    return

