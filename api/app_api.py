import sys

from fastapi import FastAPI
from enum import Enum
from api.routes import evaluation_api, graph_repository_api

class ApiOptions(Enum):
    WHOLE_APP = "all"
    GRAPH_REPOSITORY = "graph_repository"
    EVALUATION = "evaluation"

    @staticmethod
    def from_str(opt: str) -> 'ApiOptions | None':
        for option in ApiOptions:
            if option.value == opt:
                return option

        print(f"Unknow server option: {opt}", file=sys.stderr)
        return None


def create_app(mode: ApiOptions = ApiOptions.WHOLE_APP) -> FastAPI:
    app = FastAPI()

    if mode == ApiOptions.WHOLE_APP or mode == ApiOptions.EVALUATION:
        app.include_router(evaluation_api.router)

    if mode == ApiOptions.GRAPH_REPOSITORY or mode == ApiOptions.WHOLE_APP:
        app.include_router(graph_repository_api.router)

    return app


app = create_app()