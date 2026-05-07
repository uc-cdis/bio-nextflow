nextflow.enable.dsl=2

process create_workflow_inputs {
    container 'python:3.9'
    publishDir "results/${params.plpRunName}", mode: 'copy'

    input:
    val model_list

    output:
    path "workflow_inputs.yaml"

    script:
    // 1. Build the YAML string in pure Groovy
    def yaml = ""
    yaml += "plpRunName: ${params.plpRunName}\n"
    yaml += "seed: ${params.seed}\n"
    yaml += "sample_size: ${params.sample_size}\n"
    yaml += "dataset_id: ${params.dataset_id}\n"
    yaml += "outcome_id: ${params.outcome_id}\n"
    yaml += "dataset_observation_window: ${params.dataset_observation_window}\n"
    yaml += "outcome_observation_window: ${params.outcome_observation_window}\n"
    yaml += "require_time_at_risk: ${params.require_time_at_risk}\n"
    yaml += "min_time_at_risk: ${params.min_time_at_risk}\n"
    yaml += "include_all_outcomes: ${params.include_all_outcomes}\n"
    yaml += "first_exposure_only: ${params.first_exposure_only}\n"
    yaml += "remove_subjects_with_prior_outcome: ${params.remove_subjects_with_prior_outcome}\n"
    yaml += "covariate_min_fraction: ${params.covariate_min_fraction}\n"
    yaml += "test_fraction: ${params.test_fraction}\n"
    yaml += "n_fold: ${params.n_fold}\n"
    yaml += "model_list:\n"
    
    model_list.each { model ->
        yaml += "  - name: ${model.name}\n"
        // Use JsonOutput only for the nested params map
        def pJson = groovy.json.JsonOutput.toJson(model.params)
        yaml += "    params: ${pJson}\n"
    }

    // 2. Pass that string into a single-quoted Bash command
    // We use %s to safely handle the entire string at once
    """
    printf "%s" '${yaml}' > workflow_inputs.yaml
    """
}

process simulate_plp_data {
    container 'quay.io/cdis/cadc-plp:fear_optparse'
    cpus 1
    memory '1 GB'
    disk '3 GB'

    publishDir "results/${params.plpRunName}", mode: 'copy'

    output:
        path 'plp_outputs/plpData'

    script:
    """
    #mkdir -p plp_outputs/plpData

    simulate_plp_data.R \
        --sample_size ${params.sample_size} \
        --output_dir plp_outputs/plpData
    """
}

process run_plp_model {
    container 'quay.io/cdis/cadc-plp:fear_optparse'
    cpus 1
    memory '4 GB'
    disk '4 GB'
    
    publishDir "results/${params.plpRunName}", mode: 'copy'

    input:
        tuple path(plpData), val(model_name), val(model_params)

    output:
        path "plp_outputs/${model_name}"

    script:
    """
    run_plp_model.R \
        --plp_data_path ${plpData} \
        --model_name "${model_name}" \
        --model_params '${model_params}' \
        --dataset_id ${params.dataset_id} \
        --outcome_id ${params.outcome_id} \
        --dataset_observation_window ${params.dataset_observation_window} \
        --outcome_observation_window ${params.outcome_observation_window} \
        --require_time_at_risk ${params.require_time_at_risk} \
        --min_time_at_risk ${params.min_time_at_risk} \
        --include_all_outcomes ${params.include_all_outcomes} \
        --first_exposure_only ${params.first_exposure_only} \
        --remove_subjects_with_prior_outcome ${params.remove_subjects_with_prior_outcome} \
        --covariate_min_fraction ${params.covariate_min_fraction} \
        --test_fraction ${params.test_fraction} \
        --n_fold ${params.n_fold} \
        --output_directory "plp_outputs/${model_name}"
    """
}


process zip_plp_outputs {
    container 'quay.io/cdis/cadc-plp:fear_optparse'
    publishDir "results", mode: 'move'

    input:
        path model_dirs
        path workflow_inputs_yaml

    output:
        path "${params.plpRunName}.zip"

    script:
    """
    mkdir -p plp_outputs

    # Move all input directories into plp_outputs (preserving names)
    mv ${model_dirs} plp_outputs

    # Remove all runPlp.rds files
    find plp_outputs -type f -name "runPlp.rds" -delete

    zip -r ${params.plpRunName}.zip workflow_inputs.yaml plp_outputs

    echo "User-downloadable PLP outputs archived:"
    ls -la *.zip
    """
}

workflow {
    // Generate simulated data
    plp_data_ch = simulate_plp_data()

    // Prepare model parameter sets as channel
    models_ch = channel.fromList(params.model_list)
        .map { model -> [model.name, groovy.json.JsonOutput.toJson(model.params)] }

    // Combine data and model parameters for input to model runner
    run_inputs_ch = plp_data_ch
        .combine(models_ch)
        .map { data_and_model -> data_and_model.flatten() }

    // Run models
    model_results_ch = run_plp_model(run_inputs_ch)

    // Collect all model output directories
    models_output_dirs_ch = model_results_ch.collect()

    // Create workflow inputs YAML from params
    workflow_yaml_ch = channel.value(params.model_list) 
    workflow_inputs_file_ch = create_workflow_inputs(workflow_yaml_ch)

    // Package everything into zip
    zip_plp_outputs(models_output_dirs_ch, workflow_inputs_file_ch)
}
