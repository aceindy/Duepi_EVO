FROM mcr.microsoft.com/devcontainers/python:1-3.13

# Avoid interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements files (context is the workspace root)
COPY requirements_dev.txt requirements_dev.txt
COPY requirements_test.txt requirements_test.txt

# Install Python packages from requirements files
RUN pip install --upgrade pip \
    && pip install -r requirements_test.txt

# Create a non-root user
ARG USERNAME=vscode
ARG USER_UID=1000
ARG USER_GID=${USER_UID}

RUN groupadd --gid ${USER_GID} ${USERNAME} \
    && useradd --uid ${USER_UID} --gid ${USER_GID} -m ${USERNAME}

USER ${USERNAME}

WORKDIR /workspace
