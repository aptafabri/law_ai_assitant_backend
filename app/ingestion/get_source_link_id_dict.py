from pinecone import Pinecone
import os
import uuid
import json

# Initialize Pinecone with your API key
pc = Pinecone(api_key="c214371b-cf98-4c07-8afc-95a3623a518d")
INDEX_NAME = "test-index"
index = pc.Index(INDEX_NAME)

source_link_dict = {}


# Define a generator function to yield sources
def id_generator(index):
    for id_array in index.list():
        for id in id_array:
            yield id


count = 0
for id in id_generator(index):
    try:
        count += 1
        # vector = index.query(
        #     id=id, top_k=1, include_values=False, include_metadata=True
        # )
        ids = []
        ids.append(id)
        vector = index.fetch(ids=ids)
        source_link = vector["vectors"][id]["metadata"]["source_link"]

        if count % 100 == 0:
            with open(f"{INDEX_NAME}_source_link_dict.json", "w") as json_file:
                json.dump(source_link_dict, json_file, indent=4)
            print(f"writed {count} ids in source link dict")
        if source_link not in source_link_dict:
            source_link_dict[source_link] = []
            source_link_dict[source_link].append(id)
            print(count, source_link, id)
        else:
            source_link_dict[source_link].append(id)
            print(count, source_link, id)
    except Exception as e:
        with open(f"{INDEX_NAME}_source_link_dict.json", "w") as json_file:
            json.dump(source_link_dict, json_file, indent=4)
        print(f"writed {count} ids in source link dict due to error")

with open(f"{INDEX_NAME}_source_link_dict.json", "w") as json_file:
    json.dump(source_link_dict, json_file, indent=4)
    print("finaly writed data")
