FROM python:3.11

WORKDIR /app
COPY ./requirements.txt /app

RUN apt-get update && \
    apt-get install -y \
        poppler-utils \
        tesseract-ocr

RUN pip install -r requirements.txt

# Copy the app directory
COPY ./app .  

COPY .env .env

# Ensure that /app is in the PYTHONPATH
ENV PYTHONPATH="/app"

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port 8000 --env-file .env"]