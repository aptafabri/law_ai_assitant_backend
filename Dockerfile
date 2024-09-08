FROM python:3.11

WORKDIR /app
COPY ./requirements.txt /app

RUN apt-get update && \
    apt-get install -y \
        poppler-utils \
        tesseract-ocr

RUN pip install -r requirements.txt

COPY ./app .

COPY .env .env

# Run the initial DB Script to build sqlite.db, then run main app
# CMD ["sh", "-c", "gunicorn -w 1 -b 0.0.0.0:8000 -k uvicorn.workers.UvicornWorker main:app"]
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port 8000 --env-file .env"]
