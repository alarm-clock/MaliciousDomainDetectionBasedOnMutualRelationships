import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import (
    confusion_matrix,
    precision_score,
    recall_score,
    f1_score,
    accuracy_score,
    balanced_accuracy_score,
)

CLASSIFIERS = ["AVG", "CAT", "IP", "SUBD", "CNAME"]

# malicious = 0 is positive class
POS_LABEL = 0


def plt_conf_mat(cm, name: str) -> None:
    plt.figure()
    sns.heatmap(
        cm,
        annot=True,
        fmt="d",
        xticklabels=["Benign (1)", "Malicious (0)"],
        yticklabels=["Benign (1)", "Malicious (0)"],
    )
    plt.title(f"Confusion Matrix - {name}")
    plt.xlabel("Predicted")
    plt.ylabel("Actual")
    plt.show()

def plt_time_distr(times, name: str, log_scale: bool = True) -> None:
    times = np.array(times)

    if len(times) == 0:
        print(f"No data for {name}")
        return

    mean = np.mean(times)
    var = np.var(times)
    std = np.sqrt(var)

    plt.figure()

    if log_scale:
        times = times[times > 0]


    plt.hist(times, bins=5000)

    if log_scale:
        plt.xscale("log")

    # Mean line
    plt.axvline(mean, linestyle="dashed", linewidth=2, label=f"Mean: {mean:.2f}s", color="red")

    # Variance range (std dev)
    std = np.sqrt(var)
    plt.axvline(mean + std, linestyle="dotted", label=f"+1σ", color="green")

    plt.title(name + (" Log Scale" if log_scale else ""))
    plt.xlabel("Time (seconds)")
    plt.ylabel("Count")
    plt.legend()

    plt.show()

    print(f"{name} -> Mean: {mean:.3f}, Variance: {var:.3f}")

# ---------- PREDICTION LOGIC ----------
def get_final_prediction(row, clf):
    pred = int(row[f"{clf}_pred"])

    # Case 1: classifier worked
    if pred != -1:
        return pred

    # Case 2: fallback using 1-hop percentages
    bad = float(row["1_hop_mal_p"])   # NOTE: naming is confusing in your data
    good = float(row["1_hop_ben_p"])

    if good == 0 and bad == 0:
        return None

    if good > bad:
        return 1  # benign
    elif bad > good:
        return 0  # malicious
    else:
        return None


# ---------- METRICS ----------
def compute_metrics(y_true, y_pred):
    cm = confusion_matrix(y_true, y_pred, labels=[1, 0])
    tn, fp, fn, tp = cm.ravel()

    precision = precision_score(y_true, y_pred, pos_label=POS_LABEL, zero_division=0)
    recall = recall_score(y_true, y_pred, pos_label=POS_LABEL, zero_division=0)
    f1 = f1_score(y_true, y_pred, pos_label=POS_LABEL, zero_division=0)
    accuracy = accuracy_score(y_true, y_pred)
    balanced_acc = balanced_accuracy_score(y_true, y_pred)

    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0

    return {
        "Confusion Matrix": cm,
        "Precision": precision,
        "Recall (TPR)": recall,
        "F1 Score": f1,
        "Accuracy": accuracy,
        "Balanced Accuracy": balanced_acc,
        "False Positive Rate": fpr,
    }


# ---------- MAIN ----------
def analyze(file_path):
    df = pd.read_csv(file_path)

    # ---------- FIN STATE ----------
    fin_counts = df["fin_state"].value_counts()
    total_fin = len(df)

    print("=== FIN STATE STATS ===")
    for state, count in fin_counts.items():
        print(f"{state}: {count} ({(count / total_fin) * 100:.2f}%)")
    print()

    # ---------- FILTER ----------
    df = df[df["no_neighbor"] != True]

    # convert label (true=benign=1, false=malicious=0)
    df["label"] = df["label"].astype(int)

    # ---------- TIME STATS ----------
    time_fields = ["end_t", "got_graph_t", "calc_neigh_stats_t", "wait_t", "class_t"]

    time_stats = {
        t: {
            "sum": 0,
            "count": 0,
            "max": 0,
            "buckets": {
                "<2s": 0,
                "<5s": 0,
                "<10s": 0,
                "<20s": 0,
                "<60s": 0,
                "<300s": 0,
                ">=300s": 0,
            },
        }
        for t in time_fields
    }

    def update_time_stat(name, val):
        if val <= 0:
            return

        s = time_stats[name]
        s["sum"] += val
        s["count"] += 1
        s["max"] = max(s["max"], val)

        if val < 2:
            s["buckets"]["<2s"] += 1
        elif val < 5:
            s["buckets"]["<5s"] += 1
        elif val < 10:
            s["buckets"]["<10s"] += 1
        elif val < 20:
            s["buckets"]["<20s"] += 1
        elif val < 60:
            s["buckets"]["<60s"] += 1
        elif val < 300:
            s["buckets"]["<300s"] += 1
        else:
            s["buckets"][">=300s"] += 1

    all_times = []
    mal_times = []
    ben_times = []

    for _, row in df.iterrows():
        for t in time_fields:
            try:
                val = float(row[t])
            except:
                val = 0
            update_time_stat(t, val)

            if t == 'end_t':
                if val <= 0:
                    continue

                all_times.append(val)

            if int(row['label']) == 0:
                mal_times.append(val)
            else:
                ben_times.append(val)

    plt_time_distr(all_times, "All domains")
    plt_time_distr(ben_times, "Benign domains")
    plt_time_distr(mal_times, "Malicious domains")

    # ---------- CLASSIFIER METRICS ----------
    print("=== CLASSIFIER METRICS ===")

    for clf in CLASSIFIERS:
        y_true = []
        y_pred = []

        for _, row in df.iterrows():
            label = int(row["label"])
            final_pred = get_final_prediction(row, clf)

            if final_pred is None:
                continue

            y_true.append(label)
            y_pred.append(final_pred)

        print(f"\n===== {clf} =====")
        print(f"Used samples: {len(y_true)}")

        if len(y_true) == 0:
            print("No usable samples.")
            continue

        metrics = compute_metrics(y_true, y_pred)
        plt_conf_mat(metrics['Confusion Matrix'], clf)

        for k, v in metrics.items():
            print(f"{k}:")
            print(v)

    # ---------- TIME OUTPUT ----------
    print("\n=== TIME STATS ===")

    for t in time_fields:
        s = time_stats[t]
        print(f"\n--- {t} ---")

        if s["count"] == 0:
            print("No data")
            continue

        print(f"Avg: {s['sum'] / s['count']}")
        print(f"Max: {s['max']}")

        print("Buckets:")
        for k, v in s["buckets"].items():
            print(f"  {k}: {v}")


if __name__ == "__main__":
    analyze("updated_learning_all_cpu.csv")