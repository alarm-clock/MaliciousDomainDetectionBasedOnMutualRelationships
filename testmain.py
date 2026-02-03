import sys
from argparse import Namespace
from dataset_parsers.raw.DatasetJsonParser import DatasetJsonParser
from dataset_parsers.db.DatasetDBParser import DatasetDBParser
from dataset_parsers.Graph import remove_isolated_nodes, get_connected_components, get_and_export_connected_components, regenerate_train_test_mask
from dataset_parsers.heterograph.HeterographCreator import HeterographCreator
from misc.Visualize import plot_graph#, export_graph_gpu
from dataset_parsers.dglGraph.ExportGraph import export_graph, load_graph
from misc.helper_func import parse_ranges
from misc.Logger import MyLogger
from misc.demo.DemoApp import app_loop, domain_checker
from ml.deepwalk import Learning
import argparse




def check_args_logic(args: Namespace) -> bool:

    sum_of_d_args = int(args.dataset is not None) + int(args.dglformat is not None) + int(args.database) + int(args.heterograph is not None)

    if sum_of_d_args == 0:
        print('You must specify at least one option from which hgraph will be loaded or constructed.',file=sys.stderr)
        return False
    elif sum_of_d_args > 1:
        print("Only one option from which graph will be loaded or constructed can be specified.",file=sys.stderr)
        return False
    else:
        return True

def check_if_db_was_given(args: Namespace) -> bool:
    if args.db_config is not None or args.db is not None:
        return True
    else:
        print("Dataset argument must be used together with -db argument!", file=sys.stderr)
        return False

def main():

    parser = argparse.ArgumentParser(description="Program that is used to create DGL graphs from datasets and test Deepwalk method for machine learning")
    parser.add_argument("--database",action='store_true',help="Specifies that graph should be created from database with necessary information to connect to db is found in FILE")
    parser.add_argument("--dataset", metavar='FILE1', type=argparse.FileType('r'),help="Specifies that graph should be created from json dataset(s), paths to which are specified by FILE")
    parser.add_argument("--dglformat", metavar='FILE3', type=argparse.FileType('r'), help="Specifies that graph should be created from dgl format file, path to which is specified by FILE")
    parser.add_argument("-db", "--db_config", metavar='DB_CONFIG', type=argparse.FileType('r'), help="Database config file, used when program has to interact with database, program currently only supports mongodb")
    parser.add_argument("--heterograph", metavar="[EDGE_TYPES]", type=str, help="Specifies that created graph will be heterograph with specified edge types, must be used with -db parameter. Allowed values are: ipv4, subdomain, subdomain_of, CNAME")
    parser.add_argument("--etypes",metavar="TYPES",type=str, help="Specifies what edge types will be created. Allowed values are: ipv4, subdomain, subdomain_of, CNAME")
    parser.add_argument('-l','--learn', action='store_true', help="Specifies that graph should be learned or not, defaults to False")
    parser.add_argument('-e','--export',metavar='EXPORT', type=str, help="Specifies that graph should be exported, defaults to False")
    parser.add_argument('-r','--ranges',metavar='RANGES', type=str, help="Specifies ranges of nodes from which nodes should be created, NOTE works only with database, NOTE2 that real number of nodes will be much larger because neighbors that are not specified in the ranges are still created")
    parser.add_argument('--plot', action='store_true', help="Specifies that graph should be plotted or not, defaults to False, NOTE that large graphs might crash due to HW limitations")
    parser.add_argument('--export_plot', metavar='EXPORT', type=str, help="Specifies that graph should be exported, defaults to False")
    parser.add_argument("--gen_strong_comp", action='store_true', help="NOTE: do not call when you are low on ram")
    parser.add_argument("--rm_iso_nds", action='store_true', help="Remove isolated nodes from created/imported graph")
    parser.add_argument("--gen_exp_strong_comp", metavar='FILE4', type=str, help='Export strongly connected components into own graph')
    parser.add_argument("-t1", "--test1",action='store_true', help="Test function 1")
    parser.add_argument("--regenerate_test_mask", action='store_true', help="Regenerate test mask for given graph")
    parser.add_argument('--log_file', metavar='LOGFILE', type=argparse.FileType('a'), help="Log file")
    parser.add_argument('--demo', action='store_true', help='Demo app')
    parser.add_argument("--demo_from_list", type=str, help="Demo that classifies from the list")

    args = parser.parse_args()

    if args.log_file is not None:
        MyLogger(args.log_file.name)

    if not check_args_logic(args):
        return

    if args.database:
        if not check_if_db_was_given(args):
            return

        parser = DatasetDBParser.from_config(False, args.db_config.name)
        g = parser.parse() if not args.ranges else parser.parse_from_ranges(parse_ranges(args.ranges))

    elif args.dglformat is not None:

        g = load_graph(args.dglformat.name)
        if g is None:
            return

    elif args.dataset is not None:

        parser = DatasetJsonParser(args.dataset.name)

        try:
            g, _ = parser.parse()
        except ValueError as e:
            MyLogger.get_instance().log(e)
            return
    elif args.heterograph is not None:
        if not check_if_db_was_given(args):
            return

        hg_creator = HeterographCreator.from_config(args.db_config.name, args.heterograph, args.ranges)
        g = hg_creator.createHeterograph()
    else:
        return

    if g is None:
        print("No graph was created or imported so can not continue...", file=sys.stderr)
        MyLogger.get_instance().log("No graph was created or imported so can not continue...")
        return

    if args.regenerate_test_mask:
        regenerate_train_test_mask(g)

    if args.gen_strong_comp:
        kokot = get_connected_components(g)
    

    if args.rm_iso_nds:
        g = remove_isolated_nodes(g) #original IDs can be retrieved g.ndata['dgl.NID'][node]

    if args.test1:
        pass

    if args.gen_exp_strong_comp is not None:
        prefix = args.gen_exp_strong_comp
        get_and_export_connected_components(g,prefix)
        
    if args.plot:
        plot_graph(g,False)

    #if args.export_plot:
    #    export_graph_gpu(g,  args.export_plot)

    if args.export:

        export_graph(g, args.export)

    if args.learn:
        #Learning.train(g)
        Learning.train_and_test_model(g)

    if args.demo:
        app_loop(g, args.db_config.name, args.etypes)

    if args.demo_from_list:
        domain_checker(g, args.demo_from_list, args.etypes)

    MyLogger.get_instance().log("Finished!")
    return


if __name__ == "__main__":
    main()
