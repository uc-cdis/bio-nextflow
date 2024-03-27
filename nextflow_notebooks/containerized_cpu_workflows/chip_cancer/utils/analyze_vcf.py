#!/usr/bin/env python3
import argparse
import sys
import pandas as pd
from pysam import VariantFile

"""
Note that pysam is unable to run with current FIPS compliance
This code needs further debugging to work in the container
a fix is analyze_vcf_plain.py which doesn't use pysam
I left the code here for further debugging in the near future
"""


def analyze_vcf(input_vcf, output_csv, chip_truth_variants):
    # dump truth variants to a pandas df
    truth_df = pd.read_csv(chip_truth_variants, sep="\t")
    # dump sample variants to a pandas df
    chrom_list = []
    ref_list = []
    alt_list = []
    pos_list = []
    in_vcf = VariantFile(input_vcf)
    for variant in in_vcf.fetch():
        chrom = variant.chrom
        ref = variant.ref
        alt = variant.alts[0]
        pos = variant.pos

        print("cpra {} {} {} {}".format(chrom, pos, ref, alt))
        chrom_list.append(chrom)
        ref_list.append(ref)
        alt_list.append(alt)
        pos_list.append(pos)

    # create a pandas df from variant_dict

    variant_dict = {
        "chromosome_name": chrom_list,
        "start": pos_list,
        "reference": ref_list,
        "variant": alt_list,
    }
    sample_variant_df = pd.DataFrame.from_dict(variant_dict)

    print("truth df columns {}".format(truth_df.columns))
    print("sample variant df columns {}".format(sample_variant_df.columns))
    # inner join
    chip_variants = pd.merge(
        left=sample_variant_df,
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
    chip_variants = analyze_vcf(
        input_vcf=input_vcf,
        output_csv=output_csv,
        chip_truth_variants=chip_truth_variants,
    )
    chip_variants.to_csv(output_csv)


if __name__ == "__main__":
    main()
