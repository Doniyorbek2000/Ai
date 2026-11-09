FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY beauty_bot ./beauty_bot
COPY data ./data
CMD ["python", "-m", "beauty_bot"]
