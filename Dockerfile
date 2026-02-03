FROM python:3.10-slim

WORKDIR /app

# Install git and build essentials (needed for some pip packages)
RUN apt-get update && apt-get install -y \
    git \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create directories
RUN mkdir -p uploads logs

# Expose port
EXPOSE 5000

# Run Flask app
CMD ["python", "app.py"]
