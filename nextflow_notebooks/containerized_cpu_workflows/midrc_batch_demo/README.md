The first of the two MIDRC CPU workflows (midrc_download_dcm_conda.ipynb) can be run directly in the nextflow workspace. This is a non-containerized workflow, and downloads some MIDRC DICOM files onto the workspace. These files can then be processed by other workflows.

The second workflow (midrc_cpu_batch_demo.ipynb) is a containerized workflow that is run on the cloud. This workflow will execute two processes: i) convert DICOM files to png files, and ii) extract metadata from the DICOM files. The results of these two processes will then be saved to your workspace in a followup step.

To build the container, please run docker build command on the Dockerfile, in the same directory where the code, Dockerfile and requirements.txt file live. Please refer to the ["Nextflow User Guide"](https://uc-cdis.github.io/BRH-documentation/nextflow-create-docker/) in the BRH documentation for more information on how to structure your command.

Following the docker build, request credentials for pushing the container to Gen3 staging. You will need to go to the BRH website (https://brh.data-commons.org/), click on "Email Support", and send an email requesting credentials. You can copy paste the ready-made template shown in nextflow documentation in BRH, available at https://uc-cdis.github.io/BRH-documentation/nextflow-request-creds/. Once you send the credentials request email, you will get a support email back notifying the receipt, and this will form the basis of your communication with user services.

Note that you will receive credentials to upload your container to a staging environment. For containers that are already built, you will need to tag your docker image with the repository URI.  Please see instructions here https://uc-cdis.github.io/BRH-documentation/nextflow-upload-docker/#authenticate-docker-to-ecr.

After tagging, run the docker push command as specified in the credentials file sent to you by user services.

After the container is pushed, it will appear in our staging environment where we will scan the container for vulnerabilities. Once the scanning completes and the container is approved, you will receive a docker URI from user services, that you can include in the "container" field of the nextflow workflow to launch the container. This is described below.

To run the container in the nextflow workflow, paste the approved docker URI in the "container" section of the nextflow config. This section is in the nextflow workflow notebook (midrc_cpu_batch_template.ipynb). You will run this notebook in the BRH workspace to deploy your container on the cloud. Note: all the "placeholder" values in the ipynb notebook will need to be replaced with values specific to your workspace. These come pre-populated with the workspace, please see the "Nextflow welcome" page in your workspace for more details and copy the sample config values onto your nextflow config "placeholder values". The config values specific to your workspace should be in /data/sample-nextflow-config.txt file.

Please refer to nextflow documentation on the BRH website (https://uc-cdis.github.io/BRH-documentation/nextflow-getting-started/) for details on all steps of the process.

