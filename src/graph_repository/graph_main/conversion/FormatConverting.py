"""
File: graph_conversion.py
Author: Jozef Michal Bukas <xbukas00@stud.fit.vutbr.cz>
Date: 12.02.2026
Brief: File that contains helper methods for converting Neo4j graph rows into DGL
    heterographs and for preparing heterogeneous graphs for machine-learning usage
"""

import copy
from typing import Any
import dgl
from graph_repository.dataset_creator.common.Graph import create_dgl_graph, generate_train_mask_classification, \
    EDGES_T_DGL, N_DATA_T_DGL, E_T_DGL, check_if_g_is_hetero, add_diff_n_t_to_g
from dgl import DGLHeteroGraph
import torch as th
from graph_repository.workers.common.GraphTypes import NodeTypes

_ET_U_T = 0
_ET_E_T = 1
_ET_V_T = 2
_U_POS = 0
_V_POS = 1
_FROM = 0
_TO = 2
_E_T = tuple[str, str, str]
_EDGES_T = dict[_E_T, tuple[list[int], list[int]]]
_ID_MAP_T = dict[tuple[str, int], int]
_ID_CNT_T = dict[str, int]
_N_DATA_T = dict[str, dict[str, list]]


def _convert_id(id_cnt: _ID_CNT_T, id_map: _ID_MAP_T, n_t: str, node_id: int) -> int:
    """
    Method that converts original node id of given node type into consecutive local id
    :param id_cnt: `_ID_CNT_T` counters of assigned ids per node type
    :param id_map: `_ID_MAP_T` mapping from original ids to converted ids
    :param n_t: `str` node type
    :param node_id: `int` original node id
    :return: `int` converted local node id
    """
    if id_map.get((n_t, node_id)) is not None:
        return id_map[(n_t, node_id)]

    try:
        new_node_id = id_cnt[n_t]
        id_cnt[n_t] += 1

    except KeyError:
        id_cnt[n_t] = 1
        new_node_id = 0

    id_map[(n_t, node_id)] = new_node_id
    return new_node_id


def _rev_e_t_str(e_t: str) -> str:
    """
    Method that creates reverse-edge string representation from edge type string
    :param e_t: `str` edge type string
    :return: `str` reversed edge type string
    """
    e_t_arr = e_t.split('_')
    return f'{e_t_arr[0]}_{e_t_arr[2]}_{e_t_arr[1]}'

def _get_rev_e_t(e_t: _E_T) -> _E_T:
    """
    Method that creates reverse canonical edge type tuple
    :param e_t: `_E_T` original canonical edge type
    :return: `_E_T` reversed canonical edge type
    """
    return e_t[_ET_V_T], _rev_e_t_str( e_t[_ET_E_T]), e_t[_ET_U_T]


def _add_edge(edges: _EDGES_T,
              id_cnt: _ID_CNT_T,
              id_map: _ID_MAP_T,
              e_t: _E_T,
              u: dict[str, Any],
              v: dict[str, Any],
              gen_rev_edges: bool
              ) -> tuple[int, int]:
    """
    Method that stores one edge and optionally its reverse edge into edge dictionary
    :param edges: `_EDGES_T` stored edges
    :param id_cnt: `_ID_CNT_T` counters of local node ids
    :param id_map: `_ID_MAP_T` original-to-local id mapping
    :param e_t: `_E_T` canonical edge type
    :param u: `dict[str, Any]` source node description
    :param v: `dict[str, Any]` destination node description
    :param gen_rev_edges: `bool` whether reverse edge should also be created
    :return: `tuple[int, int]` converted source and destination ids
    """
    u_conv_id = _convert_id(id_cnt, id_map, u['nt'], u['nid'])
    v_conv_id = _convert_id(id_cnt, id_map, v['nt'], v['nid'])

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
    """
    Method that checks whether node data for given node id is already stored
    :param n_data: `_N_DATA_T` stored node data
    :param n_t: `str` node type
    :param new_node_id: `int` converted node id
    :return: `bool` True if data is already stored, otherwise False
    """
    try:
        return len(n_data[list(n_data.keys())[0]][n_t]) > new_node_id
    except KeyError:
        return False
    except IndexError:
        return False


def _store_n_data(n_data: _N_DATA_T, n: dict[str, Any], new_n_id: int) -> None:
    """
    Method that stores node properties for converted node id
    :param n_data: `_N_DATA_T` stored node data
    :param n: `dict[str, Any]` node properties
    :param new_n_id: `int` converted node id
    :return: None
    """
    n_t = NodeTypes.from_neo4j_to_dgl(n['nt'])
    n_t_code = NodeTypes.from_neo4j_to_dgl_code(n['nt'])
    if _check_if_n_data_already_stored(n_data, n_t, new_n_id): return

    for key, val in n.items():

        try:
            type_dictionary = n_data[key]
        except KeyError:
            n_data[key] = {}
            type_dictionary = n_data[key]

        if key != "nt":
            try:
                type_dictionary[n_t].append(val)
            except KeyError:
                type_dictionary[n_t] = [val]
        else:
            try:
                type_dictionary[n_t].append(n_t_code)
            except KeyError:
                type_dictionary[n_t] = [n_t_code]


def _map_data_types_to_torch(d_type: type) -> th._C.dtype:
    """
    Method that maps Python scalar type into torch dtype
    :param d_type: `type` Python type of value
    :return: `th._C.dtype` mapped torch dtype
    :raises TypeError: if given type cannot be converted
    """
    if d_type == int:
        return th.int32
    if d_type == float:
        return th.double
    if d_type == bool:
        return th.bool
    raise TypeError("Can only convert numbers and bool")


def _create_graph(edges: _EDGES_T, n_data: _N_DATA_T) -> DGLHeteroGraph:
    """
    Method that converts collected edges and node data into DGL heterograph
    :param edges: `_EDGES_T` stored edges
    :param n_data: `_N_DATA_T` stored node data
    :return: `DGLHeteroGraph` constructed graph
    """
    edges_dgl: EDGES_T_DGL = {}
    for e_t, e_tup in edges.items():
        edges_dgl[e_t] = (th.Tensor(e_tup[_U_POS]).to(th.int32),th.Tensor(e_tup[_V_POS]).to(th.int32))

    n_data_dgl: N_DATA_T_DGL = {}

    for key, val_dicts in n_data.items():
        n_data_dgl[key] = {}
        for n_t, val in val_dicts.items():
            n_data_dgl[key][n_t] = th.Tensor(val).to(_map_data_types_to_torch(type(val[0])))

    return create_dgl_graph(edges_dgl, n_data_dgl)


def convert_form_neo4j_to_dgl(gen_rev_edges: bool, graph: list[dict]) -> DGLHeteroGraph:
    """
    Function for converting neo4j graph to dgl heterograph.
    TODO rewrite this into language of true men, c++
    :param graph: `list[dict]` where each list element is row (`dict`) with keys `u`, `v` and `et` where
        `u` and `v` are dictionaries that must at least hold keys `nt` (node type) and `nid` (node_id) and
        `et` (edge type) is string. If any of those is missing then KeyError is raised. Note that `u` and `v`
        hold more values than those that are required, you must handle addition of missing values before calling
        this function.
    :param gen_rev_edges: `bool` flag specifying that to each edge reverse edge should be created
    :return: `DGLHeteroGraph` instance that is original graph in dgl format
    """

    #for row in graph:
    #    print(row)

    if len(graph) == 0:
        return DGLHeteroGraph()

    edges: _EDGES_T = {}
    n_data: _N_DATA_T = {}
    id_map: _ID_MAP_T = {}
    id_cnt: _ID_CNT_T = {}

    for row in graph:
        u = row["u"]
        v = row["v"]
        u_t = NodeTypes.from_neo4j_to_dgl(u['nt'])
        v_t = NodeTypes.from_neo4j_to_dgl(v['nt'])
        e_t = (u_t, row['et']+f'_{u_t}_{v_t}', v_t)

        u_c_id, v_c_id = _add_edge(edges, id_cnt, id_map, e_t, u, v, gen_rev_edges)
        _store_n_data(n_data, u, u_c_id)
        _store_n_data(n_data, v, v_c_id)

    return _create_graph(edges, n_data)


def _new_e_t(old_e_t: E_T_DGL, from_pos: bool, new_t: NodeTypes) -> E_T_DGL:
    """
    Method that creates updated canonical edge type with replaced source or destination node type
    :param old_e_t: `E_T_DGL` original canonical edge type
    :param from_pos: `bool` whether source node type should be replaced
    :param new_t: `NodeTypes` new node type
    :return: `E_T_DGL` updated canonical edge type
    """

    u_t = new_t if from_pos else old_e_t[_ET_U_T]
    v_t = new_t if not from_pos else old_e_t[_ET_V_T]
    e_t_arr = old_e_t[_ET_E_T].split('_')[0]
    e_t = f'{e_t_arr}_{u_t}_{v_t}'
    return u_t, e_t, v_t

def _replace_concrete_domain(
        e_t: E_T_DGL,
        d_e_t: E_T_DGL,
        tmp_n: th.Tensor,
        tmp_domain_d_id: int,
        du_domain_d_start_id: int,
        from_pos: bool) -> tuple[E_T_DGL, th.Tensor]:
    """
    Method that remaps dummy or temporary domain node ids into regular domain id space
    :param e_t: `E_T_DGL` original edge type
    :param d_e_t: `E_T_DGL` mutable destination edge type
    :param tmp_n: `th.Tensor` node ids to remap
    :param tmp_domain_d_id: `int` new regular-domain id of temporary domain
    :param du_domain_d_start_id: `int` offset where converted dummy domains begin
    :param from_pos: `bool` whether source or destination side is being processed
    :return: `tuple[E_T_DGL, th.Tensor]` updated edge type and remapped node ids
    """

    side = _ET_U_T if from_pos else _ET_V_T

    if e_t[side] == NodeTypes.DUMMY_DOMAIN.dgl:
        new_n = tmp_n.clone()
        new_n += du_domain_d_start_id
        d_e_t = _new_e_t(d_e_t, from_pos, NodeTypes.DOMAIN.dgl)

    elif e_t[side] == NodeTypes.TMP_DOMAIN.dgl:
        new_n = th.Tensor([tmp_domain_d_id] * len(tmp_n)).to(th.int32)
        d_e_t = _new_e_t(d_e_t, from_pos, NodeTypes.DOMAIN.dgl)

    else:
        new_n = tmp_n

    return d_e_t, new_n

def _replace_other_domain_types(
        graph: dgl.DGLHeteroGraph,
        e_t: E_T_DGL,
        tmp_domain_d_id: int,
        du_domain_d_start_id: int,
        edges_not_in_sch: dict) -> None:
    """
    Method that converts edges incident to dummy or temporary domains into regular-domain edges
    :param graph: `dgl.DGLHeteroGraph` graph being updated
    :param e_t: `E_T_DGL` processed canonical edge type
    :param tmp_domain_d_id: `int` regular-domain id assigned to temporary domain
    :param du_domain_d_start_id: `int` first regular-domain id assigned to dummy domains
    :param edges_not_in_sch: `dict` storage for edges whose types are not present in current graph schema
    :return: None
    """

    d_e_t = copy.deepcopy(e_t)
    tmp_u: th.Tensor
    tmp_v: th.Tensor
    tmp_u, tmp_v = graph.edges(etype=e_t)

    d_e_t, new_u = _replace_concrete_domain(e_t,d_e_t,tmp_u,tmp_domain_d_id,du_domain_d_start_id,True)
    d_e_t, new_v = _replace_concrete_domain(e_t,d_e_t,tmp_v,tmp_domain_d_id,du_domain_d_start_id,False)

    try:
        graph.add_edges(new_u, new_v, etype=d_e_t)
    except Exception:
        if edges_not_in_sch.get(d_e_t) is None:
            edges_not_in_sch[d_e_t] = (new_u, new_v)
        else:
            u, v = edges_not_in_sch[d_e_t]
            u = th.cat((u, new_u), dim=0)
            v = th.cat((v, new_v), dim=0)
            edges_not_in_sch[d_e_t] = (u, v)

def _create_new_updated_graph(
        graph: dgl.DGLHeteroGraph,
        edges_not_in_sch: dict,
        du_domain_d_start_id: int,
        tmp_domain_d_id: int) -> dgl.DGLHeteroGraph:
    """
    Method that builds final updated graph after temporary and dummy domains were converted
    :param graph: `dgl.DGLHeteroGraph` original graph
    :param edges_not_in_sch: `dict` extra edges not present in original schema
    :param du_domain_d_start_id: `int` start id of converted dummy domains
    :param tmp_domain_d_id: `int` converted temporary domain id
    :return: `dgl.DGLHeteroGraph` updated graph
    """

    new_edges = {}
    #If I remove all tmp edges then the canonical type for them and data structure stays which may bring problem in
    #later stages of work with this graph, but the simplest thing is to update old graph in place and then just copy
    #it into new graph, it is also less time-consuming
    for etype in graph.canonical_etypes:
        src, dst = graph.edges(etype=etype)
        if len(src) > 1:
            new_edges[etype] = (src, dst)

    new_edges.update(edges_not_in_sch)

    n_data = graph.ndata

    del graph

    if not check_if_g_is_hetero(new_edges):
        add_diff_n_t_to_g(new_edges)

    new_graph = dgl.heterograph(new_edges)

    for key, val in n_data.items():
        val.pop('tm', '')
        val.pop('du', '')
        new_graph.ndata[key] = val

    generate_train_mask_classification(new_graph, tmp_domain_d_id)
    new_graph.nodes[NodeTypes.DOMAIN.dgl].data['train_mask'][du_domain_d_start_id:tmp_domain_d_id] = False
    return new_graph

def prepare_dgl_g_for_ml(graph: DGLHeteroGraph) -> dgl.DGLHeteroGraph:
    """
    Function for preparing dgl graph for metapath2vec, mainly changing tmp domain into regular one, note that
    this function only works correctly if there is only one tmp domain (there is no reason for existence of two
    tmp domains in one graph), NOTE that for memory consumption reasons the old graph is ``DELETED``
    :param graph: `DglHeteroGraph` instance that is original graph in dgl format that will be updated
    :return: New, updated, graph
    """

    du_domain_d_start_id = graph.num_nodes(ntype=NodeTypes.DOMAIN.dgl)

    dummy_in_graph = NodeTypes.DUMMY_DOMAIN.dgl in graph.ntypes

    if dummy_in_graph:
        du_domain_data = {key: val for key, val in graph.nodes[NodeTypes.DUMMY_DOMAIN.dgl].data.items()}
        graph.add_nodes(graph.num_nodes(NodeTypes.DUMMY_DOMAIN.dgl),data=du_domain_data,ntype=NodeTypes.DOMAIN.dgl)

    tmp_domain_data = {key: th.Tensor([val[0]]).to(val.dtype) for key, val in
                       graph.nodes[NodeTypes.TMP_DOMAIN.dgl].data.items()}
    tmp_domain_data['l'] = th.Tensor([1]).to(th.int32)
    tmp_domain_d_id = graph.num_nodes(NodeTypes.DOMAIN.dgl)
    graph.add_nodes(1, data=tmp_domain_data,ntype=NodeTypes.DOMAIN.dgl)
    #note that this function will give 0 label to tmp domain

    edges_not_in_sch = {}

    for e_t in graph.canonical_etypes:
        if e_t[_ET_V_T] == NodeTypes.TMP_DOMAIN.dgl or e_t[_ET_V_T] == NodeTypes.DUMMY_DOMAIN.dgl\
            or e_t[_ET_U_T] == NodeTypes.TMP_DOMAIN.dgl or e_t[_ET_U_T] == NodeTypes.DUMMY_DOMAIN.dgl:

            _replace_other_domain_types(graph,e_t,tmp_domain_d_id,du_domain_d_start_id,edges_not_in_sch)

    graph.remove_nodes(0, ntype=NodeTypes.TMP_DOMAIN.dgl)

    if dummy_in_graph:
        graph.remove_nodes(list(range(graph.num_nodes(ntype=NodeTypes.DUMMY_DOMAIN.dgl))), ntype=NodeTypes.DUMMY_DOMAIN.dgl)

    return _create_new_updated_graph(graph, edges_not_in_sch, du_domain_d_start_id, tmp_domain_d_id)