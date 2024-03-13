#!/usr/bin/env python3
import argparse
import os
import requests
import subprocess

"""
example run on a miRNA BAM, the smallest GDC BAM file
python download_bam.py --gdc-token gdc_token/gdc-user-token.2024-03-12T16_18_35.970Z.txt --uuid dc87e1b8-d8b7-4837-88ea-fb7f017b3c69
"""


def download_bam(gdc_token, uuid):
    # read gdc token into token_string
    print("reading gdc token file")
    token_file = gdc_token
    with open(token_file, "r") as token:
        token_string = str(token.read().strip())

    # specify endpts
    print("gathering endpoints")
    endpt = "https://api.gdc.cancer.gov/data"
    bam_and_related_files = uuid + "?related_files=true"
    data_endpt = os.path.join(endpt, bam_and_related_files)

    # post requests
    print("sending request")
    response = requests.get(data_endpt, headers={"X-Auth-Token": token_string})

    output_tar_file = uuid + ".tgz"
    # output files
    print("writing bam and bai outputs for {} to {}".format(uuid, output_tar_file))
    with open(output_tar_file, "wb") as output_file:
        output_file.write(response.content)
    print("completed")


def setup_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--gdc-token", dest="gdc_token", help="path to gdc token file", required=True
    )
    parser.add_argument(
        "--uuid", dest="uuid", help="uuid of the file to download", required=True
    )
    args = parser.parse_args()
    return args


def main(argv=None):
    args = setup_args()
    uuid = args.uuid
    gdc_token = args.gdc_token
    download_bam(gdc_token=gdc_token, uuid=uuid)


if __name__ == "__main__":
    main()
