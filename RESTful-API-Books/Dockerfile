FROM python:3.9-slim

ENV FLASK_APP=bookClub.py
ENV FLASK_RUN_HOST=0.0.0.0
ENV FLASK_RUN_PORT=8000

WORKDIR /app

COPY . /app

RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8000

CMD ["flask", "run", "--host", "0.0.0.0", "--port", "8000"]