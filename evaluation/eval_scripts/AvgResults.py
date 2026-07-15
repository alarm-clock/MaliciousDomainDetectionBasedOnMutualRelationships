import re
import sys
import numpy as np
from collections import defaultdict

# Metrics to aggregate
METRICS = [
    "Precision",
    "Recall (Minority Recall / TPR)",
    "F1 Score",
    "Macro F1",
    "Accuracy",
    "Balanced Accuracy",
    "False Positive Rate",
    "ROC-AUC",
    "PR-AUC",
]

# Regex for classifier sections
SECTION_RE = re.compile(r"===== (.*?) =====")


def parse_file(path):
    """
    Parses one evaluation file.

    Returns:
        {
            clf_name: {
                metric_name: value
            }
        }
    """
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    matches = list(SECTION_RE.finditer(content))

    result = {}

    for i, match in enumerate(matches):
        clf_name = match.group(1).strip()

        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)

        section = content[start:end]

        metrics = {}

        for metric in METRICS:
            pattern = re.escape(metric) + r":\s*\n([0-9eE\.\-]+)"
            metric_match = re.search(pattern, section)

            if metric_match:
                metrics[metric] = float(metric_match.group(1))

        result[clf_name] = metrics

    return result


def aggregate(files):
    """
    Aggregates metrics across files.
    """
    data = defaultdict(lambda: defaultdict(list))

    for file in files:
        parsed = parse_file(file)

        for clf, metrics in parsed.items():
            for metric, value in metrics.items():
                data[clf][metric].append(value)

    return data


def print_results(data):
    for clf in sorted(data.keys()):
        print(f"\n===== {clf} =====")

        for metric in METRICS:
            values = data[clf].get(metric, [])

            if not values:
                continue

            mean = np.mean(values)
            std = np.std(values)

            print(f"{metric}:")
            print(f"  Mean = {mean:.6f}")
            print(f"  Std  = {std:.6f}")


def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("python metrics_avg.py file1.txt file2.txt ...")
        sys.exit(1)

    files = sys.argv[1:]

    data = aggregate(files)

    print_results(data)


if __name__ == "__main__":
    main()