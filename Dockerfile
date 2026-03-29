FROM python:3.11-slim

# System deps: ffmpeg for video processing
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy everything first so `pip install -e .` sees the full package tree
COPY . .

# Install core + audio extras (faster-whisper for local transcription)
RUN pip install --no-cache-dir -e ".[audio]"

EXPOSE 8000

CMD ["uvicorn", "temporalos.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
