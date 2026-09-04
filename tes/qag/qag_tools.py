"""
QAG Tool Python Script

OVERVIEW:
---------
This script:
- Lists available QAG tools from the GDC-QAG MCP API using a TES task.
- Submits a user-defined question (or uses a default) to the QAG API for analysis.
- Prints the tool listing and pipeline answer to stdout.

USAGE EXAMPLES:
---------------
- Run under Gen3 orchestration (Nextflow/TES config supplies TES endpoint):

    gen3 run python qag_tools.py

- Optionally override the question:

    export QAG_QUESTION="<your custom question>"
    gen3 run python qag_tools.py

CONFIGURATION NOTES:
--------------------
- TES endpoint is set via the `TES_ENDPOINT` environment variable or default value is used https://brhstaging.data-commons.org/ga4gh/tes/v1/tasks
- Container image used: `"quay.io/curl/curl:latest"` (hardcoded in the script).
- GEN3 authentication: Set `GEN3_TOKEN` in your environment via the instructions in the TES onboarding document.

REQUIREMENTS:
-------------
- A valid `GEN3_TOKEN` environment variable.
- Recommended: Follow `TES onboarding document for testers` → `General setup` section to set up API key and GEN3_TOKEN.

DEFAULT QUESTION:
-----------------
What is the co-occurence frequency of somatic heterozygous deletions in BRCA2 and NF1 in the Kidney Chromophobe TCGA-KICH project in the genomic data commons?

OUTPUTS:
--------
- Tool listing and question answer are printed to STDOUT.
- Full TES task JSON is printed for debugging if extraction fails.
"""

import json
import os
import requests
import time

qag_url = "https://gdc-qag.m3aicommons.org/gradio_api/mcp/"
question = os.environ.get(
    "QAG_QUESTION",
    "What is the co-occurence frequency of somatic heterozygous deletions in BRCA2 and NF1 in the Kidney Chromophobe TCGA-KICH project in the genomic data commons?",
)
token = os.environ.get("GEN3_TOKEN", "")

tes_endpoint = os.environ.get(
    "TES_ENDPOINT", "https://brhstaging.data-commons.org/ga4gh/tes/v1/tasks"
)

body = {
    "name": "tool-list",
    "executors": [
        {
            "image": "quay.io/curl/curl:latest",
            "command": [
                "sh",
                "-c",
                f'curl -N {qag_url} -H "Content-Type: application/json" -H "Accept: application/json,text/event-stream" -d \'{{"jsonrpc":"2.0","id":1,"method":"tools/list"}}\'',
            ],
        }
    ],
}

response = requests.post(
    tes_endpoint,
    json=body,
    headers={"authorization": f"bearer {token}"},
)
assert response.status_code == 200, response.text
data = response.json()
task_id = data["id"]
print(f"Tool-list Task id: {task_id}")

max_i = 60
for i in range(max_i):
    response = requests.get(
        f"{tes_endpoint}/{task_id}",
        headers={"authorization": f"bearer {token}"},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    status = data["state"]
    print(f"Tool-list Task status: {status}")
    if status == "COMPLETE":
        print("Tool-list Task complete!")
        break
    if status in ["SYSTEM_ERROR", "EXECUTOR_ERROR"]:
        print("Tool-list Task failed")
        break
    if i == max_i - 1:
        print("Tool-list Task did not complete")
        break
    time.sleep(5)

tools = []
if "logs" in data and data["logs"]:
    try:
        stdout = data["logs"][0]["logs"][0]["stdout"]
        for line in stdout.split("\n"):
            if line.strip().startswith("data: "):
                payload = line.strip()[len("data: ") :]
                parsed = json.loads(payload)
                tools = parsed["result"]["tools"]
                print("====== Tool-list JSON ======")
                print(json.dumps(parsed, indent=2))
                print("================================")
                break
    except Exception as e:
        print(f"Could not extract tool list: {e}")

if not tools:
    print("No tools found.")
    exit()

tool_name = tools[0]["name"]

ask_body = {
    "name": "ask-tool-execute_pipeline",
    "executors": [
        {
            "image": "quay.io/curl/curl:latest",
            "command": [
                "sh",
                "-c",
                (
                    f"curl -N {qag_url} "
                    f'-H "Content-Type: application/json" '
                    f'-H "Accept: application/json,text/event-stream" '
                    f'-d \'{{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{{"name":"execute_pipeline","arguments":{{"question":"{question}"}}}}}}\''
                ),
            ],
        }
    ],
}

response = requests.post(
    tes_endpoint,
    json=ask_body,
    headers={"authorization": f"bearer {token}"},
)
assert response.status_code == 200, response.text
ask_task_data = response.json()
ask_task_id = ask_task_data["id"]
print(f"Question Task id: {ask_task_id}")

for i in range(max_i):
    response = requests.get(
        f"{tes_endpoint}/{ask_task_id}",
        headers={"authorization": f"bearer {token}"},
    )
    assert response.status_code == 200, response.text
    ask_task_data = response.json()
    status = ask_task_data["state"]
    print(f"Question Task status: {status}")
    if status == "COMPLETE":
        print("Question Task complete!")
        break
    if status in ["SYSTEM_ERROR", "EXECUTOR_ERROR"]:
        print("Question Task failed")
        break
    if i == max_i - 1:
        print("Question Task did not complete")
        break
    time.sleep(5)

printed_answer = False
if "logs" in ask_task_data and ask_task_data["logs"]:
    try:
        stdout = ask_task_data["logs"][0]["logs"][0]["stdout"]
        for line in stdout.split("\n"):
            if line.strip().startswith("data: "):
                payload = line.strip()[len("data: ") :]
                parsed = json.loads(payload)
                result = parsed.get("result", {})
                content_list = result.get("content", [])
                print("====== Tool Answer ======")
                if content_list and content_list[0].get("type") == "text":
                    text = content_list[0]["text"]
                    sections = [
                        s.strip()
                        for s in text.replace("```", "").split("\n\n")
                        if s.strip()
                    ]
                    for section in sections:
                        print(section)
                else:
                    print(json.dumps(parsed, indent=2))
                print("================================")
                printed_answer = True
                break
    except Exception as e:
        print(f"Could not extract tool answer: {e}")

if not printed_answer:
    print("====== Full question task output ======")
    print(json.dumps(ask_task_data, indent=2))
    print("================================")

# Debug
# print(ask_task_data)
# print(parsed)
