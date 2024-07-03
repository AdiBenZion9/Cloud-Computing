FROM python:3.11-slim

WORKDIR /app

COPY . /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5002
EXPOSE 5003

ENV FLASK_APP=loans.py

CMD ["python", "loans.py"]
