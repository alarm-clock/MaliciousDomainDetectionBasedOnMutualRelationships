from DatasetJsonParser import DatasetJsonParser
from DatasetDBParser import DatasetDBParser
from Visualize import plot_graph
import Learning

if __name__ == "__main__":

    json_dataset = DatasetJsonParser()
    g, l_edges = json_dataset.parse()

    #db_parser = DatasetDBParser('localhost',27017,'datasets','domains')
    #g = db_parser.parse()

    #plot_graph(g)  # note that my computer hasn't enough ram to handle this, he is strong, but not that strong
    Learning.train(g)