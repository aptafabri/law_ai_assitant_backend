from pinecone import Pinecone
import os
import uuid
from time import sleep
import json
import signal

# Initialize Pinecone with your API key
pc = Pinecone(api_key="c214371b-cf98-4c07-8afc-95a3623a518d")
INDEX = pc.Index("adaletgpt-legalcase-data")

"""
Update vectordb source link which are duplicated using  unique source_file_dict
"""

FILE_PATH = "embedding_list.txt"


def read_file_generator(file_path):
    with open(file_path, "r") as file:
        for line in file:
            yield line.strip()


# Open and read the JSON file
with open("new_source_file_dict.json", "r") as file:
    json_data = file.read()

# Parse JSON data into a Python dictionary

source_file_dict = json.loads(json_data)
updated_source_file_dict = {}


def id_generator(index):
    for id_array in index.list():
        for id in id_array:
            yield id


count = 0

try:
    for update_id in id_generator(INDEX):
        try:
            vector = INDEX.query(
                id=update_id, top_k=1, include_values=False, include_metadata=True
            )
            source = vector["matches"][0]["metadata"]["source"]
            source_name = os.path.basename(source)
            data_type = source_name.rsplit(".", 1)[-1]

            if source not in source_file_dict:

                if source not in updated_source_file_dict:
                    id = uuid.uuid4().hex
                    updated_source_file_dict[source] = id
                    source_url = f"https://chat.adaletgpt.com/dataset/legal_case_data?case_id={id}&type={data_type}"
                    print(f"{source} does not exist!")
                    INDEX.update(
                        id=update_id,
                        set_metadata={"source_link": source_url},
                        namespace="",
                    )
                    print(f"updated {count}:", source_url)
                else:

                    id = updated_source_file_dict[source]
                    print(f"{source} are already exist!")
                    source_url = f"https://chat.adaletgpt.com/dataset/legal_case_data?case_id={id}&type={data_type}"
                    INDEX.update(
                        id=update_id,
                        set_metadata={"source_link": source_url},
                        namespace="",
                    )
                    print(f"updated {count}:", source_url)
                count += 1
                if count % 50 == 0:
                    sleep(1)
                    print("delaying 1 second")
                    with open("updated_source_file_dict.json", "w") as json_file:
                        json.dump(updated_source_file_dict, json_file, indent=4)
            else:
                print("update skipped")

        except Exception as e:
            print("error occoured:", e)
            with open("updated_source_file_dict.json", "w") as json_file:
                json.dump(updated_source_file_dict, json_file, indent=4)
            print("count:", count)
except Exception as e:
    print("error", e)
    with open("updated_source_file_dict.json", "w") as json_file:
        json.dump(updated_source_file_dict, json_file, indent=4)

with open("updated_source_file_dict.json", "w") as json_file:
    json.dump(updated_source_file_dict, json_file, indent=4)
    print("finally writed")
