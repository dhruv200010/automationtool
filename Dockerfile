# Start from a slim Python image
FROM python:3.10-slim

# Install FFmpeg and dependencies
RUN apt-get update && \
    apt-get install -y ffmpeg && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set working directory inside the container
WORKDIR /app

# Install Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy your entire project code into the container
COPY . .

# Create necessary directories
RUN mkdir -p /app/input /app/output

# Expose port 8080 (Railway expects this)
EXPOSE 8080

# Start your app
CMD ["python", "app.py"]
