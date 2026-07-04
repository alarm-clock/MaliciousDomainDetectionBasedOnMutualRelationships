"""
File: config.py
Author: Jozef Michal Bukas <xbukas00@stud.fit.vutbr.cz>
Date: 28.03.2026
Brief: File that contains configuration classes used for loading and storing application
    configuration from JSON file, including graph repository, evaluation, logging,
    and server settings
"""

import json

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

@dataclass
class KHopNeighParams:
    """
    Class that represents parameters used for k-hop neighborhood sampling and related graph
    traversal operations.
    """

    max_depth: int
    max_sample_size: int
    walk_seed: int

    @classmethod
    def from_dict(cls, data: dict) -> "KHopNeighParams":
        """
        Method that creates `KHopNeighParams` object from dictionary loaded from configuration file
        :param data: `dict` dictionary containing k-hop neighborhood parameter values
        :return: `KHopNeighParams` created object with k-hop neighborhood parameters
        """
        return cls(
            max_depth=data["max_depth"],
            max_sample_size=data["max_sample_size"],
            walk_seed=data["walk_seed"],
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
            k_hop_neigh_params=KHopNeighParams.from_dict(data["k_hop_neigh_params"]),
        )


@dataclass
class EvalParams:
    """
    Class that represents parameters used for domain evaluation and model-related computation.
    """

    w_size: int
    embedd_dim: int
    neg_size: int
    lr: float
    walk_seed: int
    regress_max_iters: int

    @classmethod
    def from_dict(cls, data: dict) -> "EvalParams":
        """
        Method that creates `EvalParams` object from dictionary loaded from configuration file
        :param data: `dict` dictionary containing evaluation parameter values
        :return: `EvalParams` created object with evaluation parameters
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
    """
    Class that represents configuration of evaluation application, including evaluation limits,
    result lifetime, and model parameters.
    """

    result_removal_time: float
    max_evaluations: int
    max_metapath2vec_evaluations: int
    eval_params: EvalParams

    @classmethod
    def from_dict(cls, data: dict) -> "EvalAppConf":
        """
        Method that creates `EvalAppConf` object from dictionary loaded from configuration file
        :param data: `dict` dictionary containing evaluation application configuration values
        :return: `EvalAppConf` created object with evaluation application configuration
        """
        return cls(
            result_removal_time=data["result_removal_time"],
            max_evaluations=data["max_evaluations"],
            max_metapath2vec_evaluations=data["max_metapath2vec_evaluations"],
            eval_params=EvalParams.from_dict(data["eval_params"]),
        )


@dataclass
class LoggingConf:
    """
    Class that represents logging configuration, including output file path and logging level.
    """

    log_file: str
    log_level: str

    @classmethod
    def from_dict(cls, data: dict) -> "LoggingConf":
        """
        Method that creates `LoggingConf` object from dictionary loaded from configuration file
        :param data: `dict` dictionary containing logging configuration values
        :return: `LoggingConf` created object with logging configuration
        """
        return cls(
            log_file=data["log_file"],
            log_level=data["log_level"],
        )


@dataclass
class ServerConf:
    """
    Class that represents server configuration, including deployment mode, network settings,
    authentication header, and optional TLS certificate files.
    """

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
        Method that creates `ServerConf` object from dictionary loaded from configuration file
        :param data: `dict` dictionary containing server configuration values
        :return: `ServerConf` created object with server configuration
        """
        # data.get(...) is used for optional configuration items that may be missing.
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
        # Prevent repeated initialization in case singleton instance already exists.
        if getattr(self, "_initialized", False):
            return
        self._initialized = True

        # Load raw JSON configuration data from provided file path.
        with open(Path(path_to_config), "r", encoding="utf-8") as f:
            data = json.load(f)

        # Create strongly typed configuration objects for all application subsystems.
        self.graph_repo_conf = GraphRepoConf.from_dict(data["graph_repo_conf"])
        self.eval_app_conf = EvalAppConf.from_dict(data["eval_app_conf"])
        self.logging_conf = LoggingConf.from_dict(data["logging_conf"])
        self.server_conf = ServerConf.from_dict(data["server_conf"])

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