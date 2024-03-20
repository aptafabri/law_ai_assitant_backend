import secrets

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "AdaletGPT"
    SECRET_KEY: str = secrets.token_urlsafe(32)
    SQLALCHEMY_DATABASE_URI: str = "postgresql://localhost:5432/fastapi_db"
    OPENAI_API_KEY: str = "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"
    PINECONE_API_KEY: str = "c214371b-cf98-4c07-8afc-95a3623a518d"
    INDEX_NAME: str = "adaletgpt"
    class Config:
        env_file = ".env"


settings = Settings()
