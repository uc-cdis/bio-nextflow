#!/usr/bin/env Rscript

library(jsonlite)
library(optparse)
library(PatientLevelPrediction)
reticulate::use_condaenv("r-reticulate")

option_list <- list(
  make_option("--plp_data_path", type="character"),
  make_option("--model_name", type="character"),
  make_option("--model_params", type="character"),
  make_option("--dataset_id", type="integer", default=1),
  make_option("--outcome_id", type="integer", default=1),
  make_option("--dataset_observation_window", type="integer", default=365),
  make_option("--outcome_observation_window", type="integer", default=730),
  make_option("--require_time_at_risk", type="logical", default=TRUE),
  make_option("--min_time_at_risk", type="integer", default=30),
  make_option("--include_all_outcomes", type="logical", default=FALSE),
  make_option("--first_exposure_only", type="logical", default=FALSE),
  make_option("--remove_subjects_with_prior_outcome", type="logical", default=FALSE),
  make_option("--covariate_min_fraction", type="double", default=0.01),
  make_option("--test_fraction", type="double", default=0.2),
  make_option("--n_fold", type="integer", default=3),
  make_option("--output_directory", type="character", default="plp_outputs")
)
opt <- parse_args(OptionParser(option_list=option_list))

plpData <- loadPlpData(opt$plp_data_path)

model_command <- switch(
  opt$model_name,
  "Ada Boost" = "setAdaBoost",
  "Decision Tree" = "setDecisionTree",
  "Gradient Boosting Machine" = "setGradientBoostingMachine",
  "Iterative Hard Thresholding" = "setIterativeHardThresholding",
  "Lasso Cox Regression" = "setCoxModel",
  "Lasso Logistic Regression" = "setLassoLogisticRegression",
  "Light Gradient Boosting Machine" = "setLightGBM",
  "Multilayer Perceptron" = "setMLP",
  "Naive Bayes" = "setNaiveBayes",
  "Random Forest" = "setRandomForest",
  "Support Vector Machine" = "setSVM"
)

model_simplify_vector_flag <- switch(
  opt$model_name,
  "Ada Boost" = FALSE,
  "Decision Tree" = FALSE,
  "Gradient Boosting Machine" = TRUE,
  "Iterative Hard Thresholding" = TRUE,
  "Lasso Cox Regression" = TRUE,
  "Lasso Logistic Regression" = TRUE,
  "Light Gradient Boosting Machine" = TRUE,
  "Multilayer Perceptron" = FALSE,
  "Naive Bayes" = TRUE,
  "Random Forest" = FALSE,
  "Support Vector Machine" = FALSE
)

populationSettings <- createStudyPopulationSettings(
  washoutPeriod = opt$dataset_observation_window,
  riskWindowEnd = opt$outcome_observation_window,
  requireTimeAtRisk = opt$require_time_at_risk,
  minTimeAtRisk = opt$min_time_at_risk,
  includeAllOutcomes = opt$include_all_outcomes,
  firstExposureOnly = opt$first_exposure_only,
  removeSubjectsWithPriorOutcome = opt$remove_subjects_with_prior_outcome
)

preprocessSettings = createPreprocessSettings(
  minFraction = opt$covariate_min_fraction
)

model_template <- fromJSON(opt$model_params, simplifyVector = model_simplify_vector_flag)
modelSettings <- do.call(model_command, model_template)
attr(modelSettings$param, "saveToJson") <- FALSE

train_fraction <- 1 - opt$test_fraction
split_args <- list(
  testFraction = opt$test_fraction,
  trainFraction = train_fraction,
  nfold = opt$n_fold
)
if(!is.null(model_template$seed)) {
  split_args$splitSeed <- model_template$seed
}
splitSettings <- do.call(createDefaultSplitSetting, split_args)

#analysis_id <- gsub(" ", "_", tolower(opt$model_name))
analysis_id = ""
output_directory <- opt$output_directory
dir.create(output_directory, recursive = TRUE, showWarnings = FALSE)

model_results <- runPlp(
  plpData,
  analysisId = analysis_id,
  populationSettings = populationSettings,
  splitSettings = splitSettings,
  preprocessSettings = preprocessSettings,
  modelSettings = modelSettings,
  saveDirectory = output_directory
)

plots_directory <- paste0(output_directory, "/", analysis_id, "/plots")
plotPlp (model_results, plots_directory)
noquote("Model plots saved in:")
noquote(plots_directory)
