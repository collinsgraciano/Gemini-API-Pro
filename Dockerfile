# Base image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies (if any needed, e.g. for Pillow)
# RUN apt-get update && apt-get install -y --no-install-recommends ...

# Copy requirements
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create static directory for persistence
RUN mkdir -p static/images

# Expose port
EXPOSE 8001

# Run server
CMD ["python", "openai_server.py"]
