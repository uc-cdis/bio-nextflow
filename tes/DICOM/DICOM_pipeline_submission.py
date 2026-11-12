import json
import time

import requests
from gen3.auth import Gen3Auth
from gen3.dpop import dpop_proxy_context

bucket = "gen3wf-brhstaging-data-commons-org-245"
project_ids = "TCIA-RICORD_1a"  # change to project id of choice

auth = Gen3Auth()

with dpop_proxy_context(auth=auth) as (task_token, proxy_port):
    tes_base = f"http://127.0.0.1:{proxy_port}/ga4gh/tes/v1"
    headers = {"Authorization": f"Bearer {task_token}"}

    body = {
        "name": f"midrc-dicom-header-pipeline-{project_ids}",
        "executors": [
            {
                "image": "quay.io/cdis/gen3-workflow:integration_tests_dicom_image",
                "workdir": "/work",
                "command": [
                    "sh", "-c",
                    f"python3 /work/DICOM_pipeline.py --project-ids {project_ids} "
                    "--endpoint staging.midrc.org --credentials /work/credentials.json "
                    "--working-dir /work/outputs --source-nodes ct_series_file --no-prompt",
                ],
            }
        ],
        "inputs": [
            {"url": f"s3://{bucket}/inputs/credentials.json",
             "path": "/work/credentials.json", "type": "FILE"},
            {"url": f"s3://{bucket}/inputs/DICOM_pipeline.py",
             "path": "/work/DICOM_pipeline.py", "type": "FILE"},
        ],
        "outputs": [
            {"url": f"s3://{bucket}/outputs/{project_ids}/",
             "path": "/work/outputs/", "type": "DIRECTORY"},
        ],
        "resources": {"cpu_cores": 12, "ram_gb": 32, "disk_gb": 100}, #change resource allocation if needed
    }

    # Submit task
    response = requests.post(f"{tes_base}/tasks", json=body, headers=headers)
    assert response.status_code == 200, f"{response.status_code}: {response.text}"
    task_id = response.json()["id"]
    print(f"Task submitted: {task_id}")

    # Monitor task
    max_i = 720  # 1 hour of monitoring (change if needed)
    data = {}
    for i in range(max_i):
        response = requests.get(f"{tes_base}/tasks/{task_id}", headers=headers)
        data = response.json()
        status = data.get("state")

        if status is None:
            print(f"({i+1}/{max_i}): invalid response, {data.get('detail', '')}")
            time.sleep(5)
            continue

        print(f"({i+1}/{max_i}): {status}")

        if status == "COMPLETE":
            print("Pipeline complete!")
            break
        if status in ["SYSTEM_ERROR", "EXECUTOR_ERROR"]:
            print("Pipeline failed")
            break
        if i == max_i - 1:
            print("Timed out")
            break
        time.sleep(5)

    print(json.dumps(data, indent=2))
