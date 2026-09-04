"""
benchmark_collect.py - Nextflow Trace Benchmark Collector
---------------------------------------------------------
Parses a Nextflow trace.txt, extracts timings and resource metrics,
and appends a row to benchmark.csv.

Column availability by profile:
  All profiles : total_time, *_time columns, total_realtime,
                 simulate_plp_data_outputs_mb  — cohorts.rds + outcomes.rds (plpData files fed into run_plp_model)
                 run_plp_model_outputs_mb      — runPlp.rds + model.pkl (trained model + full result object)
                 zip_plp_outputs_mb            — {plpRunName}.zip (final packaged output)
                 total_work_mb                 — entire Nextflow work directory (outputs + control files)
  local only   : max_cpu_percent, max_peak_rss_mb, max_peak_vmem_gb
                 (TES does not expose per-task resource usage via the TES API)

Usage:
    python benchmark_collect.py <trace_txt> <profile> <run_type> <cohort_size>
                                <benchmark_id> [benchmark_csv] [work_path]

    work_path — for local: absolute path to the Nextflow work directory on disk
                for TES  : S3 URI of the Nextflow work directory
                           (e.g. s3://bucket/plp-benchmark/<id>/work)
"""
import sys
import os
import pandas as pd
import re
import subprocess

DEFAULT_CSV = "benchmarks/benchmark.csv"
AWS_PROFILE = "tes-brh-stg"


# ── Trace download ────────────────────────────────────────────────────────────


def download_trace_if_needed(trace_path):
    if trace_path.startswith("s3://"):
        local_trace = "/tmp/" + os.path.basename(trace_path)
        cmd = ["aws", "--profile", AWS_PROFILE, "s3", "cp", trace_path, local_trace]
        print(f"Downloading trace from S3: {trace_path} -> {local_trace}")
        result = subprocess.run(cmd, capture_output=True)
        if result.returncode != 0:
            print(f"Failed to download {trace_path}: {result.stderr.decode()}")
            return None
        return local_trace
    return trace_path


# ── Parsing helpers ───────────────────────────────────────────────────────────


def parse_duration(x):
    """Parse Nextflow duration strings (e.g. '4m 30s', '601ms', '1h 2m') to seconds."""
    if pd.isna(x):
        return None
    x = str(x).strip()
    if x in ("-", ""):
        return None
    pattern = (
        r"^\s*(?:(\d+)h)?\s*(?:(\d+)m)?\s*(?:(\d+(?:\.\d+)?)s)?\s*(?:(\d+)ms)?\s*$"
    )
    m = re.match(pattern, x)
    if not m:
        try:
            return float(x)
        except Exception:
            return None
    hours = int(m.group(1)) if m.group(1) else 0
    mins = int(m.group(2)) if m.group(2) else 0
    secs = float(m.group(3)) if m.group(3) else 0.0
    ms = int(m.group(4)) if m.group(4) else 0
    return hours * 3600 + mins * 60 + secs + ms / 1000.0


def parse_bytes_to_mb(val):
    """Parse Nextflow byte strings (e.g. '18.6 MB', '3.1 GB', '886 B') to MB."""
    if val is None or val == "-" or pd.isna(val):
        return None
    val = str(val).strip()
    for unit, factor in [
        ("TB", 1024**2),
        ("GB", 1024),
        ("MB", 1),
        ("KB", 1 / 1024),
        ("B", 1 / 1024**2),
    ]:
        if val.endswith(unit):
            try:
                return float(val[: -len(unit)].strip()) * factor
            except Exception:
                return None
    try:
        return float(val) / (1024**2)
    except Exception:
        return None


# ── Trace parsing ─────────────────────────────────────────────────────────────


def parse_trace_txt(trace_file):
    df = pd.read_csv(trace_file, sep="\t")
    df["duration_s"] = df["duration"].apply(parse_duration)
    df["step"] = df["name"].apply(
        lambda x: x.split(" (")[0] if isinstance(x, str) and " (" in x else x
    )
    return df


def summarize_timings(df):
    result = {}
    for step in ["create_workflow_inputs", "simulate_plp_data", "zip_plp_outputs"]:
        step_df = df[df["step"] == step]
        result[f"{step}_time"] = (
            step_df["duration_s"].sum()
            if not step_df.empty and not step_df["duration_s"].dropna().empty
            else None
        )
    step_df = df[df["step"] == "run_plp_model"]
    if step_df.empty or step_df["duration_s"].dropna().empty:
        result.update(
            run_plp_model_time=None,
            run_plp_model_min_time=None,
            run_plp_model_max_time=None,
            n_models=0,
        )
    else:
        result.update(
            run_plp_model_time=step_df["duration_s"].sum(),
            run_plp_model_min_time=step_df["duration_s"].min(),
            run_plp_model_max_time=step_df["duration_s"].max(),
            n_models=len(step_df),
        )
    vals = df["duration_s"].dropna()
    result["total_time"] = vals.sum() if not vals.empty else None
    return result


def get_resources(df):
    """
    Extract per-task resource metrics from the trace.

    max_cpu_percent, max_peak_rss_mb, max_peak_vmem_gb — LOCAL ONLY.
    TES does not report these (the TES API does not expose process-level
    resource usage from remote nodes); they will be None for TES runs.

    total_realtime — available for both local and TES (Nextflow tracks
    task start/end at the client side regardless of executor).
    """
    cpu = rss = vmem = total_realtime = None

    if "%cpu" in df.columns:
        col = df["%cpu"].replace({"-": None}).dropna()
        if not col.empty:
            col = pd.to_numeric(
                col.astype(str).str.replace("%", "", regex=False), errors="coerce"
            ).dropna()
            if not col.empty:
                cpu = col.max()

    if "peak_rss" in df.columns:
        col = (
            df["peak_rss"]
            .replace({"-": None})
            .dropna()
            .apply(parse_bytes_to_mb)
            .dropna()
        )
        if not col.empty:
            rss = col.max()

    if "peak_vmem" in df.columns:

        def vmem_to_gb(v):
            mb = parse_bytes_to_mb(v)
            return mb / 1024 if mb is not None else None

        col = df["peak_vmem"].replace({"-": None}).dropna().apply(vmem_to_gb).dropna()
        if not col.empty:
            vmem = col.max()

    if "realtime" in df.columns:
        col = df["realtime"].apply(parse_duration).dropna()
        if not col.empty:
            total_realtime = col.sum()

    return cpu, rss, vmem, total_realtime


# ── File size collection (common to local and TES) ────────────────────────────

# Output files grouped by the step that produces them; each column sums all listed files.
#   simulate_plp_data_outputs_mb — cohorts.rds + outcomes.rds (plpData fed into run_plp_model)
#   run_plp_model_outputs_mb     — runPlp.rds + model.pkl (trained model + full result object)
#   zip_plp_outputs_mb           — {plpRunName}.zip (matched by .zip extension; name varies per run)
#   total_work_mb                — entire work directory (outputs + Nextflow control files)
_STEP_FILES = {
    "simulate_plp_data_outputs_mb": ["cohorts.rds", "outcomes.rds"],
    "run_plp_model_outputs_mb": ["runPlp.rds", "model.pkl"],
}
_SIZE_COLS = list(_STEP_FILES) + ["zip_plp_outputs_mb", "total_work_mb"]


def get_file_sizes(profile, work_path, launch_dir=None):
    """
    Collect per-step output sizes (MB) and total disk footprint.
    Works for both local (filesystem) and TES (S3) profiles.

    profile    — 'local' or 'tes'
    work_path  — absolute local path (local) or s3:// URI (TES)
    launch_dir — directory Nextflow was launched from; used to find
                 results/{id}.zip which publishDir moves here for both profiles
    """
    result = {k: None for k in _SIZE_COLS}

    # Zip lands in launch_dir/results/ for both local and TES runs
    # (publishDir mode:'move' moves it out of the work dir to local results/)
    zip_bytes = 0
    if launch_dir:
        results_dir = os.path.join(launch_dir, "results")
        r = subprocess.run(
            ["find", results_dir, "-type", "f", "-name", "*.zip"],
            capture_output=True,
            text=True,
        )
        zip_paths = [p for p in r.stdout.strip().splitlines() if p]
        if zip_paths:
            zip_bytes = sum(os.path.getsize(p) for p in zip_paths)
            result["zip_plp_outputs_mb"] = zip_bytes / (1024**2)

    if not work_path:
        return result

    if profile == "local":
        if not os.path.isdir(work_path):
            print(f"  work dir not found: {work_path}")
            return result

        for col, filenames in _STEP_FILES.items():
            total = 0
            found_any = False
            for filename in filenames:
                r = subprocess.run(
                    ["find", work_path, "-type", "f", "-name", filename],
                    capture_output=True,
                    text=True,
                )
                paths = [p for p in r.stdout.strip().splitlines() if p]
                if paths:
                    total += sum(os.path.getsize(p) for p in paths)
                    found_any = True
            if found_any:
                result[col] = total / (1024**2)

        du = subprocess.run(["du", "-sb", work_path], capture_output=True, text=True)
        if du.returncode == 0:
            work_bytes = int(du.stdout.split()[0])
            result["total_work_mb"] = (work_bytes + zip_bytes) / (1024**2)

    else:  # TES — list S3 objects
        cmd = ["aws", "s3", "ls", "--recursive", work_path, "--profile", AWS_PROFILE]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            print(f"  S3 listing failed: {r.stderr.strip()}")
            return result

        fname_to_col = {f: col for col, fnames in _STEP_FILES.items() for f in fnames}
        step_bytes = {col: 0 for col in _STEP_FILES}
        step_found = {col: False for col in _STEP_FILES}
        total_bytes = 0

        for line in r.stdout.splitlines():
            parts = line.split()
            if len(parts) < 4:
                continue
            try:
                size = int(parts[2])
            except ValueError:
                continue
            total_bytes += size
            fname = os.path.basename(parts[3])
            if fname in fname_to_col:
                col = fname_to_col[fname]
                step_bytes[col] += size
                step_found[col] = True

        for col in _STEP_FILES:
            if step_found[col]:
                result[col] = step_bytes[col] / (1024**2)
        if total_bytes or zip_bytes:
            result["total_work_mb"] = (total_bytes + zip_bytes) / (1024**2)

    return result


# ── CSV append ────────────────────────────────────────────────────────────────


def append_to_csv(benchmark_csv, run_info):
    if os.path.isfile(benchmark_csv):
        df = pd.read_csv(benchmark_csv)
        df = pd.concat([df, pd.DataFrame([run_info])], ignore_index=True)
    else:
        df = pd.DataFrame([run_info])
    df.to_csv(benchmark_csv, index=False)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) not in (6, 7, 8, 9):
        print(__doc__)
        sys.exit(1)

    trace_path = sys.argv[1]
    profile = sys.argv[2]
    run_type = sys.argv[3]
    cohort_size = sys.argv[4]
    benchmark_id = sys.argv[5]
    benchmark_csv = sys.argv[6] if len(sys.argv) >= 7 else DEFAULT_CSV
    work_path = sys.argv[7] if len(sys.argv) >= 8 else None
    launch_dir = sys.argv[8] if len(sys.argv) == 9 else None

    os.makedirs(os.path.dirname(benchmark_csv), exist_ok=True)

    trace_path = download_trace_if_needed(trace_path)
    if not trace_path or not os.path.isfile(trace_path):
        print(f"trace.txt not found at {trace_path}")
        sys.exit(1)

    df_trace = parse_trace_txt(trace_path)
    timings = summarize_timings(df_trace)
    cpu, rss, vmem, total_realtime = get_resources(df_trace)
    sizes = get_file_sizes(profile, work_path, launch_dir=launch_dir)

    run_info = {
        "benchmark_id": benchmark_id,
        "profile": profile,
        "run_type": run_type,
        "cohort_size": cohort_size,
        # ── timing (all profiles) ──────────────────────────────────────────
        "total_time": timings.get("total_time"),
        "total_realtime": total_realtime,
        "create_workflow_inputs_time": timings.get("create_workflow_inputs_time"),
        "simulate_plp_data_time": timings.get("simulate_plp_data_time"),
        "run_plp_model_time": timings.get("run_plp_model_time"),
        "run_plp_model_min_time": timings.get("run_plp_model_min_time"),
        "run_plp_model_max_time": timings.get("run_plp_model_max_time"),
        "zip_plp_outputs_time": timings.get("zip_plp_outputs_time"),
        # ── file sizes (all profiles, via filesystem or S3) ───────────────
        "simulate_plp_data_outputs_mb": sizes["simulate_plp_data_outputs_mb"],
        "run_plp_model_outputs_mb": sizes["run_plp_model_outputs_mb"],
        "zip_plp_outputs_mb": sizes["zip_plp_outputs_mb"],
        "total_work_mb": sizes["total_work_mb"],
        # ── resource usage (local only — None for TES) ────────────────────
        "max_cpu_percent": cpu,
        "max_peak_rss_mb": rss,
        "max_peak_vmem_gb": vmem,
        # ── misc ──────────────────────────────────────────────────────────
        "n_models": timings.get("n_models"),
        "trace_file": trace_path,
    }

    append_to_csv(benchmark_csv, run_info)
    print(f"Benchmark entry for {benchmark_id} appended to {benchmark_csv}")
