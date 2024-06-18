To get a few test WES BAMs for CHIP POC, see these bams from gdc portal
https://portal.gdc.cancer.gov/v1/repository?facetTab=files&filters=%7B%22op%22%3A%22and%22%2C%22content%22%3A%5B%7B%22op%22%3A%22in%22%2C%22content%22%3A%7B%22field%22%3A%22cases.case_id%22%2C%22value%22%3A%5B%2238a3ea92-8965-4bda-9dbd-144832975cdd%22%2C%2243e228ae-c890-444f-afbd-49385562e33a%22%2C%224549bff6-6886-4102-a1de-02691b664c52%22%2C%2261935424-44d0-4211-81c1-c925e436eac5%22%5D%7D%7D%2C%7B%22op%22%3A%22in%22%2C%22content%22%3A%7B%22field%22%3A%22cases.samples.tissue_type%22%2C%22value%22%3A%5B%22normal%22%5D%7D%7D%2C%7B%22op%22%3A%22in%22%2C%22content%22%3A%7B%22field%22%3A%22files.data_format%22%2C%22value%22%3A%5B%22bam%22%5D%7D%7D%2C%7B%22op%22%3A%22in%22%2C%22content%22%3A%7B%22field%22%3A%22files.experimental_strategy%22%2C%22value%22%3A%5B%22WXS%22%5D%7D%7D%5D%7D

Note: You need the "aacr.chip.project.tsv" file with truth variants for chip to be present in the
utils directory. This file is not pushed to github, so check with the team about this file

To build the container, please run docker build command on the Dockerfile, in the same directory where the code, Dockerfile and requirements.txt file live. Please refer to the ["Nextflow User Guide"](https://uc-cdis.github.io/BRH-documentation/nextflow-create-docker/) in the BRH documentation for more information on how to structure your command.

Following the docker build, request credentials for pushing the container to Gen3 staging. You will need to go to the BRH website (https://brh.data-commons.org/), click on "Email Support", and send an email requesting credentials. You can copy paste the ready-made template shown in nextflow documentation in BRH, available at https://uc-cdis.github.io/BRH-documentation/nextflow-request-creds/. Once you send the credentials request email, you will get a support email back notifying the receipt, and this will form the basis of your communication with user services.

Note that you will receive credentials to upload your container to a staging environment. For containers that are already built, you will need to tag your docker image with the repository URI. Please see instructions here https://uc-cdis.github.io/BRH-documentation/nextflow-upload-docker/#authenticate-docker-to-ecr.

After tagging, run the docker push command as specified in the credentials file sent to you by user services.

After the container is pushed, it will appear in our staging environment where we will scan the container for vulnerabilities. Once the scanning completes and the container is approved, you will receive a docker URI from user services, that you can include in the "container" field of the nextflow workflow to launch the container. This is described below.

To run the container in the nextflow workflow, paste the approved docker URI in the "container" section of the nextflow config. This section is in the nextflow workflow notebook (chip_template.ipynb). You will run this notebook in the BRH workspace to deploy your container on the cloud. Note: all the "placeholder" values in the ipynb notebook will need to be replaced with values specific to your workspace. These come pre-populated with the workspace, please see the "Nextflow welcome" page in your workspace for more details and copy the sample config values onto your nextflow config "placeholder values". The config values specific to your workspace should be in /data/sample-nextflow-config.txt file.

Please refer to nextflow documentation on the BRH website (https://uc-cdis.github.io/BRH-documentation/nextflow-getting-started/) for details on all steps of the process.
