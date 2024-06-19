from langchain.schema import Document
from langchain_pinecone import PineconeVectorStore
from langchain_community.vectorstores import Pinecone as PineconeLangChain
from langchain_openai import OpenAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders.pdf import PyPDFLoader
import os
from dotenv import load_dotenv

load_dotenv()

# Debug prints
print("Python executable:", os.popen("which python").read().strip())
print("Python version:", os.popen("python --version").read().strip())

INDEX_NAME = os.environ.get("INDEX_NAME")
DATASET = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "/Users/Shared/dataset")
)
embeddings = OpenAIEmbeddings(model="text-embedding-3-large")

pc = PineconeVectorStore(
    pinecone_api_key=os.environ.get("PINECONE_API_KEY"),
    embedding=embeddings,
    index_name=INDEX_NAME,
)


def load_files_recursively(directory):
    """
    Recursively loads all PDFs and text files from a directory and its subdirectories.
    """
    files = []
    for root, _, files_in_dir in os.walk(directory):
        for file in files_in_dir:
            if file.endswith(".pdf") or file.endswith(".txt"):
                files.append(os.path.join(root, file))
    return files


def load_txt_file(file_path):
    """
    Load a text file and return its content as a single document.
    """
    with open(file_path, "r", encoding="utf-8") as file:
        text = file.read()
    return [
        Document(page_content=text, metadata={"source": os.path.basename(file_path)})
    ]


def ingest_docs():
    """
    Embed all files in the dataset directory
    """
    print(f"Dataset directory: {DATASET}")
    files = load_files_recursively(DATASET)
    print(f"Found files: {files}")
    documents = []

    for file in files:
        print(f"Loading file: {file}")
        if file.endswith(".pdf"):
            loader = PyPDFLoader(file)
            docs = loader.load()
        elif file.endswith(".txt"):
            docs = load_txt_file(file)
        print(f"Loaded {len(docs)} documents from {file}")
        documents.extend(docs)

    splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=300)
    chunks = splitter.split_documents(documents)
    print(f"Going to add {len(chunks)} chunks to Pinecone, index_name: {INDEX_NAME}")

    # Ensure that the metadata is within the allowed size limit
    for chunk in chunks:
        if "metadata" in chunk:
            chunk.metadata = {
                k: v[:100] if isinstance(v, str) else v
                for k, v in chunk.metadata.items()
            }

    PineconeVectorStore.from_documents(chunks, embeddings, index_name=INDEX_NAME)

    print("****Loading to vectorstore done ***")


if __name__ == "__main__":
    ingest_docs()
