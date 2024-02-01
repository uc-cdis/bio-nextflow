# Bioinformatics Nextflow Research

This repository hosts some Nextflow workflow tutorials:

1. BRH Demo Notebooks

A collection of tutorial notebooks that are run on a local execution of Nextflow in the BRH Nextflow Workspace.


2. MIDRC Demo Notebooks

A collection of tutorial notebooks that are specific to MIDRC use cases. These notebooks demonstrate Nextflow
workflows run on a conda virtual environment and containerized batched workflows run on the cloud using CPU and GPU
resources.


### View Static Notebooks

Some of the notebooks can be viewed without having to execute the code by opening the html versions in a 
browser. These are located in the folder `nextflow_notebooks/static_notebooks`. Some of the notebooks can also be viewed
on the BRH Example Analysis Page (https://brh.data-commons.org/resource-browser).

# Run Notebooks on the Biomedical Research Hub

To run the interactive notebooks in the Biomedical Research Hub (BRH), go to `https://brh.data-commons.org/workspace`,
login, select a BRH Workspace Account, and launch a Nextflow workspace computational environment that is provisioned 
with either CPU or GPU resources. Once a workspace is open, upload the desired notebook to workspace image and run the
notebook. Note that some of the MIDRC batch workflows require the user to first build and push a containerized Nextflow
image to the BRH Nextflow AWS Elastic Container Repository and to configure the AWS account resources and containers in
the notebook. 

