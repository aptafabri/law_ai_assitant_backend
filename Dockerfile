FROM python:3.11

WORKDIR /app
COPY ./requirements.txt /app
# Update package lists
RUN apt-get update && apt-get install

# Install required packages
#RUN apt-get install poppler-utils tesseract-ocr tesseract

RUN pip install -r requirements.txt

COPY ./app .

# Run the initial DB Script to build sqlite.db, then run main app
CMD ["sh", "-c", "gunicorn -w 4 -b 0.0.0.0:8000 -k uvicorn.workers.UvicornWorker main:app"]


