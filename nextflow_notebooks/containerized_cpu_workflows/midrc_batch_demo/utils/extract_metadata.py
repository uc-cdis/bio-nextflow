import pandas as pd
import os
import argparse
from dicom_csv import join_tree
import sys

dicom_input = sys.argv[1]
metadata_csv = f"dicom-metadata-{dicom_input}.csv"


def main(dicom_input, metadata_csv):
    metadata_df = join_tree(dicom_input, verbose=2)
    dicom_metadata_df = metadata_df.loc[metadata_df["PixelRepresentation"].notnull()]
    dicom_metadata_df.drop_duplicates(inplace=True)
    return dicom_metadata_df.to_csv(metadata_csv)


if __name__ == "__main__":
    main(dicom_input, metadata_csv)
