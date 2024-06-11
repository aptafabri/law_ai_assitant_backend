from pinecone import Pinecone
import os
import json

pc = Pinecone(api_key="c214371b-cf98-4c07-8afc-95a3623a518d")
index = pc.Index("test-index")
# print(index)
vectors = index.list()
source_list = []

filter_condition = {
    "source_link": {
        "$eq": "https://chat.adaletgpt.com/dataset/legal_case_data?case_id=d806340d04c94e7c87d3c8a2fb2d6a96-Y01HD_2022-5690.txt"
    }
}

results = index.query(
    vector=[0.0] * 3072, top_k=10000, filter=filter_condition, include_metadata=True
)

if "page" in results["matches"][0]["metadata"]:
    sorted_results = sorted(results["matches"], key=lambda x: x["metadata"]["page"])

    text = ""
    for chunk in sorted_results:
        # print(chunk["id"], chunk["metadata"]["text"])
        text += chunk["metadata"]["text"]
else:
    text = results["matches"][0]["metadata"]["text"]
print("text", text)
