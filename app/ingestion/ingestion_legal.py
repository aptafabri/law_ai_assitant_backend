from dotenv import load_dotenv
from langchain_community.document_loaders.directory import DirectoryLoader
from langchain_community.document_loaders.pdf import PyPDFLoader
from langchain_community.document_loaders import TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain.chains.combine_documents.stuff import StuffDocumentsChain
from langchain.chains.llm import LLMChain
from langchain_core.prompts import PromptTemplate
from langchain.chains.summarize import load_summarize_chain
from langchain_openai import ChatOpenAI
from langchain_pinecone import PineconeVectorStore
from langchain.schema import Document
import os

load_dotenv()

os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_PROJECT"] = f"adaletgpt"
os.environ["LANGCHAIN_ENDPOINT"] = "https://api.smith.langchain.com"
os.environ["LANGCHAIN_API_KEY"] = "ls__41665b6c9eb44311950da14609312f3c"

INDEX_NAME = "test-index"
DATASET = "../../dataset/"

### 40kbyte limitation in pinecone metadata #############
MAX_FILE_SIZE = 40 * 1024  # 40KB in bytes

embeddings = OpenAIEmbeddings(model="text-embedding-3-large")

pc = PineconeVectorStore(
    pinecone_api_key=os.environ.get("PINECONE_API_KEY"),
    embedding=embeddings,
    index_name=INDEX_NAME,
)


def load_files_recursively(root_folder):
    files = []
    for root, dirs, files_in_dir in os.walk(root_folder):
        for file in files_in_dir:
            if file.endswith(".pdf") or file.endswith(".txt"):
                files.append(os.path.join(root, file))
    return files


def embedding_doc(file_path):
    if os.path.getsize(file_path) > MAX_FILE_SIZE:
        text = summarize_legal_case(file_path=file_path)
        raw_documents = [
            Document(
                page_content=text, metadata={"source": os.path.basename(file_path)}
            )
        ]
        embeddings = OpenAIEmbeddings(model="text-embedding-3-large")
        PineconeVectorStore.from_documents(
            raw_documents, embeddings, index_name=INDEX_NAME
        )
        print("Inserting doc:", file_path)
        os.remove(file_path)
    else:
        _, extension = os.path.splitext(file_path)
        if extension == ".txt":
            loader = TextLoader(file_path, encoding="utf-8")
        elif extension == ".pdf":
            loader = PyPDFLoader(file_path)
        raw_documents = loader.load()
        embeddings = OpenAIEmbeddings(model="text-embedding-3-large")
        PineconeVectorStore.from_documents(
            raw_documents, embeddings, index_name=INDEX_NAME
        )
        print("Inserting doc:", file_path)
        os.remove(file_path)


def summarize_legal_case(file_path):
    prompt_template = """Write a concise summary of the following legal case in turkish:
    Legal Case: {text}\n
    CONCISE SUMMARY:"""
    prompt = PromptTemplate.from_template(prompt_template)

    # Define LLM chain
    llm = ChatOpenAI(temperature=0, model_name="gpt-4-1106-preview")
    llm_chain = LLMChain(llm=llm, prompt=prompt)

    # Define StuffDocumentsChain
    stuff_chain = StuffDocumentsChain(
        llm_chain=llm_chain, document_variable_name="text"
    )
    _, extension = os.path.splitext(file_path)
    if extension == ".txt":
        loader = TextLoader(file_path, encoding="utf-8")
        docs = loader.load()
    elif extension == ".pdf":
        loader = PyPDFLoader(file_path)
        docs = loader.load()

    response = stuff_chain.invoke({"input_documents": docs})
    print("Summarizing doc where is bigger than 40kbye:", file_path)
    return response["output_text"]


def ingest_docs():
    """
    Embed all files in the dat
    """
    files_in_dir = load_files_recursively(DATASET)
    for file_path in files_in_dir:
        embedding_doc(file_path)


if __name__ == "__main__":
    ingest_docs()
