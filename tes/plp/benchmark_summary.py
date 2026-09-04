"""
benchmark_summary.py - Generate summary tables from benchmark file.

Prints both tables to the terminal and saves them as CSV files to benchmarks.

Usage: python benchmark_summary.py [benchmark.csv]
"""
import os
import sys
import pandas as pd

input_csv = sys.argv[1] if len(sys.argv) > 1 else "./benchmarks/benchmark.csv"
OUT_DIR = "./benchmarks"
os.makedirs(OUT_DIR, exist_ok=True)

df = pd.read_csv(input_csv)
tes = df[(df["profile"] == "tes") & (df["run_type"] != "wakenode")].copy()
tes["n_parallel"] = tes["run_type"].str.extract(r"(\d+)").fillna(1).astype(int)
tes["wall_min"] = tes["total_time"] / 60

SIZES = {10000: "10K", 100000: "100K", 1000000: "1M"}
COL_ORDER = sorted(s for s in SIZES if s in tes["cohort_size"].unique())

RUN_ORDER = ["single", "parallel3", "parallel5", "parallel10"]
RUN_LABELS = {
    "single": "1 workflow (4 tasks)",
    "parallel3": "3 parallel (12 tasks)",
    "parallel5": "5 parallel (20 tasks)",
    "parallel10": "10 parallel (40 tasks)",
}
TES_TASKS = {"single": 4, "parallel3": 12, "parallel5": 20, "parallel10": 40}


# ── Table 1: single-workflow job specs ────────────────────────────────────────

single = (
    tes[tes["run_type"] == "single"]
    .groupby("cohort_size")
    .agg(
        sim_mb=("simulate_plp_data_outputs_mb", "mean"),
        model_mb=("run_plp_model_outputs_mb", "mean"),
        zip_mb=("zip_plp_outputs_mb", "mean"),
        work_mb=("total_work_mb", "mean"),
        wall=("wall_min", "mean"),
    )
    .round(1)
)

ROWS_T1 = [
    ("Input data (cohorts + outcomes)", "sim_mb", "{:.1f} MB"),
    ("Model outputs (runPlp.rds + model.pkl)", "model_mb", "{:.1f} MB"),
    ("Final zip", "zip_mb", "{:.1f} MB"),
    ("Total work directory", "work_mb", "{:.0f} MB"),
    ("TES tasks per workflow", None, "4"),
    ("Wall time", "wall", "{:.1f} min"),
]

t1_data = {}
for label, col, fmt in ROWS_T1:
    t1_data[label] = {
        SIZES[s]: (fmt.format(single.loc[s, col]) if col else fmt) for s in COL_ORDER
    }
t1 = pd.DataFrame(t1_data, index=[SIZES[s] for s in COL_ORDER]).T
t1.index.name = "Metric"


# ── Table 2: parallelization wall time ───────────────────────────────────────

available_run_types = tes["run_type"].unique()
t2_data = {}
for rt in RUN_ORDER:
    if rt not in available_run_types:
        continue
    g = tes[tes["run_type"] == rt].groupby("cohort_size")["wall_min"].mean().round(1)
    t2_data[RUN_LABELS[rt]] = {SIZES[s]: f"{g[s]:.1f} min" for s in COL_ORDER}
t2 = pd.DataFrame(t2_data, index=[SIZES[s] for s in COL_ORDER]).T
t2.index.name = "Parallelization"


# ── Print ─────────────────────────────────────────────────────────────────────


def print_table(title, df_table):
    print(f"\n{'─' * 70}")
    print(f"  {title}")
    print(f"{'─' * 70}")
    print(df_table.to_string())
    print()


print_table("Table 1 — TES workflow specs (single workflow per cohort size)", t1)
print_table("Table 2 — Parallelization: average wall time per workflow", t2)


# ── Save CSV ──────────────────────────────────────────────────────────────────

t1_path = os.path.join(OUT_DIR, "benchmark_summary_job_spec.csv")
t2_path = os.path.join(OUT_DIR, "benchmark_summary_parallelization.csv")

t1.to_csv(t1_path)
t2.to_csv(t2_path)

print(f"Saved:")
print(f"  {t1_path}")
print(f"  {t2_path}")
