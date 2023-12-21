import pandas as pd
import os
import argparse
from dicom_csv import join_tree

dicom_input = "$dicom_files"
metadata_csv = "dicom-metadata.csv"


def main(dicom_input, metadata_csv):
    metadata_df = join_tree(".", verbose=2)
    dicom_metadata_df = metadata_df.loc[metadata_df["PixelRepresentation"].notnull()]
    dicom_metadata_df.drop_duplicates(inplace=True)
    return dicom_metadata_df.to_csv(metadata_csv)


if __name__ == "__main__":
    main(dicom_input, metadata_csv)
