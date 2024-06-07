from pinecone import Pinecone
import os
import uuid
from time import sleep
import json

# Initialize Pinecone with your API key
pc = Pinecone(api_key="c214371b-cf98-4c07-8afc-95a3623a518d")
index = pc.Index("test-index")

source_file_dict = {}
FILE_PATH = "embedding_list.txt"


def read_file_generator(file_path):
    with open(file_path, "r") as file:
        for line in file:
            yield line.strip()


unique_sources = set()
source_file_dict = {}
count = 0
for update_id in read_file_generator(FILE_PATH):
    try:
        count += 1

        vector = index.query(
            id=update_id, top_k=1, include_values=False, include_metadata=True
        )
        source = vector["matches"][0]["metadata"]["source"]
        source_name = os.path.basename(source)
        if count % 10 == 0:
            sleep(1)
            print("delaying 1 second")
        if source not in source_file_dict:

            id = uuid.uuid4().hex
            source_file_dict[source] = id
            source_url = (
                f"https://chat.adaletgpt.com/dataset/legal_case_data/{id}-{source_name}"
            )
            print(f"{source} does not exist!")
            index.update(
                id=update_id, set_metadata={"source_link": source_url}, namespace=""
            )
            print(f"updated {count}:", update_id, source_url)

        else:

            id = source_file_dict[source]
            print(f"{source} are already exist!")
            source_url = (
                f"https://chat.adaletgpt.com/dataset/legal_case_data/{id}-{source_name}"
            )
            index.update(
                id=update_id, set_metadata={"source_link": source_url}, namespace=""
            )
            print(f"updated {count}:", update_id, source_url)

    except Exception as e:
        print("error occoured:", e)
        with open("source_file_dict.json", "w") as json_file:
            json.dump(source_file_dict, json_file, indent=4)
