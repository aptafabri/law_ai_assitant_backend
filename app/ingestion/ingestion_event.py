from dotenv import load_dotenv
from langchain_community.document_loaders.directory import DirectoryLoader
from langchain_community.document_loaders.pdf import PyPDFLoader
from langchain_community.document_loaders import TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Pinecone as PineconeLangChain
from pinecone import Pinecone
import os

os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_PROJECT"] = f"adaletgpt"
os.environ["LANGCHAIN_ENDPOINT"] = "https://api.smith.langchain.com"
os.environ["LANGCHAIN_API_KEY"] = "ls__41665b6c9eb44311950da14609312f3c"

pc = Pinecone(api_key=os.environ.get("PINECONE_API_KEY"))
INDEX_NAME = "adaletgpt-events-data"
DATASET = "../../dataset/"

def get_subfolders(root_folder):
    for item in os.listdir(root_folder):
        item_path = os.path.join(root_folder, item)
        if os.path.isdir(item_path):
            yield item_path

def get_all_subfiles(root_folder):
    for root, dirs, files in os.walk(root_folder):
        for file in files:
            yield os.path.join(root, file)

def load_documents():
    subfolders = get_subfolders(DATASET)
    for folder in subfolders:
        files = get_all_subfiles(folder)
        for data_file in files:
            yield data_file

def ingest_docs():
    """
    Embed all files in the dat
    """
    documents = load_documents()
    for file_path in documents:
        embedding_doc(file_path)

def embedding_doc(file_path):
    loader = TextLoader(file_path, encoding='utf-8')
    raw_documents = loader.load()
    embeddings = OpenAIEmbeddings(model="text-embedding-3-large")
    PineconeLangChain.from_documents(raw_documents, embeddings, index_name=INDEX_NAME)
    print("Inserting doc:", file_path)
    os.remove(file_path)

if __name__ == "__main__":
    ingest_docs()
