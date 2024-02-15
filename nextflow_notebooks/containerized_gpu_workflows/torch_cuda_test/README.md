This simple workflow tests if cuda is available on the GPU instance requested in batch, and can work with the pytorch/cuda version in the container

The python code executed inside the container is check_torch_cuda.py

To build the container, please run docker build command on the Dockerfile, in the same directory where the code, Dockerfile and requirements.txt file lives. Then push the container to Gen3 staging by requesting credentials, get it approved and receive a docker URI to plug into the nextflow workflow.

To run the container in the nextflow workflow, paste the approved docker URI received from Gen3 in the "container" section of the nextflow config. This lives in the nextflow workflow notebook (torch_cuda_batch_template.ipynb). Run the notebook in BRH to deploy the container on AWS batch. Note: all the "placeholder" values in the notebook will need to be replaced with values specific to your workspace. These come pre-populated with the workspace, please see the "Nextflow welcome" page for more details and copy the sample config values onto your nextflow config.
