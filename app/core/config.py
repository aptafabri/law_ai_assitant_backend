import secrets

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    API_V1_STR: str
    PROJECT_NAME: str
    SECRET_KEY: str = secrets.token_urlsafe(32)
    SQLALCHEMY_DATABASE_URI: str
    POSTGRES_CHAT_HISTORY_URI: str
    OPENAI_API_KEY: str
    PINECONE_API_KEY: str
    INDEX_NAME: str
    LEGAL_CASE_INDEX_NAME: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    REFRESH_TOKEN_EXPIRE_MINUTES: int
    LLM_MODEL_NAME: str
    QUESTION_MODEL_NAME: str
    ALGORITHM: str
    JWT_SECRET_KEY: str
    JWT_REFRESH_SECRET_KEY: str
    COHERE_API_KEY: str
    AWS_ACCESS_KEY_ID: str
    AWS_SECRET_KEY: str
    AWS_BUCKET_NAME: str
    SENDGRID_API_KEY: str
    MAIL_USERNAME: str
    MAIL_PASSWORD: str
    MAIL_FROM: str
    MAIL_PORT: int
    MAIL_SERVER: str
    MAIL_FROM_NAME: str

    class Config:
        env_file = ".env"


settings = Settings()
