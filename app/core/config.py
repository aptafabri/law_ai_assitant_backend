import secrets

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "AdaletGPT"
    SECRET_KEY: str = secrets.token_urlsafe(32)
    SQLALCHEMY_DATABASE_URI: str = "postgresql://postgres:adminliu0220@localhost/adaletgpt"
    OPENAI_API_KEY: str = "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"
    PINECONE_API_KEY: str = "c214371b-cf98-4c07-8afc-95a3623a518d"
    INDEX_NAME: str = "adaletgpt-large-embedding"
    ACCESS_TOKEN_EXPIRE_MINUTES : int = 30
    REFRESH_TOKEN_EXPIRE_MINUTES :int = 60*24
    ALGORITHM :str = "HS256"
    JWT_SECRET_KEY: str = "narscbjim@$@&^@&%^&RFghgjvbdsha"
    JWT_REFRESH_SECRET_KEY :str = "13ugfdfgh@#$%^@&jkl45678902"
    class Config:
        env_file = ".env"


settings = Settings()
