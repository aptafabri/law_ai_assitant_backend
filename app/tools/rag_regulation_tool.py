from typing import Callable, Type
from langchain_core.tools import StructuredTool
from pydantic.v1 import BaseModel, Field
from crud.rag import rag_regulation_chat


class RagRegulationToolSchema(BaseModel):
    question: str = Field(description="user's question")


async def rag_regulation_tool():
    return StructuredTool.from_function(
        name="rag_regulation",
        description=" useful when user's question are realted with statues and regulations",
        func=rag_regulation_chat,
        args_schema=RagRegulationToolSchema,
        infer_schema=True,
        verbose=True,
        handle_tool_error=True,
        handle_validation_error=True,
    )
