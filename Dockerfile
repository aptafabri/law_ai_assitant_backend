FROM python:3.11-slim

WORKDIR /app
COPY ./requirements.txt /app
RUN apt-get update && \
    apt-get install -y libpq-dev python3-dev gcc
RUN pip install -r requirements.txt
COPY ./app .

# Run the initial DB Script to build sqlite.db, then run main app
CMD ["sh", "-c", "gunicorn -w 4 -b 0.0.0.0:8000 -k uvicorn.workers.UvicornWorker --timeout 1000 main:app"]

