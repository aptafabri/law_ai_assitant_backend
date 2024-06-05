from pinecone import Pinecone
import os
import json

pc = Pinecone(api_key="c214371b-cf98-4c07-8afc-95a3623a518d")
index = pc.Index("test-index")
# print(index)
vectors = index.list()
source_list = []
# try:
#     index.update(
#         id="d5018f3e-aee6-454d-835e-4bb2f6248c29",
#         set_metadata={"source_link": "https://adaletgpt.com"},
#         namespace="",
#     )
# except Exception as e:
#     print("errror", e)
for i, id_array in enumerate(index.list()):
    print("id_array:", id_array)
    for id in id_array:
        vector = index.query(
            id=id, top_k=1, include_values=False, include_metadata=True
        )

        source = vector["matches"][0]["metadata"]["source"]
        source_name = os.path.basename(source)

        source_url = f"https://adaletgpt.com/dataset/{source_name}"
        index.update(id=id, set_metadata={"source_link": source_url}, namespace="")
        print("updated:", id, source_url)
        source_list.append(source)


# unique_list = list(set(source_list))

# with open("embedding_list.txt", "a", encoding="utf-8") as file:
#     for source in unique_list:
#         file.write(source + "\n")
