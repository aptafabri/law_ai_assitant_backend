# AdaletGPT Backend

This is the backend for the AdaletGPT project, a FastAPI-based application designed to assist legal professionals with document generation, case searches, and more.

## Table of Contents
- [Project Setup](#project-setup)
- [Running the Application Locally](#running-the-application-locally)
- [Running with Docker](#running-with-docker)
- [Database Setup](#database-setup)
- [Testing](#testing)
- [Environment Variables](#environment-variables)

## Project Setup

### Prerequisites
- **Python 3.11+**
- **Pipenv** or **Virtualenv**
- **Docker** (if running with Docker)
- **PostgreSQL** (if running the app with PostgreSQL)
  
### Clone the repository

```bash
git clone https://github.com/your-repo/AdaletGPT_Backend.git
cd AdaletGPT_Backend
```

### Install Dependencies

#### Using Pipenv (preferred):

```bash
pip install pipenv
pipenv install
```

#### Using Virtualenv:

```bash
python3 -m venv venv
source venv/bin/activate  # on Windows: `venv\Scripts\activate`
pip install -r requirements.txt
```

### Set Up Environment Variables

Create a `.env` file in the root directory of the project and provide the following environment variables (refer to the `.env.example` file if available):

```env
API_V1_STR=/api/v1
PROJECT_NAME=AdaletGPT
SECRET_KEY=your-secret-key
SQLALCHEMY_DATABASE_URI=postgresql://user:password@localhost/dbname
POSTGRES_CHAT_HISTORY_URI=postgresql://user:password@localhost/chat_history
OPENAI_API_KEY=your-openai-api-key
PINECONE_API_KEY=your-pinecone-api-key
INDEX_NAME=your-index-name
LEGAL_CASE_INDEX_NAME=your-legal-case-index
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_MINUTES=1440
LLM_MODEL_NAME=gpt-3.5-turbo
QUESTION_MODEL_NAME=gpt-3.5-turbo
ALGORITHM=HS256
JWT_SECRET_KEY=your-jwt-secret-key
JWT_REFRESH_SECRET_KEY=your-jwt-refresh-secret-key
COHERE_API_KEY=your-cohere-api-key
AWS_ACCESS_KEY_ID=your-aws-access-key
AWS_SECRET_KEY=your-aws-secret-key
AWS_BUCKET_NAME=your-bucket-name
SENDGRID_API_KEY=your-sendgrid-api-key
MAIL_USERNAME=your-email-username
MAIL_PASSWORD=your-email-password
MAIL_FROM=your-email@example.com
MAIL_PORT=587
MAIL_SERVER=smtp.sendgrid.net
MAIL_FROM_NAME="AdaletGPT Support"
TAVILY_API_KEY=your-tavily-api-key
SENDGRID_AUTH_EMAIL=your-auth-email@example.com
AWS_EXPORTDATA_BUCKET_NAME=your-export-bucket-name
AWS_LEGALCASE_BUCKET_NAME=your-legalcase-bucket-name
```

### Database Setup

The app uses PostgreSQL by default, but you can use SQLite for local development.

#### Using PostgreSQL:
1. Install PostgreSQL and ensure it’s running.
2. Update the `SQLALCHEMY_DATABASE_URI` and `POSTGRES_CHAT_HISTORY_URI` in your `.env` file to point to your local database.

#### Using SQLite:
1. If you prefer SQLite for development, set the `SQLALCHEMY_DATABASE_URI` in your `.env` file as follows:
   ```env
   SQLALCHEMY_DATABASE_URI=sqlite:///./sql_app.db
   ```

2. Run migrations (if any):
   ```bash
   alembic upgrade head
   ```

## Running the Application Locally

After setting up the environment and dependencies, you can run the FastAPI app locally using Uvicorn.

### Start the FastAPI Server:

#### With Pipenv:
```bash
pipenv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

#### With Virtualenv:
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The app will now be accessible at `http://localhost:8000`.

You can explore the API documentation at `http://localhost:8000/docs`.

## Running with Docker

### Build the Docker Image:

```bash
docker build -t adaletgpt-backend .
```

### Run the Docker Container:

```bash
docker run -p 8000:8000 adaletgpt-backend
```

The app should now be running at `http://localhost:8000`.

## Testing

The project includes a set of unit and integration tests. You can run them as follows:

1. Make sure the environment is set up.
2. Run tests using `pytest`:

```bash
pytest
```

## Environment Variables

- The application uses environment variables for configuration, which should be set in a `.env` file at the project root.
- Example environment variables are listed in the `.env.example` file.

Make sure to adjust the environment variables according to your setup, particularly the API keys, database URIs, and secret keys.
