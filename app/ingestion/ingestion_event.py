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
from core.config import settings
import os

os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_PROJECT"] = f"adaletgpt"
os.environ["LANGCHAIN_ENDPOINT"] = "https://api.smith.langchain.com"
os.environ["LANGCHAIN_API_KEY"] = "ls__41665b6c9eb44311950da14609312f3c"

INDEX_NAME = "adaletgpt-legalcase-data"
DATASET = "../../dataset/"
MIN_FILE_SIZE = 40 * 1024  # 40KB in bytes

embeddings = OpenAIEmbeddings(model="text-embedding-3-large")

pc = PineconeVectorStore(
    pinecone_api_key=settings.PINECONE_API_KEY,
    embedding=embeddings,
    index_name=INDEX_NAME,
)
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
    if os.path.getsize(file_path) > MIN_FILE_SIZE:
        summarize_legal_case(file_path=file_path)
        loader = TextLoader(file_path, encoding='utf-8')
        raw_documents = loader.load()
        embeddings = OpenAIEmbeddings(model="text-embedding-3-large")
        PineconeVectorStore.from_documents(raw_documents, embeddings, index_name=INDEX_NAME)
        print("Inserting doc:", file_path)
        os.remove(file_path)
    else:
        loader = TextLoader(file_path, encoding='utf-8')
        raw_documents = loader.load()
        embeddings = OpenAIEmbeddings(model="text-embedding-3-large")
        PineconeVectorStore.from_documents(raw_documents, embeddings, index_name=INDEX_NAME)
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
    stuff_chain = StuffDocumentsChain(llm_chain=llm_chain, document_variable_name="text")
    loader = TextLoader(file_path, encoding='utf-8')
    docs = loader.load()
    response = stuff_chain.invoke({"input_documents":docs})

    with open(file_path, 'w', encoding='utf-8' ) as file:
        file.write(response["output_text"])
        print("Summarizing docs where is bigger than 5kbyte:", file_path)

if __name__ == "__main__":
    ingest_docs()
    