The algorithm to test this challenge can be found under https://github.com/MIDRC/COVID19_Challenges/tree/main/Challenge_2022_COVIDx/Winning%20Challenge%20Submissions
Click on Download under the Winner to download all files. 

If you are working on a VM or terminal, one way to copy all model files onto your VM is the following:
Right-click on "Download" under Winner => Copy Link Address => wget <copied link address>
Unzip the submission. When inflating, provide distinct names for Dockerfile and requirements.txt file, so as to not overwrite the files in this git repo.

Note that the algorithm expects chest X-ray DICOM images in its 'in' directory as input files. Output is a single csv file in the 'out' directory with a score for each image.

We have modified the inference.py entrypoint python code to make it more argument friendly and run in a containerized nextflow workflow. The modified file is called "inference_modified_for_batch.py". We also provide a Dockerfile to build the container, and a requirements.txt file for software that will be installed in the container. 


To build the container, please run docker build command on the Dockerfile, in the same directory where the code, Dockerfile and requirements.txt file live. Please refer to the ["Nextflow User Guide"](https://uc-cdis.github.io/BRH-documentation/nextflow-create-docker/) in the BRH documentation for more information on how to structure your command.

Following the docker build, request credentials for pushing the container to Gen3 staging. You will need to go to the BRH website (https://brh.data-commons.org/), click on "Email Support", and send an email requesting credentials. You can copy paste the ready-made template shown in nextflow documentation in BRH, available at https://uc-cdis.github.io/BRH-documentation/nextflow-request-creds/. Once you send the credentials request email, you will get a support email back notifying the receipt, and this will form the basis of your communication with user services.

Note that you will receive credentials to upload your container to a staging environment. For containers that are already built, you will need to tag your docker image with the repository URI. Please see instructions here https://uc-cdis.github.io/BRH-documentation/nextflow-upload-docker/#authenticate-docker-to-ecr.

After tagging, run the docker push command as specified in the credentials file sent to you by user services.

After the container is pushed, it will appear in our staging environment where we will scan the container for vulnerabilities. Once the scanning completes and the container is approved, you will receive a docker URI from user services, that you can include in the "container" field of the nextflow workflow to launch the container. This is described below.

To run the container in the nextflow workflow, paste the approved docker URI in the "container" section of the nextflow config. This section is in the nextflow workflow notebook (midrc_gpu_batch_template.ipynb). You will run this notebook in the BRH workspace to deploy your container on the cloud. Note: all the "placeholder" values in the ipynb notebook will need to be replaced with values specific to your workspace. These come pre-populated with the workspace, please see the "Nextflow welcome" page in your workspace for more details and copy the sample config values onto your nextflow config "placeholder values". The config values specific to your workspace should be in /data/sample-nextflow-config.txt file.

Please refer to nextflow documentation on the BRH website (https://uc-cdis.github.io/BRH-documentation/nextflow-getting-started/) for details on all steps of the process.

