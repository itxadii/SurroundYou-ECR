# Use an official Python runtime as a parent image. 'slim' is a smaller version.
FROM python:3.12-slim

# Set the working directory inside the container
WORKDIR /app

# Install system dependencies, including FFmpeg, and then clean up
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy the requirements file first to leverage Docker layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy your Python script into the container
COPY process_audio.py .

# Command to run your Python script when the container starts
CMD ["python", "process_audio.py"]