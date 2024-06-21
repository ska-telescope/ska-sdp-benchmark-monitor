FROM python:3.10

COPY requirements.testing.txt .
RUN pip install -r requirements.testing.txt