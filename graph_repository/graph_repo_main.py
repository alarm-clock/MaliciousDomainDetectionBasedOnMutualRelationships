import argparse
import sys
import warnings

from dgl.base import DGLWarning

from graph_repository.dataset_creator.DatasetImporter import DatasetImporter
from graph_repository.dataset_creator.DGLImporter import import_dgl_graph, export_dgl_graph
from graph_repository.dataset_creator.common.Graph import regenerate_train_test_mask
from misc.Logger import MyLogger
import dgl

warnings.filterwarnings("ignore",category=DGLWarning) #it actually comes from package itself

def main():

    parser = argparse.ArgumentParser()

    #Global args go here
    parser.add_argument("--mongo_db",metavar='MONGO_CONF_FILE',type=str,help="Path to MongoDB database connection config file")
    parser.add_argument("--neo_db",metavar='NEO_DB_CONF_FILE',type=str,help="Path to Neo database connection config file")
    parser.add_argument("-l","--log",metavar='LOG_FILE',type=str,help="Path where log file will be stored")

    subparsers = parser.add_subparsers(dest='mode', required=True)

    # Dataset import go here
    import_parser = subparsers.add_parser('import_db')
    import_parser.add_argument('--dgl',action='store_true',help="Import from mongodb and create dgl graph")
    import_parser.add_argument('--neo',action='store_true',help="Import from mongodb and create neo4j graph")
    import_parser.add_argument('--dgl_exp',type=str,help="Path where created dgl graph will be stored")
    import_parser.add_argument('-e','--etypes',type=str,help="Edge types that will be created, specified in format \"etype1,etype2,...\"")
    import_parser.add_argument("-r","--ranges",type=str,help="Ranges specified in format \"start1,end1,start2,end2,...\"")

    # Dgl import go here
    dgl_import_parser = subparsers.add_parser('import_dgl')
    dgl_import_parser.add_argument('path_to_graph',type=str,help="Path where graph is stored")
    dgl_import_parser.add_argument("-r",action='store_true',help="Regenerate train/test mask")
    dgl_import_parser.add_argument('--exp',type=str, help="Path where dgl graph will be stored")

    args = parser.parse_args()

    if args.log is not None:
        MyLogger(args.log)

    if args.mode == "import_db":

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


if __name__ == '__main__':
    main()