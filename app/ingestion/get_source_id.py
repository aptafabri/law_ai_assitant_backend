from pinecone import Pinecone
import os
import uuid

# Initialize Pinecone with your API key
pc = Pinecone(api_key="c214371b-cf98-4c07-8afc-95a3623a518d")
index = pc.Index("adaletgpt-legalcase-data")

source_file_dict = {}
FILE_PATH = "embedding_list.txt"


# Define a generator function to yield sources
def id_generator(index):
    for id_array in index.list():
        for id in id_array:
            yield id


# Open the file in append mode
with open(FILE_PATH, "a") as file:
    unique_sources = set()
    count = 0
    # Process each source from the generator
    for id in id_generator(index):
        if id not in unique_sources:
            count += 1
            print(f"writed {count}:", id)
            file.write(id + "\n")
