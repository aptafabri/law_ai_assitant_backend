from pinecone import Pinecone
import os
import json
from time import sleep

pc = Pinecone(api_key="c214371b-cf98-4c07-8afc-95a3623a518d")
INDEX_NAME = "adaletgpt-legalcase-data"
index = pc.Index(INDEX_NAME)
vectors = index.list()
source_list = []
# source_link = "https://chat.adaletgpt.com/dataset/legal_case_data?case_id=ad15d70a747e47d59f23560413e38d68&type=pdf"

filter_condition = {
    "source": {
        "$eq": "dataset\\DANISTAY\\d12\\2021\\704420100.2018_10244.2021_2060.20_04_2021.txt"
    }
}

results = index.query(
    vector=[0.0] * 3072,
    top_k=10000,
    include_metadata=True,
    filter=filter_condition,
    namespace="",
)
print(results)

# sorted_results = sorted(results["matches"], key=lambda x: x["metadata"]["page"])

# text = ""
# print(sorted_results)
# for chunk in sorted_results:
#     print(
#         chunk["id"],
#         chunk["metadata"]["source"],
#         chunk["metadata"]["page"],
#     )
#     page = chunk["metadata"]["page"]
#     text += "\n\n\n"
#     text += f"page:{page}"
#     text += chunk["metadata"]["text"]


# # print("text", text)
# with open("test_result.txt", "w", encoding="utf-8") as file:
#     file.write(text)

# source_link_dict = {}
# with open("test-index_source_link_dict.json", "r") as file:
#     json_data = file.read()
# source_link_dict = json.loads(json_data)
# ids = source_link_dict[source_link]
# ids = [
#     "0f6fef08-ce40-4f4d-85f9-1f661588d1a4",
#     "1269be36-4931-43a2-9fd7-cb082e7db16c",
#     "191e4d33-f7c0-480e-acfa-c759b109e237",
#     "253d6948-055e-4686-94c7-6ed658018d73",
#     "26fa349d-7bd8-4a04-a831-25e4a616c231",
#     "2764f724-676a-4df7-9041-78bd2b081187",
#     "2b595b5b-bec8-4421-9bbb-3ea13bc7c211",
#     "33cf6773-0353-4949-9224-353076e4406b",
#     "36832ed5-6f83-4fda-a0a2-ca5b7a4546e2",
#     "3686a664-c6ac-4292-b187-4c6c73323d91",
#     "4643771c-568d-4d97-b542-c8624df7427d",
#     "464e3237-f3c8-44c7-8a32-035ae721d5f1",
#     "46811c64-c394-40f0-95c2-7dccbdc911b4",
# ]
# vectors = index.fetch(ids=ids)
# datas = vectors["vectors"]
# metadata_array = []
# for id in ids:
#     metadata_array.append(datas[id]["metadata"])

# sorted_results = sorted(metadata_array, key=lambda x: x["page"])

# for result in sorted_results:
#     print(result["page"])
#     print(result["text"])
#     sleep(1)
