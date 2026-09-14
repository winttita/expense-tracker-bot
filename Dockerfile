FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Solo lo necesario para correr el bot
COPY src/ src/

CMD ["python", "-m", "src.main"]
