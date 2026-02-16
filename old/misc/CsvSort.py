import csv
import argparse

def is_float(s):
    try:
        float(s)
        return True
    except ValueError:
        return False

def sort_csv(csv_file: str, column: int|str, out_file: str| None) -> None:
    header = None
    with open(csv_file, mode='r') as f:

        if type(column) == int:
            reader = csv.reader(f)
            header = next(reader)
            #for col in h_list:
            #    header += (col + ',')
            #header = header[:-1]

        else:
            reader = csv.DictReader(f)
        rows = list(reader)

    if rows[0][column].isdigit():
        rows.sort(key=lambda x: int(x[column]))
    elif is_float(rows[0][column]):
        rows.sort(key=lambda x: float(x[column]))
    else:
        rows.sort(key=lambda x: x[column])

    if out_file is not None:
        with open(out_file, mode='w') as f:
            if type(column) == int:
                writer = csv.writer(f)
                writer.writerow(header)
                writer.writerows(rows)
            else:
                writer = csv.DictWriter(f, reader.fieldnames)
                writer.writeheader()
                writer.writerows(rows)

    else:

        if type(column) == int:
            header_str = ''
            for s in header:
                header_str += f'{s},'

            header_str = header_str[:-1]
            print(header_str)


        for row in rows:
            s = ''
            for col in row:
                s += (col + ',')

            s = s[:-1]
            print(s)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('csv_file', type=str)
    parser.add_argument('column', type=str, nargs='?', default="0")
    parser.add_argument('-o', type=str, default=None)
    args = parser.parse_args()

    if args.column.isdigit():
        sort_csv(args.csv_file, int(args.column), args.o)
    else:
        sort_csv(args.csv_file, args.column, args.o)

if __name__ == '__main__':
    main()