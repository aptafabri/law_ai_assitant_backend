from typing import Callable, Type
from langchain_core.tools import StructuredTool, Tool
from crud.rag import rag_legal_source_chat
from pydantic.v1 import BaseModel, Field


class RagLegalToolSchema(BaseModel):
    question: str = Field(description="user's question")


async def rag_legal_tool():
    return StructuredTool(
        name="rag_legal",
        description="useful when user's query is realted with legal cases (case law or judicial decisions and precedents) and court decisions",
        func=rag_legal_source_chat,
        args_schema=RagLegalToolSchema,
        infer_schema=True,
        verbose=True,
        handle_tool_error=True,
        handle_validation_error=True,
    )
