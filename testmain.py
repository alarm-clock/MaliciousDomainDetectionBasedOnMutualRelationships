import sys
from argparse import Namespace
from dataset_parsers.raw.DatasetJsonParser import DatasetJsonParser
from dataset_parsers.db.DatasetDBParser import DatasetDBParser
from dataset_parsers.Graph import remove_isolated_nodes, get_connected_components, get_and_export_connected_components
from misc.Visualize import plot_graph
from dataset_parsers.dglGraph.ExportGraph import export_graph, load_graph
from misc.helper_func import parse_ranges
from ml.deepwalk import Learning
import argparse


def check_args_logic(args: Namespace) -> bool:

    sum_of_d_args = int(args.dataset is not None) + int(args.dglformat is not None) + int(args.database is not None)

    if sum_of_d_args == 0:
        print('You must specify at least one option from which hgraph will be loaded or constructed.',file=sys.stderr)
        return False
    elif sum_of_d_args > 1:
        print("Only one option from which graph will be loaded or constructed can be specified.",file=sys.stderr)
        return False
    else:
        return True

def main():

    parser = argparse.ArgumentParser(description="Program that is used to create DGL graphs from datasets and test Deepwalk method for machine learning")
    parser.add_argument("--database", metavar='FILE', type=argparse.FileType('r'),help="Specifies that graph should be created from database with necessary information to connect to db is found in FILE")
    parser.add_argument("--dataset", metavar='FILE1', type=argparse.FileType('r'),help="Specifies that graph should be created from json dataset(s), paths to which are specified by FILE")
    parser.add_argument("--dglformat", metavar='FILE3', type=argparse.FileType('r'), help="Specifies that graph should be created from dgl format file, path to which is specified by FILE")
    parser.add_argument('-l','--learn', action='store_true', help="Specifies that graph should be learned or not, defaults to False")
    parser.add_argument('-e','--export',metavar='EXPORT', type=str, help="Specifies that graph should be exported, defaults to False")
    parser.add_argument('-r','--ranges',metavar='RANGES', type=str, help="Specifies ranges of nodes from which nodes should be created, NOTE works only with database, NOTE2 that real number of nodes will be much larger because neighbors that are not specified in the ranges are still created")
    parser.add_argument('--plot', action='store_true', help="Specifies that graph should be plotted or not, defaults to False, NOTE that large graphs might crash due to HW limitations")
    parser.add_argument("--gen_strong_comp", action='store_true', help="NOTE: do not call when you are low on ram")
    parser.add_argument("--rm_iso_nds", action='store_true', help="Remove isolated nodes from created/imported graph")
    parser.add_argument("--gen_exp_strong_comp", metavar='FILE4', type=str, help='Export strongly connected components into own graph')

    args = parser.parse_args()

    if not check_args_logic(args):
        return

    if args.database is not None:

        parser = DatasetDBParser.from_config(args.database.name)
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
            print(e)
            return
    else:
        return

    if args.gen_strong_comp:
        kokot = get_connected_components(g)
    

    if args.rm_iso_nds:
        g = remove_isolated_nodes(g)

    if args.gen_exp_strong_comp is not None:
        prefix = args.gen_exp_strong_comp
        get_and_export_connected_components(g,prefix)
        
    if args.plot:
        plot_graph(g)

    if args.export:
        export_graph(g, args.export)

    if args.learn:
        Learning.train(g)

    return


if __name__ == "__main__":
    main()
