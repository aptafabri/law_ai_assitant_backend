from pinecone import Pinecone
import os
import uuid
from time import sleep
import json
import signal

# Initialize Pinecone with your API key
pc = Pinecone(api_key="c214371b-cf98-4c07-8afc-95a3623a518d")
INDEX = pc.Index("adaletgpt-legalcase-data")


source_file_dict = {}
FILE_PATH = "embedding_list.txt"


def read_file_generator(file_path):
    with open(file_path, "r") as file:
        for line in file:
            yield line.strip()


def id_generator(index):
    for id_array in index.list():
        for id in id_array:
            yield id


unique_sources = set()
source_file_dict = {}
count = 0
for update_id in id_generator(INDEX):
    try:
        vector = INDEX.query(
            id=update_id, top_k=1, include_values=False, include_metadata=True
        )
        source = vector["matches"][0]["metadata"]["source"]
        source_name = os.path.basename(source)
        source_link = vector["matches"][0]["metadata"]["source_link"]
        id = source_link.split("-")[0].split("/")[-1]
        data_type = source_name.rsplit(".", 1)[-1]
        if count % 10 == 0:
            sleep(1)
            print("delaying 1 second")
        source_url = f"https://chat.adaletgpt.com/dataset/legal_case_data?case_id={id}&type={data_type}"
        INDEX.update(
            id=update_id, set_metadata={"source_link": source_url}, namespace=""
        )
        count += 1

        print(f"updated {count}:", source_name, source_url)

    except Exception as e:
        print("error occoured:", e)
        print("count:", count)
