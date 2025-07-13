# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app
# Mkdir /data
RUN mkdir /data

# Copy requirements file and install
COPY requirements.txt /app/
RUN pip install --no-cache-dir uv
RUN uv pip install --system --no-cache-dir -r requirements.txt

# Copy the rest of the application

# Copy ./Source files to /app/

# Expos e the port FastAPI will run on
EXPOSE 8020

# Run the app
CMD ["python", "-m", "plotting_server_src"]
