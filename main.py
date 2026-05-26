import json
import time

import dgl
import uvicorn
import signal
from api.app_api import ApiOptions, create_app
from api.config.config import Config
from domain_evaluation.Evaluate import  test_from_collection
from domain_evaluation.EvaluationApp import EvaluationApp, test_from_parquet
from evaluation.graph_repository.generate_and_send_new_domains import direct_test, direct_test_of_copy_on_write
from graph_repository.Neo4jDBDriver import Neo4jDBDriver, CouldNotConnect
from graph_repository.dataset_creator.DGLImporter import import_dgl_graph, export_dgl_graph
from graph_repository.dataset_creator.common.Graph import regenerate_train_test_mask
from graph_repository.graph_main.GraphRepository import GraphRepository
from graph_repository.graph_main.graph_editing.common.RequestPriority import RequestPriority
from graph_repository.dataset_creator.DatasetImporter import DatasetImporter
from graph_repository.graph_main.graph_editing.requests.EditRequest import EditRequest
from graph_repository.graph_main.graph_editing.requests.AddRequest import AddRequest
from graph_repository.graph_main.graph_editing.requests.DeleteRequest import DeleteRequest
from misc.Logger import MyLogger
import sys
import argparse
import multiprocessing as mp

def add_signal_handlers():
    def _graceful_exit(signum, frame):
        MyLogger.get_instance().log(f"Received signal {signum}, gracefully exiting...")

        eval_app = EvaluationApp.get_instance()
        if eval_app is not None:
            eval_app.stop()

        repo_instance = GraphRepository.get_instance()
        if repo_instance is not None:
            repo_instance.stop()

        exit(0)

    signal.signal(signal.SIGINT, _graceful_exit)
    signal.signal(signal.SIGTERM, _graceful_exit)

def main():
    parser = argparse.ArgumentParser()

    parser.add_argument('--config', type=str, help="Path to config file")
    parser.add_argument("--mongo_db", metavar='MONGO_CONF_FILE', type=str, help="Path to MongoDB database connection config file")
    parser.add_argument("--neo_db", metavar='NEO_DB_CONF_FILE', type=str, help="Path to Neo database connection config file")
    parser.add_argument("-l", "--log", metavar='LOG_FILE', type=str, help="Path where log file will be stored")
    parser.add_argument('-ll', '--log_level', metavar='LEVEL', type=str, help="Logging level", default='INFO')

    subparsers = parser.add_subparsers(dest='mode', required=True)

    # Dataset import go here
    import_parser = subparsers.add_parser('import_db')
    import_parser.add_argument('--dgl', action='store_true', help="Import from mongodb and create dgl graph")
    import_parser.add_argument('--neo', action='store_true', help="Import from mongodb and create neo4j graph")
    import_parser.add_argument('--empty',action='store_true', help="Create empty graph")
    import_parser.add_argument('--dgl_exp', type=str, help="Path where created dgl graph will be stored")
    import_parser.add_argument('-e', '--etypes', type=str, help="Edge types that will be created, specified in format \"etype1,etype2,...\"")
    import_parser.add_argument("-r", "--ranges", type=str, help="Ranges specified in format \"start1,end1,start2,end2,...\"")
    import_parser.add_argument('--convert_supporting', '-c', action='store_true', help="Convert supporting dummy domains into normal dummy domains")
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

    # tmp edit here
    tmp_edit_parser = subparsers.add_parser('tmp')
    tmp_edit_parser.add_argument("-jf", '--json_file', type=str, help="Path where json file will be temporary added/deleted")
    tmp_edit_parser.add_argument('-j', '--json', type=str, help="Json string that will be used to temporary add or delete domain")
    tmp_edit_parser.add_argument('-a', '--add', action='store_true', help="Add tmp domain to graph")
    tmp_edit_parser.add_argument('-d', '--delete', action='store_true', help="Delete tmp domain from graph")

    """
    classify_parser = subparsers.add_parser('classify')
    classify_parser.add_argument("-jf", '--json_file', type=str, help="Path where json file will be stored")
    classify_parser.add_argument('-j', '--json', type=str, help="Json string that will be used to update graph")
    classify_parser.add_argument('-m','--mongo',action='store_true',help="Use MongoDB database to get domains")
    classify_parser.add_argument('-p',"--parallel", action='store_true', help="Parallel test domains")
    classify_parser.add_argument('-t','--trained',action='store_true', help="Flag indicating that some domains in mongo were train/test separated")
    classify_parser.add_argument('-e','--exists',action='store_true',help="Flag that indicates that tmp domain is already in graph")
    classify_parser.add_argument('--test',type=str, metavar='OUT_FILE_CSV' ,help="Test metapath2vec model")
    """

    #test_parser = subparsers.add_parser('test')
    #test_parser.add_argument('output', type=str, help="Path where output will be stored")
    #test_parser.add_argument('-p',type=str, help="Path to parquet file")

    #size_parser = subparsers.add_parser('size_test')
    #size_parser.add_argument('-p',type=str, help="Path to stable file")

    #copy_parser = subparsers.add_parser('copy_test')
    #copy_parser.add_argument("output", type=str, help="Path where output will be stored")

    server_parser = subparsers.add_parser('server')
    #server_parser.add_argument('available_endpoints', type=str, help=f"Endpoints that will available, available options are: {', '.join([opt.value for opt in ApiOptions])}")
    #server_parser.add_argument('-a','--address',metavar='HOST', type=str, help="Host to which will server bind", default='localhost')
    #server_parser.add_argument('-p','--port', metavar='PORT', type= int, help="Port to which will server bind", default=8000)
    #server_parser.add_argument('--max_eval',type=int, help="Maximum number of concurrent evaluations", default=16)
    #server_parser.add_argument('--max_concurent_gpu',type=int, help="Maximum number of concurrent evaluations on gpu", default=4)

    args = parser.parse_args()

    conf = Config.get_instance(args.config)

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

    MyLogger(conf.logging_conf.log_file, conf.logging_conf.log_level)

    if args.mode == "import_db":

        if args.test_connection is not None:

            try:
                Neo4jDBDriver.from_config(args.test_connection)
            except CouldNotConnect:
                print("Could not connect to Neo4j server", file=sys.stderr)
                return
            return

        if args.empty:
            Neo4jDBDriver.from_config(args.neo_db).create_empty_graph()
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

        if args.r is not None and g is not None:
            regenerate_train_test_mask(g)

        if args.exp is not None and g is not None:
            export_dgl_graph(g, args.exp)

    elif args.mode == "edit":
        repository = GraphRepository.init(GraphRepository.ABI, args.neo_db)

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
        # driver.create_new_version_mirror_of_graph()

        current_graph_version = driver.get_current_active_graph_version()
        driver.close()
        request.filter()
        request.edit(current_graph_version)

    elif args.mode == "tmp":

        repository: GraphRepository = GraphRepository.init(GraphRepository.ABI, args.neo_db)

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
            repository.temporary_add_domain(data, None)
        elif args.delete:
            driver = repository.get_neo4j_driver()
            driver.delete_node(data)

        else:
            return

    elif args.mode == 'server':

        mode = ApiOptions.from_str(conf.server_conf.deploy_option)
        if mode is None:
            return

        try:
            g_r = GraphRepository.init(GraphRepository.ABI, conf.graph_repo_conf.neo4j_db_conf)
            if g_r is None:
                print("Neo database connection config file not provided, exiting", file=sys.stderr)
                return

        except Exception as e:
            print("Neo database connection config file not provided, exiting", file=sys.stderr)
            return

        if mode == ApiOptions.WHOLE_APP or mode == ApiOptions.EVALUATION or mode == ApiOptions.READ_AND_GRAPH_REPO:
            mp.set_start_method("spawn")
            EvaluationApp(g_r,conf.eval_app_conf.max_evaluations, conf.eval_app_conf.max_metapath2vec_evaluations)

        add_signal_handlers()
        app = create_app(mode)
        uvicorn.run(
            app,
            host=conf.server_conf.host,
            port=conf.server_conf.port,
            ssl_certfile = conf.server_conf.cert_file,
            ssl_keyfile = conf.server_conf.key_file
        )


    if args.mode == "test":
        mp.set_start_method("spawn")
        r = GraphRepository.init(GraphRepository.ABI, args.neo_db)
        if r is None:
            print("amana hy")
            return

        if args.p is None:
            test_from_collection(args.mongo_db,args.output,True)
        else:
            EvaluationApp(r)

            test_from_parquet(args.p,args.output)

        GraphRepository.get_instance().stop()

    if args.mode == "size_test":

        mp.set_start_method("spawn")
        r = GraphRepository.init(GraphRepository.ABI, args.neo_db)
        if r is None:
            print("amana hy")
            return

        EvaluationApp(r)
        direct_test(args.neo_db, args.p)
        EvaluationApp.get_instance().stop()
        GraphRepository.get_instance().stop()

    if args.mode == "copy_test":
        GraphRepository.init(GraphRepository.ABI, args.neo_db)
        direct_test_of_copy_on_write(args.neo_db, args.output)


    """
    elif args.mode == 'classify':
        if args.json is not None:
            data = json.loads(args.json)
        elif args.json_file is not None:
            with open(args.json_file, 'r') as f:
                data = json.load(f)
        elif args.mongo:
            data = args.mongo_db
        else:
            return

        repo  = GraphRepository.init(GraphRepository.ABI, args.neo_db)
        if repo is None:
            print("Neo database connection config file not provided, exiting", file=sys.stderr)
            return

        mp.set_start_method("spawn")

        if args.test is not None:

            if args.mongo:
                test_from_collection(data,args.test,args.parallel,args.trained)
            else:
                test(data, args.test,False)
            return

        if type(data) == dict:
            test_evaluate_domain_metapath2vec(data, None)
        else:
            evaluate_domain_metapath2vec_mult(data)
    """



if __name__ == "__main__":
    main()