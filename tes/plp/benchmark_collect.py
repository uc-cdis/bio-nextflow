"""
benchmark_collect.py - Nextflow Trace Benchmark Collector
---------------------------------------------------------
This script parses a Nextflow trace.txt file from a workflow run, extracts timings and resource metrics,
and appends them to a benchmark CSV file as a benchmarking entry.
CSV is saved after each addition for data integrity.
Defaults to benchmarks/benchmark.csv unless another CSV is specified.

Usage:
    python benchmark_collect.py <trace_txt> <profile> <run_type> <cohort_size> <benchmark_id> [benchmark_csv]
"""
import csv
import sys
import os
import pandas as pd
import re
import subprocess

DEFAULT_CSV = "benchmarks/benchmark.csv"


def download_trace_if_needed(trace_path):
    if trace_path.startswith("s3://"):
        local_trace = "/tmp/" + os.path.basename(trace_path)
        cmd = ["aws", "--profile", "tes-brh-stg", "s3", "cp", trace_path, local_trace]
        print(f"Downloading trace from S3: {trace_path} -> {local_trace}")
        result = subprocess.run(cmd, capture_output=True)
        if result.returncode != 0:
            print(f"Failed to download {trace_path}: {result.stderr.decode()}")
            return None
        return local_trace
    else:
        return trace_path


# parse arguments
if len(sys.argv) == 6:
    trace_path, profile, run_type, cohort_size, benchmark_id = sys.argv[1:6]
    benchmark_csv = DEFAULT_CSV
elif len(sys.argv) == 7:
    trace_path, profile, run_type, cohort_size, benchmark_id, benchmark_csv = sys.argv[
        1:7
    ]
else:
    print(
        "Usage: python benchmark_collect.py <trace_txt> <profile> <run_type> <cohort_size> <benchmark_id> [benchmark_csv]"
    )
    sys.exit(1)

os.makedirs(os.path.dirname(benchmark_csv), exist_ok=True)

trace_path = download_trace_if_needed(trace_path)
if not trace_path or not os.path.isfile(trace_path):
    print(f"trace.txt not found at {trace_path}")
    sys.exit(1)


def parse_duration(x):
    """
    Parse Nextflow 'duration' strings into seconds (float).
    Handles forms like:
      - '3s'
      - '3.2s'
      - '601ms'
      - '4m 30s'
      - '7m 44s'
      - '1h 2m 3.4s'
      - numeric seconds as plain float/int strings
    """
    if pd.isna(x):
        return None
    x = str(x).strip()
    if x == "-" or x == "":
        return None

    pattern = (
        r"^\s*(?:(\d+)h)?\s*(?:(\d+)m)?\s*(?:(\d+(?:\.\d+)?)s)?\s*(?:(\d+)ms)?\s*$"
    )
    m = re.match(pattern, x)
    if not m:
        # maybe just a raw number in seconds
        try:
            return float(x)
        except Exception:
            return None

    hours = int(m.group(1)) if m.group(1) else 0
    mins = int(m.group(2)) if m.group(2) else 0
    secs = float(m.group(3)) if m.group(3) else 0.0
    ms = int(m.group(4)) if m.group(4) else 0

    total = hours * 3600 + mins * 60 + secs + ms / 1000.0
    return total


def parse_trace_txt(trace_file):
    df = pd.read_csv(trace_file, sep="\t")

    # durations in seconds
    df["duration_s"] = df["duration"].apply(parse_duration)

    # step name: strip off " (x)" suffix
    df["step"] = df["name"].apply(
        lambda x: x.split(" (")[0] if isinstance(x, str) and " (" in x else x
    )

    return df


def summarize_timings(df):
    result = {}

    # Per-step times: sum of durations in seconds
    for step in ["create_workflow_inputs", "simulate_plp_data", "zip_plp_outputs"]:
        step_df = df[df["step"] == step]
        if step_df.empty or step_df["duration_s"].dropna().empty:
            result[f"{step}_time"] = None
        else:
            result[f"{step}_time"] = step_df["duration_s"].sum()

    # run_plp_model: sum / min / max durations
    step = "run_plp_model"
    step_df = df[df["step"] == step]
    if step_df.empty or step_df["duration_s"].dropna().empty:
        result["run_plp_model_time"] = None
        result["run_plp_model_min_time"] = None
        result["run_plp_model_max_time"] = None
        result["n_models"] = 0
    else:
        result["run_plp_model_time"] = step_df["duration_s"].sum()
        result["run_plp_model_min_time"] = step_df["duration_s"].min()
        result["run_plp_model_max_time"] = step_df["duration_s"].max()
        result["n_models"] = len(step_df)

    # total_time: sum of all durations
    if df["duration_s"].dropna().empty:
        result["total_time"] = None
    else:
        result["total_time"] = df["duration_s"].sum()

    return result


def get_resources(df):
    cpu, rss, vmem = None, None, None

    # CPU
    if "%cpu" in df.columns:
        cpu_col = df["%cpu"].replace({"-": None}).dropna()
        if not cpu_col.empty:
            if cpu_col.dtype == "O":
                cpu_col = cpu_col.str.replace("%", "", regex=False)
                cpu_col = pd.to_numeric(cpu_col, errors="coerce")
                cpu_col = cpu_col.dropna()
            if not cpu_col.empty:
                cpu = cpu_col.max()

    # RSS (to MB)
    if "peak_rss" in df.columns:

        def rss_to_mb(rss):
            if rss is None or rss == "-" or pd.isna(rss):
                return None
            rss = str(rss).strip()
            if rss.endswith("MB"):
                try:
                    return float(rss.replace("MB", "").strip())
                except Exception:
                    return None
            if rss.endswith("GB"):
                try:
                    return float(rss.replace("GB", "").strip()) * 1024.0
                except Exception:
                    return None
            try:
                return float(rss)
            except Exception:
                return None

        rss_col = df["peak_rss"].replace({"-": None}).dropna().apply(rss_to_mb)
        rss_col = rss_col.dropna()
        if not rss_col.empty:
            rss = rss_col.max()

    # VMEM (to GB)
    if "peak_vmem" in df.columns:

        def vmem_to_gb(vmem):
            if vmem is None or vmem == "-" or pd.isna(vmem):
                return None
            vmem = str(vmem).strip()
            if vmem.endswith("GB"):
                try:
                    return float(vmem.replace("GB", "").strip())
                except Exception:
                    return None
            if vmem.endswith("MB"):
                try:
                    return float(vmem.replace("MB", "").strip()) / 1024.0
                except Exception:
                    return None
            try:
                return float(vmem)
            except Exception:
                return None

        vmem_col = df["peak_vmem"].replace({"-": None}).dropna().apply(vmem_to_gb)
        vmem_col = vmem_col.dropna()
        if not vmem_col.empty:
            vmem = vmem_col.max()

    return cpu, rss, vmem


def append_to_csv(benchmark_csv, run_info):
    if os.path.isfile(benchmark_csv):
        df = pd.read_csv(benchmark_csv)
        df = pd.concat([df, pd.DataFrame([run_info])], ignore_index=True)
    else:
        df = pd.DataFrame([run_info])
    df.to_csv(benchmark_csv, index=False)


df = parse_trace_txt(trace_path)
timings = summarize_timings(df)
cpu, rss, vmem = get_resources(df)

run_info = {
    "benchmark_id": benchmark_id,
    "profile": profile,
    "run_type": run_type,
    "cohort_size": cohort_size,
    "total_time": timings.get("total_time"),
    "create_workflow_inputs_time": timings.get("create_workflow_inputs_time"),
    "simulate_plp_data_time": timings.get("simulate_plp_data_time"),
    "run_plp_model_time": timings.get("run_plp_model_time"),
    "run_plp_model_min_time": timings.get("run_plp_model_min_time"),
    "run_plp_model_max_time": timings.get("run_plp_model_max_time"),
    "zip_plp_outputs_time": timings.get("zip_plp_outputs_time"),
    "max_cpu_percent": cpu,
    "max_peak_rss_mb": rss,
    "max_peak_vmem_gb": vmem,
    "n_models": timings.get("n_models"),
    "trace_file": trace_path,
}

append_to_csv(benchmark_csv, run_info)
print(f"Benchmark entry for {benchmark_id} appended to {benchmark_csv}")
