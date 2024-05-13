# from pinecone import Pinecone

# pc = Pinecone(api_key='c214371b-cf98-4c07-8afc-95a3623a518d')
# index = pc.Index("adaletgpt-large-embedding")
# # print(index)
# vectors = index.list()
# source_list = []
# for i, id_array in enumerate(index.list()):
#     for id in id_array:
#        vector =  index.query(
#             id=id_array[0],
#             top_k=1,
#             include_values=False,
#             include_metadata=True
#         )
#        print("source:",vector["matches"][0]["metadata"]['source'])
#        source = vector["matches"][0]["metadata"]['source']
#        source_list.append(source)

# unique_list = list(set(source_list))

# with open('embedding_list.txt', 'a', encoding= 'utf-8') as file:
#     for source in unique_list:
#         file.write(source+"\n")


with open('embedding_list.txt', 'r') as infile:
    # Read the lines from the file
    lines = infile.readlines()

# Define the substring to remove
substring_to_remove = "..\dataset\\"

# Modify each line to remove the substring
modified_lines = [line.replace(substring_to_remove, '') for line in lines]
# print(modified_lines)
# Open the output file in write mode
with open('final_embedding_list.txt', 'w') as outfile:
    # Write the modified lines back to the file
    outfile.writelines(modified_lines)



        

