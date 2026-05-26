import json

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

@dataclass
class Neo4jDbConf:
    host: str
    port: int
    user: str
    pwd: str
    db: str
    batch_delay: float
    batch_size: int

    @classmethod
    def from_dict(cls, data: dict) -> "Neo4jDbConf":
        """
        Build a Neo4jDbConf object from a dictionary loaded from JSON
        """
        return cls(
            host=data["host"],
            port=data["port"],
            user=data["user"],
            pwd=data["pwd"],
            db=data["db"],
            batch_delay=data["batch_delay"],
            batch_size=data["batch_size"],
        )

@dataclass
class KHopNeighParams:
    max_depth: int
    max_sample_size: int
    walk_seed: int

    @classmethod
    def from_dict(cls, data: dict) -> "KHopNeighParams":
        """
        Build a KHopNeighParams object from a dictionary
        """
        return cls(
            max_depth=data["max_depth"],
            max_sample_size=data["max_sample_size"],
            walk_seed=data["walk_seed"],
        )

@dataclass
class GraphRepoConf:
    neo4j_db_conf: Neo4jDbConf
    k_hop_neigh_params: KHopNeighParams

    @classmethod
    def from_dict(cls, data: dict) -> "GraphRepoConf":
        """
        Build the GraphRepoConf object from nested dictionaries
        """
        return cls(
            neo4j_db_conf=Neo4jDbConf.from_dict(data["neo4j_db_conf"]),
            k_hop_neigh_params=KHopNeighParams.from_dict(data["k_hop_neigh_params"]),
        )

@dataclass
class EvalParams:
    w_size: int
    embedd_dim: int
    neg_size: int
    lr: float
    walk_seed: int
    regress_max_iters: int

    @classmethod
    def from_dict(cls, data: dict) -> "EvalParams":
        """
        Build an EvalParams object from a dictionary
        """
        return cls(
            w_size=data["w_size"],
            embedd_dim=data["embedd_dim"],
            neg_size=data["neg_size"],
            lr=data["lr"],
            walk_seed=data["walk_seed"],
            regress_max_iters=data["regress_max_iters"],
        )

@dataclass
class EvalAppConf:
    result_removal_time: float
    max_evaluations: int
    max_metapath2vec_evaluations: int
    eval_params: EvalParams

    @classmethod
    def from_dict(cls, data: dict) -> "EvalAppConf":
        """
        Build the EvalAppConf object, including the nested EvalParams
        """
        return cls(
            result_removal_time=data["result_removal_time"],
            max_evaluations=data["max_evaluations"],
            max_metapath2vec_evaluations=data["max_metapath2vec_evaluations"],
            eval_params=EvalParams.from_dict(data["eval_params"]),
        )

@dataclass
class LoggingConf:
    log_file: str
    log_level: str

    @classmethod
    def from_dict(cls, data: dict) -> "LoggingConf":
        """
        Build a LoggingConf object from a dictionary
        """
        return cls(
            log_file=data["log_file"],
            log_level=data["log_level"],
        )

@dataclass
class ServerConf:
    host: str
    port: int
    deploy_option: str
    auth_header_name: str = "pass"
    pvd_hash: Optional[str] = None
    cert_file: Optional[str] = None
    key_file: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict) -> "ServerConf":
        """
                Build a ServerConf object from a dictionary

                data.get(...) is used because these are optional
                """
        return cls(
            host=data["host"],
            port=data["port"],
            deploy_option=data["deploy_option"],
            auth_header_name=data.get("auth_header_name", "PVD"),
            pvd_hash=data.get("pvd_hash"),
            cert_file=data.get("cert_file"),
            key_file=data.get("key_file"),
        )

class Config:
    _instance = None

    def __init__(self, path_to_config: str):
        """
        Load the JSON file and build all nested objects
        """
        if getattr(self, "_initialized", False):
            return
        self._initialized = True

        with open(Path(path_to_config), "r", encoding="utf-8") as f:
            data = json.load(f)

        self.graph_repo_conf = GraphRepoConf.from_dict(data["graph_repo_conf"])
        self.eval_app_conf = EvalAppConf.from_dict(data["eval_app_conf"])
        self.logging_conf = LoggingConf.from_dict(data["logging_conf"])
        self.server_conf = ServerConf.from_dict(data["server_conf"])

    @classmethod
    def get_instance(cls, path_to_config: str = "config.json") -> "Config":
        """
        Create and return the single shared Config instance
        """
        if cls._instance is None:
            cls._instance = cls(path_to_config)
        return cls._instance