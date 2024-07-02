from pinecone import Pinecone
import os
import json
from time import sleep

pc = Pinecone(api_key="c214371b-cf98-4c07-8afc-95a3623a518d")
INDEX_NAME = "adaletgpt-mevzuat-28-05-2024"
index = pc.Index(INDEX_NAME)
vectors = index.list(namespace="")


def id_generator():
    for id_array in index.list(namespace=""):
        for id in id_array:
            yield id


count = 0

for id in id_generator():
    count += 1
    ids = []
    ids.append(id)
    vector = index.fetch(ids=ids)
    update_vector = vector["vectors"][id]
    index.upsert(vectors=[update_vector], namespace="YONETMELIK")
    print("updated:", count)
    index.delete(ids=ids, namespace="")
    print("deleted in old namesapce:", count)
    if count % 10 == 0:
        sleep(1)
        print("delaying 1s.")
