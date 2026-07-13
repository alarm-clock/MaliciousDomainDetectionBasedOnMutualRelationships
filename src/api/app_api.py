"""
File: app_api.py
Author: Jozef Michal Bukas <xbukas00@stud.fit.vutbr.cz>
Date: 27.12.2025
Brief: File that contains API application initialization logic, including available API modes,
    router registration, and creation of FastAPI application instance
"""

import sys
from fastapi import FastAPI, Depends
from enum import Enum
from api.config.auth import authenticate


class ApiOptions(Enum):
    """
    Class that represents available API deployment modes which determine which routers
    are registered in created FastAPI application.
    """

    WHOLE_APP = "all"
    GRAPH_REPOSITORY = "graph_repository"
    EVALUATION = "evaluation"
    READ_AND_EVAL = "read_and_eval"
    READ = "read"
    READ_AND_GRAPH_REPO = "read_and_graph_repository"

    @staticmethod
    def from_str(opt: str) -> 'ApiOptions | None':
        """
        Method that converts string representation of API mode into matching `ApiOptions` value
        :param opt: `str` string specifying requested API mode
        :return: `ApiOptions | None` matching enum value on success, None if given option is unknown
        """
        # Iterate through all available API options and return matching one.
        for option in ApiOptions:
            if option.value == opt:
                return option

        # Print error message to standard error if unknown option was provided.
        print(f"Unknow server option: {opt}", file=sys.stderr)
        return None


def create_app(mode: ApiOptions = ApiOptions.WHOLE_APP) -> FastAPI:
    """
    Method that creates FastAPI application instance and registers routers according to selected mode
    :param mode: `ApiOptions` deployment mode specifying which API parts should be enabled
    :return: `FastAPI` initialized FastAPI application instance
    """
    # Create base FastAPI application instance.
    app = FastAPI()

    # Register evaluation routes when full API, evaluation-only API, or read-and-evaluation API is requested.
    if mode in (ApiOptions.WHOLE_APP, ApiOptions.EVALUATION, ApiOptions.READ_AND_EVAL):
        from api.routes import evaluation_api

        app.include_router(
            evaluation_api.router,
            dependencies=[Depends(authenticate)]
        )

    # Register graph repository routes when full API, graph-repository-only API,
    # or read-and-graph-repository API is requested.
    if mode in (ApiOptions.GRAPH_REPOSITORY, ApiOptions.WHOLE_APP, ApiOptions.READ_AND_GRAPH_REPO):
        from api.routes import graph_repository_api

        app.include_router(
            graph_repository_api.router,
            dependencies=[Depends(authenticate)]
        )

    # Register read query routes when read functionality is enabled in selected deployment mode.
    if mode in (ApiOptions.READ_AND_EVAL, ApiOptions.READ_AND_GRAPH_REPO, ApiOptions.WHOLE_APP, ApiOptions.READ):
        from api.routes import read_query_api

        app.include_router(
            read_query_api.router,
            dependencies=[Depends(authenticate)]
        )

    return app


# Module-level app stays lightweight; main.py creates the configured app.
app = create_app(ApiOptions.READ_AND_GRAPH_REPO)
