from neo4j import GraphDatabase
from misc.Logger import MyLogger
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
            MyLogger.get_instance().log(f"Could not connect to Neo4j with error: {err}")
            print(err, file=sys.stderr)
            self._err = True
            raise CouldNotConnect(url, port, username)

        try:
            driver.verify_connectivity()
        except AuthError as err:
            MyLogger.get_instance().log(f"Authentication failed when connecting to Neo4j: {err}")
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


