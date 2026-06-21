# Use a lightweight official Python image
FROM python:3.11-slim

# Set the working directory inside the container
WORKDIR /app

# Copy requirements first to leverage Docker cache for faster builds
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy all project files (main.py, resume_engine.py, sheets_manager.py, credentials.json)
COPY . .

# Expose the port Flask runs on
EXPOSE 8080

# Command to run the application using Gunicorn (production standard)
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "main:app"]
