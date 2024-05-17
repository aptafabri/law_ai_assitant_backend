import secrets

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "AdaletGPT"
    SECRET_KEY: str = secrets.token_urlsafe(32)
    SQLALCHEMY_DATABASE_URI: str = (
        "postgresql+psycopg://postgres:adaletgpt0318@database-1.cz0c0omykjh2.eu-central-1.rds.amazonaws.com/adaletgpt"
    )
    POSTGRES_CHAT_HISTORY_URI: str = (
        "postgresql://postgres:adaletgpt0318@database-1.cz0c0omykjh2.eu-central-1.rds.amazonaws.com/adaletgpt"
    )
    OPENAI_API_KEY: str = "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"
    PINECONE_API_KEY: str = "c214371b-cf98-4c07-8afc-95a3623a518d"
    INDEX_NAME: str = "adaletgpt-ceza-embeddings"
    LEGAL_CASE_INDEX_NAME: str = "adaletgpt-legalcase-data"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 60 * 24
    LLM_MODEL_NAME: str = "gpt-4o"
    QUESTION_MODEL_NAME: str = "gpt-4-1106-preview"
    ALGORITHM: str = "HS256"
    JWT_SECRET_KEY: str = "narscbjim@$@&^@&%^&RFghgjvbdsha"
    JWT_REFRESH_SECRET_KEY: str = "13ugfdfgh@#$%^@&jkl45678902"
    COHERE_API_KEY: str = "ntWFpAliup6EdbZH6mt7xJHnYKvgQviJXywzOtTM"
    AWS_ACCESS_KEY_ID: str = "AKIA5FTZBZ7ZO36ZRH6Z"
    AWS_SECRET_KEY: str = "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"
    AWS_BUCKET_NAME: str = "adaletgpt"
    SENDGRID_API_KEY: str = (
        "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"
    )
    MAIL_USERNAME: str = "auth@adaletgpt.com"
    MAIL_PASSWORD: str = "fzdi cczq oiwj ayuy"
    MAIL_FROM: str = "auth@adaletgpt.com"
    MAIL_PORT: int = 587
    MAIL_SERVER: str = "smtp.gmail.com"
    MAIL_FROM_NAME: str = "Liu Chin Lung"

    class Config:
        env_file = ".env"


settings = Settings()
