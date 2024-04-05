from langchain.chains.summarize import load_summarize_chain
from langchain_openai import ChatOpenAI
from langchain.chains.combine_documents.stuff import StuffDocumentsChain
from langchain.chains.llm import LLMChain
from langchain_core.prompts import PromptTemplate

llm = ChatOpenAI(temperature=0.5, model_name="gpt-3.5-turbo-1106")
# Define prompt
prompt_template = """
    I want you to make concise summary using following conversation.
    You must write concise summary as title format with a 5-8 in turkish
    CONVERSATION:
    ============
    Human:{question}
    AI:{answer}
    ============
    CONCISE Summary:
"""
prompt = PromptTemplate.from_template(prompt_template)

# Define LLM chain
llm = ChatOpenAI(temperature=0, model_name="gpt-3.5-turbo-16k")
llm_chain = LLMChain(llm=llm, prompt=prompt)

response = llm_chain.invoke({
    "question":"please explain python",
    "answer":"Python is best programing language"
})

print(response)