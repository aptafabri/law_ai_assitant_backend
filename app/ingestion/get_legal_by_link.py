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
        "$eq": "https://adaletgpt.com/dataset/866456800.2022_39.2023_394.02_02_2023.pdf"
    }
}

results = index.query(
    vector=[0.0] * 3072, top_k=10000, filter=filter_condition, include_metadata=True
)
sorted_results = sorted(results["matches"], key=lambda x: x["metadata"]["page"])

text = ""
for chunk in sorted_results:
    # print(chunk["id"], chunk["metadata"]["text"])
    text += chunk["metadata"]["text"]

print("text", text)

