from pinecone import Pinecone
import os
import uuid
import json
from langchain.schema import Document
from langchain_pinecone import PineconeVectorStore
from langchain_community.vectorstores import Pinecone as PineconeLangChain
from langchain_openai import OpenAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders.pdf import PyPDFLoader
from langchain_community.document_loaders import TextLoader
from dotenv import load_dotenv
import shutil
from time import sleep

"""script for updating vectordb with source link but before ingestion, the files must be canged as uuid file name"""

load_dotenv()

DATASET = "ingestion"
INDEX_NAME = "adaletgpt-legalcase-data"

### 40kbyte limitation in pinecone metadata #############
MAX_PDF_FILE_SIZE = 30 * 1024  # 40KB in bytes
MAX_TXT_FILE_SIZE = 15 * 1024

embeddings = OpenAIEmbeddings(
    model="text-embedding-3-large",
    openai_api_key="sk-proj-zYzv6Je0bQH8MiVlJkMKT3BlbkFJHklfzkue2VwSqVS07C9P",
)

pc = PineconeVectorStore(
    pinecone_api_key=os.environ.get("PINECONE_API_KEY"),
    embedding=embeddings,
    index_name=INDEX_NAME,
)


def load_files_recursively(directory):
    """
    Recursively loads all PDFs and text files from a directory and its subdirectories.
    """
    for root, _, files_in_dir in os.walk(directory):
        for file in files_in_dir:
            if file.endswith(".pdf") or file.endswith(".txt"):
                file_path = os.path.join(root, file)
                yield file_path


def move_file(source_file, destination_dir):
    try:
        # Create destination directory if it doesn't exist
        os.makedirs(destination_dir, exist_ok=True)

        # Move file to destination directory
        shutil.move(source_file, destination_dir)

        print(f"File moved successfully to {destination_dir}")
    except FileNotFoundError:
        print(f"Error: {source_file} not found")
    except Exception as e:
        print(f"Error: {e}")


def ingest_docs():
    """
    Embed all files in the dataset
    """
    count = 0
    try:
        for file_path in load_files_recursively(DATASET):

            print("Started Embedding:", count, file_path)

            _, extension = os.path.splitext(file_path)
            data_type = None
            if extension == ".txt":
                data_type = "txt"
            elif extension == ".pdf":
                data_type = "pdf"
            MAX_FILE_SIZE = (
                MAX_PDF_FILE_SIZE if data_type == "pdf" else MAX_TXT_FILE_SIZE
            )

            print("max file size:", MAX_FILE_SIZE)
            folder_name = os.path.dirname(file_path)
            source_name = os.path.basename(file_path)
            case_id = source_name.rsplit(".", 1)[0]

            source_url = f"https://chat.adaletgpt.com/dataset/legal_case_data?case_id={case_id}&type={data_type}"
            print("Doc source_url:", source_url)

            if os.path.getsize(file_path) > MAX_FILE_SIZE:
                print("file is larger than 40kbyte:", file_path)
                splitter = RecursiveCharacterTextSplitter(
                    chunk_size=800, chunk_overlap=300
                )
                if data_type == "txt":
                    loader = TextLoader(file_path, encoding="utf-8")
                elif data_type == "pdf":
                    loader = PyPDFLoader(file_path=file_path, extract_images=True)
                raw_documents = loader.load()
                document = raw_documents[0]
                documents = [
                    Document(
                        page_content=document.page_content,
                        metadata={
                            "source": document.metadata["source"],
                            "source_link": source_url,
                        },
                    )
                ]
                chunks = splitter.split_documents(documents)
                print(
                    f"Going to add {len(chunks)} chunks to Pinecone, index_name: {INDEX_NAME}"
                )
                pc.from_documents(chunks, embeddings, index_name=INDEX_NAME)
            else:
                if data_type == "txt":
                    loader = TextLoader(file_path, encoding="utf-8")
                elif data_type == "pdf":
                    loader = PyPDFLoader(file_path=file_path, extract_images=True)
                raw_documents = loader.load()
                document = raw_documents[0]
                documents = [
                    Document(
                        page_content=document.page_content,
                        metadata={
                            "source": document.metadata["source"],
                            "source_link": source_url,
                        },
                    )
                ]
                print(
                    f"Going to add {len(documents)} chunks to Pinecone, index_name: {INDEX_NAME}"
                )
                pc.from_documents(documents, embeddings, index_name=INDEX_NAME)
            file_real_path = os.path.relpath(folder_name, "updated_doc")
            move_file(file_path, file_real_path)
            print()
            count += 1

        with open(f"error_log.txt", "w") as file:
            file.write(f"count:{count}")
    except Exception as e:
        with open(f"error_log.txt", "w") as file:
            file.write(f"count:{count}")


ingest_docs()
