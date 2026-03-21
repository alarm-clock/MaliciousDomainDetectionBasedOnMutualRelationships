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

    VERSION_CURR = -2
    VERSION_MAX = -1

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

    def __del__(self):
        self.close()

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
        self.execute_write(f"CREATE (:{NodeTypes.MAINTENANCE.neo4j})")

    def remove_maintenance_node(self) -> None:
        self.execute_write(f"MATCH (n:{NodeTypes.MAINTENANCE.neo4j}) DETACH DELETE n")

    def is_graph_in_maintenance(self) -> bool:
        return self.execute_read(f"MATCH (n: {NodeTypes.MAINTENANCE.neo4j}) RETURN n AS is")[0]['is']

    def get_max_id_of_node_type(self, n_t: NodeTypes | str) -> int:
        """
        Method that returns max node_id of given ``n_t`` that is present in the graph
        :param n_t: `NodeTypes` node type for which max id will be returned
        :return: `int` max id
        """
        n_t_str = n_t.neo4j if type(n_t) == NodeTypes else n_t
        return self.execute_read(f"MATCH (n:{n_t_str}) RETURN max(n.node_id) AS {n_t_str}_max_id")[0][f'{n_t_str}_max_id']

    def get_current_active_graph_version(self) -> int:
        """
        Method that returns current graph version that should be used for computation
        :return: `int` current version
        """
        active_version = self.execute_read(f"MATCH (v: {NodeTypes.MAINTENANCE.neo4j}) RETURN v.version AS vers")
        if len(active_version) == 0:
            return -1

        return active_version[0]['vers']

    def get_existing_versions(self) -> list[int]:
        """
        Method that returns all existing version of graph
        :return: `list[int] all graph versions
        """
        return self.execute_read(f"MATCH (v: {NodeTypes.MAINTENANCE.neo4j}) RETURN collect(v.version) AS vers")[0]['vers']

    def get_existing_versions_nodes(self) -> list[dict[str, int]]:
        return self.execute_read(
            f"MATCH (v: {NodeTypes.MAINTENANCE.neo4j}) RETURN collect({{version: v.version, users: v.n_users}}) AS vers"
        )[0]['vers']

    def get_n_existing_versions(self) -> int:
        return self.execute_read(f'MATCH (v: {NodeTypes.MAINTENANCE.neo4j}) RETURN COUNT(v) AS cnt')[0]['cnt']

    def set_new_graph_version_node(self, new_version: int) -> None:
        """
        Method for setting new graph version node, if such version already exists then nothing will happen
        :param new_version: `int` new graph version number
        :return: None
        """
        query = f"""
        MERGE (: {NodeTypes.MAINTENANCE.neo4j} {{version: {new_version}, n_users: 0}})
        """
        self.execute_write(query)

    def create_node_id_cnt(self, n_t: NodeTypes | str, start_value: int = 0) -> None:
        """
        Method that creates node_id counter for given ``n_t`` node type, if counter for given ``n_t`` exists, nothing will happen
        :param n_t: `NodeTypes` for which counter will be created
        :param start_value: `int` Counters start value
        :return: None
        """
        n_t_str = n_t.neo4j if type(n_t) == NodeTypes else n_t
        self.execute_write(f"MERGE (:{NodeTypes.MAINTENANCE.neo4j} {{ cnt_name: \"{n_t_str}\", val: {start_value} }}) ")

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
            MATCH (free_id: {n_t.neo4j}{Neo4jDBClient._FREE_NODE_ID_POSTFIX})
            WITH free_id
            LIMIT {req_number_of_ids}
            WITH collect(free_id) AS free_nodes
            WITH free_nodes, [x IN free_nodes | x.node_id] as reused_ids
            
            FOREACH (x IN free_nodes | DELETE x)
            
            WITH reused_ids, {req_number_of_ids} - size(reused_ids) AS rem_cnt
            
            CALL(rem_cnt){{
                WITH rem_cnt
                WHERE rem_cnt > 0
                MATCH (counter: {NodeTypes.MAINTENANCE.neo4j} {{cnt_name: '{n_t.neo4j}' }})
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
            OPTIONAL MATCH (free_id: {n_t.neo4j}{Neo4jDBClient._FREE_NODE_ID_POSTFIX})
            WITH free_id
            LIMIT 1
            
            CALL (free_id) {{
                WITH free_id
                WHERE free_id IS NOT NULL
                WITH free_id.node_id AS free_node_id, free_id
                DELETE free_id
                RETURN free_node_id

                UNION
                
                WITH free_id
                WHERE free_id IS NULL
                MATCH (counter: {NodeTypes.MAINTENANCE.neo4j} {{cnt_name: '{n_t.neo4j}' }})
                SET counter.val = counter.val + 1
                RETURN counter.val - 1 AS free_node_id
            }}
            
            RETURN free_node_id
            """


            f"""
            OPTIONAL MATCH (free_id: {n_t.neo4j}{Neo4jDBClient._FREE_NODE_ID_POSTFIX})
            WITH free_id
            LIMIT 1
            
            MATCH (counter: {NodeTypes.MAINTENANCE.neo4j} {{cnt_name: '{n_t.neo4j}' }})

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

    def check_and_create_node_id_cnt(self, n_t: NodeTypes | str) -> None:
        """
        Method that creates node_id counter for given node type if there is no such counter, otherwise does nothing
        :param n_t: `NodeTypes | str` node type
        :return: None
        """

        n_t_str = n_t.neo4j if type(n_t) == NodeTypes else n_t
        query = f"""
        MERGE (n: {NodeTypes.MAINTENANCE.neo4j} {{cnt_name: '{n_t_str}'}})
        ON CREATE SET n.val = 0 
        """
        self.execute_write(query)

    def get_free_node_id(self, n_t: NodeTypes, req_number_of_ids: int = 1) -> list[int] | int:
        """
        Method that allocates and returns specified number of node_ids for given ``n_t`` `NodeTypes`
        :param n_t: `NodeTypes` specifying for which node type these ids are
        :param req_number_of_ids: `int` required number of ids
        :return: `int | list[int]` ids that have been allocated
        """
        if req_number_of_ids < 1:
            return []

        self.check_and_create_node_id_cnt(n_t)

        res = self.execute_write(self.get_free_node_id_query(n_t, False, req_number_of_ids))
        ret_val = res[0]['free_node_id' if req_number_of_ids == 1 else 'free_node_ids']
        return ret_val

    @staticmethod
    def get_node_id_return_query(n_t: NodeTypes | str, id_var_name: str, with_survival: str, last: bool) -> str:
        """
        Method that returns query for returning node_ids of deleted nodes
        :param last: `bool` that signals that nothing will follow this query
        :param with_survival: `str` variables that should survive this query
        :param n_t: `NodeTypes | str` node type of node which's node_id is returned, can be dynamic function like "labels(var_name)[0]"
        :param id_var_name: `str` variable that holds node_id that will be returned
        :return: `str` query
        """

        return f"""
        WITH {'"'+ n_t.neo4j + '"' if type(n_t) == NodeTypes else n_t} || "{Neo4jDBClient._FREE_NODE_ID_POSTFIX}" AS del_q_n_t, 
             {with_survival} 
        CREATE (:$(del_q_n_t) {{node_id: {id_var_name} }})
        """ + ('' if last else 'WITH ' + with_survival )


    def return_unused_node_ids(self, n_t: NodeTypes, node_ids: int | list[int]) -> None:
        """
        Method for returning unused node_ids that have been allocated
        :param n_t: `NodeTypes` specifying to which node types these ids belong to
        :param node_ids: `int | list[int]` Ids that will be returned
        :return: None
        """

        query = f"""
        UNWIND $ids AS returned_id
        {Neo4jDBClient.get_node_id_return_query(n_t, 'returned_id', "returned_id", True)}
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
        OPTIONAL MATCH (old_version: {NodeTypes.MAINTENANCE.neo4j})
        DETACH DELETE old_version
        CREATE (: {NodeTypes.MAINTENANCE.neo4j} {{version: {new_current_version}}})
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

    def wait_for_index_creation(self, index_names: list[str] | None, time_between_queries: float = 8.0) -> None:
        """
        Method that waits until indexes in ``index_names`` have been created.
        :param index_names: `list[str]` of index names
        :param time_between_queries: `float` in seconds how much to wait between subsequent queries
        :return: None
        """

        query = f"""
        SHOW INDEXES
        YIELD name, state, populationPercent
        WHERE state = 'POPULATING' OR state = 'ERROR' {'AND name IN $index_names' if index_names is not None else ''} 
        RETURN name, state, populationPercent
        """

        all_created = False
        while not all_created:

            if index_names is not None:
                result = self.execute_read(query, index_names=index_names)
            else:
                result = self.execute_read(query)

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
        WHERE label <> "{NodeTypes.MAINTENANCE.neo4j}" AND 
              label <> "{NodeTypes.MAINTENANCE.neo4j}" AND 
              label <> "{NodeTypes.MAINTENANCE.neo4j}" AND
              label <> "{NodeTypes.MAINTENANCE.neo4j}" AND
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
            MyLogger.get_instance().log_warning(f"Tried to delete current graph version which is version v.{version}!")
            return False

        labels = self.get_all_labels_in_graph()
        for label in labels:
            query = f"""
            CALL apoc.periodic.iterate(
                "MATCH (n:{label} {{graph_version: {version} }}) RETURN n",
                "DETACH DELETE n",
                {{
                    batchSize: {self._batch_size},
                    parallel: true,
                    batchMode: 'BATCH'
                }}
            ) YIELD batch
            RETURN 0
            """
            self.execute_write(query)

        self.execute_write(f"MATCH (n: {NodeTypes.MAINTENANCE.neo4j} {{version: {version} }} ) DELETE n")
        if force and current_version == version:
            MyLogger.get_instance().log_warning(f"Deleted current version of graph which was version v.{version}! Force flag was set")
            self.execute_write(f"MATCH (n: {NodeTypes.MAINTENANCE.neo4j} {{version: {version} }} ) DELETE n")
        else:
            MyLogger.get_instance().log(f"Deleted graph version v.{version}, current graph version is v.{current_version}")
        return True

    def delete_unused_graph_versions(self) -> bool:
        """
        Method that deletes unused graph versions, e.g. graph versions with 0 users
        :return: `bool` flag indicating if any graph version was deleted
        """

        existing_versions = self.get_existing_versions_nodes()
        current_version = self.get_current_active_graph_version()
        deleted = False
        for version_dict in existing_versions:
            if version_dict["users"] > 0 or version_dict['version'] == current_version:
                continue

            deleted = True
            self.delete_graph_version(version_dict['version'])

        return deleted

    def _create_node_version_index(self) -> None:

        labels = self.get_all_labels_in_graph()
        index_names = [label+"_version" for label in labels]
        for label in labels:
            query = f"""
            CREATE INDEX {label}_version
            IF NOT EXISTS
            FOR (n: {label}) 
            ON n.graph_version
            """

            self.execute_write(query)

        self.wait_for_index_creation(index_names,10.0)

    def create_new_version_mirror_of_graph(self) -> int:

        if self.get_n_existing_versions() > 3:

            if not self.delete_unused_graph_versions():
                raise TooManyVersions

        self._create_indexes_for_graph_copy()
        current_version = self.get_current_active_graph_version()
        labels = self.get_all_labels_in_graph()

        MyLogger.get_instance().log(f"Creating new version copy of graph v.{current_version}")
        for label in labels:

            copy_query = f"""
            
            CALL apoc.periodic.iterate(
                "MATCH (n: {label} {{graph_version: {current_version}}}) RETURN n",
                "CREATE (copy: {label}) SET copy = n {{.*, graph_version: {current_version + 1}}}",
                {{
                    batchSize: {self._batch_size},
                    parallel: true,
                    batchMode: 'BATCH'
                }}
            
            ) YIELD batch
            
            RETURN batch
            """
            MyLogger.get_instance().log_debug(f"Creating new version copy of nodes {label}...")
            res = self.execute_write(copy_query)
            MyLogger.get_instance().log_debug(f"Created new version copy of nodes {label}: res is {res[0]}")


        self._create_node_version_index()
        for u_label in labels:
            for v_label in labels:
                edge_copy_query = f"""
                CALL apoc.periodic.iterate(
                    "MATCH (n: {u_label} {{ graph_version: {current_version}}})-[r]->(m: {v_label} {{graph_version: {current_version}}})
                     WITH DISTINCT r, n, m
                     RETURN r, n.node_id AS n_id, m.node_id AS m_id
                    ",
                    "MATCH (n_copy: {u_label} {{node_id: n_id, graph_version: {current_version + 1}}}),
                           (m_copy: {v_label} {{node_id: m_id, graph_version: {current_version + 1}}})
                     CREATE (n_copy)-[rel_copy: $(type(r))]->(m_copy)
                     SET rel_copy = properties(r)
                    ",
                    {{
                        batchSize: {self._batch_size},
                        parallel: false,
                        batchMode: 'BATCH'
                    }}
                )
                """
                MyLogger.get_instance().log_debug(f"Coping edges into new version between ({u_label})->({v_label})...")
                res = self.execute_write(edge_copy_query)
                MyLogger.get_instance().log_debug(f"Copied all edges between {u_label} and {v_label}, res: {res}")

        self.set_new_graph_version_node(current_version + 1)
        MyLogger.get_instance().log_debug(f"Copied all edges")
        MyLogger.get_instance().log(f"Created new version of graph. New graph version is v.{current_version + 1}")
        return current_version + 1

    def create_tmp_node(self, tmp_domain: dict[str, Any]) -> int | None:
        """
        Method for creating a temporary node in the graph that will hold given data
        :param tmp_domain: `dict[str, Any]` Temporary domain data, must hold at least domain name
        :return: Temporary node's node_id on success otherwise None (if tmp_domain doesn't have domain name)
        """
        if tmp_domain.get('domain_name') is None:
            return None

        allocated_id = self.get_free_node_id(NodeTypes.TMP_DOMAIN)
        tmp_domain['node_id'] = allocated_id
        item_str = self.create_pre_filled_item_string(tmp_domain)
        query = f"""
        CREATE (:{NodeTypes.MAINTENANCE.neo4j} {{ {item_str} }})
        """
        self.execute_write(query)

        return allocated_id

    def create_nodes(self, n_t: NodeTypes | str, rows: list[dict], edit_type: EditTypes = EditTypes.IGNORE_EXISTING) -> None:
        """
        Method for creating nodes in the graph
        :param n_t: Either `NodeTypes` or `str` specifying node types, (best to use NodeTypes)
        :param rows: `list[dict]` with data that will be stored in the node's
        :param edit_type: `EditTypes` enum specifying how to handle case when created node is duplicate in graph
        :return: None
        """

        if len(rows) <= 0:
            return

        items_str = Neo4jDBClient.create_unwind_item_string(rows, "row")
        create_query = "UNWIND $rows AS row "
        query = ("CREATE" if edit_type == EditTypes.IGNORE_EXISTING else 'MERGE') + f"(:{n_t if type(n_t) == str else n_t.neo4j} {{ {items_str} }})"
        create_query += query

        self.execute_write(create_query, rows=rows)

    @staticmethod
    def create_unwind_item_string(rows: list[dict], unwind_var_name: str) -> str | None:
        if len(rows) == 0:
            return None

        return  ",".join([str(key) + ":" + unwind_var_name + "." + str(key) for key in list(rows[0].keys())])

    @staticmethod
    def create_pre_filled_item_string(node: dict[str, Any]) -> str:
        return ','.join([ str(key) + ':' + str(value) + ' ' for key, value in node.items()])

    @staticmethod
    @deprecated
    def get_delete_nodes_edge_free_neighbours(
            var_name: str,
            as_subquery: bool,
            only_rels_with_domains: bool = True ,
            also_delete_domains: bool = False,
            with_survival: str = "" ) -> str:
        """
        Method that returns (sub)query for deleting neighboring nodes that have no other relation then that with `var_name`
        :param var_name: `string` variable name of the node which's neighbors should be checked and deleted
        :param as_subquery: `bool` flag indicating if query should be used inside CALL (...) {...}
        :param only_rels_with_domains: `bool` flag indicating if only relations with domains should be counted, defaults to `True`
        :param also_delete_domains: `bool` flag indicating that also domains should be checked, defaults to `False`
        :param with_survival: `str` that is used to pass variables that should survive WITH, do not use if ``as_subquery`` is True, defaults to ""
        :return: `str` (sub)query or "" if invalid combination of parameters was used
        """

        if as_subquery and with_survival.lstrip() != "":
            return ""

        where_label = f":{NodeTypes.MAINTENANCE.neo4j}" if only_rels_with_domains else ""
        do_not_match_domains = f'AND NOT m_del_var:{NodeTypes.MAINTENANCE.neo4j}' if not also_delete_domains else ''

        if with_survival != "":
            removed_white_space = with_survival.lstrip()
            if removed_white_space != "":
                with_survival = (',' if removed_white_space[0] != ',' else "" ) + with_survival

        return f"""
        {('CALL ('+var_name+'){') if as_subquery else ''}
        WITH {var_name} {with_survival}
        OPTIONAL MATCH ({var_name})-->(m_del_var)
        WITH {var_name}, m_del_var {with_survival}
        WHERE m_del_var IS NOT NULL AND COUNT {{(m_del_var)--(m_other_rel{where_label} WHERE m_other_rel <> {var_name})}} = 0 {do_not_match_domains}
        {Neo4jDBClient.get_node_id_return_query(
            "labels(m_del_var)[0]", 
            "m_del_var.node_id", 
            f'{var_name}, m_del_var {with_survival}',
            True
        )}
        DETACH DELETE m_del_var
        {'}' if as_subquery else 'WITH DISTINCT ' + var_name + ' ' + with_survival}
        """

    def delete_nodes(self, nodes: list[dict[str, Any]], n_t: NodeTypes,
                     only_rels_with_domains: bool = True, ignore_subdomains: bool = False,
                     version: int = VERSION_MAX ) -> None:
        """
        Method that deletes `nodes` and optionally deletes neighbors that won't have any other relation after `nodes` are deleted
        :param nodes: `list[dict]` of nodes where dictionary contains element name/s that will be matched to find node that will be deleted
        :param n_t: `NodeTypes` node type of deleted nodes
        :param only_rels_with_domains: `bool` flag indicating if only relations with domains should be counted, only used if `del_lone_neigh` is true, defaults to `True`
        :param ignore_subdomains: `bool` flag indicating that subdomain relations should be ignored, defaults to `False`
        :param version: `int` graph version on which's nodes will be deleted, defaults to `VERSION_MAX`
        :return: None
        """

        items_str = Neo4jDBClient.create_unwind_item_string(nodes, "node")
        if items_str is None:
            return
        where_label = f":{NodeTypes.MAINTENANCE.neo4j}" if only_rels_with_domains else ""
        ignore_subdomains = f'[:!{EdgeTypes.SUBDOMAIN.value}]' if ignore_subdomains else ''

        if version == Neo4jDBClient.VERSION_MAX:
            version = max(self.get_existing_versions())
        elif version == Neo4jDBClient.VERSION_CURR:
            version = self.get_current_active_graph_version()

        node_del_query= f"""
        UNWIND $nodes AS node
        MATCH (n: {n_t.neo4j} {{ {items_str} {get_version_query(version,False)} }})
        //must put this before opt match because otherwise rows would explode and node id would be returned many many times
        {Neo4jDBClient.get_node_id_return_query(n_t,"n.node_id", 'n', False)}
        OPTIONAL MATCH (n)-{ignore_subdomains}-(node_for_del:!{NodeTypes.MAINTENANCE.neo4j}  {{ {get_version_query(version, True)} }} )
        DETACH DELETE n

        WITH DISTINCT node_for_del WHERE node_for_del IS NOT NULL AND COUNT {{(node_for_del)--(m_other_rel{where_label})}} = 0 
        {Neo4jDBClient.get_node_id_return_query("labels(node_for_del)[0]","node_for_del.node_id", f'node_for_del', True)}
        DETACH DELETE node_for_del
        """

        MyLogger.get_instance().log_debug(f"Deleting nodes and their neighbors in graph version v.{version}")
        self.execute_write(node_del_query, nodes=nodes)
        MyLogger.get_instance().log_debug(f"Deleted nodes and their neighbors in graph version v.{version}")
        return


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
                                    n_t1: NodeTypes | str, n_t2: NodeTypes | str, e_v: str | None =  None, e_vers: int = VERSION_MAX, e_no_dup: bool = False) -> dict[str, str]:

        if e_vers == Neo4jDBClient.VERSION_MAX:
            version = max(self.get_existing_versions())
        elif e_vers == Neo4jDBClient.VERSION_CURR:
            version = self.get_current_active_graph_version()
        else:
            version = e_vers

        query = f"""
        UNWIND $edges AS edge
        MATCH (u: {n_t1.neo4j if type(n_t1) == NodeTypes else n_t1} {{{m1}: edge.u {get_version_query(version,False)} }}), 
              (v: {n_t2.neo4j if type(n_t1) == NodeTypes else n_t2} {{{m2}: edge.v {get_version_query(version,False)} }}) 
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

            query += f" {creation_command} (u)-[:{e_t} {{{e_v}: edge.{e_v}}}]->(v)"

            if option == self.EdgeCreationQueryOptions.WEIGHT_REVERSE:
                query += f" {creation_command} (v)-[:{e_t} {{{e_v}: edge.{e_v}}}]->(u)"

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
    def get_node_replace_query(old_var: str, new_var: str, old_label: str | None = None, call: bool = False) -> str:
        """
        Method that returns query subpart for node replacing
        :param old_var: `str` Old noded variable that will be replaced
        :param new_var: `str` New noded variable that will be replaced
        :param call: `bool` Whether to use replace query as sub-query
        :param old_label: `str` Old node label or `None` in which case node's label will be dynamically found and replaced
        :return: `str` query
        """

        return f"""
        {f'CALL ('+old_var+','+new_var+'){' if call else ''}
        WITH {old_var} AS old, {new_var} AS new
        REMOVE old:{'$(labels(old))' if old_label is not None else old_label}
        WITH old, new
        
        CALL apoc.refactor.mergeNodes([new, old], {{
            properties: 'discard',
            mergeRels: true
        }}) YIELD node 
        RETURN node
        {'}' if call else ''}
        """

    def check_label_exists(self, label: NodeTypes | str) -> bool:
        label_str = label if type(label) == str else label.neo4j
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

    def get_k_hop_neighborhood_universal(self, match: dict[str, Any], max_depth: int, max_sample_size: int, get_back_edges: bool):

        #TODO also add edge values, now it is not required but who knows what future holds
        query = f"""
        CALL mapoc.sampling.bfs($match, {max_depth}, {max_sample_size}, {get_back_edges}) YIELD relId
        MATCH ()-[r]-()
        WHERE elementId(r) = relId
        WITH startNode(r) AS from, endNode(r) AS to, r
        RETURN {{node_id: from.node_id, label: labels(from)[0]}} AS u,
               type(r) AS e_t,
               {{node_id: to.node_id, label: labels(to)[0]}}  AS v
        """
        return self.execute_read(query, match=match)

    def get_k_hop_neighborhood(self, n_t: NodeTypes | str, node_id: int, max_depth: int, max_sample_size: int, get_back_edges: bool):

        n_t = n_t.neo4j if type(n_t) == NodeTypes else n_t

        # TODO also add edge values, now it is not required but who knows what future holds
        query = f"""
        CALL mapoc.sampling.bfs_nd_id({n_t}, {node_id}, {max_depth}, {max_sample_size}, {get_back_edges}) YIELD relId
        MATCH ()-[r]-()
        WHERE elementId(r) = relId
        WITH startNode(r) AS from, endNode(r) AS to, r
        //not using _ to save memory
        RETURN {{nid: from.node_id, nt: labels(from)[0], l: from.label}} AS u,  
               type(r) AS et,
               {{nid: to.node_id, nt: labels(to)[0], l: to.label}}  AS v
        """

        return self.execute_read(query)


def get_version_query(version: int, alone: bool, variable: str | None = None) -> str:
    return ('' if alone else ', ') + (variable+'.' if variable is not None else '')  +f"graph_version: {version}"
