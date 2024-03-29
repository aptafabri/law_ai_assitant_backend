FROM python:3.11-alpine

WORKDIR /app
COPY ./requirements.txt /app
RUN apt-get update \
    && apt-get -y install libpq-dev gcc \
    && pip install psycopg2
RUN pip install -r requirements.txt
COPY ./app .

# Run the initial DB Script to build sqlite.db, then run main app
CMD ["sh", "-c", "gunicorn -w 4 -b 0.0.0.0:8000 -k uvicorn.workers.UvicornWorker main:app"]

