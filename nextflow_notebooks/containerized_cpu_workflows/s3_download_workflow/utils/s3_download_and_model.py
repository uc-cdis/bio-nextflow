#!/usr/bin/env python3
import argparse
import boto3
import pandas as pd
from io import BytesIO
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier


def download_data(bucket_name, aws_access_key_id, aws_secret_access_key):
    # Use boto3 to create a session with your AWS credentials
    session = boto3.Session(
        aws_access_key_id=aws_access_key_id, aws_secret_access_key=aws_secret_access_key
    )
    # Create an S3 client
    s3 = session.client("s3")

    response = s3.get_object(Bucket=bucket_name, Key="iris.data")
    object_data = response["Body"].read()
    df = pd.read_csv(BytesIO(object_data))

    print("Download complete")

    return df


def modeling(df):
    X = np.array(df.iloc[:, :4])
    y = np.array(df.iloc[:, 4])

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2)

    rfc = RandomForestClassifier(max_depth=2, random_state=0)
    rfc.fit(X_train, y_train)
    y_pred = rfc.predict(X_test)

    results_df = pd.DataFrame({"labels": y_test, "predictions": y_pred})

    results_df.to_csv("rfc_results_df.csv")

    return


def setup_args():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--bucket-name", dest="bucket_name", help="s3 bucket name", required=True
    )
    parser.add_argument(
        "--key-id", dest="aws_access_key_id", help="aws access key id", required=True
    )

    parser.add_argument(
        "--secret-key",
        dest="aws_secret_access_key",
        help="aws secret access key",
        required=True,
    )
    args = parser.parse_args()
    return args


def main(argv=None):
    args = setup_args()
    bucket_name = args.bucket_name
    aws_access_key_id = args.aws_access_key_id
    aws_secret_access_key = args.aws_secret_access_key
    iris_df = download_data(
        bucket_name=bucket_name,
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
    )

    modeling(iris_df)


if __name__ == "__main__":
    main()
