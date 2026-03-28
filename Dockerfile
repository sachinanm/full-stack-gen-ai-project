# Use official python slim image
FROM python:3.11-slim

# Prevent python from writing pyc files and buffering stdout
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Define persistent storage directories inside the container
ENV CHROMA_DB_DIR /app/data/chroma_db
ENV UPLOADS_DIR /app/data/uploads

# Install system dependencies (ChromaDB often needs some compilation tools)
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory
WORKDIR /app

# Copy requirement files and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire app code into the container
COPY . .

# Ensure storage directories exist in case a volume isn't automatically mounted
RUN mkdir -p /app/data/uploads /app/data/chroma_db

# Expose standard FastAPI port
EXPOSE 8000

# Start the web server. It binds to $PORT if provided (Render/Railway), otherwise 8000
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
