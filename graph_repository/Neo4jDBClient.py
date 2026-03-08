import time

from neo4j import GraphDatabase
from enum import Enum

from sklearn.utils import deprecated

from misc.Logger import MyLogger
from graph_repository.workers.common.GraphTypes import NodeTypes, EdgeTypes
from graph_repository.workers.common.Enums import EditTypes
from neo4j.exceptions import ServiceUnavailable, AuthError
from graph_repository.graph_main.graph_editing.common.Exceptions import TooManyVersions, Neo4jIndexError
import json
import sys
from typing import Any


class CouldNotConnect(Exception):
    def __init__(self, url: str, port: int, username: str):
        self.url = url
        self.port = port
        self.username = username
        super().__init__(f'Could not connect to Neo4j with url: {url}, port: {port}, username: {username}')


class Neo4jDBClient:
    """
    Class that represents Neo4j domain relationship graph database driver. While it provides simple functions for
    direct graph querying, it also has more complex methods for managing domain relationship graph.
    """

    def __init__(self, host: str, port: int, username: str, password: str, database: str, alt_host: str | None = None, batch_delay: float = 0.0, batch_size: int = 1000):
        """
        Class constructor that checks parameter validity and connects to database
        :param host: `str`
        :param port: `int`
        :param username: `str`
        :param password: `str`
        :param database: `str`
        :param alt_host: `str` Alias that can be used to connect to the database
        :param batch_delay: `float`
        :param batch_size: `int`
        """

        self._err = False

        if batch_delay < 0.0 or batch_size < 1:
            self._err = True
            raise ValueError("Invalid batch options")

        MyLogger.get_instance().log(f"Trying to connect to Neo4j db at {host}:{port} with user {username}...")
        try:
            driver = GraphDatabase.driver(f'bolt://{host}:{port}', auth=(username, password))
        except ServiceUnavailable as err:

            if alt_host is not None:
                try:
                    driver = GraphDatabase.driver(f'bolt://{alt_host}:{port}', auth=(username, password))
                except ServiceUnavailable as err_2:
                    MyLogger.get_instance().log_error(f"Could not connect to Neo4j with with error on host: {err} and error on alt_host: {err_2}")
                    print(err, err_2, file=sys.stderr)
                    self._err = True
                    raise CouldNotConnect(host, port, username)

                MyLogger.get_instance().log_warning(f"Could not connect to Neo4j using host {host} with error: {err} but connected to server using alternate host: {alt_host}")

            else:
                MyLogger.get_instance().log_error(f"Could not connect to Neo4j with error: {err}")
                print(err, file=sys.stderr)
                self._err = True
                raise CouldNotConnect(host, port, username)

        try:
            driver.verify_connectivity()
        except AuthError as err:
            MyLogger.get_instance().log_error(f"Authentication failed when connecting to Neo4j: {err}")
            print(err, file=sys.stderr)
            self._err = True
            raise CouldNotConnect(host, port, username)
        except ServiceUnavailable as err:
            MyLogger.get_instance().log_error(f"Even though connected to the server, verify connection returned service unavailable: {err}")
            print(err, file=sys.stderr)
            self._err = True
            raise CouldNotConnect(host, port, username)

        self.driver = driver
        self.database = database
        self._batch_delay = batch_delay
        self._batch_size = batch_size

    @classmethod
    def from_config(cls, config: str):
        """
        Method that creates instance of `Neo4jDBClient` from configuration file
        :param config: `str` path to configuration file
        :return: Instance of `Neo4jDBClient`
        """

        host = ''
        alt_host = None
        batch_delay = 0.0
        batch_size = 1000
        user = ''
        port = 0
        pwd = ''
        db = ''

        with open(config, mode='r') as f:
            conf = json.load(f)

            try:
                host = conf['host']
                user = conf['user']
                port = conf['port']
                pwd = conf['pwd']
                db = conf['db']

            except KeyError:
                print("Missing keys in config file, it must contain: host, user, port, pwd, db", file=sys.stderr)
                MyLogger.get_instance().log(f"Missing keys in config file, it must contain: host, user, pwd, db")
                return None

            try:
                alt_host = conf['alternate_host']
            except KeyError:
                alt_host = None

            try:
                batch_delay = conf['batch_delay']
            except KeyError:
                pass

            try:
                batch_size = conf['batch_size']
            except KeyError:
                pass

        return Neo4jDBClient(host, port, user, pwd, db, alt_host, batch_delay, batch_size)

    def close(self) -> None:
        """
        Method that closes connection with the database
        :return: None
        """
        self.driver.close()

    def execute_write(self, query, **params) -> Any:
        """
        Method that executes write on the graph
        :param query: `str`
        :param params: query parameters (values that will be substituted in query instead of $variables in query)
        :return: `Any` query result
        """
        with self.driver.session(database=self.database) as s:
            return s.execute_write(lambda tx: tx.run(query, **params).data())

    def execute_read(self, query, **params) -> Any:
        """
        Method that executes read on the graph
        :param query: `str`
        :param params: query parameters (values that will be substituted in query instead of $variables in query)
        :return: `Any` query result
        """
        with self.driver.session(database=self.database) as s:
            return s.execute_read(lambda tx: tx.run(query, **params).data())

    def set_maintenance_node(self) -> None:
        self.execute_write(f"CREATE (:{NodeTypes.MAINTENANCE.value})")

    def remove_maintenance_node(self) -> None:
        self.execute_write(f"MATCH (n:{NodeTypes.MAINTENANCE.value}) DETACH DELETE n")

    def is_graph_in_maintenance(self) -> bool:
        return self.execute_read(f"MATCH (n: {NodeTypes.MAINTENANCE.value}) RETURN n AS is")[0]['is']

    def get_max_id_of_node_type(self, n_t: NodeTypes | str) -> int:
        """
        Method that returns max node_id of given ``n_t`` that is present in the graph
        :param n_t: `NodeTypes` node type for which max id will be returned
        :return: `int` max id
        """
        n_t_str = n_t.value if type(n_t) == NodeTypes else n_t
        return self.execute_read(f"MATCH (n:{n_t_str}) RETURN max(n.node_id) AS {n_t_str}_max_id")[0][f'{n_t_str}_max_id']

    def get_current_active_graph_version(self) -> int:
        """
        Method that returns current graph version that should be used for computation
        :return: `int` current version
        """
        return self.execute_read(f"MATCH (v: {NodeTypes.CURRENT_VERSION.value}) RETURN v.version AS vers")[0]['vers']

    def get_existing_versions(self) -> list[int]:
        """
        Method that returns all existing version of graph
        :return: `list[int] all graph versions
        """
        return self.execute_read(f"MATCH (v: {NodeTypes.VERSION.value}) RETURN collect(v.version) AS vers")[0]['vers']

    def set_new_graph_version_node(self, new_version: int) -> None:
        """
        Method for setting new graph version node, if such version already exists then nothing will happen
        :param new_version: `int` new graph version number
        :return: None
        """
        query = f"""
        MERGE (: {NodeTypes.VERSION.value} {{version: {new_version}, n_users: 0}})
        """
        self.execute_write(query)

    def create_node_id_cnt(self, n_t: NodeTypes | str, start_value: int = 0) -> None:
        """
        Method that creates node_id counter for given ``n_t`` node type, if counter for given ``n_t`` exists, nothing will happen
        :param n_t: `NodeTypes` for which counter will be created
        :param start_value: `int` Counters start value
        :return: None
        """
        n_t_str = n_t.value if type(n_t) == NodeTypes else n_t
        self.execute_write(f"MERGE (:{NodeTypes.ND_ID_CNT.value} {{ cnt_name: \"{n_t_str}\", val: {start_value} }}) ")

    _FREE_NODE_ID_POSTFIX = "_free_node_id"

    @staticmethod
    def get_free_node_id_query(n_t: NodeTypes, as_subquery: bool, req_number_of_ids: int = 1) -> str | None:
        """
        Method that returns query that can be used as part of larger query for dynamic allocation of node_ids for given ``n_t`` `NodeTypes`
        :param n_t: `NodeTypes` specifying for which node type these ids are
        :param as_subquery: `bool` specifying if query is being called as subquery
        :param req_number_of_ids: `int` number of ids that need to be allocated
        :return: `str` on success, None if ``req_number_of_ids is less then 1
        """

        if req_number_of_ids < 1:
            return None

        if req_number_of_ids != 1:
            query = f"""
            MATCH (free_id: {n_t.value}{Neo4jDBClient._FREE_NODE_ID_POSTFIX})
            WITH free_id
            LIMIT {req_number_of_ids}
            WITH collect(free_id) AS free_nodes
            WITH free_nodes, [x IN free_nodes | x.node_id] as reused_ids
            
            FOREACH (x IN free_nodes | DELETE x)
            
            WITH reused_ids, {req_number_of_ids} - size(reused_ids) AS rem_cnt
            
            CALL(rem_cnt){{
                WITH rem_cnt
                WHERE rem_cnt > 0
                MATCH (counter: {NodeTypes.ND_ID_CNT.value} {{cnt_name: \"{n_t.value}\" }})
                SET counter.val = counter.val + rem_cnt
                RETURN range(counter.val - rem_cnt, counter.val - 1) AS allocated_ids 
                
                UNION
                
                WITH rem_cnt
                WHERE rem_cnt = 0
                RETURN [] AS allocated_ids
            }}
            RETURN reused_ids + coalesce( allocated_ids, []) AS free_node_ids
            """
        else:
            query = f"""
            OPTIONAL MATCH (free_id: {n_t.value}{Neo4jDBClient._FREE_NODE_ID_POSTFIX})
            WITH free_id
            LIMIT 1
            
            MATCH (counter: {NodeTypes.ND_ID_CNT.value} {{cnt_name: \"{n_t.value}\" }})

            WITH free_id, counter, 
                CASE WHEN free_id IS NOT NULL
                    THEN free_id.node_id 
                    ELSE counter.val
                END AS free_node_id
            
            SET counter.val = CASE WHEN free_id IS NOT NULL
                                  THEN counter.val
                                  ELSE counter.val + 1
                              END 
                              
            FOREACH(_ IN CASE WHEN free_id IS NOT NULL THEN [1] ELSE [] END | DELETE free_id)
            
            RETURN free_node_id
            """

        if as_subquery:
            query = f"CALL () {{ {query} }}"

        return query

    def get_free_node_id(self, n_t: NodeTypes, req_number_of_ids: int = 1) -> list[int] | int:
        """
        Method that allocates and returns specified number of node_ids for given ``n_t`` `NodeTypes`
        :param n_t: `NodeTypes` specifying for which node type these ids are
        :param req_number_of_ids: `int` required number of ids
        :return: `int | list[int]` ids that have been allocated
        """

        res = self.execute_write(self.get_free_node_id_query(n_t, False, req_number_of_ids))
        print(res)
        ret_val = res[0]['free_node_id' if req_number_of_ids == 1 else 'free_node_ids']
        return ret_val

    def return_unused_node_ids(self, n_t: NodeTypes, node_ids: int | list[int]) -> None:
        """
        Method for returning unused node_ids that have been allocated
        :param n_t: `NodeTypes` specifying to which node types these ids belong to
        :param node_ids: `int | list[int]` Ids that will be returned
        :return: None
        """

        query = f"""
        UNWIND $ids AS returned_id
        CREATE (:{n_t.value}{self._FREE_NODE_ID_POSTFIX} {{node_id: returned_id}})
        """

        ids = [node_ids] if type(id) == int else node_ids
        self.execute_write(query,**{"ids": ids})
        return


    #TODO RETURN node_id when deleting any node

    def set_new_current_graph_version_node(self, new_current_version: int) -> bool:
        """
        Method that sets the new current graph version
        :param new_current_version: `int` new current graph version
        :return: True on success, False otherwise (new version is not present in graph)
        """

        if new_current_version not in self.get_existing_versions():
            MyLogger.get_instance().log_error(f'Version {new_current_version} is not present in graph, therefore can not be set as new current graph version')
            return False

        if new_current_version == self.get_current_active_graph_version():
            MyLogger.get_instance().log(f"Version {new_current_version} is already set as current graph version")
            return True

        query = f"""
        OPTIONAL MATCH (old_version: {NodeTypes.CURRENT_VERSION.value})
        DETACH DELETE old_version
        CREATE (: {NodeTypes.CURRENT_VERSION.value} {{version: {new_current_version}}})
        """
        self.execute_write(query)
        return True

    def _create_indexes_for_graph_copy(self) -> None:
        labels = self.get_all_labels_in_graph()
        index_names = []

        for label in labels:

            index_name = label + "_node_id_version_index"
            index_names.append(index_name)

            query = f"""
            CREATE INDEX {index_name}
            IF NOT EXISTS
            FOR (n: {label})
            ON (n.node_id, n.graph_version);
            """

            self.execute_write(query)

        self.wait_for_index_creation(index_names)

    def wait_for_index_creation(self, index_names: list[str], time_between_queries: float = 8.0) -> None:
        """
        Method that waits until indexes in ``index_names`` have been created.
        :param index_names: `list[str]` of index names
        :param time_between_queries: `float` in seconds how much to wait between subsequent queries
        :return: None
        """

        query = f"""
        SHOW INDEXES
        YIELD name, state, populationPercent
        WHERE state = 'POPULATING' OR state = 'ERROR' AND name IN $index_names 
        RETURN name, state, populationPercent
        """

        all_created = False
        while not all_created:
            result = self.execute_read(query, index_names=index_names)

            if len(result) == 0:
                break

            for index in result:
                name = index['name']
                percentage = index['populationPercent']
                if index['state'] == 'ERROR':
                    MyLogger.get_instance().log_error(f"Index {name} is in state ERROR with percentage {percentage}")
                    raise Neo4jIndexError(name)
                else:
                    MyLogger.get_instance().log(f"Index {name} is in state POPULATING with percentage {percentage}")

            time.sleep(time_between_queries) #do not bombard database with queries

        MyLogger.get_instance().log(f"All indexes are in state ONLINE and populated")
        return

    def get_all_labels_in_graph(self) -> list[str]:
        """
        Method that returns all node types that are in the graphs, excluding those used to manage system
        :return: `list[str]` With all node types that are in the graph
        """

        node_label_q = "\" AND label <> \"".join([ n_t_str+Neo4jDBClient._FREE_NODE_ID_POSTFIX for n_t_str in NodeTypes.get_data_n_t_str()])

        return self.execute_read(f"""
        CALL db.labels() 
        YIELD label 
        WHERE label <> "{NodeTypes.VERSION.value}" AND 
              label <> "{NodeTypes.CURRENT_VERSION.value}" AND 
              label <> "{NodeTypes.TMP_DOMAIN.value}" AND
              label <> "{NodeTypes.ND_ID_CNT.value}" AND
              label <> "{node_label_q}"
        RETURN collect(label) AS lab
        """)[0]['lab']

    def get_all_relationships_in_graph(self) -> list[str]:
        """
        Method that returns all relationships that are in graph
        :return: `list[str]` with all relationships types
        """
        return self.execute_read(f"""
        CALL db.relationshipTypes()
        YIELD relationshipType
        RETURN collect(relationshipType) AS rel
        """)[0]['rel']


    def delete_graph_version(self, version: int, force: bool = False) -> bool:
        """
        Method that deletes one version of graph
        :param version: `int` specifying version that will be deleted
        :param force: `bool` used to bypass checks like if deleted version is current graph version
        :return: True on success, False otherwise
        """
        current_version = self.get_current_active_graph_version()
        if current_version == version and not force:
            MyLogger.get_instance().log_warning(f"Tried to delete current graph version which is version {version}!")
            return False

        #TODO BATCHES BABY
        labels = self.get_all_labels_in_graph()
        for label in labels:
            query = f"""
            MATCH (n:{label} {{graph_version: {version} }})
            DETACH DELETE n
            """
            self.execute_write(query)

        self.execute_write(f"MATCH (n: {NodeTypes.VERSION.value} {{version: {version} }} ) DELETE n")
        if force and current_version == version:
            MyLogger.get_instance().log_warning(f"Deleted current version of graph which was version {version}! Force flag was set")
            self.execute_write(f"MATCH (n: {NodeTypes.CURRENT_VERSION.value} {{version: {version} }} ) DELETE n")
        return True

    def _create_edge_copy_query(self, v_label: str, relation: str, current_version: int) -> str:

        copy_query = f"""
        WITH n, copy
            OPTIONAL MATCH (n)-[rel:{relation}]->(v:{v_label})
            WHERE v.graph_version = {current_version}
            OPTIONAL MATCH (v_copy:{v_label} {{
                node_id: v.node_id,
                graph_version: {current_version + 1}
            }})
            WITH DISTINCT n, copy, rel, v_copy
            FOREACH (_ IN CASE WHEN rel IS NOT NULL AND v_copy IS NOT NULL THEN [1] ELSE [] END |
                CREATE (copy)-[rel_copy:{relation}]->(v_copy)
                SET rel_copy = properties(rel)
            )
        """
        #for future me: Optional match is used because most of those relation combinations doesn't exist in the graph
        # and if I would use normal match, which doesn't return null, then it would not work, and it would end early
        # foreach is used to create edge for each n->v where there is relation and copy of v

        #domain only creates edge going out, other domain creates edge going back
        if v_label != NodeTypes.DOMAIN.value:

            copy_query += f"""
            WITH n, copy
                OPTIONAL MATCH (v:{v_label})-[rel:{relation}]->(n)
                WHERE v.graph_version = {current_version}
                OPTIONAL MATCH (v_copy:{v_label} {{
                    node_id: v.node_id,
                    graph_version: {current_version + 1}
                }})
                WITH DISTINCT n, copy, rel, v_copy
                FOREACH (_ IN CASE WHEN rel IS NOT NULL AND v_copy IS NOT NULL THEN [1] ELSE [] END |
                    CREATE (v_copy)-[rel_copy:{relation}]->(copy)
                    SET rel_copy = properties(rel)
                )
            """
        return copy_query

    def create_new_version_mirror_of_graph(self) -> int:

        all_used_versions = self.get_existing_versions()

        if len(all_used_versions) > 3:
            raise TooManyVersions

        self._create_indexes_for_graph_copy()
        current_version = self.get_current_active_graph_version()
        labels = self.get_all_labels_in_graph()
        relations = self.get_all_relationships_in_graph()

        MyLogger.get_instance().log(f"Creating new version copy of graph v.{current_version}")
        for label in labels:

            label_max_id = self.get_max_id_of_node_type(NodeTypes.from_str(label))

            copy_query = f"""
            UNWIND $ids as id 
            MATCH (n: {label} {{node_id: id}})
            WHERE n.graph_version = {current_version}
            CREATE (copy: {label})
            SET copy = n {{.*, graph_version: {current_version + 1}}}
            """
            MyLogger.get_instance().log_debug(f"Creating new version copy of nodes {label}...")
            #self.execute_write(copy_query)

            #TODO
            #self.send_query_in_batches(copy_query,  ,"ids")

            MyLogger.get_instance().log_debug(f"Created new version copy of nodes {label}")


        domain_max_id = self.get_max_id_of_node_type(NodeTypes.DOMAIN)

        #TODO this will no longer work because now there are other types of nodes that have edges between each other
        edge_copy_match = f"""
            MATCH(n: {NodeTypes.DOMAIN.value})
            WHERE n.graph_version = {current_version}
        
            MATCH(copy: {NodeTypes.DOMAIN.value})
            WHERE copy.graph_version = {current_version + 1} AND copy.domain_name = n.domain_name
            
            """

        for v_label in labels:
            for relation in relations:
                edge_copy_match += self._create_edge_copy_query(v_label, relation, current_version)

        MyLogger.get_instance().log_debug(f"Coping edges into new version...")
        self.execute_write(edge_copy_match)
        self.set_new_graph_version_node(current_version + 1)
        MyLogger.get_instance().log_debug(f"Copied all edges")
        MyLogger.get_instance().log(f"Created new version of graph. New graph version is v.{current_version + 1}")
        return current_version + 1


# this is universal solution that will work, but for now, all other types of nodes are only connected with domain nodes therefore
# only this will be coded for now but I leave this here if I decide to model something that doesn't follow this pattern
 #       for label in labels:

 #           edge_copy_match = f"""
 #           MATCH (n: {label} {{version: {current_version}}}), (copy: {label} {{version:  {current_version + 1} }})
 #           WHERE n.node_id = copy.node_id
 #           """
 #           if label == NodeTypes.DOMAIN.value:
 #               for v_label in labels:
 #                   edge_copy_match += self._create_edge_copy_query(v_label, current_version)
 #
 #           else:
 #               #in the future I might code some storage to store pairings
 #               v_label = NodeTypes.DOMAIN.value
 #               edge_copy_match += self._create_edge_copy_query(v_label, current_version)
#
 #           self.execute_write(edge_copy_match)
#
 #       return current_version + 1

    def create_nodes(self, node_type: NodeTypes | str, rows: list[dict], edit_type: EditTypes = EditTypes.IGNORE_EXISTING) -> None:
        """
        Method for creating nodes in the graph
        :param node_type: Either `NodeTypes` or `str` specifying node types, (best to use NodeTypes)
        :param rows: `list[dict]` with data that will be stored in the node's
        :param edit_type: `EditTypes` enum specifying how to handle case when created node is duplicate in graph
        :return: None
        """

        if len(rows) <= 0:
            return

        items_str = ",".join([str(key) + ": row." + str(key) for key in list(rows[0].keys())])

        create_query = "UNWIND $rows AS row "
        query = ("CREATE" if edit_type == EditTypes.IGNORE_EXISTING else 'MERGE') + f"(:{node_type if type(node_type) == str else node_type.value} {{ {items_str} }})"
        create_query += query

        self.execute_write(create_query, rows=rows)

    class EdgeCreationQueryOptions(Enum):

        NO_WEIGHT_NO_REVERSE = 0
        NO_WEIGHT_REVERSE = 1
        WEIGHT_NO_REVERSE = 2
        WEIGHT_REVERSE = 3

    E_OPTION = "option"
    E_MATCH1 = "m1"
    E_MATCH2 = "m2"
    E_EDGE_T = "e_t"
    E_NODE_T1 = "n_t1"
    E_NODE_T2 = "n_t2"
    E_EDGE_VALUE_NAME = "e_v"
    E_VERSION = 'e_vers'
    E_NO_DUP = 'e_no_dup'

    def _create_edge_creation_query(self, option: EdgeCreationQueryOptions, m1: str, m2: str, e_t: EdgeTypes | str,
                                    n_t1: NodeTypes | str, n_t2: NodeTypes | str, e_v: str | None, e_vers: int = -1, e_no_dup: bool = False) -> dict[str, str]:

        version = e_vers if e_vers != -1 else self.get_current_active_graph_version()
        query = f"""
        UNWIND $edges AS edge
        MATCH (u: {n_t1.value if type(n_t1) == NodeTypes else n_t1} {{{m1}: edge.u {get_version_query(version,False)} }}), 
              (v: {n_t2.value if type(n_t1) == NodeTypes else n_t2} {{{m2}: edge.v {get_version_query(version,False)} }}) 
        """
        creation_command = "CREATE" if e_no_dup else "MERGE"

        e_t = e_t.value if type(e_t) == EdgeTypes else e_t
        if option == self.EdgeCreationQueryOptions.NO_WEIGHT_NO_REVERSE or option == self.EdgeCreationQueryOptions.NO_WEIGHT_REVERSE:
            query += f" {creation_command} (u)-[:{e_t}]->(v)"

            if option == self.EdgeCreationQueryOptions.NO_WEIGHT_REVERSE:
                query += f" {creation_command} (v)-[:{e_t}]->(u)"

        elif option == self.EdgeCreationQueryOptions.WEIGHT_NO_REVERSE or option == self.EdgeCreationQueryOptions.WEIGHT_REVERSE:

            if e_v is None:
                MyLogger.get_instance().log_warning(
                    f"Edge value was not given a name to edge type {e_t}. Default value \"weight\" will be used")
                e_v = "weight"

            query += f" {creation_command} (u)-[:{e_t} {{{e_v}: edge.weight}}]->(v)"

            if option == self.EdgeCreationQueryOptions.WEIGHT_REVERSE:
                query += f" {creation_command} (v)-[:{e_t.value} {{{e_v}: edge.weight}}]->(u)"

        return {"edges": query}

    def create_edges(self, query: tuple[str, str] | dict, rows: list[dict]) -> None:
        """
        Method for creating edges in graph
        :param query: `dict` edge creation query parameters from which query is build, best to use this option ``OR``
            `tuple[str, str]` where first `str` is custom query string and second `str` is parameter name
        :param rows: `list[dict]` List with edges, if query is build from parameters then dict must consist from 2 keys
            where the first key (u) is start of the edge and the second key (v) is end of edge
        :return: None
        """

        if type(query) != dict:
            self.execute_write(query[0], **{query[1]: rows})
        else:
            query_str = self._create_edge_creation_query(**query)['edges']
            self.execute_write(query_str, edges=rows)
        return

    @staticmethod
    def get_node_replace_query(old_var: str, new_var: str, call: bool = False) -> str:
        """
        Method that returns query subpart for node replacing
        :param old_var: `str` Old noded variable that will be replaced
        :param new_var: `str` New noded variable that will be replaced
        :param call: `bool` Whether to use replace query as sub-query
        :return: `str` query
        """

        return f"""
        {f'CALL ('+old_var+','+new_var+'){' if call else ''}
        WITH {old_var} AS old, {new_var} AS new
        MATCH (old)-[r]->()
        CALL apoc.refactor.from(r, new) YIELD input, output
        
        WITH old, new
        MATCH ()-[r]->(old)
        CALL apoc.refactor.to(r, new) YIELD input, output
        
        WITH  old
        DETACH DELETE old
        {'}' if call else ''}
        """
    #        DELETE r
    #    DELETE r_rev
    def check_label_exists(self, label: NodeTypes | str) -> bool:
        label_str = label if type(label) == str else label.value
        return len(self.execute_read(f"MATCH (n:{label_str}) RETURN n LIMIT 1")) != 0

    def _create_cartesian_batches(self, func, data: list[tuple[str, list]], batch_build: dict[str, list],
                                  batch_size: int, batch_delay: float) -> None:

        if len(data) == 0:
            return

        key, rows = data[0]
        rest = data[1:]
        rest_empty = len(rest) == 0

        for cnt in range(0, len(rows), batch_size):
            batch = rows[cnt:cnt + batch_size]
            batch_build[key] = batch

            if rest_empty:
                time.sleep(batch_delay)
                MyLogger.get_instance().log_debug(f"Creating cartesian batch starting at {cnt} for key {key}...")
                func(**batch_build)
            else:
                self._create_cartesian_batches(func, rest, batch_build, batch_size, batch_delay)

    def _send_batch(self, func, data: list[dict] | tuple[str, list], batch_size: int, batch_delay: float) -> None:

        mode = type(data) == list
        rows = data if mode else data[1]

        for cnt in range(0, len(rows), batch_size):
            time.sleep(batch_delay)
            MyLogger.get_instance().log(f"Creating batch starting at {cnt}...")
            batch = rows[cnt:cnt + batch_size]

            if mode:
                func(batch)
            else:
                func(**{data[0]: batch})

    def send_query_in_batches_func(self, func, rows: list[dict] | dict[str, list], batch_size: int | None = None,
                                   batch_delay: float | None = None, as_one_param: bool = True) -> None:
        """
        Function that sends query in batches if there is high chance that query is too large to handled by database server
        :param func: Function that sends query that takes rows as it's parameter
        :param rows: Either `list[dict]` where each dict is one input row (this is for functions that have specific param
             for input rows) ``or`` `dict[str, list]` where the `list` part are data that will be unwinded in query
            function's parameter name and data
        :param batch_size: `int` size of batch, if `None` is provided, instances default value is used
        :param batch_delay: `float` delay between two queries, if `None` is provided, instances default value is used
        :param as_one_param: `bool` whether to send query as one parameter or not, has only meaning when rows is `dict` and there is more than one item in it, default is True
        :return: None
        """

        if batch_size is None:
            batch_size = self._batch_size
        if batch_delay is None:
            batch_delay = self._batch_delay

        if batch_size < 1:
            return

        if type(rows) is dict:
            if as_one_param:
                self._create_cartesian_batches(func, list(rows.items()), {}, batch_size, batch_delay)
            else:
                # I mean I know this is a bit stupid but there could be some obscure use of this mode
                for key, val in rows.items():
                    self._send_batch(func, (key, val), batch_size, batch_delay)
        else:
            self._send_batch(func, rows, batch_size, batch_delay)


def get_version_query(version: int, alone: bool, variable: str | None = None) -> str:
    return ('' if alone else ', ') + (variable+'.' if variable is not None else '')  +f"graph_version: {version}"



"""
        MATCH (old)-[r]->(other)
        WITH old, new, r, other
        CALL apoc.merge.relationship(
            startNode1,
            type(r),
            properties(r),
            {{}},
            endNode1
        ) YIELD rel AS rel1
        DELETE r
        
        MATCH (other2)-[r_rev]->(old)
        WITH old, new, r, r_rev, other, other2


        CALL apoc.merge.relationship(
            startNode2,
            type(r_rev),
            properties(r_rev),
            {{}},
            endNode2
        ) YIELD rel AS  rel2

        
"""