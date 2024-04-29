This simple workflow tests if cuda is available on the GPU instance requested in batch, and can work with the pytorch/cuda version in the container, as specified in the requirements.txt file.

The python code executed inside the container is check_torch_cuda.py, which simply prints a message if torch cuda is available.

To build the container, please run docker build command on the Dockerfile, in the same directory where the code, Dockerfile and requirements.txt file lives. Example docker build command: "docker build . -t torch_cuda_test" 

Following docker build, push the container to Gen3 staging by requesting credentials. For this, you will need to go to the BRH website (https://brh.data-commons.org/), click on "Email Support", and send an email requesting credentials. You can copy paste the ready-made template shown in nextflow documentation in BRH, available at https://uc-cdis.github.io/BRH-documentation/nextflow-request-creds/. Once you send email, you will get a support email back notifying the receipt, and this will form the basis of your communication with user services.

Note that you will receive credentials to upload your container to a staging environment. For containers that are already built, such as this one tagged "torch_cuda_test", you will need to tag your docker image with the repository URI. Please see instructions here https://uc-cdis.github.io/BRH-documentation/nextflow-upload-docker/#authenticate-docker-to-ecr

In this case, we can run  the following (note that repositoryURI refers to the entire ECR Repository URI that will be sent to you by user services in the credentials message. You will copy paste the whole URI below)
docker tag torch_cuda_test:latest <repositoryURI>:torch_cuda_test
Run docker push command as sent to you in the credentials file user services.

Once the container is approved, you will receive a docker URI from user services, that you can include in your nextflow workflow as described below.

To run the container in the nextflow workflow, paste the approved docker URI in the "container" section of the nextflow config. This section is in the nextflow workflow notebook (torch_cuda_batch_template.ipynb). You will run this notebook in the BRH workspace to deploy your container on the cloud. Note: all the "placeholder" values in the ipynb notebook will need to be replaced with values specific to your workspace. These come pre-populated with the workspace, please see the "Nextflow welcome" page in your workspace for more details and copy the sample config values onto your nextflow config "placeholder values". The config values specific to your workspace should be in /data/sample-nextflow-config.txt file. 

Please refer to nextflow documentation on the BRH website (https://uc-cdis.github.io/BRH-documentation/nextflow-getting-started/) for details on all steps of the process.
