"""
benchmark_plp.py - Nextflow Workflow Parallel Benchmarking Script
------------------------------------------------------------------
This script benchmarks Nextflow workflow execution for different cohort sizes and parallel submission scenarios.
It tests workflow-level concurrency (not process-level parallelism) by submitting multiple identical workflows simultaneously.

For each combination of cohort size, run type, and execution profile:
    - single    : Submits one workflow and waits for it to finish.
    - parallel3 : Submits three workflows simultaneously and waits for all to finish.
    - parallel5 : Submits five workflows simultaneously and waits for all to finish.

Each workflow uses a Random Forest model and a unique plpRunName/output.
Resulting trace.txt files are safely moved to ./benchmarks with unique IDs,
and performance metrics are collected into benchmark.csv using collect_benchmark.py.

How to use:
-----------
1. Place this script, your plp.nf workflow, plp-params.yaml params file, and collect_benchmark.py in your project directory.
2. Make sure Python packages pyyaml, pandas are installed.
3. Run this script with:

    python3 benchmark_plp.py

4. After completion, analyze benchmark.csv for workflow efficiency and bottlenecks.

Customization:
--------------
- Edit COHORT_SIZES, RUN_TYPES, PROFILES as needed.
- Each run will only contain one Random Forest model.
- Parallelism is at the workflow submission level.
"""
import os
import subprocess
import yaml
import time
import sys

# COHORT_SIZES = [10000, 100000]
# COHORT_SIZES = [1000000, 100000, 10000]
COHORT_SIZES = [1000000, 100000, 10000]
RUN_TYPES = {
    "wakenode": 1,
    "single": 1,
    "parallel3": 3,
    "parallel5": 5,
    "parallel10": 10,
}
PROFILES = ["tes"]
# PROFILES = ['tes', 'local']

BENCHMARK_DIR = "./benchmarks"
os.makedirs(BENCHMARK_DIR, exist_ok=True)

BASE_PARAMS_FILE = "plp-params.yaml"
BASE_WORKFLOW_FILE = os.path.abspath("plp.nf")

# Get bucket from environment variable for TES S3 URIs
S3_BUCKET = os.environ.get("BUCKET")
if not S3_BUCKET:
    print(
        "BUCKET environment variable is not set. Please set it to your S3 bucket name."
    )
    sys.exit(1)
S3_BASE = f"s3://{S3_BUCKET}/plp-benchmark"


def prepare_params_file(base_params, cohort_size, plpRunName):
    params = base_params.copy()
    params["sample_size"] = cohort_size
    params["plpRunName"] = plpRunName
    params["model_list"] = [params["model_list"][0]]  # use first model for benchmark
    run_params_file = os.path.join(BENCHMARK_DIR, f"{plpRunName}_params.yaml")
    with open(run_params_file, "w") as f:
        yaml.dump(params, f)
    return run_params_file


def benchmark_batch():
    project_root = os.path.abspath(os.getcwd())
    with open(BASE_PARAMS_FILE) as f:
        base_params = yaml.safe_load(f)
    for cohort in COHORT_SIZES:
        for run_type, n_workflows in RUN_TYPES.items():
            for profile in PROFILES:
                benchmark_id_base = f"{cohort}-{run_type}-{profile}"
                print(f"Starting batch: {benchmark_id_base}")
                procs = []
                trace_paths = [None] * n_workflows
                for i in range(n_workflows):
                    benchmark_id = f"{benchmark_id_base}-{i+1}"
                    plpRunName = benchmark_id
                    local_params_file = os.path.abspath(
                        prepare_params_file(base_params, cohort, plpRunName)
                    )
                    if profile == "tes":
                        remote_trace_out = f"{S3_BASE}/{benchmark_id}.trace.txt"
                        remote_work_dir = f"{S3_BASE}/{benchmark_id}/work"
                        # TODO: gen3 orchestration doesn't support long-time tokens yet, uncomment after the fix
                        cmd = [
                            # "gen3", "run",
                            "nextflow",
                            "run",
                            BASE_WORKFLOW_FILE,
                            "-params-file",
                            local_params_file,
                            "-profile",
                            profile,
                            "-with-trace",
                            remote_trace_out,
                            "-w",
                            remote_work_dir,
                        ]
                        trace_out = remote_trace_out
                    else:
                        trace_out = os.path.abspath(
                            os.path.join(BENCHMARK_DIR, f"{benchmark_id}.trace.txt")
                        )
                        work_dir = os.path.join(BENCHMARK_DIR, benchmark_id)
                        os.makedirs(work_dir, exist_ok=True)
                        # TODO: gen3 orchestration doesn't support long-time tokens yet, uncomment after the fix
                        cmd = [
                            # "gen3", "run",
                            "nextflow",
                            "run",
                            BASE_WORKFLOW_FILE,
                            "-params-file",
                            local_params_file,
                            "-profile",
                            profile,
                            "-with-trace",
                            trace_out,
                            "-w",
                            work_dir,
                        ]
                    # print(f"Submitting: {' '.join(cmd)}  [cwd={project_root}]")
                    # procs.append(subprocess.Popen(cmd, cwd=project_root))
                    launch_dir = os.path.join(BENCHMARK_DIR, f"{benchmark_id}-launch")
                    os.makedirs(launch_dir, exist_ok=True)
                    print(f"Submitting: {' '.join(cmd)}  [cwd={launch_dir}]")
                    procs.append(subprocess.Popen(cmd, cwd=launch_dir))
                    trace_paths[i] = trace_out
                for proc in procs:
                    proc.wait()
                    time.sleep(1)
                for i, trace_path in enumerate(trace_paths):
                    benchmark_id = f"{benchmark_id_base}-{i+1}"
                    collect_cmd = [
                        "python3",
                        "benchmark_collect.py",
                        trace_path,
                        profile,
                        run_type,
                        str(cohort),
                        benchmark_id,
                        os.path.join(BENCHMARK_DIR, "benchmark.csv"),
                    ]
                    print(f"Collecting benchmark for {benchmark_id}")
                    subprocess.run(collect_cmd)
                    time.sleep(1)


if __name__ == "__main__":
    benchmark_batch()
