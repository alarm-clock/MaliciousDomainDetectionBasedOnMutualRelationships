import argparse
import json
import signal
import sys
import time
import warnings
from dgl.base import DGLWarning
from fontTools import agl

from graph_repository.dataset_creator.DatasetImporter import DatasetImporter
from graph_repository.dataset_creator.DGLImporter import import_dgl_graph, export_dgl_graph
from graph_repository.dataset_creator.common.Graph import regenerate_train_test_mask
from graph_repository.graph_main.GraphRepository import GraphRepository
from graph_repository.graph_main.graph_editing.requests.AddRequest import AddRequest
from graph_repository.graph_main.graph_editing.requests.DeleteRequest import DeleteRequest
from graph_repository.graph_main.graph_editing.requests.EditRequest import EditRequest
from graph_repository.graph_main.graph_editing.common.RequestPriority import RequestPriority
from graph_repository.Neo4jDBDriver import Neo4jDBDriver, CouldNotConnect
from graph_repository.graph_main.conversion.FormatConverting import convert_form_neo4j_to_dgl, prepare_dgl_g_for_ml
from graph_repository.workers.common.GraphTypes import NodeTypes
from misc.Logger import MyLogger
import dgl
import uvicorn
from evaluation.graph_repository.setTrainTestDomians import generateRanges, setTrainTestTODomains
from functools import partial

warnings.filterwarnings("ignore", category=DGLWarning)  #it actually comes from package itself


def signal_handlers_for_graph_repo():
    def _graceful_exit(signum, frame):
        MyLogger.get_instance().log(f"Received signal {signum}, gracefully exiting...")
        repo_instance = GraphRepository.get_instance()
        if repo_instance is not None:
            repo_instance.stop()

        exit(0)

    signal.signal(signal.SIGINT, _graceful_exit)
    signal.signal(signal.SIGTERM, _graceful_exit)


def main():
    parser = argparse.ArgumentParser()

    #Global args go here
    parser.add_argument("--mongo_db", metavar='MONGO_CONF_FILE', type=str,
                        help="Path to MongoDB database connection config file")
    parser.add_argument("--neo_db", metavar='NEO_DB_CONF_FILE', type=str,
                        help="Path to Neo database connection config file")
    parser.add_argument("-l", "--log", metavar='LOG_FILE', type=str, help="Path where log file will be stored")
    parser.add_argument('-ll', '--log_level', metavar='LEVEL', type=str, help="Logging level", default='INFO')

    subparsers = parser.add_subparsers(dest='mode', required=True)

    # Dataset import go here
    import_parser = subparsers.add_parser('import_db')
    import_parser.add_argument('--dgl', action='store_true', help="Import from mongodb and create dgl graph")
    import_parser.add_argument('--neo', action='store_true', help="Import from mongodb and create neo4j graph")
    import_parser.add_argument('--dgl_exp', type=str, help="Path where created dgl graph will be stored")
    import_parser.add_argument('-e', '--etypes', type=str,
                               help="Edge types that will be created, specified in format \"etype1,etype2,...\"")
    import_parser.add_argument("-r", "--ranges", type=str,
                               help="Ranges specified in format \"start1,end1,start2,end2,...\"")
    import_parser.add_argument('--convert_supporting', '-c', action='store_true',
                               help="Convert supporting dummy domains into normal dummy domains")
    import_parser.add_argument('-t', '--test_connection', type=str, help="Test connection to Neo4j server")

    # Dgl import go here
    dgl_import_parser = subparsers.add_parser('import_dgl')
    dgl_import_parser.add_argument('path_to_graph', type=str, help="Path where graph is stored")
    dgl_import_parser.add_argument("-r", action='store_true', help="Regenerate train/test mask")
    dgl_import_parser.add_argument('--exp', type=str, help="Path where dgl graph will be stored")

    # Edit go here
    edit_parser = subparsers.add_parser('edit')
    edit_parser.add_argument("-jf", '--json_file', type=str, help="Path where json file will be stored")
    edit_parser.add_argument('-j', '--json', type=str, help="Json string that will be used to update graph")
    edit_parser.add_argument('-a', '--add', action='store_true', help="Add domains to graph")
    edit_parser.add_argument('-d', '--delete', action='store_true', help="Delete domains from graph")
    edit_parser.add_argument('-e', '--edit', action="store_true", help="Edit domains in graph")

    #tmp edit here
    tmp_edit_parser = subparsers.add_parser('tmp')
    tmp_edit_parser.add_argument("-jf", '--json_file', type=str, help="Path where json file will be stored")
    tmp_edit_parser.add_argument('-j', '--json', type=str, help="Json string that will be used to update graph")
    tmp_edit_parser.add_argument('-a', '--add', action='store_true', help="Add tmp domain to graph")
    tmp_edit_parser.add_argument('-d', '--delete', action='store_true', help="Delete tmp domain from graph")

    #Api go here
    api_parser = subparsers.add_parser('server')
    api_parser.add_argument('-p', "--port", type=int, help="Port on which server will run, defaults to 8000",
                            default=8000)
    api_parser.add_argument('-a', '--address', type=str, help="Host on which server will run, defaults to localhost",
                            default='localhost')
    #api_parser.add_argument('--live_reloading',action='store_true',help="Enable live reloading")
    #TODO ADD RUN ASYNC OPTION

    subparsers.add_parser('test')

    args = parser.parse_args()

    if args.log is not None:

        log_level = MyLogger.LogLevel.INFO
        if args.log_level is not None:
            log_level_str = args.log_level.upper()

            no_match = True
            for level in MyLogger.LogLevel:
                if level.value[0] == log_level_str:
                    no_match = False
                    log_level = level

            if no_match:
                print(f"Unknown log level {log_level_str}, exiting!", file=sys.stderr)
                return

        MyLogger(args.log, log_level)

    if args.mode == "import_db":

        if args.test_connection is not None:

            try:
                Neo4jDBDriver.from_config(args.test_connection)
            except CouldNotConnect:
                print("Could not connect to Neo4j server", file=sys.stderr)
                return
            return

        if args.convert_supporting:
            driver = Neo4jDBDriver.from_config(args.neo_db)
            DatasetImporter.replace_other_dummies_with_default_dummy_domain(driver)
            driver.close()
            return

        if args.mongo_db is None:
            print("MongoDB connection config file not provided, exiting", file=sys.stderr)
            return

        dset_importer = DatasetImporter.from_config(args.mongo_db, args.etypes, args.ranges, neo_config=args.neo_db)
        g = dgl.DGLGraph()

        if args.dgl:
            g = dset_importer.create_dgl_graph()
        elif args.dgl_exp is not None:
            g = dset_importer.create_dgl_graph(args.dgl_exp)
        elif args.neo:
            dset_importer.create_graph_and_import_to_neo4j()

    elif args.mode == "import_dgl":
        g = import_dgl_graph(args.path_to_graph)

        if args.r is not None:
            regenerate_train_test_mask(g)

        if args.exp is not None:
            export_dgl_graph(g, args.exp)

    elif args.mode == "edit":
        repository = GraphRepository.get_instance(args.neo_db)

        if repository is None:
            print("Neo database connection config file not provided, exiting", file=sys.stderr)
            return

        if args.add:
            cls = AddRequest
        elif args.delete:
            cls = DeleteRequest
        elif args.edit:
            cls = EditRequest
        else:
            return

        if args.json_file is not None:
            request = cls.from_json_file(args.json_file, RequestPriority.LOW)
        elif args.json is not None:
            request = cls.from_json_str(args.json, RequestPriority.LOW)
        else:
            print("No add input was provided, exiting", file=sys.stderr)
            return
        # todo add graph copying here
        driver: Neo4jDBDriver = GraphRepository.get_instance().get_neo4j_driver()
        #driver.create_new_version_mirror_of_graph()

        current_graph_version = driver.get_current_active_graph_version()
        driver.close()
        request.filter()
        request.edit(current_graph_version)

    elif args.mode == "tmp":

        repository: GraphRepository = GraphRepository.get_instance(args.neo_db)

        if repository is None:
            print("Neo database connection config file not provided, exiting", file=sys.stderr)
            return

        if args.json is not None:
            data = json.loads(args.json)
        elif args.json_file is not None:
            with open(args.json_file, 'r') as f:
                data = json.load(f)
        else:
            return

        data = data[0] if type(data) is list else data

        if args.add:
            repository.temporary_add_domain(data)
        elif args.delete:
            driver = repository.get_neo4j_driver()
            driver.delete_node(data)

        else:
            return

    elif args.mode == 'server':
        repository = GraphRepository.get_instance(args.neo_db)
        signal_handlers_for_graph_repo()

        if repository is None:
            print("Neo database connection config file not provided, exiting", file=sys.stderr)
            return

        uvicorn.run("graph_repository.api.server:app", host=args.address, port=args.port)

    elif args.mode == "test":
        client = Neo4jDBDriver.from_config(args.neo_db) #tmp.test.microsoft.com

        start = time.time()
        res = client.get_k_hop_neighborhood_universal(
            {"label": NodeTypes.TMP_DOMAIN.neo4j, "domain_name": "pipinka.A.C.at"}, 2, 5000, False)

        graph = convert_form_neo4j_to_dgl(True, res)
        end = time.time()

        print(end - start)
        #print(graph.num_nodes(ntype='d'))
        #print(graph.ndata)

        for et in graph.canonical_etypes:
            print(et)
            print(graph.edges(etype=et))

        #print(graph.nodes(ntype=NodeTypes.TMP_DOMAIN.dgl))
        start = time.time()
        graph = prepare_dgl_g_for_ml(graph)
        end = time.time()
        print(end - start)
        print('*' * 260)

        for et in graph.canonical_etypes:
            print(et)
            print(graph.edges(etype=et))

        print(graph.ndata)
        return


if __name__ == '__main__':
    main()
