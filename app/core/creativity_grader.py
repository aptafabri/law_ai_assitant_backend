from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from core.prompt import creativity_grader_prompt_template

class GradeCreativity(BaseModel):
    """Grade the creativity of a user's question on a scale of 1 to 10."""
    creativity_score: int = Field(
        description="Creativity score of the user's question, ranging from 1 to 10"
    )

def get_llm_parameter(question:str):
    try:
        llm = ChatOpenAI(model="gpt-4o", temperature=0)
        structured_llm_grader = llm.with_structured_output(GradeCreativity)
        grade_prompt = ChatPromptTemplate.from_template(creativity_grader_prompt_template)
        retrieval_grader = grade_prompt | structured_llm_grader
        result = retrieval_grader.invoke({"question": question})
        creativity_score = result["creativity_score"]
        temperature = creativity_score/10
        max_tokens = 3000 + creativity_score*500
        return {
            "temperature": temperature,
            "max_tokens": max_tokens
        }
            
    except Exception as ex:
        raise RuntimeError(f"OpenAI calling error:{ex}")