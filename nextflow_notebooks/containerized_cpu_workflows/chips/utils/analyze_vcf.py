import sys
import pandas as pd
import cyvcf2


vcf_file = sys.argv[1]
file_uuid = sys.argv[2]
results_csv = f"{vcf_file}_analysis.csv"


def main(vcf_file, results_csv):
    df = pd.DataFrame()

    for variant in vcf_file:
        if variant.QUAL > 100:
            d = {
                "Chrom": variant.CHROM,
                "Position": variant.POS,
                "Mutation": variant.REF + "|" + variant.ALT[0],
                "Quality": variant.QUAL,
            }
            df = pd.concat([df, pd.DataFrame([d])], ignore_index=True)

    df["Sample"] = vcf_file[:-4]
    df["Data Commons"] = "Bio Data Catalyst"

    return df.to_csv(results_csv)


if __name__ == "__main__":
    main(vcf_file, results_csv)
