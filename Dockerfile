FROM python:3.11

WORKDIR /app
COPY ./requirements.txt /app
# Update package lists
RUN sudo apt-get update

# Install required packages
RUN sudo apt-get install -y \
    tesseract-ocr \
    tesseract \

RUN pip install -r requirements.txt

COPY ./app .

# Run the initial DB Script to build sqlite.db, then run main app
CMD ["sh", "-c", "gunicorn -w 4 -b 0.0.0.0:8000 -k uvicorn.workers.UvicornWorker main:app"]


