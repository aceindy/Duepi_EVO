FROM mcr.microsoft.com/devcontainers/python:1-3.13

# Avoid interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
# Remove the yarn repository pre-configured in the base image (GPG key is invalid)
RUN rm -f /etc/apt/sources.list.d/yarn.list

RUN apt-get update && apt-get install -y \
    git \
    curl \
    build-essential \
    ffmpeg libturbojpeg0-dev \
    libpcap-dev libpcap0.8-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements files (context is the workspace root)
COPY requirements_dev.txt requirements_dev.txt
COPY requirements_test.txt requirements_test.txt

# Install Python packages from requirements files
RUN pip install --upgrade pip \
    && pip install -r requirements_test.txt