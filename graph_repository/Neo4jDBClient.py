from neo4j import GraphDatabase
from misc.Logger import MyLogger
from graph_repository.workers.common.GraphTypes import NodeTypes
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
        with self.driver.session( database= self.database) as s:
            return s.execute_write(lambda tx: tx.run(query, **params).data())

    def execute_read(self, query, **params):
        with self.driver.session( database= self.database) as s:
            return s.execute_read(lambda tx: tx.run(query, **params).data())

    def get_max_id_of_node_type(self, node_type: NodeTypes) -> int:
        return self.execute_read(f"MATCH (n:{node_type.value}) RETURN max(n.node_id) AS {node_type.value}_max_id")


    def create_nodes(self, node_type: NodeTypes | str, rows: list[dict]) -> None:

        if len(rows) <= 0:
            return

        items_str = ",".join([str(key) + ": row." + str(key) for key in list(rows[0].keys())])

        create_query = f"""
        UNWIND $rows AS row
        CREATE(:{node_type if type(node_type) == str else node_type.value} {{ {items_str} }})
        """

        self.execute_write(create_query, rows=rows)
