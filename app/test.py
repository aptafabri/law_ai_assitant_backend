import boto3
import pytesseract as tess
from PIL import Image
from pdf2image import convert_from_bytes


source_file_path = "../dataset/Y01CD/Y01CD_2022-9504.txt"
access_key_id = "AKIA5FTZBZ7ZO36ZRH6Z"
secret_key = "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"


s3_client = boto3.client(service_name='s3', aws_access_key_id=access_key_id,
                                       aws_secret_access_key=secret_key)
# with open(source_file_path, 'rb') as f:
#     s3_client.put_object(Bucket="adaletgpt", Body=f, Key="legalcase/1.txt")


objects = s3_client.list_objects(Bucket = "adaletgpt", Prefix = '2')
for o in objects.get('Contents'):
    data = s3_client.get_object(Bucket="adaletgpt", Key=o.get('Key'))
    contents = data['Body'].read()
    print(o.get('Key'))
    # s3_client.delete_object(Bucket="adaletgpt", Key=o.get('Key'))


def read_pdf(file_contents):
    pages = []

    try:
        # Convert PDF bytes to images
        images = convert_from_bytes(file_contents)

        # Extract text from each image
        for i, image in enumerate(images):
            # Generating filename for each image
            filename = f"page_{i}.jpeg"
            image.save(filename, "JPEG")
            # Extract text from each image using pytesseract
            text = tess.image_to_string(Image.open(filename))
            pages.append(text)

    except Exception as e:
        print(e)
    return "\n".join(pages)