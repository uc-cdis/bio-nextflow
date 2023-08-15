# Bioinformatics Nextflow Research

This repository hosts some Nextflow workflow tutorials:

1. Canine Nextflow Tutorial
Details how to utilize Nextflow to analyze FASTQ files from the Canine Data Commons, demonstrates how to download data using the Gen3 SDK, and how to perform sequence analysis on the retrieved FASTQ file. The tutorial covers the structure and components of a Nextflow workflow, including processes, channels, execution abstraction, and scripting

2. Proteomic Data Commons Nextflow Tutorial
Demonstrates how to retrieve, process, and visualize protein relative expression data from the PDC API with Nextflow. Illustrates use of Nextflow features such as channels, parameters, and environment and configuration files

3. Multiple Container Nextflow Tutorial
Illustrate how to set up a multi-container Nextflow workflow using two Python scripts, each operating in a distinct Conda environment


# View Notebook Results without Running

The results of the notebooks can be viewed without having to execute the code by opening their html versions in a broswer. These are located in the folder `nextflow_notebooks/static_notebooks`. Additionally, the Github website allows you to preview the results of the interactive notebooks without running them as well (these are located at `nextflow_notebooks/interactive_notebooks`).

# Run Notebooks on the Biomedical Research Hub

To run interactive notebooks (located in `nextflow_notebooks/interactive_notebooks`) in the Biomedical Research Hub (BRH), go to `https://brh.data-commons.org/workspace`, login, and launch the Test Nextflow in BRH Workspace. Once open, upload the desired notebook ending in `.ipynb` to the Nextflow image and run all the cells. They will automatically create all relevant files for and run their respective Nextflow workflows in the workspace.

