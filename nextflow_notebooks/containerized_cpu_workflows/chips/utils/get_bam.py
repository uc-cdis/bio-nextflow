import sys
import requests
import json
import re
import os

credentials_path = sys.argv[1]
file_uuid = sys.argv[2]


def main(path, uuid):
    with open(path, "r") as token:
        token_string = str(token.read().strip())

    headers = {"X-Auth-Token": token_string}

    response = requests.get(
        "https://api.gdc.cancer.gov/data/" + uuid + "?related_files=true",
        headers=headers,
    )

    # The file name can be found in the header within the Content-Disposition key.
    file_name = re.findall("filename=(.+)", response.headers["Content-Disposition"])[0]

    with open(file_name, "wb") as output_file:
        output_file.write(response.content)

    files1 = os.listdir()
    file = [i for i in files1 if "gdc_download" in i]
    if len(file) != 0:
        os.system(f"tar -xf {file[0]}")

    files2 = os.listdir()
    new_files = list(set(files2) - set(files1))
    bam_file_dir = [i for i in new_files if "." not in i]
    print(os.listdir(bam_file_dir[0]))


if __name__ == "__main__":
    main(credentials_path, file_uuid)
