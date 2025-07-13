# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set the working directory in the container
WORKDIR /app
# Mkdir /data
RUN mkdir /data

# Create user and group with the provided UID/GID
# RUN groupadd -g ${GID} appuser && \
#     useradd -u ${UID} -g ${GID} -m -s /bin/bash appuser

# Install system dependencies including build tools
RUN apt update && apt-get install -y \
    build-essential \
    gcc \
    g++ \
    make \
    libc6-dev \
    libffi-dev \
    libssl-dev \
    libasound2-dev \
    libasound2-plugins \
    alsa-utils \
    pulseaudio-utils

RUN apt update && apt install -y portaudio19-dev python3-pyaudio && apt-get clean \
    && rm -rf /var/lib/apt/lists/*


# Copy requirements file and install
COPY requirements.txt /app/
RUN pip install --no-cache-dir uv
RUN uv pip install --system pyaudio numpy
RUN uv pip install --system --no-cache-dir -r requirements.txt

# Copy the rest of the application

# Copy ./Source files to /app/
COPY main.py /app/
COPY network /app/network
COPY wled /app/wled
COPY audio /app/audio
COPY config.py /app/config.py
COPY scripts /app/scripts
# Run the app
CMD ["python3", "main.py"]

LABEL maintainer="miksolo" \
    description="Windy Cube application" \
    version="1.0" \
    org.opencontainers.image.source="https://github.com/mikprin/windy_cube"\
    name="windy_cube"