from dotenv import load_dotenv
load_dotenv()
import os
from langchain_community.document_loaders.directory import DirectoryLoader
from langchain_community.document_loaders.pdf import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Pinecone as PineconeLangChain
from pinecone import Pinecone


pc= Pinecone(
    api_key=os.environ.get("PINECONE_API_KEY")
)

INDEX_NAME = os.environ.get("INDEX_NAME")

DATASET= "../dataset/"


def ingest_docs():
    """
    Embed all files in the dataset directory
    """
    
    loader = DirectoryLoader(DATASET, glob="*.pdf", loader_cls=PyPDFLoader, show_progress= True)
    
    documents = loader.load()
    
    splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=200)
    chunks = splitter.split_documents(documents)
    embeddings = OpenAIEmbeddings(model="text-embedding-3-large")
    print(f"Going to add {len(chunks)} to Pinecone")
    
    PineconeLangChain.from_documents(chunks, embeddings, index_name="adaletgpt-large-embedding")
    
    print("****Loading to vectorstore done ***")

    

if __name__ == "__main__":
    ingest_docs()

