"""
File: config.py
Author: Jozef Michal Bukas <xbukas00@stud.fit.vutbr.cz>
Date: 28.03.2026
Brief: File that contains configuration classes used for loading and storing application
    configuration from JSON file, including graph repository, evaluation, logging,
    and server settings
"""

import json
import sys

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional
from misc.Logger import MyLogger


@dataclass
class KHopNeighParams:
    """
    Class that represents parameters used for k-hop neighborhood sampling and related graph
    traversal operations.
    """

    max_depth: int = 3
    max_sample_size: int = 1000
    walk_seed: int = 42

    @classmethod
    def from_dict(cls, data: dict | None) -> "KHopNeighParams":
        """
        Method that creates `KHopNeighParams` object from dictionary loaded from configuration file
        :param data: `dict` dictionary containing k-hop neighborhood parameter values
        :return: `KHopNeighParams` created object with k-hop neighborhood parameters
        """
        if data is None:
            return cls()

        return cls(
            max_depth=data.get("max_depth",KHopNeighParams.max_depth),
            max_sample_size=data.get("max_sample_size",KHopNeighParams.max_sample_size),
            walk_seed=data.get("walk_seed",KHopNeighParams.walk_seed),
        )


@dataclass
class GraphRepoConf:
    """
    Class that represents configuration of graph repository, including Neo4j database settings
    and k-hop neighborhood parameters.
    """

    neo4j_db_conf: str
    k_hop_neigh_params: KHopNeighParams

    @classmethod
    def from_dict(cls, data: dict) -> "GraphRepoConf":
        """
        Method that creates `GraphRepoConf` object from nested dictionaries loaded from configuration file
        :param data: `dict` dictionary containing graph repository configuration values
        :return: `GraphRepoConf` created object with graph repository configuration
        """
        return cls(
            neo4j_db_conf=data["neo4j_db_conf"],
            k_hop_neigh_params=KHopNeighParams.from_dict(data.get("k_hop_neigh_params")),
        )


@dataclass
class EvalParams:
    """
    Class that represents parameters used for domain evaluation and model-related computation.
    """

    w_size: int = 1
    embedd_dim: int = 64
    neg_size: int = 5
    lr: float = 0.01
    walk_seed: int = 42
    regress_max_iters: int = 300

    @classmethod
    def from_dict(cls, data: dict | None) -> "EvalParams":
        """
        Method that creates `EvalParams` object from dictionary loaded from configuration file
        :param data: `dict` dictionary containing evaluation parameter values
        :return: `EvalParams` created object with evaluation parameters
        """
        if data is None:
            return cls()

        return cls(
            w_size=data.get("w_size", EvalParams.w_size),
            embedd_dim=data.get("embedd_dim", EvalParams.embedd_dim),
            neg_size=data.get("neg_size", EvalParams.neg_size),
            lr=data.get("lr", EvalParams.lr),
            walk_seed=data.get("walk_seed", EvalParams.walk_seed),
            regress_max_iters=data.get("regress_max_iters", EvalParams.regress_max_iters)
        )


@dataclass
class EvalAppConf:
    """
    Class that represents configuration of evaluation application, including evaluation limits,
    result lifetime, and model parameters.
    """

    eval_params: EvalParams = EvalParams.from_dict(None)
    result_removal_time: float= 600.0
    max_evaluations: int = 24
    max_metapath2vec_evaluations: int = 24

    @classmethod
    def from_dict(cls, data: dict | None) -> "EvalAppConf":
        """
        Method that creates `EvalAppConf` object from dictionary loaded from configuration file
        :param data: `dict` dictionary containing evaluation application configuration values
        :return: `EvalAppConf` created object with evaluation application configuration
        """
        if data is None:
            return cls()

        return cls(
            result_removal_time=data.get("result_removal_time",EvalAppConf.result_removal_time),
            max_evaluations=data.get("max_evaluations",EvalAppConf.max_evaluations),
            max_metapath2vec_evaluations=data.get("max_metapath2vec_evaluations",EvalAppConf.max_metapath2vec_evaluations),
            eval_params=EvalParams.from_dict(data.get("eval_params")),
        )


@dataclass
class LoggingConf:
    """
    Class that represents logging configuration, including output file path and logging level.
    """

    log_file: str | None = "System_log.log"
    log_level: str | None = MyLogger.LogLevel.DEBUG.value[0]

    @classmethod
    def from_dict(cls, data: dict | None) -> "LoggingConf":
        """
        Method that creates `LoggingConf` object from dictionary loaded from configuration file
        :param data: `dict` dictionary containing logging configuration values
        :return: `LoggingConf` created object with logging configuration
        """
        if data is None:
            return cls()

        return cls(
            log_file=data.get("log_file"),
            log_level=data.get("log_level", MyLogger.LogLevel.DEBUG.value)
        )

@dataclass
class ServerConf:
    """
    Class that represents server configuration, including deployment mode, network settings,
    authentication header, and optional TLS certificate files.
    """

    host: str = "localhost"
    port: int = 8000
    deploy_option: str = 'all'
    auth_header_name: str = "PWD"
    pvd_hash: Optional[str] = None
    cert_file: Optional[str] = None
    key_file: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict | None) -> "ServerConf":
        """
        Method that creates `ServerConf` object from dictionary loaded from configuration file
        :param data: `dict` dictionary containing server configuration values
        :return: `ServerConf` created object with server configuration
        """
        if data is None:
            return cls()

        return cls(
            host=data.get("host",ServerConf.host),
            port=data.get("port",ServerConf.port),
            deploy_option=data.get("deploy_option",ServerConf.deploy_option),
            auth_header_name=data.get("auth_header_name", "PWD"),
            pvd_hash=data.get("pwd_hash",None),
            cert_file=data.get("cert_file"),
            key_file=data.get("key_file"),
        )


class Config:
    """
    Class that represents application configuration loader and singleton container for all
    loaded configuration sections.
    """

    _instance = None

    def __init__(self, path_to_config: str):
        """
        Method that loads configuration file and initializes all nested configuration objects
        :param path_to_config: `str` path to JSON configuration file
        :return: None
        """
        if getattr(self, "_initialized", False):
            return
        self._initialized = True

        # Load raw JSON configuration data from provided file path.
        with open(Path(path_to_config), "r", encoding="utf-8") as f:
            data = json.load(f)

        # Create strongly typed configuration objects for all application subsystems.
        self.graph_repo_conf = GraphRepoConf.from_dict(data["graph_repo_conf"])
        self.eval_app_conf = EvalAppConf.from_dict(data.get("eval_app_conf"))
        self.logging_conf = LoggingConf.from_dict(data.get("logging_conf"))
        self.server_conf = ServerConf.from_dict(data.get("server_conf"))

    @classmethod
    def get_instance(cls, path_to_config: str = "config.json") -> "Config":
        """
        Method that returns singleton instance of `Config` class
        :param path_to_config: `str` path to JSON configuration file used when creating instance
        :return: `Config` singleton configuration instance
        """
        # Create shared configuration instance only once.
        if cls._instance is None:
            cls._instance = cls(path_to_config)
        return cls._instance

    @staticmethod
    def generate_default_configuration(out_path: str, full: bool) -> None:
        """
        Method that generates default configuration file where user only needs to put path to neo4j configuration
        :param out_path: Path where configuration file will be saved
        :param full: `bool` whether to generate whole configuration file or just part where path to Neo4j database configuration is stored
        :return: Nothing
        """

        if full:
            config: dict[str, dict] = {
                'eval_app_conf': asdict(EvalAppConf()),
                'logging_conf': asdict(LoggingConf()),
                'server_conf': asdict(ServerConf()),
                'graph_repo_conf': {
                    'neo4j_db_conf': "PATH TO DATABASE CONFIG FILE!!!!!!!",
                    'k_hop_neigh_params': asdict(KHopNeighParams())
                }
            }
        else:
            config: dict[str, dict] = {
                'graph_repo_conf': {
                    'neo4j_db_conf': "PATH TO DATABASE CONFIG FILE!!!!!!!",
                }
            }

        try:
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(e, file=sys.stderr)