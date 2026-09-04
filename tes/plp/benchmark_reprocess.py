"""
benchmark_reprocess.py - One-time backfill script for pre-disk-metrics benchmarks.

NOTE: This is a temporary script to enrich older benchmark.csv files that were
collected before benchmark_collect.py gained file size support. New benchmarks
produced by benchmark_plp.py automatically include all disk metrics — this
script is not needed for them.

Reads benchmark.csv, re-parses each trace file and work directory, and writes
benchmark_w_disk.csv with the unified column set (same as a fresh benchmark_collect run).

For local runs: looks for the Nextflow work dir at
    benchmarks/{id}-launch/benchmarks/{id}/
For TES runs  : downloads file listing from
    s3://$BUCKET/plp-benchmark/{id}/work  (requires BUCKET env var)

Usage: python benchmark_reprocess.py [benchmark.csv] [output.csv]
"""
import os
import sys
import pandas as pd

from benchmark_collect import (
    download_trace_if_needed,
    parse_trace_txt,
    summarize_timings,
    get_resources,
    get_file_sizes,
)

BENCHMARK_DIR = "./benchmarks"
WORKFLOW_DIR = "./benchmarks/workflows"
input_csv = (
    sys.argv[1] if len(sys.argv) > 1 else os.path.join(BENCHMARK_DIR, "benchmark.csv")
)
output_csv = (
    sys.argv[2]
    if len(sys.argv) > 2
    else os.path.join(BENCHMARK_DIR, "benchmark_w_disk.csv")
)

df_bench = pd.read_csv(input_csv)
rows = []

for _, row in df_bench.iterrows():
    benchmark_id = row["benchmark_id"]
    profile = row["profile"]

    # ── Locate trace file ──────────────────────────────────────────────────
    if profile == "local":
        trace_path = os.path.join(WORKFLOW_DIR, f"{benchmark_id}.trace.txt")
        trace_path = trace_path if os.path.isfile(trace_path) else None
    else:
        tmp = f"/tmp/{benchmark_id}.trace.txt"
        if os.path.isfile(tmp):
            trace_path = tmp
        else:
            bucket = os.environ.get("BUCKET")
            s3 = (
                f"s3://{bucket}/plp-benchmark/{benchmark_id}.trace.txt"
                if bucket
                else None
            )
            trace_path = download_trace_if_needed(s3) if s3 else None

    # ── Locate work directory ──────────────────────────────────────────────
    if profile == "local":
        launch_dir = os.path.join(WORKFLOW_DIR, f"{benchmark_id}-launch")
        work_path = os.path.abspath(
            os.path.join(launch_dir, WORKFLOW_DIR, benchmark_id)
        )
        work_path = work_path if os.path.isdir(work_path) else None
    else:
        bucket = os.environ.get("BUCKET")
        work_path = (
            f"s3://{bucket}/plp-benchmark/{benchmark_id}/work" if bucket else None
        )

    # ── Parse ──────────────────────────────────────────────────────────────
    timings = total_realtime = cpu = rss = vmem = None
    sizes = {
        k: None
        for k in [
            "simulate_plp_data_outputs_mb",
            "run_plp_model_outputs_mb",
            "zip_plp_outputs_mb",
            "total_work_mb",
        ]
    }

    if trace_path and os.path.isfile(trace_path):
        try:
            df_trace = parse_trace_txt(trace_path)
            timings = summarize_timings(df_trace)
            cpu, rss, vmem, total_realtime = get_resources(df_trace)
        except Exception as e:
            print(f"  {benchmark_id}: trace parse error — {e}")
    else:
        print(f"  {benchmark_id}: trace not found, keeping original timings")

    launch_dir = os.path.join(WORKFLOW_DIR, f"{benchmark_id}-launch")
    launch_dir = launch_dir if os.path.isdir(launch_dir) else None

    sizes = get_file_sizes(profile, work_path, launch_dir=launch_dir)

    # Report
    parts = []
    if total_realtime is not None:
        parts.append(f"realtime={total_realtime:.0f}s")
    if sizes["total_work_mb"]:
        parts.append(f"work={sizes['total_work_mb']:.1f} MB")
    if sizes["simulate_plp_data_outputs_mb"]:
        parts.append(f"sim_outputs={sizes['simulate_plp_data_outputs_mb']:.2f} MB")
    print(f"  {benchmark_id}: {', '.join(parts) if parts else 'no new data'}")

    # Use re-parsed timings if available, otherwise fall back to original CSV values
    t = timings or {}
    rows.append(
        {
            "benchmark_id": benchmark_id,
            "profile": profile,
            "run_type": row["run_type"],
            "cohort_size": row["cohort_size"],
            "total_time": t.get("total_time", row.get("total_time")),
            "total_realtime": total_realtime,
            "create_workflow_inputs_time": t.get(
                "create_workflow_inputs_time", row.get("create_workflow_inputs_time")
            ),
            "simulate_plp_data_time": t.get(
                "simulate_plp_data_time", row.get("simulate_plp_data_time")
            ),
            "run_plp_model_time": t.get(
                "run_plp_model_time", row.get("run_plp_model_time")
            ),
            "run_plp_model_min_time": t.get(
                "run_plp_model_min_time", row.get("run_plp_model_min_time")
            ),
            "run_plp_model_max_time": t.get(
                "run_plp_model_max_time", row.get("run_plp_model_max_time")
            ),
            "zip_plp_outputs_time": t.get(
                "zip_plp_outputs_time", row.get("zip_plp_outputs_time")
            ),
            "simulate_plp_data_outputs_mb": sizes["simulate_plp_data_outputs_mb"],
            "run_plp_model_outputs_mb": sizes["run_plp_model_outputs_mb"],
            "zip_plp_outputs_mb": sizes["zip_plp_outputs_mb"],
            "total_work_mb": sizes["total_work_mb"],
            "max_cpu_percent": cpu if cpu is not None else row.get("max_cpu_percent"),
            "max_peak_rss_mb": rss if rss is not None else row.get("max_peak_rss_mb"),
            "max_peak_vmem_gb": vmem
            if vmem is not None
            else row.get("max_peak_vmem_gb"),
            "n_models": t.get("n_models", row.get("n_models")),
            "trace_file": row.get("trace_file"),
        }
    )

df_out = pd.DataFrame(rows)
df_out.to_csv(output_csv, index=False)
print(f"\nWrote {len(df_out)} rows → {output_csv}")
