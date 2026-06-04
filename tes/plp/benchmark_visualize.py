"""
benchmark_visualize.py - Workflow Benchmark Visualization
---------------------------------------------------------
Loads benchmark.csv and generates analytical plots (PNG) to benchmarks/plots/.
Plots include total workflow time, stepwise timing, resource usage, and parallel efficiency.

Usage: python benchmark_visualize.py [benchmark.csv]
(Defaults to benchmarks/benchmark.csv if not specified)
"""
import os
import sys
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

PLOT_DIR = "./benchmarks/plots"
os.makedirs(PLOT_DIR, exist_ok=True)

# --- Load CSV ---
benchmark_csv = sys.argv[1] if len(sys.argv) > 1 else "./benchmarks/benchmark.csv"
df = pd.read_csv(benchmark_csv)

# --- 1. Total Workflow Time Barplot ---
plt.figure(figsize=(10, 6))
sns.barplot(
    data=df, x="run_type", y="total_time", hue="profile", palette="colorblind", ci=None
)
plt.title("Total Workflow Time by Run Type and Profile")
plt.ylabel("Total time (seconds)")
plt.xlabel("Run Type")
plt.legend()
plt.tight_layout()
plt.savefig(os.path.join(PLOT_DIR, "total_workflow_time.png"))
plt.close()

# --- 2. Stepwise Timing Boxplot ---
steps = [
    "create_workflow_inputs_time",
    "simulate_plp_data_time",
    "run_plp_model_time",
    "zip_plp_outputs_time",
]
melted = df.melt(
    id_vars=["benchmark_id", "cohort_size", "profile", "run_type"],
    value_vars=steps,
    var_name="step",
    value_name="time",
)

plt.figure(figsize=(12, 7))
sns.barplot(
    data=melted,
    x="step",
    y="time",
    hue="profile",
    ci="sd",
    palette="colorblind",
    edgecolor="black",
)
sns.stripplot(
    data=melted,
    x="step",
    y="time",
    hue="profile",
    dodge=True,
    palette="colorblind",
    marker="o",
    alpha=0.7,
)
plt.title("Stepwise Run Time by Profile")
plt.ylabel("Step Time (seconds)")
plt.xlabel("Step")
plt.xticks(rotation=15)
plt.tight_layout()
plt.legend()
plt.savefig(os.path.join(PLOT_DIR, "stepwise_run_time.png"))
plt.close()

# --- 3. Resource Usage ---
# COMMENTED OUT: no CPU/memory for TES
# plt.figure(figsize=(10,6))
# sns.barplot(data=df, x='run_type', y='max_cpu_percent', hue='profile', palette='colorblind', ci=None)
# plt.title('Max CPU Usage by Run Type and Profile')
# plt.ylabel("Max CPU (%)")
# plt.tight_layout()
# plt.savefig(os.path.join(PLOT_DIR, "max_cpu_usage.png"))
# plt.close()
#
# plt.figure(figsize=(10,6))
# sns.barplot(data=df, x='run_type', y='max_peak_rss_mb', hue='profile', palette='colorblind', ci=None)
# plt.title('Max Memory Usage (RSS) by Run Type and Profile')
# plt.ylabel("Max Memory (MB)")
# plt.tight_layout()
# plt.savefig(os.path.join(PLOT_DIR, "max_memory_usage.png"))
# plt.close()

# --- 4. Parallel Efficiency ---
df["n_parallel"] = df["run_type"].str.extract("(\d+)").fillna(1).astype(int)
plt.figure(figsize=(11, 7))
palette = sns.color_palette("colorblind")
profiles = df["profile"].unique()
profile_colors = dict(zip(profiles, palette[: len(profiles)]))
sns.lineplot(
    data=df,
    x="n_parallel",
    y="total_time",
    hue="profile",
    style="profile",
    palette=profile_colors,
    markers=True,
    dashes=False,
    linewidth=2.5,
)
for i, row in df.iterrows():
    plt.scatter(
        row["n_parallel"],
        row["total_time"],
        color=profile_colors[row["profile"]],
        s=50,
        zorder=3,
    )
plt.title("Parallel Scalability: Total Time vs Number of Workflows")
plt.xlabel("Number of Parallel Workflows")
plt.ylabel("Total Workflow Time (seconds)")
plt.tight_layout()
plt.savefig(os.path.join(PLOT_DIR, "parallel_scalability.png"))
plt.close()

print(f"Plots saved in: {os.path.abspath(PLOT_DIR)}")
