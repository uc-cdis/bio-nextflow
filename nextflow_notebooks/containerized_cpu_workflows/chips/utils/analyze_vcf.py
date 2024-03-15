#!/usr/bin/env python3
import argparse
import sys
import pandas as pd
from cyvcf2 import VCF


def analyze_vcf(input_vcf, output_csv, chip_truth_variants):
    # dump truth variants to a pandas df
    truth_df = pd.read_csv(chip_truth_variants, sep="\t")
    # dump sample variants to a pandas df
    chrom_list = []
    ref_list = []
    alt_list = []
    start_list = []
    end_list = []
    for variant in VCF(input_vcf):
        chrom = variant.CHROM
        ref = variant.REF
        alt = variant.ALT[0]
        start = variant.start
        end = variant.end

        ref_list.append(ref)
        alt_list.append(alt)
        start_list.append(start)
        end_list.append(end)

    # create a pandas df from variant_dict
    variant_dict = {
        "chromosome_name": chrom_list,
        "start": start_list,
        "stop": end_list,
        "reference": ref_list,
        "variant": alt_list,
    }
    sample_variant_df = pd.DataFrame.from_dict(variant_dict)

    # inner join
    chip_variants = sample_variant_df.join(
        truth_df,
        on=["chromosome_name", "start", "stop", "reference", "variant"],
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
