"""
benchmark_visualize.py - Workflow Benchmark Visualization
---------------------------------------------------------
Loads benchmark.csv and generates two groups of plots to benchmarks/plots/:

  Group 1 — profile_comparison_*.png  (only when multiple profiles present)
    Local vs TES at the cohort sizes common to both — hue=profile.

  Group 2 — *.png
    Profiles that have multiple cohort sizes (e.g. TES) — hue=cohort_size.

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

# Categorical palette — reference slots 1–4 (blue, orange, aqua, yellow)
COHORT_PALETTE = ["#2a78d6", "#eb6834", "#1baf7a"]  # 10K=blue, 100K=orange, 1M=aqua
RUN_TYPE_PALETTE = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]

# Profile colors: tes=blue (matches TES 10K in cohort plots), local=yellow (unused by TES)
PROFILE_COLORS = {"tes": "#2a78d6", "local": "#eda100"}

# --- Load ---
benchmark_csv = sys.argv[1] if len(sys.argv) > 1 else "./benchmarks/benchmark.csv"
df = pd.read_csv(benchmark_csv)

# Seconds → minutes
time_cols = [c for c in df.columns if c.endswith("_time")]
df[time_cols] = df[time_cols] / 60

# Human-readable cohort labels (ordered categorical)
size_labels = {10000: "10K", 100000: "100K", 1000000: "1M"}
df["Cohort size"] = pd.Categorical(
    df["cohort_size"].map(size_labels),
    categories=["10K", "100K", "1M"],
    ordered=True,
)
df["n_parallel"] = df["run_type"].str.extract(r"(\d+)").fillna(1).astype(int)

RUN_TYPE_ORDER = ["wakenode", "single", "parallel3", "parallel5", "parallel10"]
PARALLEL_RUN_TYPES = ["single", "parallel3", "parallel5", "parallel10"]

STEPS = [
    "create_workflow_inputs_time",
    "simulate_plp_data_time",
    "run_plp_model_time",
    "zip_plp_outputs_time",
]
STEP_LABELS = {
    "create_workflow_inputs_time": "Create inputs",
    "simulate_plp_data_time": "Simulate data",
    "run_plp_model_time": "Run PLP model",
    "zip_plp_outputs_time": "Zip outputs",
}
STEP_ORDER = [STEP_LABELS[s] for s in STEPS]

# --- Profile / cohort coverage analysis ---
profiles = sorted(df["profile"].unique())
n_profiles = len(profiles)

# Profiles that cover more than one cohort size → used for Group 2 scaling plots
multi_cohort_profiles = (
    df.groupby("profile")["cohort_size"]
    .nunique()
    .pipe(lambda s: s[s > 1].index.tolist())
)
df_g2 = df[df["profile"].isin(multi_cohort_profiles)] if multi_cohort_profiles else df

# Cohort sizes present in every profile → used for Group 1 comparison
common_sizes = set.intersection(
    *[set(df[df["profile"] == p]["cohort_size"].unique()) for p in profiles]
)

# Labels and filename prefixes derived from data
g2_profiles = multi_cohort_profiles if multi_cohort_profiles else profiles
g2_title_tag = "(" + " + ".join(p.upper() for p in sorted(g2_profiles)) + " only)"
g2_file_prefix = "_".join(sorted(g2_profiles))  # e.g. "tes"

g1_size_label = " + ".join(
    size_labels[s] for s in sorted(common_sizes) if s in size_labels
)
g1_title_tag = f"({g1_size_label} cohort)"
g1_file_prefix = "_".join(
    size_labels[s].lower() for s in sorted(common_sizes) if s in size_labels
)


def _add_strip(g, x, y, hue, hue_order, palette, order=None):
    kw = dict(
        x=x,
        y=y,
        hue=hue,
        hue_order=hue_order,
        dodge=True,
        palette=palette,
        alpha=0.7,
        size=4,
        jitter=True,
        linewidth=0.8,
        edgecolor="white",
        legend=False,
    )
    if order is not None:
        kw["order"] = order
    g.map_dataframe(sns.stripplot, **kw)


def _add_scatter(g, x, y, hue, hue_order, palette):
    g.map_dataframe(
        sns.scatterplot,
        x=x,
        y=y,
        hue=hue,
        hue_order=hue_order,
        palette=palette,
        alpha=0.35,
        s=30,
        zorder=3,
        legend=False,
    )


def _save(
    g, filename, title, legend_title, x_label="", rotate_x=False, has_col_facet=False
):
    g.figure.suptitle(title, y=1.02)
    if has_col_facet:
        g.set_titles(col_template="{col_name}")
    if g.legend is not None:
        g.legend.set_title(legend_title)
    # Re-apply after map_dataframe overwrites labels with raw column names
    g.set_axis_labels(x_label, "Time (minutes)")
    if rotate_x:
        g.set_xticklabels(rotation=10)
    g.savefig(os.path.join(PLOT_DIR, filename), dpi=150, bbox_inches="tight")
    plt.close("all")


def _melt(data):
    m = data.melt(
        id_vars=["benchmark_id", "Cohort size", "run_type", "profile"],
        value_vars=STEPS,
        var_name="step",
        value_name="time",
    )
    m["step"] = m["step"].map(STEP_LABELS)
    return m


# ── GROUP 2: cohort size scaling (profiles with full cohort coverage) ────────────
g2_multi = len(multi_cohort_profiles) > 1
g2_col_kw = {"col": "profile"} if g2_multi else {}
aspect_g2 = 1.7 if not g2_multi else 1.2

# 2a. Total workflow time
g = sns.catplot(
    data=df_g2,
    kind="bar",
    x="run_type",
    y="total_time",
    hue="Cohort size",
    palette=COHORT_PALETTE,
    order=RUN_TYPE_ORDER,
    errorbar="sd",
    height=6,
    aspect=aspect_g2,
    **g2_col_kw,
)
_add_strip(
    g,
    "run_type",
    "total_time",
    "Cohort size",
    ["10K", "100K", "1M"],
    COHORT_PALETTE,
    RUN_TYPE_ORDER,
)
_save(
    g,
    f"{g2_file_prefix}_total_workflow_time.png",
    f"Total Workflow Time by Run Type and Cohort Size {g2_title_tag}",
    "Cohort size",
    x_label="Run type",
    has_col_facet=g2_multi,
)

# 2b. Stepwise timing
g = sns.catplot(
    data=_melt(df_g2),
    kind="bar",
    x="step",
    y="time",
    hue="Cohort size",
    palette=COHORT_PALETTE,
    errorbar="sd",
    height=6,
    aspect=aspect_g2,
    **g2_col_kw,
)
_add_strip(
    g, "step", "time", "Cohort size", ["10K", "100K", "1M"], COHORT_PALETTE, STEP_ORDER
)
_save(
    g,
    f"{g2_file_prefix}_stepwise_run_time.png",
    f"Stepwise Run Time by Cohort Size {g2_title_tag}",
    "Cohort size",
    x_label="Step",
    rotate_x=True,
    has_col_facet=g2_multi,
)

# 2c. Parallel scalability
df_par_g2 = df_g2[df_g2["run_type"].isin(PARALLEL_RUN_TYPES)].copy()
g = sns.relplot(
    data=df_par_g2,
    kind="line",
    x="n_parallel",
    y="total_time",
    hue="Cohort size",
    palette=COHORT_PALETTE,
    markers=True,
    dashes=False,
    linewidth=2.5,
    errorbar="sd",
    height=6,
    aspect=aspect_g2,
    **g2_col_kw,
)
g.set(xticks=[1, 3, 5, 10])
_add_scatter(
    g, "n_parallel", "total_time", "Cohort size", ["10K", "100K", "1M"], COHORT_PALETTE
)
_save(
    g,
    f"{g2_file_prefix}_parallel_scalability.png",
    f"Parallel Scalability by Cohort Size {g2_title_tag}",
    "Cohort size",
    x_label="Number of parallel workflows",
    has_col_facet=g2_multi,
)

# 2d. Cohort size scaling
df_scale = df_g2[df_g2["run_type"].isin(PARALLEL_RUN_TYPES)].copy()
g = sns.relplot(
    data=df_scale,
    kind="line",
    x="cohort_size",
    y="total_time",
    hue="run_type",
    hue_order=PARALLEL_RUN_TYPES,
    palette=RUN_TYPE_PALETTE,
    markers=True,
    dashes=False,
    linewidth=2.5,
    errorbar="sd",
    height=6,
    aspect=aspect_g2,
    **g2_col_kw,
)
for ax in g.axes.flat:
    ax.set_xscale("log")
    ax.set_xticks([10000, 100000, 1000000])
    ax.set_xticklabels(["10K", "100K", "1M"])
_add_scatter(
    g, "cohort_size", "total_time", "run_type", PARALLEL_RUN_TYPES, RUN_TYPE_PALETTE
)
_save(
    g,
    f"{g2_file_prefix}_cohort_size_scaling.png",
    f"Cohort Size Scaling by Run Type {g2_title_tag}",
    "Run type",
    x_label="Cohort size",
    has_col_facet=g2_multi,
)


# ── GROUP 1: profile comparison (only when >1 profile present) ───────────────────
if n_profiles > 1:
    profile_palette = [
        PROFILE_COLORS.get(p, RUN_TYPE_PALETTE[i]) for i, p in enumerate(profiles)
    ]
    df_g1 = df[df["cohort_size"].isin(common_sizes)].copy()
    g1_multi = len(common_sizes) > 1
    g1_col_kw = {"col": "Cohort size"} if g1_multi else {}
    aspect_g1 = 1.7 if not g1_multi else 1.2

    # 1a. Total workflow time
    g = sns.catplot(
        data=df_g1,
        kind="bar",
        x="run_type",
        y="total_time",
        hue="profile",
        hue_order=profiles,
        palette=profile_palette,
        order=RUN_TYPE_ORDER,
        errorbar="sd",
        height=6,
        aspect=aspect_g1,
        **g1_col_kw,
    )
    _add_strip(
        g,
        "run_type",
        "total_time",
        "profile",
        profiles,
        profile_palette,
        RUN_TYPE_ORDER,
    )
    _save(
        g,
        f"profile_comparison_{g1_file_prefix}_total_time.png",
        f"Profile Comparison: Total Workflow Time {g1_title_tag}",
        "Profile",
        x_label="Run type",
        has_col_facet=g1_multi,
    )

    # 1b. Stepwise timing
    g = sns.catplot(
        data=_melt(df_g1),
        kind="bar",
        x="step",
        y="time",
        hue="profile",
        hue_order=profiles,
        palette=profile_palette,
        errorbar="sd",
        height=6,
        aspect=aspect_g1,
        **g1_col_kw,
    )
    _add_strip(g, "step", "time", "profile", profiles, profile_palette, STEP_ORDER)
    _save(
        g,
        f"profile_comparison_{g1_file_prefix}_stepwise.png",
        f"Profile Comparison: Stepwise Run Time {g1_title_tag}",
        "Profile",
        x_label="Step",
        rotate_x=True,
        has_col_facet=g1_multi,
    )

    # 1c. Parallel scalability
    df_par_g1 = df_g1[df_g1["run_type"].isin(PARALLEL_RUN_TYPES)].copy()
    g = sns.relplot(
        data=df_par_g1,
        kind="line",
        x="n_parallel",
        y="total_time",
        hue="profile",
        hue_order=profiles,
        palette=profile_palette,
        markers=True,
        dashes=False,
        linewidth=2.5,
        errorbar="sd",
        height=6,
        aspect=aspect_g1,
        **g1_col_kw,
    )
    g.set(xticks=[1, 3, 5, 10])
    _add_scatter(g, "n_parallel", "total_time", "profile", profiles, profile_palette)
    _save(
        g,
        f"profile_comparison_{g1_file_prefix}_parallel.png",
        f"Profile Comparison: Parallel Scalability {g1_title_tag}",
        "Profile",
        x_label="Number of parallel workflows",
        has_col_facet=g1_multi,
    )

# --- Summary ---
print(f"Plots saved in: {os.path.abspath(PLOT_DIR)}")
if n_profiles > 1:
    print(
        f"  Group 1 (profile comparison): cohort sizes {sorted(common_sizes)} — {n_profiles} profiles"
    )
    print(f"  Group 2 (cohort scaling): profiles {multi_cohort_profiles}")
