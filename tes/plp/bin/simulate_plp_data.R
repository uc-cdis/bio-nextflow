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

# Redirect Andromeda temporary files to /mnt/data/andromeda-tmp
# PatientLevelPrediction and other OHDSI tools require temporary database files for DuckDB.
# On Kubernetes persistent volumes, the filesystem may pre-create stub files when R calls tempfile(),
# causing DuckDB to fail opening them as valid databases.
# Setting the Andromeda temp folder to a local directory (such as /dev/shm/andromeda-tmp or
# /mnt/data/andromeda-tmp) avoids this issue, ensuring DuckDB can create and access valid database
# files during simulation.
# library(Andromeda)
#options(andromedaTempFolder = "/mnt/data/andromeda-tmp")
# options(andromedaTempFolder = "/dev/shm/andromeda-tmp")

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