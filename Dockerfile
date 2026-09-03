FROM python:3.11-slim

WORKDIR /app

# ffmpeg: stream merging, metadata, thumbnails, subtitle remux
# aria2:  accelerated segmented/HLS downloads
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev curl ffmpeg aria2 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p downloads temp

ENV PYTHONUNBUFFERED=1
CMD ["python", "bot.py"]
