import sys
from fastapi import FastAPI, Depends
from enum import Enum
from api.routes import evaluation_api, graph_repository_api, read_query_api
from api.config.auth import authenticate


class ApiOptions(Enum):
    WHOLE_APP = "all"
    GRAPH_REPOSITORY = "graph_repository"
    EVALUATION = "evaluation"
    READ_AND_EVAL = "read_and_eval"
    READ = "read"
    READ_AND_GRAPH_REPO = "read_and_graph_repository"

    @staticmethod
    def from_str(opt: str) -> 'ApiOptions | None':
        for option in ApiOptions:
            if option.value == opt:
                return option

        print(f"Unknow server option: {opt}", file=sys.stderr)
        return None


def create_app(mode: ApiOptions = ApiOptions.WHOLE_APP) -> FastAPI:
    app = FastAPI()

    if mode == ApiOptions.WHOLE_APP or mode == ApiOptions.EVALUATION or mode == ApiOptions.READ_AND_EVAL:
        app.include_router(
            evaluation_api.router,
            dependencies=[Depends(authenticate)]
        )

    if mode == ApiOptions.GRAPH_REPOSITORY or mode == ApiOptions.WHOLE_APP or mode == ApiOptions.READ_AND_GRAPH_REPO:
        app.include_router(
            graph_repository_api.router,
            dependencies=[Depends(authenticate)]
        )

    if mode == ApiOptions.READ_AND_EVAL or mode == ApiOptions.READ_AND_GRAPH_REPO or mode == ApiOptions.WHOLE_APP or mode == ApiOptions.READ:
        app.include_router(
            read_query_api.router,
            dependencies=[Depends(authenticate)]
        )

    return app
app = create_app()