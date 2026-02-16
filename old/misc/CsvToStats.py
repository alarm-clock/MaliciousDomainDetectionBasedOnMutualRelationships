import csv
import argparse

def create_stats(path_to_csv: str) -> None:

    n_correct: int = 0
    n_incorrect: int = 0
    n_false_positive: int = 0
    n_false_negative: int = 0
    n_classified: int = 0

    n_no_neighbours: int = 0
    n_only_good: int = 0
    n_only_bad: int = 0
    n_one_type: int = 0
    n_all: int = 0

    with open(path_to_csv, mode='r') as csvfile:
        reader = csv.reader(csvfile)
        next(reader)

        for row in reader:
            correct = int(row[9])
            prediction = int(row[7])
            label = int(row[8])
            n_all += 1
            if correct == -1:
                n_no_neighbours += 1
                continue
            elif correct == 1:
                n_correct += 1
            elif correct == 0:
                n_incorrect += 1

                if prediction == 1 and label == 0:
                    n_false_negative += 1
                elif prediction == 0 and label == 1:
                    n_false_positive += 1

            n_classified += 1
            good = int(row[2])
            bad = int(row[3])

            if good > 0 and bad == 0:
                n_only_good += 1
                n_one_type += 1
            elif good == 0 and bad > 0:
                n_only_bad += 1
                n_one_type += 1



    str_for_print: str = f"""
Stats for {path_to_csv}:
    Number of domains: {n_all}
    Where this number of nodes had no neighbours: {n_no_neighbours}
    Number of correct predictions: {n_correct}
    Number of incorrect predictions: {n_incorrect}
    Number of false positive predictions: {n_false_positive}
    Number of false negative predictions: {n_false_negative}
    Percentage of correct predictions: {(n_correct / n_classified) * 100}
    Percentage of incorrect predictions: {(n_incorrect / n_classified) * 100}
    Number of domains with only one type of neighbour: {n_one_type}
    Where number of nodes was only good: {n_only_good}
    Where number of nodes was only bad: {n_only_bad}
"""
    print(str_for_print)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('csv_file', type=str, help='Path to csv file')
    args = parser.parse_args()

    create_stats(args.csv_file)

if __name__ == "__main__":
    main()