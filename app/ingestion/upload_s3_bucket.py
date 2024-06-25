import boto3
import os

AWS_ACCESS_KEY_ID = "AKIA5FTZBZ7ZO36ZRH6Z"
AWS_SECRET_KEY = "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"
AWS_BUCKET_NAME = "adaletgpt-legalcase-data"
s3_client = boto3.client(
    service_name="s3",
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_KEY,
)


def upload_files_recursively(directory):
    """
    Recursively loads all PDFs and text files from a directory and its subdirectories.
    """
    count = 0
    files = []
    for root, _, files_in_dir in os.walk(directory):
        for file in files_in_dir:
            count += 1

            if file.endswith(".pdf") or file.endswith(".txt"):
                file_path = os.path.abspath(os.path.join(root, file))
                s3_key = os.path.basename(file_path)
                with open(file_path, "rb") as content_file:
                    content = content_file.read()
                    try:
                        s3_client.put_object(
                            Bucket=AWS_BUCKET_NAME, Body=content, Key=s3_key
                        )
                        print("uploaded:", count, file_path)
                    except Exception as e:
                        print("ERROR:", e)

    return files


upload_files_recursively("dataset")
