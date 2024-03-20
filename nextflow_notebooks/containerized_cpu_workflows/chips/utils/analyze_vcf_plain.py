#!/usr/bin/env python3
import argparse
import sys
import pandas as pd


def analyze_vcf(input_vcf, output_csv, chip_truth_variants):
    # dump truth variants to a pandas df
    print("Reading truth df")
    truth_df = pd.read_csv(chip_truth_variants, sep="\t")
    # dump sample variants to a pandas df
    print("Reading sample df")
    sample_variant_df_full = pd.read_csv(
        input_vcf, sep="\t", comment="#", header=None, compression="gzip"
    )
    # select first five columns
    sample_variant_df_mini = sample_variant_df_full.iloc[:, [0, 1, 2, 3, 4]]
    sample_variant_df_mini.columns = [
        "chromosome_name",
        "start",
        "id",
        "reference",
        "variant",
    ]
    # remove chr prefix from chromosome column
    sample_variant_df_mini["chromosome_name"] = sample_variant_df_mini[
        "chromosome_name"
    ].str.replace("chr", "")

    # inner join
    chip_variants = pd.merge(
        left=sample_variant_df_mini,
        right=truth_df,
        left_on=["chromosome_name", "start", "reference", "variant"],
        right_on=["chromosome_name", "start", "reference", "variant"],
        how="inner",
    )
    return chip_variants


def setup_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input-vcf", dest="input_vcf", help="path to input vcf file", required=True
    )
    parser.add_argument(
        "--output-csv",
        dest="output_csv",
        help="output csv with CHIP variants",
        required=True,
    )
    parser.add_argument(
        "--chip-truth-variants",
        dest="chip_truth_variants",
        help="truth variants for CHIP",
        required=True,
    )
    args = parser.parse_args()
    return args


def main(argv=None):
    args = setup_args()
    input_vcf = args.input_vcf
    output_csv = args.output_csv
    chip_truth_variants = args.chip_truth_variants
    print("Identifying CHIP variants")
    chip_variants = analyze_vcf(
        input_vcf=input_vcf,
        output_csv=output_csv,
        chip_truth_variants=chip_truth_variants,
    )
    print("Dumping to csv")
    chip_variants.to_csv(output_csv)


if __name__ == "__main__":
    main()
