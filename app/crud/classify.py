from pydantic import BaseModel, Field
from langchain.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from core.prompt import legalcase_classify_prompt_template


class CategoryQuestion(BaseModel):
    """Binary score for classification on categories."""

    category: str = Field(
        description="Question are relevant to the categories, 'YARGITAY' or 'DANISTAY'"
    )


class Classifier:
    def __init__(self, model_name="gpt-4o", temperature=0):
        self.llm = ChatOpenAI(model=model_name, temperature=temperature)
        self.structured_llm_classifier = self.llm.with_structured_output(
            CategoryQuestion
        )
        self.template = legalcase_classify_prompt_template
        self.classify_prompt = PromptTemplate(
            template=self.template, input_variables=["question"]
        )

    def classify(self, question: str):
        classify_chain = self.classify_prompt | self.structured_llm_classifier
        result = classify_chain.invoke({"question": question})
        return result.category
