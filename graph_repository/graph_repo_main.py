import argparse
import signal
import sys
import warnings

from dgl.base import DGLWarning
from graph_repository.dataset_creator.DatasetImporter import DatasetImporter
from graph_repository.dataset_creator.DGLImporter import import_dgl_graph, export_dgl_graph
from graph_repository.dataset_creator.common.Graph import regenerate_train_test_mask
from graph_repository.graph_main.GraphRepository import GraphRepository
from graph_repository.graph_main.graph_editing.AddRequest import AddRequest
from graph_repository.graph_main.graph_editing.common.RequestPriority import RequestPriority
from graph_repository.Neo4jDBClient import Neo4jDBClient, CouldNotConnect
from misc.Logger import MyLogger
import dgl

warnings.filterwarnings("ignore",category=DGLWarning) #it actually comes from package itself

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
    parser.add_argument("--mongo_db",metavar='MONGO_CONF_FILE',type=str,help="Path to MongoDB database connection config file")
    parser.add_argument("--neo_db",metavar='NEO_DB_CONF_FILE',type=str,help="Path to Neo database connection config file")
    parser.add_argument("-l","--log",metavar='LOG_FILE',type=str,help="Path where log file will be stored")
    parser.add_argument('-ll','--log_level',metavar='LEVEL', type=str, help="Logging level", default='INFO')

    subparsers = parser.add_subparsers(dest='mode', required=True)

    # Dataset import go here
    import_parser = subparsers.add_parser('import_db')
    import_parser.add_argument('--dgl',action='store_true',help="Import from mongodb and create dgl graph")
    import_parser.add_argument('--neo',action='store_true',help="Import from mongodb and create neo4j graph")
    import_parser.add_argument('--dgl_exp',type=str,help="Path where created dgl graph will be stored")
    import_parser.add_argument('-e','--etypes',type=str,help="Edge types that will be created, specified in format \"etype1,etype2,...\"")
    import_parser.add_argument("-r","--ranges",type=str,help="Ranges specified in format \"start1,end1,start2,end2,...\"")
    import_parser.add_argument('-t','--test_connection', type=str,help="Test connection to Neo4j server")

    # Dgl import go here
    dgl_import_parser = subparsers.add_parser('import_dgl')
    dgl_import_parser.add_argument('path_to_graph',type=str,help="Path where graph is stored")
    dgl_import_parser.add_argument("-r",action='store_true',help="Regenerate train/test mask")
    dgl_import_parser.add_argument('--exp',type=str, help="Path where dgl graph will be stored")

    # Add edit go here
    add_edit_pareser = subparsers.add_parser('edit_add')
    add_edit_pareser.add_argument("-jf", '--json_file', type=str, help="Path where json file will be stored")
    add_edit_pareser.add_argument('-j', '--json', type=str, help="Json string that will be used to update graph")



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
                Neo4jDBClient.from_config(args.test_connection)
            except CouldNotConnect:
                print("Could not connect to Neo4j server", file=sys.stderr)
                return
            return

        if args.mongo_db is None:
            print("MongoDB connection config file not provided, exiting",file=sys.stderr)
            return

        dset_importer = DatasetImporter.from_config(args.mongo_db, args.etypes, args.ranges)
        g = dgl.DGLGraph()

        if args.dgl:
            g = dset_importer.create_dgl_graph()
        elif args.dgl_exp is not None:
            g = dset_importer.create_dgl_graph(args.dgl_exp)
        elif args.neo:
            dset_importer.create_graph_and_import_to_neo4j(args.neo_db)

    elif args.mode == "import_dgl":
        g = import_dgl_graph(args.path_to_graph)

        if args.r is not None:
            regenerate_train_test_mask(g)

        if args.exp is not None:
            export_dgl_graph(g,args.exp)

    elif args.mode == "edit_add":
        repository = GraphRepository.get_instance(args.neo_db)

        if repository is None:
            print("Neo database connection config file not provided, exiting",file=sys.stderr)
            return

        if args.json_file is not None:
            request = AddRequest.from_json_file(args.json_file,RequestPriority.LOW)
        elif args.json is not None:
            #request = AddRequest.from_json_str(args.json, RequestPriority.LOW)
            e = 42
        else:
            print("No add input was provided, exiting", file=sys.stderr)
            return

        #todo add graph copying here

        driver: Neo4jDBClient = GraphRepository.get_instance().get_neo4j_driver()
        driver.create_new_version_mirror_of_graph()

        current_graph_version = driver.get_current_active_graph_version()
        driver.close()
        #request.edit(current_graph_version)




if __name__ == '__main__':
    main()