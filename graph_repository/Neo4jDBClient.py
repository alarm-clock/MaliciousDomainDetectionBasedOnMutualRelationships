from neo4j import GraphDatabase
from enum import Enum
from misc.Logger import MyLogger
from graph_repository.workers.common.GraphTypes import NodeTypes, EdgeTypes
from graph_repository.workers.common.Enums import EditTypes
from neo4j.exceptions import ServiceUnavailable, AuthError
import json
import sys


class CouldNotConnect(Exception):
    def __init__(self, url: str, port: int, username: str):
        self.url = url
        self.port = port
        self.username = username
        super().__init__(f'Could not connect to Neo4j with url: {url}, port: {port}, username: {username}')


class Neo4jDBClient:
    def __init__(self, url: str, port: int, username: str, password: str, database: str):

        self._err = False
        MyLogger.get_instance().log(f"Trying to connect to Neo4j db at {url}:{port} with user {username}...")
        try:
            driver = GraphDatabase.driver(f'bolt://{url}:{port}', auth=(username, password))
        except ServiceUnavailable as err:
            MyLogger.get_instance().log_error(f"Could not connect to Neo4j with error: {err}")
            print(err, file=sys.stderr)
            self._err = True
            raise CouldNotConnect(url, port, username)

        try:
            driver.verify_connectivity()
        except AuthError as err:
            MyLogger.get_instance().log_error(f"Authentication failed when connecting to Neo4j: {err}")
            print(err, file=sys.stderr)
            self._err = True
            raise CouldNotConnect(url, port, username)

        self.driver = driver
        self.database = database

    @classmethod
    def from_config(cls, config: str):

        host = ''
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

        return Neo4jDBClient(host, port, user, pwd, db)

    def close(self):
        self.driver.close()

    def execute_write(self, query, **params):
        with self.driver.session(database=self.database) as s:
            return s.execute_write(lambda tx: tx.run(query, **params).data())

    def execute_read(self, query, **params):
        with self.driver.session(database=self.database) as s:
            return s.execute_read(lambda tx: tx.run(query, **params).data())

    def get_max_id_of_node_type(self, node_type: NodeTypes) -> int:
        return self.execute_read(f"MATCH (n:{node_type.value}) RETURN max(n.node_id) AS {node_type.value}_max_id")[f'{node_type.value}_max_id']

    def get_current_active_graph_version(self) -> int:
        return self.execute_read(f"MATCH (v: {NodeTypes.CURRENT_VERSION.value}) RETURN v.version AS vers")[0]['vers']

    def get_existing_versions(self) -> list[int]:
        return self.execute_read(f"MATCH (v: {NodeTypes.VERSION.value}) RETURN collect(v.version) AS vers")[0]['vers']

    def set_new_graph_version_node(self, new_version: int) -> None:
        query = f"""
        CREATE(: {NodeTypes.VERSION.value} {{version: {new_version}, n_users: 0}})
        """
        self.execute_write(query)

    def set_new_current_graph_version_node(self, new_current_version: int) -> None:
        query = f"""
        OPTIONAL MATCH (old_version: {NodeTypes.CURRENT_VERSION.value})
        DETACH DELETE old_version
        CREATE (: {NodeTypes.CURRENT_VERSION.value} {{version: {new_current_version}}})
        """
        self.execute_write(query)

    def _create_indexes_for_graph_copy(self):
        labels = self.get_all_labels_in_graph()

        for label in labels:
            query = f"""
            CREATE INDEX {label}_node_id_version_index
            IF NOT EXISTS
            FOR (n: {label})
            ON (n.node_id, n.graph_version);
            """

            self.execute_write(query)


    def get_all_labels_in_graph(self) -> list[str]:
        return self.execute_read(f"""
        CALL db.labels() 
        YIELD label 
        WHERE label <> "{NodeTypes.VERSION.value}" AND label <> "{NodeTypes.CURRENT_VERSION.value}" 
        RETURN collect(label) AS lab
        """)[0]['lab']

    def get_all_relationships_in_graph(self) -> list[str]:
        return self.execute_read(f"""
        CALL db.relationshipTypes()
        YIELD relationshipType
        RETURN collect(relationshipType) AS rel
        """)[0]['rel']

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
            return -1

        self._create_indexes_for_graph_copy()
        current_version = self.get_current_active_graph_version()
        labels = self.get_all_labels_in_graph()
        relations = self.get_all_relationships_in_graph()

        MyLogger.get_instance().log(f"Creating new version copy of graph v.{current_version}")
        for label in labels:

            copy_query = f"""
            MATCH (n: {label})
            WHERE n.graph_version = {current_version}
            CREATE (copy: {label})
            SET copy = n {{.*, graph_version: {current_version + 1}}}
            """
            MyLogger.get_instance().log_debug(f"Creating new version copy of nodes {label}...")
            self.execute_write(copy_query)
            MyLogger.get_instance().log_debug(f"Created new version copy of nodes {label}")

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

        if len(rows) <= 0:
            return

        items_str = ",".join([str(key) + ": row." + str(key) for key in list(rows[0].keys())])

        create_query = "UNWIND $rows AS row "
        query = "CREATE" if edit_type == EditTypes.IGNORE_EXISTING else 'MERGE' + f"(:{node_type if type(node_type) == str else node_type.value} {{ {items_str} }})"
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

    def _create_edge_creation_query(self, option: EdgeCreationQueryOptions, m1: str, m2: str, e_t: EdgeTypes,
                                    n_t1: NodeTypes, n_t2: NodeTypes, e_v: str | None) -> dict[str, str]:

        query = f"""
        UNWIND $edges AS edge
        MATCH (u: {n_t1.value} {{{m1}: edge.u }}), (v: {n_t2.value} {{{m2}: edge.v }}) 
        """

        if option == self.EdgeCreationQueryOptions.NO_WEIGHT_NO_REVERSE or option == self.EdgeCreationQueryOptions.NO_WEIGHT_REVERSE:
            query += f" MERGE (u)-[:{e_t.value}]->(v)"

            if option == self.EdgeCreationQueryOptions.NO_WEIGHT_REVERSE:
                query += f" MERGE (v)-[:{e_t.value}]->(u)"

        elif option == self.EdgeCreationQueryOptions.WEIGHT_NO_REVERSE or option == self.EdgeCreationQueryOptions.WEIGHT_REVERSE:

            if e_v is None:
                MyLogger.get_instance().log_warning(
                    f"Edge value was not given a name to edge type {e_t.value}. Default value \"weight\" will be used")
                e_v = "weight"

            query += f" MERGE (u)-[:{e_t.value} {{{e_v}: edge.weight}}]->(v)"

            if option == self.EdgeCreationQueryOptions.WEIGHT_REVERSE:
                query += f" MERGE (v)-[:{e_t.value} {{{e_v}: edge.weight}}]->(u)"

        return {"edges": query}

    def create_edges(self, rows: list[dict], query: tuple[str, str] | dict) -> None:

        if type(query) == dict:
            self.execute_write(query[0], **{query[1]: rows})
        else:
            query_str = self._create_edge_creation_query(**query)
            self.execute_write(query_str, edges=rows)

        return
