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
        return self.execute_read(f"MATCH (v: {NodeTypes.CURRENT_VERSION.value}) RETURN v.version AS vers")['vers']

    def get_existing_versions(self) -> list[int]:
        return self.execute_read(f"MATCH (v: {NodeTypes.VERSION.value}) RETURN collect(v.version) AS vers")['vers']

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
