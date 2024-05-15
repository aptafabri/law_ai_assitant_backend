from dotenv import load_dotenv
load_dotenv()
import os
from langchain_community.document_loaders.pdf import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Pinecone as PineconeLangChain
from langchain_pinecone import PineconeVectorStore
from core.config import settings

INDEX_NAME = os.environ.get("INDEX_NAME")
DATASET = "../../dataset/"
embeddings = OpenAIEmbeddings(model="text-embedding-3-large")

pc = PineconeVectorStore(
    pinecone_api_key=settings.PINECONE_API_KEY,
    embedding=embeddings,
    index_name=INDEX_NAME,
)

def load_pdfs_recursively(directory):
    """
    Recursively loads all PDFs from a directory and its subdirectories.
    """
    pdf_files = []
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(".pdf"):
                pdf_files.append(os.path.join(root, file))
    return pdf_files


def ingest_docs():
    """
    Embed all files in the dataset directory
    """
    pdf_files = load_pdfs_recursively(DATASET)
    documents = []
    print(pdf_files)
    for pdf_file in pdf_files:
        loader = PyPDFLoader(pdf_file)
        documents.extend(loader.load())
    splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=200)
    chunks = splitter.split_documents(documents)
    print(f"Going to add {len(chunks)} to Pinecone")
    
    PineconeVectorStore.from_documents(documents, embeddings, index_name=INDEX_NAME)
    
    print("****Loading to vectorstore done ***")

if __name__ == "__main__":
    ingest_docs()