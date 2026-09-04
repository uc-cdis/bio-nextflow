#!/usr/bin/env Rscript

#' Simulate Patient Level Prediction Data
#'
#' This script generates simulated plpData for the PLP framework.
#' Arguments may be provided as named options:
#'   --sample_size: Number of samples to generate [default: 1000]
#'   --output_dir: Directory to save results [default: plp_outputs]
#'
#' Usage example:
#' Rscript simulate_plp_data.R --sample_size=500 --output_dir=my_output

library(optparse)
library(PatientLevelPrediction)

option_list <- list(
  make_option("--sample_size", type="integer", default=1000,
              help="Sample size [default %default]", metavar="number"),
  make_option("--output_dir", type="character", default="plp_outputs",
              help="Output directory [default %default]", metavar="directory")
)
opt <- parse_args(OptionParser(option_list=option_list))

dir.create(opt$output_dir, recursive = TRUE, showWarnings = FALSE)
plp_data_path <- file.path(opt$output_dir)

data(simulationProfile)
plp_data <- simulatePlpData(
  simulationProfile,
  n = opt$sample_size
)
savePlpData(plp_data, plp_data_path)
print("All done!")