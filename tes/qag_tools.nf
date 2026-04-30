/*
QAG Tool Nextflow Workflow

OVERVIEW:
---------
This workflow:
- Lists available QAG tools (tools/list).
- Executes a pipeline to answer your question using the QAG MCP API (tools/call).
- Runs these processes in parallel.
- Outputs are saved in `results/qag_outputs`.

USAGE EXAMPLES:
---------------
- Run workflow under Gen3 orchestration:
    gen3 run nextflow run qag_tools.nf

- Optionally override the question:
    gen3 run nextflow run qag_tools.nf --qag_question "<your custom question>"

CONFIGURATION NOTES:
--------------------
- Make sure "docker.enabled = true" is in your nextflow.config
- Follow `TES onboarding document for testers` → `Running Nextflow workflows` for nextflow.config setup

REQUIREMENTS:
-------------
- Make sure you have a valid GEN3_TOKEN set as an environment variable before running.
- Follow `TES onboarding document for testers` → `General setup` section to set API key and GEN3_TOKEN.

DEFAULT QUESTION:
-----------------
What is the co-occurence frequency of somatic heterozygous deletions in BRCA2 and NF1 in the Kidney Chromophobe TCGA-KICH project in the genomic data commons?

OUTPUTS:
--------
Workflow results and tool listings are saved in `results/qag_outputs`.
*/

params.qag_question = "What is the co-occurence frequency of somatic heterozygous deletions in BRCA2 and NF1 in the Kidney Chromophobe TCGA-KICH project in the genomic data commons?"
params.outdir = "results"
params.qag_url = "https://gdc-qag.m3aicommons.org/gradio_api/mcp/"

process list_tools {
    container 'python:3.9'

    output:
        path 'qag_outputs/output_list_tools.json'
    publishDir params.outdir


    script:
    """
    mkdir -p qag_outputs

    # Get tool list
    curl -s -H "Content-Type: application/json" \
        -H "Accept: application/json,text/event-stream" \
        -H "Authorization: Bearer ${GEN3_TOKEN}" \
        -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' \
        ${params.qag_url} \
    | grep '^data:' \
    | sed 's/^data: //' \
    | python -m json.tool > qag_outputs/output_list_tools.json
    """
}

process execute_pipeline {
    container 'python:3.9'

    input:
        val(params.qag_question)

    output:
        path 'qag_outputs/output_execute_pipeline.json'
    publishDir params.outdir

    script:
    """
    mkdir -p qag_outputs

    # Get answer for a question from execute_pipeline
    curl -s -H "Content-Type: application/json" \
        -H "Accept: application/json,text/event-stream" \
        -H "Authorization: Bearer ${GEN3_TOKEN}" \
        -d '{
            "jsonrpc":"2.0",
            "id":2,
            "method":"tools/call",
            "params":{
                "name":"execute_pipeline",
                "arguments":{"question":"${params.qag_question}"}
                }
            }' \
        ${params.qag_url} \
    | grep '^data:' \
    | sed 's/^data: //' \
    | python -m json.tool > qag_outputs/output_execute_pipeline.json
    """
}

workflow {
    list_tools()
    execute_pipeline(params.qag_question)
}
